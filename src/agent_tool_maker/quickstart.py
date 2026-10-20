"""Local one-window onboarding for trusted same-user projects.

The agent creates a NON-SECRET request; a human approves the visible project and
credential scope in a local browser. No password is returned to the requesting
CLI. Consent creates a session-bound project grant, not permanent owner access.
This convenience mode trusts project code. It is deliberately not a sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
import uuid
import webbrowser
from importlib.resources import files

from .broker import call, safe_path, socket_path
from .errors import RouterError
from .extensions import credential_name
from .secrets_provider import credential_rows, fingerprint, normalized_argv, parse_mapping
from .storage import State, atomic_write, canonical
from .sync import strict_json

PENDING_SECONDS = 600
PENDING_STATUSES = {'starting', 'needs_unlock', 'needs_approval'}
CLIENT_LABEL = 'local-project'


def project_path(state, workspace):
    workspace = safe_path(Path(workspace)).resolve()
    if not workspace.is_dir():
        raise RouterError('workspace_missing', 'The current project directory must exist.')
    home = state.home.resolve()
    if workspace == home or workspace.is_relative_to(home) or home.is_relative_to(workspace):
        raise RouterError('unsafe_workspace', 'Do not authorize the vault or its parent/child as a project.')
    if workspace == Path.home().resolve() or workspace == Path(workspace.anchor):
        raise RouterError('unsafe_workspace', 'Choose a project, not your entire home or filesystem.')
    return workspace


def project_id(workspace):
    return hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()[:24]


def profile_path(state, workspace):
    return safe_path(state.home / 'project-clients' / (project_id(workspace) + '.json'), secret=True)


def scope_plan(state, workspace, names):
    workspace = project_path(state, workspace)
    if not isinstance(names, list) or not 1 <= len(names) <= 32 or len(set(names)) != len(names):
        raise RouterError('invalid_scope', 'Select between 1 and 32 distinct credential slots.')
    for name in names:
        credential_name(name)
    return {'workspace': str(workspace), 'credentials': sorted(names), 'mode': 'trusted_local_project',
            'clients': ['Claude Code', 'Codex'], 'lease': 'current_fixed_session',
            'risk': 'Code in this project may receive the selected Keys, use the network and spend. Not a sandbox.'}


def grant_project(router, server, args):
    """Owner-session RPC only; the exact visible scope is bound to this unlock."""
    if set(args) != {'workspace', 'credentials', 'approved_sha256'}:
        raise RouterError('invalid_request', 'Unexpected project grant fields.')
    plan = scope_plan(router.state, args['workspace'], args['credentials'])
    if args['approved_sha256'] != fingerprint(plan):
        raise RouterError('plan_changed', 'Review the project and credential scope again.')
    if server.closing.is_set() or server._key is None or time.monotonic() >= server.deadline:
        raise RouterError('session_locked', 'This unlock session has ended.')
    for row in credential_rows(router.state, scope=plan['credentials']):
        if row['state'] != 'configured_not_verified':
            raise RouterError(row['state'], 'Repair the selected connection before granting project access.')
    state = router.state
    path = profile_path(state, plan['workspace'])
    previous = None
    if path.exists():
        saved = strict_json(path.read_bytes(), limit=65536)
        previous = state.setting('access:' + str(saved.get('id')))
        if not previous or previous.get('kind') != 'project_session':
            raise RouterError('profile_conflict', 'Existing profile is not a project session; it was preserved.')
    identifier, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
    now = time.time()
    policy = {'id': identifier, 'kind': 'project_session', 'agent': CLIENT_LABEL,
              'workspace': plan['workspace'], 'credentials': plan['credentials'],
              'tools': [], 'pins': {}, 'exec_rules': [], 'permissions': [], 'allow_paid': False,
              'socket': str(server.path), 'socket_owner_uid': os.getuid(), 'socket_gid': None,
              'client_uid': os.getuid(), 'created_at': now,
              'expires_at': now + max(0, server.deadline - time.monotonic()),
              'session_binding': server.owner_id, 'revoked': False,
              'token_hash': hashlib.sha256(token.encode()).hexdigest()}
    with state.db() as db:
        from .sync import _set
        db.execute('BEGIN IMMEDIATE')
        if previous:
            _set(db, 'access:' + previous['id'], {**previous, 'revoked': True})
        _set(db, 'access:' + identifier, policy)
    try:
        atomic_write(path, canonical({'format': 'atm-client-v1', 'id': identifier, 'agent': CLIENT_LABEL,
                     'socket': str(server.path), 'token': token, 'socket_owner_uid': os.getuid(), 'socket_gid': None}).encode())
    except BaseException:
        state.set_setting('access:' + identifier, {**policy, 'revoked': True})
        raise
    return {'status': 'ready', 'workspace': plan['workspace'], 'credentials': plan['credentials'],
            'seconds_remaining': server.metadata_status()['seconds_remaining'], 'secrets_returned': False}


def ready(state, workspace, names=()):
    path = profile_path(state, workspace)
    if not path.exists():
        return None
    try:
        result = call(path, 'status', {}, timeout=2)
    except RouterError as e:
        if e.code in {'broker_unavailable', 'broker_locked', 'unauthorized', 'session_locked'}:
            return None
        raise
    if result.get('kind') != 'project_session' or result.get('workspace') != str(workspace):
        raise RouterError('profile_conflict', 'Project profile does not match this project.')
    if set(names) - set(result.get('credentials', [])):
        return None
    return {'status': 'ready', 'workspace': str(workspace), 'credentials': result['credentials'],
            'seconds_remaining': result['broker_seconds_remaining'], 'secrets_returned': False}


def request_record(state, identifier):
    if not isinstance(identifier, str) or len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
        raise RouterError('invalid_request', 'Invalid local request identifier.')
    record = state.setting('desktop-request:' + identifier)
    if not record:
        raise RouterError('request_missing', 'This local request no longer exists.')
    return record


def pending_requests(state) -> list[dict]:
    """Non-secret view of requests still waiting for the human in the local approval window.
    Never the window URL, launch codes, bearer tokens or approval hashes. The console cannot approve."""
    with state.db() as db:
        identifiers = [json.loads(row[0]) for row in
                       db.execute("SELECT value FROM settings WHERE name LIKE 'desktop-active:%'")]
    now, rows = time.time(), []
    for identifier in identifiers:
        if not isinstance(identifier, str):
            continue
        record = state.setting('desktop-request:' + identifier)
        # Each record is checked on its own: a malformed one is skipped, never listed, and never fails the page.
        if not _pending_shape(record) or now - record['created_at'] >= PENDING_SECONDS:
            continue
        heartbeat = record.get('heartbeat', record['created_at'])
        rows.append({'id': record['id'], 'workspace': record['workspace'],
                     'credentials': list(record['credentials']), 'status': record['status'],
                     'created_at': record['created_at'], 'expires_at': record['created_at'] + PENDING_SECONDS,
                     'live': _number(heartbeat) and now - heartbeat < 10})
    return sorted(rows, key=lambda row: row['created_at'], reverse=True)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _pending_shape(record):
    return (isinstance(record, dict) and record.get('status') in PENDING_STATUSES
            and isinstance(record.get('id'), str) and re.fullmatch(r'[0-9a-f]{32}', record['id']) is not None
            and isinstance(record.get('workspace'), str)
            and isinstance(record.get('credentials'), list) and all(isinstance(name, str) for name in record['credentials'])
            and _number(record.get('created_at')))


def request_summary(record):
    return {k: record[k] for k in ('status', 'id', 'workspace', 'credentials', 'url', 'browser_opened') if k in record} | {
        'secrets_returned': False, 'next_action': 'The human uses the local ATM window. Never ask for the password in chat. Re-run after approval.'}


def start(home, workspace, *, names=None, open_browser=True):
    """Prepare/reuse one request. Never unlock or approve from the caller process."""
    if os.name != 'posix':
        raise RouterError('desktop_platform', 'Local one-window sessions currently require macOS or Linux.')
    import fcntl
    state = State(Path(home)); workspace = project_path(state, workspace)
    chosen = names if names is not None else state.secret_names()
    if not chosen:
        return {'status': 'missing_credential', 'next_action': 'Choose the required slot with --key NAME; the local form will collect it.', 'secrets_returned': False}
    plan = scope_plan(state, workspace, list(chosen))
    reuse = ready(state, workspace, plan['credentials'])
    if reuse:
        return reuse
    lockfile = safe_path(state.home / 'desktop-launch.lock')
    fd = os.open(lockfile, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        active = state.setting('desktop-active:' + project_id(workspace))
        if active:
            old = request_record(state, active)
            live = time.time() - old.get('heartbeat', old['created_at']) < 10
            if old['status'] == 'denied' and old['credentials'] == plan['credentials'] and time.time() - old['created_at'] < PENDING_SECONDS:
                return request_summary(old)
            if old['status'] in {'starting', 'needs_unlock', 'needs_approval'} and live:
                if old['credentials'] != plan['credentials']:
                    raise RouterError('request_pending', 'Finish or close the existing project request before changing its scope.')
                return request_summary(old)
        identifier = uuid.uuid4().hex
        record = {'id': identifier, **plan, 'status': 'starting', 'created_at': time.time(), 'heartbeat': time.time(),
                  'open_browser': bool(open_browser), 'approval_sha256': fingerprint(plan)}
        state.set_setting('desktop-request:' + identifier, record)
        state.set_setting('desktop-active:' + project_id(workspace), identifier)
        # Start only ATM's installed module, never shell text from a caller.
        import sys
        environment = {k: os.environ[k] for k in ('PATH', 'HOME', 'DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY',
            'DBUS_SESSION_BUS_ADDRESS', 'XDG_RUNTIME_DIR', 'LANG') if k in os.environ}
        subprocess.Popen([sys.executable, '-m', 'agent_tool_maker', '--home', str(state.home),
                          '_desktop', identifier], cwd=str(state.home), env=environment,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True)
    finally:
        os.close(fd)
    for _ in range(60):
        record = request_record(state, identifier)
        if record['status'] != 'starting':
            return request_summary(record)
        time.sleep(.05)
    return request_summary(record)


def use(home, workspace, mappings, argv, *, request_key=None, dry_run=False, open_browser=True):
    state = State(Path(home)); workspace = project_path(state, workspace)
    mapping = parse_mapping(mappings)
    argv = normalized_argv(argv)
    key = request_key or uuid.uuid4().hex
    availability = ready(state, workspace, mapping.values())
    if not availability:
        if dry_run:
            return {'status': 'needs_unlock', 'dry_run': True, 'credentials_read': False, 'execution_started': False}
        return {**start(home, workspace, names=sorted(set(mapping.values())), open_browser=open_browser),
                'request_key': key, 'execution_started': False}
    try:
        return call(profile_path(state, workspace), 'exec', {'argv': argv, 'environment': mapping,
                    'workspace': str(workspace), 'request_key': key, 'dry_run': dry_run}, timeout=320)
    except RouterError as e:
        if e.uncertain:
            raise RouterError(e.code, str(e) + ' Preserve request key ' + key + '; do not blindly resubmit.', uncertain=True) from None
        raise


def add_commands(sub):
    p = sub.add_parser('start', help='Agent opens a local unlock/consent window; reuses an approved project session')
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--key', action='append', default=None)
    p.add_argument('--no-browser', action='store_true')
    p = sub.add_parser('use', help='Use saved Keys in a program; opens the local window when approval is needed')
    p.add_argument('--env', action='append', required=True)
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--request-key'); p.add_argument('--dry-run', action='store_true')
    p.add_argument('--no-browser', action='store_true')
    p.add_argument('argv', nargs=argparse.REMAINDER)
    p = sub.add_parser('_desktop', help=argparse.SUPPRESS); p.add_argument('request_id')


def dispatch(args):
    if args.command == '_desktop':
        from .quickstart_web import serve_request
        return serve_request(args.home, args.request_id)
    if args.command == 'start':
        return start(args.home, args.workspace, names=args.key, open_browser=not args.no_browser)
    argv = args.argv[1:] if args.argv and args.argv[0] == '--' else args.argv
    return use(args.home, args.workspace, args.env, argv, request_key=args.request_key,
               dry_run=args.dry_run, open_browser=not args.no_browser)
