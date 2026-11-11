"""What this ATM holds, for an Agent deciding how to get a Key, login or service: never a value.

Read only from local metadata. The vault is not opened, so this works while ATM is locked, and it
tells the Agent how to use each resource without ever seeing a Key: injection into its own program
(`atm use`), MCP through the session (`atm mcp`), tools through `atm run`.
"""
from __future__ import annotations

import os
from collections import defaultdict

READY = 'configured_not_verified'
HOW_TO = {
    'find_key': 'atm keys find ENV_NAME_OR_SLOT',
    'use_key': ('atm use --workspace /absolute/project --env ENV_NAME=atm://SLOT --request-key STABLE -- <program> '
                '(injects the Key into that program only; the Agent never sees it)'),
    'unlock': ('atm start --workspace /absolute/project --key SLOT (opens the local ATM window; the owner unlocks it '
               'there, with a Passkey such as 1Password first; never ask for a password or Key in chat)'),
    'missing_key': 'atm start --workspace /absolute/project --key SLOT (the owner fills the Key in the same window)',
    'mcp': ('each mcp_servers entry names its route in `use`. A Key-authenticated https server runs under the project '
            'approval: atm mcp tools SERVER --workspace /absolute/project, then atm mcp call SERVER TOOL --arguments JSON '
            '--workspace /absolute/project --request-key STABLE; native tools: atm mcp serve SERVER --workspace /absolute/project'),
    'tool': ('atm describe TOOL_ID, then atm run TOOL_ID --input input.json --workspace /absolute/project. atm run opens '
             'the vault in your own process: it works with the system keychain, but on a password vault the window '
             'unlock does not reach it; then use the Key through atm use (your own program) or MCP instead.'),
}


def inventory(router) -> dict:
    from .mcp_servers import list_servers
    from .oauth import OAuth
    from .secrets_provider import credential_rows
    from .session import status
    from .web_recipe import sessions
    state = router.state
    registry = state.setting('credential_registry', {}) or {}
    env_names = defaultdict(list)
    for env, slots in (state.setting('key_aliases', {}) or {}).items():
        for slot in slots if isinstance(slots, list) else []:
            env_names[slot].append(env)
    keys, missing, states = [], [], {}
    for row in credential_rows(state):
        states[row['name']] = row['state']
        label = registry.get(row['name'], {}).get('label') if isinstance(registry.get(row['name']), dict) else None
        item = {'name': row['name'], 'label': label or row['name'], 'reference': row['reference'],
                'env_names': sorted(env_names.get(row['name'], [])), 'state': row['state'], 'expires_at': row['expires_at']}
        (keys if row['configured'] else missing).append(item)
    # A run can open the vault in the Agent's own process only with the system keychain (or a password in its env).
    backend = (state.setting('vault', {}) or {}).get('backend')
    direct = backend == 'keyring' or bool(os.environ.get('ATM_VAULT_PASSWORD'))
    recipe_tools = defaultdict(list)
    services = defaultdict(lambda: {'ready_tools': 0, 'examples': [], 'needs_vault_password': 0})
    for tool in router.catalog.tools.values():
        recipe = tool.get('recipe') if isinstance(tool.get('recipe'), dict) else {}
        if recipe.get('session'):
            recipe_tools[recipe['session']].append(tool['id'])
        if tool.get('adapter') == 'catalog_only' or router.readiness(tool) != READY:
            continue
        names = _credentials(state, tool)
        if any(states.get(name, 'missing_credential') != READY for name in names):
            continue  # An expired, conflicting or missing Key: not ready, whatever the tool's own check says.
        group = services[tool['provider']]
        if (names or recipe.get('session')) and not direct:
            group['needs_vault_password'] += 1
            continue
        group['ready_tools'] += 1
        if len(group['examples']) < 3:
            group['examples'].append(tool['id'])
    web = [{'session': s['name'], 'origins': s['origins'], 'expired': s['expired'], 'tools': sorted(recipe_tools.get(s['name'], []))}
           for s in sessions(state)['sessions']]
    oauth = OAuth(state, router.vault, router.net).status()
    lease = status(state.home)
    return {
        'session': {'status': lease.get('status'), 'unlocked': bool(lease.get('unlocked')),
                    'seconds_remaining': lease.get('seconds_remaining', 0)},
        'keys': keys,
        'declared_without_key': missing,
        'web_logins': web,
        'oauth': [{k: oauth.get(k) for k in ('provider', 'status', 'resource', 'expires_at', 'keep_login')}],
        'mcp_servers': [_with_route(s) for s in list_servers(router)['servers']],
        'services': [{'provider': name, **group} for name, group in sorted(services.items())],
        'direct_runs': {'available': direct, 'vault_backend': backend,
                        'note': None if direct else ('atm run reads the vault in your own process and cannot use the window '
                                                     'unlock on this password vault: use Keys through atm use or MCP.')},
        'how_to': HOW_TO,
        'note': ('Metadata only: no Key, password or login is ever returned. Ask the owner in chat only to approve '
                 'a use, never for a secret; the local ATM window collects anything missing.'),
        'secrets_returned': False, 'network_calls': 0,
    }


def _credentials(state, tool):
    """The Key slots a run of this tool reads, including an MCP binding's."""
    names = [tool['credential']] if tool.get('credential') else []
    command = tool.get('command') if isinstance(tool.get('command'), dict) else {}
    names += list((command.get('credential_env') or {}).values()) if command.get('credential_required') else []
    if tool.get('adapter') == 'mcp' and tool.get('server'):
        cfg = state.setting('mcp:' + tool['server']) or {}
        names += [cfg['credential']] if isinstance(cfg.get('credential'), str) else []
        names += [v for v in (cfg.get('env_credentials') or {}).values() if isinstance(v, str)] if isinstance(cfg.get('env_credentials'), dict) else []
    return list(dict.fromkeys(names))


def _with_route(server):
    keyed = server.get('transport') == 'http' and isinstance(server.get('credential'), str) and not server['credential'].startswith('oauth:')
    name = server['server']
    route = (f'atm mcp tools {name} / atm mcp call {name} TOOL / atm mcp serve {name} (project approval)' if keyed
             else f'atm describe {name}.mcp_tools, then atm run {name}.mcp_tools / {name}.mcp_batch')
    return {**server, 'use': route}
