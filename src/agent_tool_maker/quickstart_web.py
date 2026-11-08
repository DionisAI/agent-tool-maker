"""Small, token-protected human window. Password and Keys never reach agent stdout."""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path
import threading
import time
import webbrowser

from .errors import RouterError
from .quickstart import PENDING_SECONDS, request_record, scope_plan
from .secrets_provider import credential_rows, fingerprint
from .storage import State
from .webapp import Console, Handler, fields, flag, text


class ApprovalWindow(Console):
    def __init__(self, home, request_id, **kwargs):
        self.record = request_record(State(Path(home)), request_id)
        self.request_id = request_id
        self.plan = scope_plan(State(Path(home)), self.record['workspace'], self.record['credentials'])
        if self.record['approval_sha256'] != fingerprint(self.plan):
            raise RouterError('plan_changed', 'Local request was changed before opening. Request a new window.')
        self.terminal = False
        self.failures = 0
        super().__init__(home, **kwargs)
        self.RequestHandlerClass = ApprovalHandler

    def update_record(self, **patch):
        self.record = {**self.record, **patch}
        State(self.home).set_setting('desktop-request:' + self.request_id, self.record)

    def view(self, router):
        from .session import status
        current = status(self.home)
        cfg = router.state.setting('vault')
        return {'plan': self.plan, 'approved_sha256': fingerprint(self.plan),
                'connections': credential_rows(router.state, scope=self.plan['credentials']),
                'initialized': bool(cfg), 'backend': cfg.get('backend') if cfg else 'passphrase',
                'passkeys': self.passkeys.status(),
                'session': current, 'status': self.record['status'], 'attempts_left': max(0, 5 - self.failures)}

    def check_pending(self, body):
        if self.terminal or self.record['status'] == 'ready':
            raise RouterError('request_finished', 'This request was already completed or declined.')
        if time.time() - self.record['created_at'] >= PENDING_SECONDS or self.failures >= 5:
            self.passkeys.clear()
            raise RouterError('request_expired', 'This window expired. Ask the Agent to open a new request.')
        if not flag(body, 'consent') or text(body, 'approved_sha256') != fingerprint(self.plan):
            self.passkeys.clear()
            raise RouterError('approval_required', 'Approve the exact project and credential list shown here.')

    def passkey_intent(self):
        return 'desktop:' + self.request_id + ':' + fingerprint(self.plan)

    def approve(self, router, body):
        from .session import status, SecretSession, run_service, owner_call, shared_put
        from .extensions import declare_credential
        fields(body, ('approved_sha256', 'consent'), ('passphrase', 'confirm_password', 'credentials', 'passkey'))
        self.check_pending(body)
        if 'passkey' in body and ('passphrase' in body or 'confirm_password' in body):
            self.passkeys.clear()
            raise RouterError('invalid_request', 'Select one local unlock method.')
        supplied = body.get('credentials', {})
        if not isinstance(supplied, dict) or set(supplied) - set(self.plan['credentials']):
            raise RouterError('invalid_scope', 'Only missing credentials listed in this request can be saved.')
        rows = credential_rows(router.state, scope=self.plan['credentials'])
        missing = {r['name'] for r in rows if r['state'] == 'missing_credential'}
        if set(supplied) != missing:
            raise RouterError('state_changed', 'The missing-key list changed. Refresh this window; existing Keys will not be replaced.')
        for r in rows:
            if r['state'] not in {'configured_not_verified', 'missing_credential'}:
                raise RouterError(r['state'], 'Use ATM management to repair expiry or synchronization conflict; do not replace blindly.')
        for value in supplied.values():
            if not isinstance(value, str) or not value or len(value) > 16384 or any(c in value for c in '\r\n\x00'):
                raise RouterError('bad_credential', 'Key must be nonempty and single-line.')
        current = status(self.home)
        if not current['unlocked']:
            if not router.state.setting('vault'):
                password = text(body, 'passphrase')
                if not password or password != text(body, 'confirm_password'):
                    raise RouterError('password_confirmation', 'First use: confirm the new master password.')
                router.vault.init('passphrase')
            try:
                if 'passkey' in body:
                    self.passkeys.auth_finish(router.vault, body['passkey'], self.passkey_intent())
                service = SecretSession(self.home, seconds=1800, vault=router.vault)
            except RouterError as e:
                if e.code in {'vault_locked', 'passkey_verification', 'passkey_unwrap_failed', 'passkey_binding'}:
                    self.failures += 1
                raise
            self.secret_session = service
            self.secret_session_thread = threading.Thread(target=run_service, args=(service,), daemon=True)
            self.secret_session_thread.start()
        self.passkeys.clear()
        for name, value in supplied.items():
            declare_credential(router, name, apply=True)
            shared_put(self.home, name, value, replace=False)
        result = owner_call(self.home, 'session.project', {
            'workspace': self.plan['workspace'], 'credentials': self.plan['credentials'],
            'approved_sha256': fingerprint(self.plan)})
        self.update_record(status='ready', approved_at=time.time())
        return result


