"""Owner-added remote MCP servers.

One reviewed plan holds the Streamable HTTP endpoint, the Key slot sent to it as a Bearer
header, the tool allowlist and the two generated definitions (<name>.mcp_tools and
<name>.mcp_batch). Approval is the plan's SHA-256; a change compares against the previous
plan. No Key value is read, printed or stored here.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from .errors import RouterError
from .extensions import credential_name
from .maker import digest, validate_manifest
from .mcp_bridge import SERVER_NAME, builtin_servers, custom_definitions, custom_endpoint, matches_definition
from .storage import canonical
from .sync import _get, _set

TOOL_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:~@-]{0,199}\Z')


def _custom(tools, name):
    return sorted((t for t in tools if t.get('adapter') == 'mcp' and t.get('server') == name), key=lambda t: t['id'])


def _snapshot(binding, definitions, name):
    if binding is None and not definitions:
        return None
    return {'server': name, 'binding': binding, 'definitions': definitions}


def _current(db, name):
    return _snapshot(_get(db, 'mcp:' + name), _custom(_get(db, 'custom_tools', []), name), name)


def _sha(snapshot):
    return digest(snapshot) if snapshot is not None else None


def plan(router, name, url, credential, *, allow_tools=(), timeout=120, title=None):
    if not isinstance(name, str) or not SERVER_NAME.fullmatch(name):
        raise RouterError('bad_server', 'Use a lowercase server name of 2-64 letters, digits, - or _.')
    if name in builtin_servers():
        raise RouterError('bad_server', 'This is a built-in MCP server; bind it with atm mcp bind.')
    custom_endpoint(url)
    credential_name(credential)
    from .management import known_credentials
    if credential not in known_credentials(router):
        raise RouterError('unknown_credential', 'Declare the Key slot first: atm credentials declare NAME --apply.')
    allow = list(allow_tools or [])
    if len(allow) > 200 or len(set(allow)) != len(allow) or any(not isinstance(t, str) or not TOOL_NAME.fullmatch(t) for t in allow):
        raise RouterError('bad_server', 'Allowed tools are up to 200 distinct exact names from discovery.')
    if type(timeout) is not int or not 1 <= timeout <= 900:
        raise RouterError('bad_server', 'Timeout must be 1-900 seconds.')
    if title is not None and (not isinstance(title, str) or not 0 < len(title) <= 120):
        raise RouterError('bad_server', 'Title must be 1-120 characters.')
    definitions = sorted((validate_manifest(d) for d in custom_definitions(name, url, credential, title)), key=lambda t: t['id'])
    for tool in definitions:
        existing = router.catalog.tools.get(tool['id'])
        if existing and not (existing.get('user_defined') and existing.get('adapter') == 'mcp' and existing.get('server') == name):
            raise RouterError('duplicate_tool', 'A tool with this ID already exists; choose another server name.')
    binding = {'transport': 'http', 'url': url, 'credential': credential, 'allow_tools': sorted(allow), 'timeout': timeout}
    return _snapshot(binding, definitions, name)


def _summary(snapshot):
    binding = snapshot['binding'] or {}
    return {'server': snapshot['server'], 'endpoint': binding.get('url'),
            'host': urlsplit(binding['url']).hostname if binding.get('url') else None,
            'credential': binding.get('credential'), 'allow_tools': binding.get('allow_tools', []),
            'timeout': binding.get('timeout'),
            'definitions': [{'id': t['id'], 'paid': t['paid'], 'permissions': t['permissions']} for t in snapshot['definitions']]}


def add(router, name, url, credential, *, allow_tools=(), timeout=120, title=None, approve=None, expected=None):
    candidate = plan(router, name, url, credential, allow_tools=allow_tools, timeout=timeout, title=title)
    sha = _sha(candidate)
    with router.state.db() as db:
        previous = _sha(_current(db, name))
    result = {**_summary(candidate), 'plan_sha256': sha, 'previous_sha256': previous, 'applied': False,
              'credentials_read': False, 'secrets_returned': False}
    if approve is None:
        approval = ' --approve ' + sha + (' --expected ' + previous if previous else '')
        return {**result, 'next': 'Review the endpoint, Key slot and allowed tools, then repeat the same command with' + approval + '.'}
    if approve != sha:
        raise RouterError('approval_mismatch', 'Approve the plan_sha256 shown by the preview of these exact options.')
    with router.state.db() as db:
        db.execute('BEGIN IMMEDIATE')
        # Compare-and-swap against the state the owner reviewed (none for a first add).
        if _sha(_current(db, name)) != (expected or None):
            raise RouterError('definition_changed', 'This server changed since the preview; run the preview again.')
        tools = _get(db, 'custom_tools', [])
        old = {t['id']: t for t in _custom(tools, name)}
        new = {digest(t) for t in candidate['definitions']}
        for tool_id, tool in old.items():
            if digest(tool) not in new:  # Replaced definitions stay inspectable, as with make update.
                db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('tool_history:' + tool_id + ':' + digest(tool), canonical(tool)))
        kept = [t for t in tools if t['id'] not in old]
        if {t['id'] for t in kept} & {t['id'] for t in candidate['definitions']}:
            raise RouterError('duplicate_tool', 'Another custom tool already uses one of these IDs.')
        _set(db, 'custom_tools', kept + candidate['definitions'])
        _set(db, 'mcp:' + name, candidate['binding'])
    return {**result, 'applied': True, 'unchanged': sha == previous, 'live_tested': False,
            'next': ('Discover with: atm mcp tools ' + name + ' --workspace /absolute/project. '
                     'Approve exact names with --allow-tool. Native use: atm mcp serve ' + name + ' --workspace /absolute/project.')}


def remove(router, name, *, approve=None):
    if not isinstance(name, str) or not SERVER_NAME.fullmatch(name):
        raise RouterError('bad_server', 'Invalid server name.')
    with router.state.db() as db:
        snapshot = _current(db, name)
    if snapshot is None:
        raise RouterError('mcp_not_configured', 'No MCP server with this name is bound or installed.')
    sha = _sha(snapshot)
    result = {'server': name, 'remove_binding': snapshot['binding'] is not None,
              'remove_definitions': [t['id'] for t in snapshot['definitions']], 'plan_sha256': sha,
              'applied': False, 'existing_jobs_preserved': True}
    if approve is None:
        return {**result, 'next': 'Repeat with --approve ' + sha + ' to remove exactly this.'}
    if approve != sha:
        raise RouterError('approval_mismatch', 'Approve the plan_sha256 shown by the preview.')
    with router.state.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if _sha(_current(db, name)) != sha:
            raise RouterError('definition_changed', 'This server changed since the preview; run the preview again.')
        ids = {t['id'] for t in snapshot['definitions']}
        _set(db, 'custom_tools', [t for t in _get(db, 'custom_tools', []) if t['id'] not in ids])
        db.execute('DELETE FROM settings WHERE name=?', ('mcp:' + name,))
    return {**result, 'applied': True}


def list_servers(router):
    with router.state.db() as db:
        rows = db.execute("SELECT name, value FROM settings WHERE name LIKE 'mcp:%'").fetchall()
        tools = _get(db, 'custom_tools', [])
    servers = []
    for row in rows:
        name, cfg = row[0][4:], json.loads(row[1])
        custom = _custom(tools, name)
        item = {'server': name, 'built_in': name in builtin_servers(), 'transport': cfg.get('transport'),
                'credential': cfg.get('credential') or ('oauth:' + cfg['oauth'] if cfg.get('oauth') else None),
                'allow_tools': cfg.get('allow_tools', []), 'definitions': [t['id'] for t in custom]}
        if cfg.get('transport') == 'http':
            item['endpoint'] = cfg.get('url')
        elif cfg.get('command'):
            item['command'] = cfg['command']
        if custom:
            item['matches_review'] = all(matches_definition(cfg, t) for t in custom)
        servers.append(item)
    return {'servers': sorted(servers, key=lambda s: s['server']), 'secrets_returned': False}


def binding_for(router, name):
    """The bound config of a server that exposes both standard operations, or a certain refusal."""
    if not isinstance(name, str) or not SERVER_NAME.fullmatch(name):
        raise RouterError('bad_server', 'Invalid server name.')
    cfg = router.state.setting('mcp:' + name)
    if not cfg:
        raise RouterError('mcp_not_configured', 'Bind this MCP server first (atm mcp add or atm mcp bind).')
    for operation in ('tools', 'batch'):
        router.catalog.get(name + '.mcp_' + operation)
    return cfg
