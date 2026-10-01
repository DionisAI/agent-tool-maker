"""One finite unlock session shared by terminal, Web management and scoped clients.

Owner control uses a private, per-session profile plus Unix peer identity. There is
no raw-secret read RPC. Owner profile is never handed to Agent Skills or sync.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import secrets
import threading
import time
import uuid

from .broker import Broker, call, safe_path, socket_path
from .errors import RouterError
from .storage import State, atomic_write, canonical
from .sync import strict_json
from .vault import Vault


def owner_path(home):
    return safe_path(Path(home).expanduser().absolute() / 'session-owner.json', secret=True)


def ttl_seconds(value):
    import re
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,5}[smh]', value):
        raise RouterError('invalid_ttl', 'Use an explicit fixed duration such as 30m or 8h.')
    seconds = int(value[:-1]) * {'s': 1, 'm': 60, 'h': 3600}[value[-1]]
    if not 1 <= seconds <= 86400:
        raise RouterError('invalid_ttl', 'Session duration must be 1 second to 24 hours; default is 30 minutes.')
    return seconds


def owner_call(home, operation, args=None, *, timeout=30):
    p = owner_path(home)
    if not p.exists():
        raise RouterError('session_locked', 'No unified unlock session. Owner runs atm unlock --ttl 30m; saved Keys need not be re-entered.')
    try:
        return call(p, operation, args or {}, timeout=timeout)
    except RouterError as e:
        if e.code in {'broker_unavailable', 'broker_locked', 'unauthorized'}:
            raise RouterError('session_locked', 'Unlock session is stopped, expired or revoked. No direct-vault fallback was attempted.') from None
        raise


def status(home):
    try:
        return owner_call(home, 'session.status')
    except RouterError as e:
        if e.code != 'session_locked':
            raise
        return {'status': 'locked', 'unlocked': False, 'seconds_remaining': 0, 'secrets_returned': False, 'session_mode_enabled': exists(home)}


def exists(home):
    """An opted-in session remains authoritative even after it ends: no silent fallback."""
    return owner_path(home).exists() or State(Path(home)).setting('secrets_session_enabled', False) is True


def shared_put(home, provider, value, *, replace=False, expires_at=None):
    return owner_call(home, 'session.put', {'provider': provider, 'value': value,
                                          'replace': replace, 'expires_at': expires_at})


class SessionVault(Vault):
    """A request-scoped master-key snapshot. NEVER falls back to a password/keyring."""
    def __init__(self, state, key):
        super().__init__(state)
        self._key = key

    def unlock(self):
        if self._key is None:
            raise RouterError('broker_locked', 'The session key is unavailable. No password or keyring fallback was attempted.')
        return self._key


class SecretSession(Broker):
    # Non-daemon handlers finish admitted bounded commands before process exit.
    daemon_threads = False

    def __init__(self, home, *, seconds=1800, vault=None):
        if type(seconds) not in (int, float) or not 0 < seconds <= 86400:
            raise RouterError('invalid_ttl', 'Use a positive session lease up to 24 hours.')
        self.closing = threading.Event()
        self.capacity = threading.BoundedSemaphore(2)
        self.owner_id = None
        super().__init__(home, ttl_hours=seconds / 3600, vault=vault)
        # Lease starts only after the successful unlock, not while a human is typing.
        self.deadline = time.monotonic() + seconds
        self.started_at = time.time()
        target = owner_path(self.state.home)
        if target.exists():
            old = strict_json(target.read_bytes(), limit=65536)
            previous = self.state.setting('access:' + str(old.get('id')))
            if previous:
                self.state.set_setting('access:' + previous['id'], {**previous, 'revoked': True})
        identifier, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
        self.owner_id = identifier
        policy = {'id': identifier, 'kind': 'session_owner', 'agent': 'owner-session', 'tools': [],
                  'pins': {}, 'workspace': str(self.state.home), 'permissions': [], 'allow_paid': False,
                  'socket': str(self.path), 'client_uid': os.getuid(), 'socket_owner_uid': os.getuid(), 'socket_gid': None,
                  'token_hash': hashlib.sha256(token.encode()).hexdigest(), 'created_at': time.time(),
                  'expires_at': time.time() + seconds + 300, 'revoked': False}
        try:
            self.state.set_setting('secrets_session_enabled', True)
            self.state.set_setting('access:' + identifier, policy)
            atomic_write(target, canonical({'format': 'atm-client-v1', 'id': identifier, 'agent': 'owner-session',
                                            'socket': str(self.path), 'token': token,
                                            'socket_owner_uid': os.getuid(), 'socket_gid': None}).encode())
        except BaseException:
            self.server_close()
            raise
        self.state.set_setting('broker_status', {'pid': os.getpid(), 'socket': str(self.path),
            'started_at': self.started_at, 'lease_expires_at': self.started_at + seconds,
            'state': 'running', 'mode': 'secrets_session'})

    def open_router(self):
        # A lock can race with the first authorization. Do not create a regular
        # Vault with key=None: that would re-prompt from a request handler.
        key = self._key
        if key is None or self.closing.is_set() or time.monotonic() >= self.deadline:
            raise RouterError('broker_locked', 'Session ended before the request opened; no unlock fallback.')
        from .engine import Router
        router = Router(self.state.home)
        router.vault = SessionVault(router.state, key)
        return router


    def _authorize(self, request, peer_uid, *, require_unlocked=True):
        policy = super()._authorize(request, peer_uid, require_unlocked=require_unlocked)
        if policy.get('kind') == 'project_session' and policy.get('session_binding') != self.owner_id:
            raise RouterError('unauthorized', 'Project approval belongs to an earlier unlock session.')
        return policy

    def metadata_status(self):
        seconds = max(0, self.deadline - time.monotonic())
        unlocked = seconds > 0 and self._key is not None and not self.closing.is_set()
        return {'status': 'unlocked' if unlocked else 'locked', 'unlocked': unlocked,
                'seconds_remaining': int(seconds) if unlocked else 0,
                'lease': 'fixed_not_sliding', 'secrets_returned': False, 'session_mode_enabled': True}

    def _require_owner(self, policy):
        if policy.get('kind') != 'session_owner' or policy['id'] != self.owner_id or policy['client_uid'] != os.getuid():
            raise RouterError('operation_denied', 'Credential users cannot manage, unlock or lock the Owner session.')

    def handle(self, request, *, peer_uid=None):
        uid = os.getuid() if peer_uid is None else peer_uid
        op = request.get('operation') if isinstance(request, dict) else None
        if op == 'status':
            policy = self._authorize(request, uid)
            if request['args']:
                raise RouterError('invalid_request', 'Status does not accept parameters.')
            return {'agent': policy['agent'], 'kind': policy.get('kind', 'tools'),
                    'credentials': policy.get('credentials', []), 'grant_id': policy['id'], 'tools': policy['tools'],
                    'workspace': policy['workspace'], 'expires_at': policy['expires_at'],
                    'broker_seconds_remaining': self.metadata_status()['seconds_remaining'],
                    'exec_permits': [{k: r[k] for k in ('id', 'argv', 'environment', 'workspace', 'timeout')} for r in policy.get('exec_rules', [])],
                    'secrets_returned': False}
        if op == 'job':
            policy = self._authorize(request, uid, require_unlocked=False)
            args = request['args']
            if set(args) - {'id', 'refresh'} or not isinstance(args.get('id'), str) or len(args['id']) > 100 or type(args.get('refresh', False)) is not bool:
                raise RouterError('invalid_request', 'Invalid owned-job lookup.')
            job = self.state.job(args['id'])
            if job['tool'] == 'atm.exec':
                if not job['request_key'].startswith('exec:' + policy['id'] + ':'):
                    raise RouterError('job_denied', 'This grant cannot inspect another credential-execution receipt.')
                return job  # Only rule ID, status and exit metadata were persisted, never output.
        new_ops = {'keys.find', 'keys.list', 'exec', 'session.status', 'session.lock', 'session.put', 'session.remove', 'session.project'}
        if op not in new_ops:
            return super().handle(request, peer_uid=uid)
        metadata = op in {'keys.find', 'keys.list', 'session.status', 'session.lock'}
        policy = self._authorize(request, uid, require_unlocked=not metadata)
        args = request['args']
        if op.startswith('session.'):
            self._require_owner(policy)
            allowed = {'session.status': set(), 'session.lock': set(),
                       'session.put': {'provider', 'value', 'replace', 'expires_at'},
                       'session.remove': {'provider', 'confirm'},
                       'session.project': {'workspace', 'credentials', 'approved_sha256'}}
            if set(args) - allowed[op]:
                raise RouterError('invalid_request', 'Unexpected session management fields.')
            if op == 'session.status':
                return self.metadata_status()
            if op == 'session.lock':
                # Lock does not wait for or revoke plaintext already given to running children.
                self.deadline = 0
                self._key = None
                self.vault._key = None
                self.vault.password = None
                self.vault._used_secrets.clear()
                self.closing.set()
                return self.metadata_status()
        if not self.capacity.acquire(blocking=False):
            raise RouterError('session_busy', 'Two bounded calls are active; no new call or automatic retry was started.')
        router = None
        try:
            router = self.open_router()
            if op in {'keys.find', 'keys.list'}:
                if set(args) - {'query'}:
                    raise RouterError('invalid_request', 'Only a metadata query is accepted.')
                from .secrets_provider import find_keys, permitted_names
                return {**find_keys(router.state, args.get('query', ''), scope=permitted_names(router, policy)),
                        'session': self.metadata_status()}
            if op == 'exec':
                from .secrets_provider import execute
                return execute(self, router, policy, args, request, uid)
            self._authorize(request, uid)  # Revalidate after acquiring the request slot.
            if op == 'session.project':
                from .quickstart import grant_project
                return grant_project(router, self, args)
            if op == 'session.put':
                from .management import connect_value
                if type(args.get('replace', False)) is not bool:
                    raise RouterError('invalid_request', 'replace must be a boolean.')
                return connect_value(router, args.get('provider'), args.get('value'),
                                     replace=args.get('replace', False), expires_at=args.get('expires_at'))
            from .extensions import credential_name
            name = credential_name(args.get('provider'))
            if args.get('confirm') != name:
                raise RouterError('approval_required', 'Confirm the exact connection to remove locally.')
            return router.vault.delete(name)
        finally:
            if router:
                router.close()
                router.vault._key = None
                router.vault.password = None
                router.vault._used_secrets.clear()
            self.capacity.release()

    def server_close(self):
        self.closing.set()
        self.deadline = 0
        self._key = None
        super().server_close()
        if self.owner_id:
            p = self.state.setting('access:' + self.owner_id)
            if p:
                self.state.set_setting('access:' + self.owner_id, {**p, 'revoked': True})


def run_service(server):
    """Explicit finite service. Caller owns terminal/thread lifetime; never auto-installed."""
    def expire():
        while not server.closing.wait(min(.1, max(.001, server.deadline - time.monotonic()))):
            if time.monotonic() >= server.deadline:
                break
        server.deadline = 0
        server._key = None
        server.vault._key = None
        server.shutdown()
    watch = threading.Thread(target=expire, daemon=True)
    watch.start()
    try:
        server.serve_forever(poll_interval=.1)
    finally:
        server.closing.set()
        server.server_close()
        watch.join(2)


def serve(home, *, ttl='30m'):
    seconds = ttl_seconds(ttl)
    current = status(home)
    if current['unlocked']:
        print(canonical({**current, 'action': 'unchanged', 'note': 'An existing lease was reused, not extended.'}), flush=True)
        return 0
    server = SecretSession(home, seconds=seconds)
    print(canonical({**server.metadata_status(), 'pid': os.getpid(), 'foreground': True,
                     'note': 'Owner service; leave this terminal open. New Agent processes reuse the lease. Ctrl-C or atm lock ends it.'}), flush=True)
    try:
        run_service(server)
    except KeyboardInterrupt:
        # run_service already clears key references and closes the listener.
        pass
    return 0