class ApprovalHandler(Handler):
    def do_GET(self):
        # Retain the exact Host/Origin/bearer checks. Only the static empty shell is public.
        names = {'/': ('quickstart.html', 'text/html; charset=utf-8'),
                 '/assets/quickstart.js': ('quickstart.js', 'text/javascript; charset=utf-8'),
                 '/assets/passkeys.js': ('passkeys.js', 'text/javascript; charset=utf-8'),
                 '/assets/quickstart.css': ('quickstart.css', 'text/css; charset=utf-8')}
        if self.path == '/api/desktop':
            return self.handle_request(False)
        if self.path not in names:
            self.respond(404, {'error': {'code': 'not_found', 'message': 'Unknown window resource.'}})
            return
        try:
            self.check_request(authenticated=False)
            name, mime = names[self.path]
            self.respond(200, files('agent_tool_maker.data').joinpath('web').joinpath(name).read_bytes(), mime=mime)
        except RouterError as e:
            self.respond(403, {'error': e.as_dict()})

    def read(self, router):
        if self.path == '/api/desktop':
            return self.server.view(router)
        raise RouterError('not_found', 'This window only handles this local project request.')

    def mutate(self, router, body):
        if self.path == '/api/desktop/passkey/begin':
            fields(body, ('approved_sha256', 'consent', 'credential_id'))
            self.server.check_pending(body)
            from .session import status
            if status(self.server.home)['unlocked']:
                raise RouterError('session_already_unlocked', 'Existing lease was preserved; approve its exact scope without unlocking again.')
            return self.server.passkeys.auth_begin(text(body, 'credential_id'), self.server.passkey_intent())
        if self.path == '/api/desktop/passkey/cancel':
            fields(body)
            self.server.passkeys.clear()
            return {'status': 'cancelled'}
        if self.path == '/api/desktop/approve':
            return self.server.approve(router, body)
        if self.path == '/api/desktop/cancel':
            fields(body)
            if self.server.record['status'] == 'ready':
                raise RouterError('request_finished', 'Use lock to end an already approved session.')
            self.server.update_record(status='denied'); self.server.terminal = True
            self.server.passkeys.clear()
            return {'status': 'denied'}
        if self.path == '/api/desktop/lock':
            fields(body)
            self.server.passkeys.clear()
            from .session import owner_call
            result = owner_call(self.server.home, 'session.lock')
            self.server.update_record(status='locked'); self.server.terminal = True
            return result
        raise RouterError('not_found', 'No shell, raw-key read or arbitrary management is exposed here.')


def serve_request(home, identifier):
    """Finite local process started by the Agent, not a boot service or public listener."""
    server = None
    try:
        server = ApprovalWindow(home, identifier, localhost=True)
        import signal
        def stop(signum, frame):
            server.terminal = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        from .session import status
        current = status(home)
        server.update_record(url=server.origin, browser_opened=False, heartbeat=time.time())
        opened = False
        if server.record.get('open_browser'):
            # A one-time launch code, never the per-window bearer, goes into the browser's URL and history.
            # The page trades it at the exact Origin for the bearer. Neither goes to CLI JSON/logs.
            # It lives as long as the request can be approved: rerunning `atm start` reuses this window
            # and mints no new code, so a browser that opens late must still be let in (once).
            left = PENDING_SECONDS - (time.time() - server.record['created_at'])
            opened = bool(webbrowser.open(server.origin + '/#launch=' + server.launch_code(seconds=max(1, left))))
        server.update_record(status='needs_approval' if current['unlocked'] else 'needs_unlock', browser_opened=opened)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
        thread.start()
        try:
            while not server.terminal:
                if server.record['status'] == 'ready':
                    if not status(home)['unlocked']:
                        break
                elif time.time() - server.record['created_at'] >= PENDING_SECONDS:
                    break
                server.update_record(heartbeat=time.time())
                time.sleep(.2)
        finally:
            server.shutdown(); thread.join(5)
    except (OSError, ValueError, RouterError):
        state = State(Path(home))
        record = request_record(state, identifier)
        state.set_setting('desktop-request:' + identifier, {**record, 'status': 'window_unavailable'})
        if server:
            server.record = {**record, 'status': 'window_unavailable'}
        return 2
    finally:
        if server:
            if server.record['status'] not in {'denied', 'locked', 'window_unavailable'}:
                server.update_record(status='expired')
            server.server_close()
    return 0
