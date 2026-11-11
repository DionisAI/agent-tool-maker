"""What this ATM holds, for an Agent deciding how to get a Key, login or service: never a value.

Read only from local metadata. The vault is not opened, so this works while ATM is locked, and it
tells the Agent how to use each resource without ever seeing a Key: injection into its own program
(`atm use`), MCP through the session (`atm mcp`), tools through `atm run`.
"""
from __future__ import annotations

from collections import defaultdict

READY = 'configured_not_verified'
HOW_TO = {
    'find_key': 'atm keys find ENV_NAME_OR_SLOT',
    'use_key': ('atm use --workspace /absolute/project --env ENV_NAME=atm://SLOT --request-key STABLE -- <program> '
                '(injects the Key into that program only; the Agent never sees it)'),
    'unlock': ('atm start --workspace /absolute/project --key SLOT (opens the local ATM window; the owner unlocks it '
               'there, with a Passkey such as 1Password first; never ask for a password or Key in chat)'),
    'missing_key': 'atm start --workspace /absolute/project --key SLOT (the owner fills the Key in the same window)',
    'mcp': ('atm mcp tools SERVER --workspace /absolute/project, then atm mcp call SERVER TOOL; native tools for '
            'Claude Code / Codex: atm mcp serve SERVER --workspace /absolute/project'),
    'tool': 'atm describe TOOL_ID, then atm run TOOL_ID --input input.json --workspace /absolute/project',
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
    keys, missing = [], []
    for row in credential_rows(state):
        label = registry.get(row['name'], {}).get('label') if isinstance(registry.get(row['name']), dict) else None
        item = {'name': row['name'], 'label': label or row['name'], 'reference': row['reference'],
                'env_names': sorted(env_names.get(row['name'], [])), 'state': row['state'], 'expires_at': row['expires_at']}
        (keys if row['configured'] else missing).append(item)
    recipe_tools = defaultdict(list)
    services = defaultdict(lambda: {'ready_tools': 0, 'examples': []})
    for tool in router.catalog.tools.values():
        recipe = tool.get('recipe') if isinstance(tool.get('recipe'), dict) else {}
        if recipe.get('session'):
            recipe_tools[recipe['session']].append(tool['id'])
        if tool.get('adapter') != 'catalog_only' and router.readiness(tool) == READY:
            group = services[tool['provider']]
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
        'mcp_servers': list_servers(router)['servers'],
        'services': [{'provider': name, **group} for name, group in sorted(services.items())],
        'how_to': HOW_TO,
        'note': ('Metadata only: no Key, password or login is ever returned. Ask the owner in chat only to approve '
                 'a use, never for a secret; the local ATM window collects anything missing.'),
        'secrets_returned': False, 'network_calls': 0,
    }
