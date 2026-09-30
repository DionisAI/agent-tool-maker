"""Credential discovery and exact-command injection, independent of the tool catalog.

This is not a sandbox: the approved program can use/export each injected secret.
No secret values are returned over RPC or persisted in process-output captures.
Generic exec is deliberately same-UID only until a real privilege-drop/sandbox exists.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import time
import uuid
from urllib.parse import quote

from .broker import client_path, safe_path, socket_path, _ttl
from .errors import RouterError
from .extensions import credential_name
from .storage import canonical
from .sync import strict_json, write_sync_file

MAX_OUTPUT = 256 * 1024  # Combined stdout+stderr, memory only; overflow suppresses all output.
MAX_FILE = 256 * 1024 * 1024
CONTROL_NAMES = {
    'PATH','HOME','USER','LOGNAME','SHELL','IFS','ENV','BASH_ENV','ZDOTDIR','CDPATH',
    'SHELLOPTS','BASHOPTS','PROMPT_COMMAND','PS4','TMPDIR','TMP','TEMP','COMSPEC',
    'SYSTEMROOT','WINDIR','APPDATA','LOCALAPPDATA','USERPROFILE','LANG','LANGUAGE',
    'SSL_CERT_FILE','SSL_CERT_DIR','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE',
    'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','GCONV_PATH','LOCPATH',
    'PERL5OPT','PERL5LIB','RUBYOPT','RUBYLIB','JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS',
    'CLASSPATH','DOTNET_STARTUP_HOOKS','OPENSSL_CONF','OPENSSL_MODULES',
}
CONTROL_PREFIXES = ('ATM_', 'ATR_', 'LD_', 'DYLD_', 'PYTHON', 'NODE_', 'NPM_', 'BASH_', 'GIT_', 'XDG_', 'LC_', 'DOTNET_', 'COMPLUS_')


def env_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Z_][A-Z0-9_]{0,99}', name):
        raise RouterError('invalid_environment', 'Use a bounded uppercase environment variable name.')
    if name in CONTROL_NAMES or name.startswith(CONTROL_PREFIXES):
        raise RouterError('unsafe_environment', 'Execution-control, proxy, certificate and ATM environment overrides are forbidden.')
    return name


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def credential_rows(state, *, scope=None):
    """One metadata snapshot; no decryption. Undeclared requested names report missing."""
    with state.db() as db:
        db.execute('BEGIN')
        names = {r[0] for r in db.execute('SELECT name FROM secrets')}
        settings = {r[0]: json.loads(r[1]) for r in db.execute(
            "SELECT name,value FROM settings WHERE name='credential_registry' OR name LIKE 'credential_meta:%' OR name LIKE 'sync_conflict:%'")}
    selected = sorted(set(scope) if scope is not None else names | set(settings.get('credential_registry', {})))
    out = []
    for name in selected:
        meta = settings.get('credential_meta:' + name, {})
        expiry = meta.get('expires_at')
        state_name = ('sync_conflict' if settings.get('sync_conflict:' + name) else
                      'missing_credential' if name not in names else
                      'credential_expired' if expiry is not None and expiry <= time.time() else 'configured_not_verified')
        out.append({'name': name, 'reference': 'atm://' + name, 'configured': name in names,
                    'state': state_name, 'expires_at': expiry})
    return out


def find_keys(state, query='', *, scope=None):
    if not isinstance(query, str) or len(query) > 200 or any(ord(c) < 32 for c in query):
        raise RouterError('invalid_query', 'Use a bounded credential name, alias or environment name.')
    rows = credential_rows(state, scope=scope)
    aliases = state.setting('key_aliases', {})
    if query.startswith('atm://'):
        query = query[6:]
        credential_name(query)
    if query:
        exact = [r for r in rows if r['name'] == query]
        targets = aliases.get(query, [])
        if not exact:
            exact = [r for r in rows if r['name'] in targets]
        if not exact and not targets:
            # Suggestions only. Never use fuzzy/prefix matching for actual injection.
            exact = [r for r in rows if re.sub('[^A-Z0-9_]', '_', r['name'].upper()) + '_KEY' == query]
        if not exact and not targets:
            prefix = query.removesuffix('_KEY').lower().replace('_', '.')
            exact = [r for r in rows if r['name'].startswith(prefix + '.')]
        if not exact and not targets:
            exact = [r for r in rows if query.lower() in r['name']]
        rows = exact
    return {'status': 'ambiguous' if query and len(rows) > 1 else 'found' if rows else 'not_found',
            'query': query, 'matches': rows, 'secrets_returned': False,
            'note': 'Discovery is metadata only; exec requires an exact atm:// reference and a separate owner-approved command permit.'}


def alias(state, name, credentials, *, apply=False, expected=None):
    env_name(name)
    if not isinstance(credentials, list) or not 1 <= len(credentials) <= 32 or len(set(credentials)) != len(credentials):
        raise RouterError('invalid_alias', 'Choose 1–32 distinct credential names.')
    for value in credentials:
        credential_name(value)
    with state.db() as db:
        db.execute('BEGIN IMMEDIATE')
        from .sync import _get, _set
        aliases = _get(db, 'key_aliases', {})
        old = aliases.get(name)
        revision = fingerprint(old)
        if apply and old is not None and old != sorted(credentials) and expected != revision:
            raise RouterError('alias_changed', 'Review the existing alias revision before replacing it with --expected.')
        if apply:
            _set(db, 'key_aliases', {**aliases, name: sorted(credentials)})
    return {'alias': name, 'credentials': sorted(credentials), 'previous_sha256': revision,
            'applied': apply, 'synced': False, 'execution_permission_granted': False}


def parse_mapping(items):
    if not isinstance(items, (list, tuple)) or not 1 <= len(items) <= 32:
        raise RouterError('invalid_mapping', 'Select 1–32 ENV=atm://exact.name mappings.')
    result = {}
    for item in items:
        if not isinstance(item, str) or '=' not in item:
            raise RouterError('invalid_mapping', 'Use ENV=atm://exact.name, never a literal secret or a guessed alias.')
        name, ref = item.split('=', 1)
        env_name(name)
        if not ref.startswith('atm://'):
            raise RouterError('invalid_mapping', 'Only exact atm:// references are accepted; literal values are forbidden.')
        target = credential_name(ref[6:])
        if name in result:
            raise RouterError('invalid_mapping', 'Duplicate environment mappings are rejected.')
        result[name] = target
    return dict(sorted(result.items()))


def file_pin(path, *, executable=False):
    """Reject symlink operands; pin bytes plus stable inode metadata while hashing."""
    if executable:
        # Preserve the invocation path: resolving a venv Python symlink for Popen
        # silently drops pyvenv.cfg discovery and the user's installed dependencies.
        invoked = Path(os.path.abspath(os.path.expanduser(str(path))))
        try:
            resolved = invoked.resolve(strict=True)
        except (OSError, RuntimeError):
            raise RouterError('command_missing', 'Cannot resolve the selected executable.') from None
        if not os.access(invoked, os.X_OK):
            raise RouterError('bad_executable', 'Program is not executable.')
        target = file_pin(resolved)
        contexts = []
        for parent in (invoked.parent, invoked.parent.parent):
            cfg = parent / 'pyvenv.cfg'
            if cfg.exists() or cfg.is_symlink():
                contexts.append(file_pin(cfg))
        return {'path': str(invoked), 'resolved': str(resolved), 'sha256': target['sha256'], 'contexts': contexts}
    path = safe_path(Path(path)).resolve()
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
                raise RouterError('unsafe_command_file', 'Pinned files must be bounded regular files.')
            if executable and not os.access(path, os.X_OK):
                raise RouterError('bad_executable', 'Program is not executable.')
            digest = hashlib.sha256()
            while chunk := os.read(fd, 1024 * 1024):
                digest.update(chunk)
            after = os.fstat(fd)
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise RouterError('command_changed', 'A pinned file changed during inspection.')
        finally:
            os.close(fd)
    except OSError:
        raise RouterError('command_missing', 'An approved program or pinned input file is missing or unreadable.') from None
    return {'path': str(path), 'sha256': digest.hexdigest()}


def normalized_argv(argv):
    if not isinstance(argv, (list, tuple)) or not 1 <= len(argv) <= 128 or any(
        not isinstance(a, str) or len(a) > 8192 or '\x00' in a or '\n' in a or '\r' in a for a in argv):
        raise RouterError('invalid_command', 'Use a bounded argument array; no shell-string interpretation is performed.')
    if not argv[0]:
        raise RouterError('invalid_command', 'A program is required after --.')
    # Select an absolute executable, preserving its invocation context. file_pin
    # separately fixes the real target and any adjacent Python venv configuration.
    p = Path(argv[0]).expanduser() if '/' in argv[0] else Path(shutil.which(argv[0]) or '')
    if not p.is_file():
        raise RouterError('command_missing', 'Cannot resolve the selected executable; no program was started.')
    return [os.path.abspath(str(p)), *argv[1:]]


def command_plan(router, argv, mapping, workspace, *, pin_files=(), timeout=60):
    workspace = safe_path(Path(workspace)).resolve()
    if not workspace.is_dir():
        raise RouterError('workspace_missing', 'Create the approved project directory first.')
    home = router.state.home.resolve()
    if home == workspace or home.is_relative_to(workspace) or workspace.is_relative_to(home):
        raise RouterError('unsafe_workspace', 'The vault directory and its ancestors/descendants cannot be the execution workspace.')
    argv = normalized_argv(argv)
    if type(timeout) is not int or not 1 <= timeout <= 300:
        raise RouterError('invalid_timeout', 'Exec timeout must be between 1 and 300 seconds.')
    pinned = [file_pin(argv[0], executable=True)]
    candidates = list(pin_files)
    # Pin every existing positional file operand. Exact argv alone is not a code pin.
    for arg in argv[1:]:
        if arg and not arg.startswith('-'):
            candidate = Path(arg) if Path(arg).is_absolute() else workspace / arg
            if candidate.exists() or candidate.is_symlink():
                if candidate.is_file() or candidate.is_symlink():
                    candidates.append(str(candidate))
    for value in candidates:
        candidate = safe_path(Path(value) if Path(value).is_absolute() else workspace / value).resolve()
        if not candidate.is_relative_to(workspace):
            raise RouterError('unsafe_command_file', 'Non-executable file operands must be inside the approved project.')
        p = file_pin(candidate)
        if p not in pinned:
            pinned.append(p)
    if len(pinned) > 65:
        raise RouterError('too_many_pins', 'At most 64 project files can be pinned per rule.')
    rule = {'argv': argv, 'environment': mapping, 'workspace': str(workspace),
            'files': pinned, 'timeout': timeout, 'output_limit': MAX_OUTPUT}
    return {**rule, 'id': fingerprint(rule)}


def _profile_policy(state, path):
    safe_path(path, secret=True)
    if not path.exists():
        return None
    data = strict_json(path.read_bytes(), limit=65536)
    if not isinstance(data, dict) or data.get('format') != 'atm-client-v1':
        raise RouterError('invalid_profile', 'Existing profile is not an ATM client profile; it was preserved.')
    p = state.setting('access:' + str(data.get('id')))
    if not p or not hmac.compare_digest(p.get('token_hash', ''), hashlib.sha256(str(data.get('token')).encode()).hexdigest()):
        raise RouterError('invalid_profile', 'Existing profile is not owned by this vault; it was preserved.')
    if p.get('kind') == 'session_owner' or p['revoked'] or p['expires_at'] <= time.time():
        raise RouterError('grant_expired', 'Existing grant is unusable; revoke it and deliberately choose a new private profile.')
    return p


def permit_exec(router, agent, *, mappings, argv, workspace, output=None, ttl_hours=168,
                pin_files=(), timeout=60, apply=False, approve=None, user_home=None):
    if os.name != 'posix':
        raise RouterError('broker_platform', 'Generic session exec currently requires Linux/macOS Unix sockets.')
    if agent not in {'claude', 'codex', 'local'}:
        raise RouterError('unsupported_agent', 'Use claude, codex or local as the client label.')
    target = safe_path(Path(output) if output else router.state.home / 'local-exec.client.json'
                       if agent == 'local' else client_path(agent, user_home), secret=True)
    mapping = parse_mapping(mappings)
    rule = command_plan(router, argv, mapping, workspace, pin_files=pin_files, timeout=timeout)
    old = _profile_policy(router.state, target)
    seconds = _ttl(ttl_hours)
    if old and (old['client_uid'] != os.getuid() or old['socket'] != str(socket_path(router.state)) or old['agent'] != agent):
        raise RouterError('grant_identity_mismatch', 'The profile UID, socket or client label differs from this local execution plan.')
    rules = (old or {}).get('exec_rules', [])
    if len(rules) >= 32 and rule['id'] not in {r['id'] for r in rules}:
        raise RouterError('too_many_rules', 'At most 32 exact command permits are allowed in a profile.')
    plan = {'agent': agent, 'profile': str(target), 'socket': str(socket_path(router.state)),
            'rule': rule, 'previous_policy_sha256': fingerprint(old),
            'ttl_hours_for_new_profile': ttl_hours,
            'action': 'unchanged' if rule in rules else 'add_rule',
            'risk': 'Approved code receives selected plaintext credentials and may network, spend or exfiltrate them. This is not a code sandbox.'}
    digest = fingerprint(plan)
    if not apply:
        return {**plan, 'sha256': digest, 'applied': False, 'credentials_read': False}
    if approve != digest:
        raise RouterError('approval_required', 'Use --approve with the SHA-256 of the exact reviewed plan; no authority was changed.')
    import secrets
    identifier = old['id'] if old else uuid.uuid4().hex
    token = secrets.token_urlsafe(32) if old is None else None
    policy = old or {'id': identifier, 'agent': agent, 'kind': 'credentials', 'tools': [], 'pins': {},
                     'workspace': rule['workspace'], 'profile': str(target), 'socket': str(socket_path(router.state)),
                     'client_uid': os.getuid(), 'socket_owner_uid': os.getuid(), 'socket_gid': None,
                     'permissions': [], 'allow_paid': False, 'created_at': time.time(),
                     'expires_at': time.time() + seconds, 'revoked': False,
                     'token_hash': hashlib.sha256(token.encode()).hexdigest()}
    new_rules = rules if rule in rules else [*[r for r in rules if not (r['argv'] == rule['argv'] and r['workspace'] == rule['workspace'] and r['environment'] == rule['environment'])], rule]
    from .sync import _get, _set
    with router.state.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if _get(db, 'access:' + identifier) != old:
            raise RouterError('state_changed', 'Grant changed after preview. Review again.')
        _set(db, 'access:' + identifier, {**policy, 'exec_rules': new_rules})
    if token:
        try:
            write_sync_file(target, canonical({'format': 'atm-client-v1', 'id': identifier, 'agent': agent,
                                               'socket': str(socket_path(router.state)), 'token': token,
                                               'socket_owner_uid': os.getuid(), 'socket_gid': None}).encode())
        except BaseException:
            from .broker import revoke
            revoke(router.state, identifier, apply=True)
            raise
    return {'applied': True, 'action': plan['action'], 'grant_id': identifier, 'rule_id': rule['id'],
            'profile': str(target), 'expires_at': policy['expires_at'], 'sha256': digest, 'secrets_returned': False}


def permitted_names(router, policy):
    names = {name for r in policy.get('exec_rules', []) for name in r['environment'].values()}
    for tool_id in policy.get('tools', []):
        from .broker import _tool_pin
        try:
            if _tool_pin(router, tool_id) != policy.get('pins', {}).get(tool_id):
                continue
            tool = router.catalog.get(tool_id)
        except RouterError:
            continue
        if tool.get('credential'):
            names.add(tool['credential'])
        names.update(tool.get('command', {}).get('credential_env', {}).values())
    return sorted(names)


def redact_output(data, values):
    text = data.decode('utf-8', errors='replace')
    variants = set()
    for value in values:
        raw = value.encode()
        variants.update((value, quote(value, safe=''), json.dumps(value)[1:-1],
                         base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode()))
    for value in sorted(variants, key=len, reverse=True):
        if value:
            text = text.replace(value, '[REDACTED]')
    # No terminal escape sequences/control injection in JSON/terminal renderings.
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', text)


def captured_process(argv, workspace, values, *, timeout, limit=MAX_OUTPUT):
    """Bounded memory pipes, fresh minimal env, no temp output file, no inherited stdin."""
    env = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'NO_COLOR': '1', 'CI': '1', **values}
    try:
        proc = subprocess.Popen(argv, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                                close_fds=True, start_new_session=True)
    except OSError:
        raise RouterError('exec_start_failed', 'Could not start the approved program; no output was logged.') from None
    deadline, captured = time.monotonic() + timeout, {'stdout': bytearray(), 'stderr': bytearray()}
    total = 0
    reason = None
    try:
        with selectors.DefaultSelector() as sel:
            for name, pipe in (('stdout', proc.stdout), ('stderr', proc.stderr)):
                os.set_blocking(pipe.fileno(), False)
                sel.register(pipe, selectors.EVENT_READ, name)
            while sel.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    reason = 'exec_timeout'
                    break
                for key, _ in sel.select(min(remaining, .1)):
                    chunk = os.read(key.fileobj.fileno(), min(65536, limit + 1))
                    if not chunk:
                        sel.unregister(key.fileobj)
                        continue
                    total += len(chunk)
                    if total > limit:
                        reason = 'exec_output_limit'
                        break
                    captured[key.data].extend(chunk)
                if reason:
                    break
            if not reason:
                try:
                    proc.wait(timeout=max(.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    reason = 'exec_timeout'
    finally:
        # A command is a bounded job, not a persistent service launcher. Clean up its group.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()
        env.clear()
    if reason:
        captured.clear()
        raise RouterError(reason, 'Approved process exceeded its time/output bound. Output suppressed; reconcile side effects before retry.', uncertain=True)
    return {'returncode': proc.returncode,
            'stdout': redact_output(bytes(captured['stdout']), values.values()),
            'stderr': redact_output(bytes(captured['stderr']), values.values())}


def _connection_snapshot(state, names):
    """Private encrypted-row revision. Never hash plaintext or return this value to clients."""
    rows = []
    with state.db() as db:
        db.execute('BEGIN')
        from .sync import _get
        for name in sorted(set(names)):
            record = db.execute('SELECT nonce,ciphertext FROM secrets WHERE name=?', (name,)).fetchone()
            meta = _get(db, 'credential_meta:' + name, {})
            conflict = _get(db, 'sync_conflict:' + name, False)
            if conflict:
                raise RouterError('sync_conflict', 'Resolve the selected connection before execution.')
            if not record:
                raise RouterError('missing_credential', 'The selected connection is missing; no program was started.')
            if meta.get('expires_at') is not None and meta['expires_at'] <= time.time():
                raise RouterError('credential_expired', 'The selected connection expired; no program was started.')
            rows.append([name, record[0].hex(), record[1].hex(), meta])
    return fingerprint(rows)


def execute(broker, router, policy, args, request, peer_uid):
    if set(args) - {'argv', 'environment', 'workspace', 'request_key', 'dry_run'}:
        raise RouterError('invalid_request', 'Unknown generic exec fields; no process was started.')
    if policy['client_uid'] != os.getuid():
        raise RouterError('exec_uid_unsupported', 'Generic code execution across UIDs is disabled: no owner-privilege escalation is permitted.')
    mapping = args.get('environment')
    if not isinstance(mapping, dict):
        raise RouterError('invalid_mapping', 'Environment must be exact credential references.')
    # Protocol values are credential names, never caller-supplied plaintext.
    mapping = parse_mapping([str(k) + '=atm://' + str(v) for k, v in mapping.items()])
    argv = args.get('argv')
    if not isinstance(argv, list) or not argv or not Path(argv[0]).is_absolute():
        raise RouterError('invalid_command', 'Client must resolve the executable to an absolute path.')
    workspace = str(safe_path(Path(args.get('workspace', ''))).resolve())
    matches = [r for r in policy.get('exec_rules', []) if r['argv'] == argv and
               r['workspace'] == workspace and r['environment'] == mapping]
    if len(matches) != 1:
        raise RouterError('exec_denied', 'Command, project or credential mapping is outside this client grant.')
    rule = matches[0]
    for index, pin in enumerate(rule['files']):
        if file_pin(pin['path'], executable=index == 0) != pin:
            raise RouterError('grant_stale', 'Approved program or pinned input changed. Review a new permit, not a new Key.')
    statuses = credential_rows(router.state, scope=mapping.values())
    for r in statuses:
        if r['state'] != 'configured_not_verified':
            raise RouterError(r['state'], 'Repair only the affected credential connection; no process was started.')
    if type(args.get('dry_run', False)) is not bool:
        raise RouterError('invalid_request', 'dry_run must be a boolean.')
    if args.get('dry_run'):
        return {'dry_run': True, 'rule_id': rule['id'], 'credentials_read': False, 'execution_started': False}
    key = args.get('request_key')
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}', key):
        raise RouterError('request_key_required', 'Use a stable 1–120 character task key.')
    connection_revision = _connection_snapshot(router.state, mapping.values())

    def admit():
        current = broker._authorize(request, peer_uid)
        if rule not in current.get('exec_rules', []):
            raise RouterError('grant_stale', 'The execution permit changed before admission; no program was started.')
        if _connection_snapshot(router.state, mapping.values()) != connection_revision:
            raise RouterError('connection_changed', 'A selected connection changed during admission; inspect its current state before retrying.')

    values = {}
    try:
        for env, name in mapping.items():
            values[env] = router.vault.get(name)
        # Recheck lease and revocation immediately before admission, after expensive file/secret work.
        admit()
        job, created = router.state.create_job('atm.exec', {'rule_id': rule['id']}, Path(workspace),
                                              'exec:' + policy['id'] + ':' + key, context=rule['id'])
        if not created:
            return {'id': job['id'], 'status': job['status'], 'reused_request': True,
                    'returncode': job['data'].get('returncode'), 'output_retained': False, 'secrets_returned': False}
        try:
            admit()
            result = captured_process(argv, workspace, values, timeout=rule['timeout'], limit=rule['output_limit'])
            status = 'completed' if result['returncode'] == 0 else 'failed'
            router.state.update_job(job['id'], status, returncode=result['returncode'], verification='process_exit',
                                    output_retained=False)
            return {'id': job['id'], 'status': status, **result, 'output_retained': False, 'secrets_returned': False,
                    'output_redaction': 'best_effort_not_a_sandbox'}
        except RouterError as e:
            router.state.update_job(job['id'], 'submission_unknown' if e.uncertain else 'failed', error=e.as_dict(), output_retained=False)
            raise
    finally:
        values.clear()
