"""`atm ui` reopens this home's live console; never a foreign listener or another home."""
from contextlib import contextmanager
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from agent_tool_maker import __version__, webapp
from agent_tool_maker.cli import main
from agent_tool_maker.storage import atomic_write
from agent_tool_maker.webapp import Console

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Owner-only token files are a POSIX contract')
KEYS = {'url', 'session_token_file', 'scope', 'expires_after_hours', 'note', 'reused'}


@pytest.fixture
def ui(tmp_path, monkeypatch, capsys):
    exe = tmp_path/'atm'; exe.write_text('#!/bin/sh\nexit 0\n'); exe.chmod(0o700)
    opened, started = [], []
    monkeypatch.setattr(webapp.webbrowser, 'open', lambda url: opened.append(url) or True)

    class Once(Console):
        # A fresh `atm ui` server binds, writes its file and announces; then Ctrl-C.
        def serve_forever(self, poll_interval=0.5):
            started.append(SimpleNamespace(origin=self.origin, token=self.token, token_path=self.token_path,
                                           server_port=self.server_port, codes=list(self.launch_codes)))
            raise KeyboardInterrupt
    monkeypatch.setattr(webapp, 'Console', Once)

    def run(home, *extra):
        code = main(['--home', str(home), 'ui', '--atm-executable', str(exe), *extra])
        out = capsys.readouterr()
        assert code == 0 and out.err == '', out
        result = json.loads(out.out)
        assert set(result) == KEYS and result['scope'] == 'loopback_only'
        assert all(url.partition('#launch=')[2] not in out.out for url in opened)  # Codes are never printed.
        return result

    def fail(home, *extra):
        code = main(['--home', str(home), 'ui', '--atm-executable', str(exe), *extra])
        out = capsys.readouterr()
        assert code == 2 and out.err == '', out
        return json.loads(out.out)['error']
    return SimpleNamespace(run=run, fail=fail, opened=opened, started=started, home=tmp_path/'state')


@contextmanager
def running(home, **kw):
    server = Console(home, localhost=True, **kw)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True); thread.start()
    try:
        yield server
    finally:
        server.shutdown(); server.server_close(); thread.join(5)


@contextmanager
def listener(answer, length=True):
    """Another local HTTP program; records each request's headers and every byte it received.

    answer(headers) -> (status, type, body, headers). length=False answers without Content-Length.
    """
    seen, received = [], []

    class Other(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def setup(self):
            # Every byte the client sends before it waits for the answer, then parsed from that copy.
            super().setup()
            self.rfile.close()
            data = b''
            self.connection.settimeout(.05)
            try:
                while chunk := self.connection.recv(4096):
                    data += chunk
            except TimeoutError:
                pass
            self.connection.settimeout(None)
            received.append(data); self.rfile = io.BytesIO(data)
        def do_GET(self):
            seen.append(dict(self.headers))
            status, ctype, body, extra = answer(self.headers)
            raw = body.encode()
            self.send_response(status); self.send_header('Content-Type', ctype)
            if length: self.send_header('Content-Length', str(len(raw)))
            for name, value in extra.items(): self.send_header(name, value)
            self.end_headers(); self.wfile.write(raw)
        do_POST = do_GET
    server = ThreadingHTTPServer(('127.0.0.1', 0), Other)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield SimpleNamespace(port=server.server_address[1], seen=seen, received=received)
    finally:
        server.shutdown(); server.server_close(); thread.join(5)


def foreign(status, ctype, body, location=None):
    return listener(lambda headers: (status, ctype, body, {'Location': location} if location else {}))


def proof(token, challenge):
    return hmac.new(token.encode(), b'atm-console-probe|' + challenge.encode(), hashlib.sha256).hexdigest()


def impostor(token, identity, pad=0, length=True):
    """Holds the token (so it passes the proof) but reports the given identity."""
    def answer(headers):
        if 'X-ATM-Challenge' in headers and 'Authorization' not in headers:
            body = json.dumps({'service': 'atm-console', 'proof': proof(token, headers['X-ATM-Challenge'])})
            return 200, 'application/json', body + ' ' * pad, {}
        if headers.get('Authorization') == 'Bearer ' + token:
            return 200, 'application/json', json.dumps(identity), {}
        return 401, 'application/json', '{"error":{"code":"unauthorized"}}', {}
    return listener(answer, length)


def bearer_sent(seen):
    return any(name.lower() == 'authorization' for headers in seen for name in headers)


def leaked(token, other):
    """Whether the token's value is anywhere in the bytes that listener received, not only as a bearer."""
    return token.encode() in b''.join(other.received)


@contextmanager
def trickling(seconds=8):
    """Accepts, then sends a response that never finishes, one byte every 50 ms; records the bytes it received."""
    server = socket.create_server(('127.0.0.1', 0)); server.settimeout(.1)
    stop, received = threading.Event(), []

    def record(connection):
        connection.setblocking(False)  # Only what has already arrived; the trickle keeps its pace.
        try:
            while chunk := connection.recv(4096):
                received.append(chunk)
        except OSError:
            pass
        finally:
            connection.settimeout(.5)

    def serve():
        end = time.monotonic() + seconds
        while not stop.is_set() and time.monotonic() < end:
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            with connection:
                connection.settimeout(.5)
                try:
                    received.append(connection.recv(4096))
                except OSError:
                    pass
                for byte in b'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nX-Pad: ' + b'a' * 4000:
                    if stop.is_set() or time.monotonic() >= end:
                        break
                    try:
                        connection.sendall(bytes([byte]))
                    except OSError:
                        break
                    record(connection)  # Anything sent later on this connection.
                    stop.wait(.05)
                record(connection)
        server.setblocking(False)  # Connections still waiting when it stops: their bytes count too.
        while True:
            try:
                connection, _ = server.accept()
            except OSError:
                break
            with connection:
                connection.settimeout(.2)
                try:
                    received.append(connection.recv(4096))
                except OSError:
                    pass
    thread = threading.Thread(target=serve, daemon=True); thread.start()
    try:
        yield SimpleNamespace(port=server.getsockname()[1], received=received)
    finally:
        stop.set(); thread.join(5); server.close()


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


def fresh(ui, result):
    assert len(ui.started) == 1 and result['reused'] is False
    new = ui.started[0]
    assert result['url'] == new.origin and len(new.codes) == 1
    # The browser gets a one-time launch code, never the bearer.
    assert ui.opened == [new.origin + '/#launch=' + new.codes[0]] and new.token not in ui.opened[0]
    assert not new.token_path.exists()  # Ctrl-C removed only its own file.
    return new


def test_console_identity_requires_bearer_and_is_non_secret(ui):
    with running(ui.home) as server, httpx.Client(base_url=server.origin, trust_env=False) as client:
        assert client.get('/api/console').status_code == 401
        assert client.get('/api/console', headers={'Authorization': 'Bearer wrong'}).status_code == 401
        body = client.get('/api/console', headers={'Authorization': 'Bearer ' + server.token}).json()
        assert body == {'service': 'atm-console', 'version': __version__, 'home': str(server.home),
                        'expires_in_seconds': body['expires_in_seconds']}
        assert 8 * 3600 - 60 < body['expires_in_seconds'] <= 8 * 3600 and server.token not in json.dumps(body)
        assert client.post('/api/console', json={}, headers={'Authorization': 'Bearer ' + server.token, 'Origin': server.origin}).status_code == 404


def test_console_challenge_answers_only_a_proof_of_the_token(ui):
    with running(ui.home) as server, httpx.Client(base_url=server.origin, trust_env=False) as client:
        challenge = secrets.token_hex(32)
        response = client.get('/api/console', headers={'X-ATM-Challenge': challenge})
        assert response.status_code == 200
        assert response.json() == {'service': 'atm-console', 'proof': proof(server.token, challenge)}
        assert server.token not in response.text and str(server.home) not in response.text and __version__ not in response.text
        assert client.get('/api/console', headers={'X-ATM-Challenge': secrets.token_hex(32)}).json()['proof'] != response.json()['proof']
        for bad in ['', 'zz' * 32, 'AB' * 32, challenge[:-1], challenge + '0']:
            assert client.get('/api/console', headers={'X-ATM-Challenge': bad}).status_code == 400
        # A request with any bearer is the identity mode: a wrong one is refused, not proven.
        assert client.get('/api/console', headers={'X-ATM-Challenge': challenge, 'Authorization': 'Bearer wrong'}).status_code == 401
        assert client.get('/api/console', headers={'X-ATM-Challenge': challenge, 'Origin': 'http://evil.test'}).status_code == 403
        assert client.get('/api/console', headers=[('X-ATM-Challenge', challenge)] * 2).status_code == 403


def redeem(server, code, **headers):
    with httpx.Client(base_url=server.origin, trust_env=False) as client:
        return client.post('/api/console/redeem', json={'code': code}, headers={'Origin': server.origin, **headers})


@pytest.mark.parametrize('extra', [(), ('--no-browser',), ('--port', 'SAME')], ids=['browser', 'no-browser', 'same-port'])
def test_running_console_of_this_home_is_reused(ui, extra):
    with running(ui.home) as server:
        before = server.token_path.read_bytes()
        extra = tuple(str(server.server_port) if x == 'SAME' else x for x in extra)
        result = ui.run(ui.home, *extra)
        assert ui.started == []  # No second server was bound.
        assert result['reused'] is True and result['url'] == server.origin
        assert result['session_token_file'] == str(server.token_path) and 7.9 < result['expires_after_hours'] <= 8
        assert server.token not in json.dumps(result)
        codes = list(server.launch_codes)
        assert len(codes) == (0 if '--no-browser' in extra else 1)
        assert ui.opened == [server.origin + '/#launch=' + code for code in codes]
        assert all(server.token not in url for url in ui.opened)
        assert server.token_path.read_bytes() == before
        for code in codes:  # The opened page trades the code for the bearer exactly once.
            assert redeem(server, code).json() == {'token': server.token}
            assert redeem(server, code).status_code == 401
        with httpx.Client(base_url=server.origin, trust_env=False) as client:
            assert client.get('/api/overview', headers={'Authorization': 'Bearer ' + server.token}).status_code == 200


def test_launch_code_is_single_use_short_lived_and_exact_origin_only(ui):
    with running(ui.home) as server, httpx.Client(base_url=server.origin, trust_env=False) as client:
        bearer = {'Authorization': 'Bearer ' + server.token}

        def mint():
            response = client.post('/api/console/launch-code', json={}, headers={**bearer, 'Origin': server.origin})
            assert response.status_code == 200 and set(response.json()) == {'code'}
            return response.json()['code']
        assert client.post('/api/console/launch-code', json={}, headers={'Origin': server.origin}).status_code == 401
        assert client.post('/api/console/launch-code', json={}, headers=bearer).status_code == 403
        code = mint()
        assert re.fullmatch(r'[A-Za-z0-9_-]{43}', code) and code != server.token
        # Exact Origin and Host, or nothing; a refused attempt does not use up the code.
        assert client.post('/api/console/redeem', json={'code': code}).status_code == 403
        assert redeem(server, code, Origin='http://localhost:1').status_code == 403
        assert redeem(server, code, Origin='null').status_code == 403
        assert redeem(server, code, Host=f'127.0.0.1:{server.server_port}').status_code == 403
        response = redeem(server, code)
        assert response.status_code == 200 and response.json() == {'token': server.token}
        assert response.headers['cache-control'] == 'no-store'
        again = redeem(server, code)
        assert again.status_code == 401 and again.json()['error']['code'] == 'launch_expired' and server.token not in again.text
        for unknown in [secrets.token_urlsafe(32), 'x', server.token, '']:
            assert redeem(server, unknown).json()['error']['code'] == 'launch_expired'
        assert client.post('/api/console/redeem', json={'code': mint(), 'extra': 1}, headers={'Origin': server.origin}).status_code == 400
        late = mint()
        assert 0 < server.launch_codes[late] - time.monotonic() <= 60
        server.launch_codes[late] = time.monotonic() - 1
        assert redeem(server, late).json()['error']['code'] == 'launch_expired'
        for _ in range(12):
            mint()
        assert len(server.launch_codes) <= 8  # Outstanding codes stay bounded.
        valid = mint()
        server.expires_at = time.monotonic() - 1  # An expired session hands out no bearer.
        response = redeem(server, valid)
        assert response.status_code == 401 and response.json()['error']['code'] == 'session_expired' and server.token not in response.text


def test_newest_live_console_is_reused_and_dead_files_are_removed(ui):
    dead = ui.home/f'ui-session-{free_port()}.token'
    with running(ui.home) as older, running(ui.home) as newer:
        atomic_write(dead, secrets.token_urlsafe(32).encode())
        os.utime(older.token_path, (time.time() - 60, time.time() - 60))
        os.utime(dead, (time.time() + 60, time.time() + 60))
        result = ui.run(ui.home)
        assert result['reused'] is True and result['url'] == newer.origin and ui.started == []
        assert not dead.exists() and older.token_path.exists() and newer.token_path.exists()


def test_stale_file_for_dead_port_is_removed_and_new_console_starts(ui):
    stale = ui.home/f'ui-session-{free_port()}.token'
    atomic_write(stale, secrets.token_urlsafe(32).encode())
    fresh(ui, ui.run(ui.home))
    assert not stale.exists()


def test_file_rewritten_during_a_refused_probe_is_kept(ui, monkeypatch):
    stale = ui.home/f'ui-session-{free_port()}.token'
    atomic_write(stale, secrets.token_urlsafe(32).encode())
    replacement = secrets.token_urlsafe(32)

    def refused(*args):
        atomic_write(stale, replacement.encode())  # A new console took the port meanwhile.
        raise ConnectionRefusedError
    monkeypatch.setattr(webapp, 'probe', refused)
    fresh(ui, ui.run(ui.home))
    assert stale.read_text() == replacement


IDENTITY = '{"service":"%s","version":"%s","home":"HOME","expires_in_seconds":%d}'


@pytest.mark.parametrize('status,ctype,body,redirect', [
    (401, 'application/json', '{"error":{"code":"unauthorized"}}', False),
    (200, 'application/json', IDENTITY % ('other', __version__, 3600), False),
    (200, 'application/json', IDENTITY % ('atm-console', __version__, 0), False),
    (200, 'text/plain', IDENTITY % ('atm-console', __version__, 3600), False),
    (200, 'application/json', '[]', False),
    (200, 'text/html', '<html>console</html>', False),
    (302, 'application/json', '{}', True),
], ids=['401', 'other-service', 'expired-identity', 'not-json-type', 'array', 'html', 'redirect'])
def test_foreign_listener_is_not_reused_and_its_file_is_kept(ui, status, ctype, body, redirect):
    with running(ui.home) as server:
        # Even the real token copied beside another listener must not reach it via that port.
        server.token_path.unlink()
        location = server.origin + '/api/console' if redirect else None
        with foreign(status, ctype, body.replace('HOME', str(server.home)), location) as other:
            path = ui.home/f'ui-session-{other.port}.token'
            atomic_write(path, server.token.encode())
            result = ui.run(ui.home)
            fresh(ui, result)
            assert result['url'] != f'http://localhost:{other.port}'
            assert path.read_text() == server.token
            assert other.seen and not bearer_sent(other.seen) and not leaked(server.token, other)


def test_perfect_shape_listener_without_the_token_never_receives_the_bearer(ui):
    with running(ui.home) as server:
        server.token_path.unlink()
        identity = {'service': 'atm-console', 'version': __version__, 'home': str(server.home), 'expires_in_seconds': 3600}

        def answer(headers):
            if 'X-ATM-Challenge' in headers:  # Right shape, but it cannot compute the proof.
                return 200, 'application/json', json.dumps({'service': 'atm-console', 'proof': secrets.token_hex(32)}), {}
            return 200, 'application/json', json.dumps(identity), {}
        with listener(answer) as other:
            path = ui.home/f'ui-session-{other.port}.token'
            atomic_write(path, server.token.encode())
            fresh(ui, ui.run(ui.home))
            assert other.seen and re.fullmatch('[0-9a-f]{64}', other.seen[0]['X-ATM-Challenge'])
            assert not bearer_sent(other.seen) and not leaked(server.token, other) and path.read_text() == server.token


def test_trickling_listener_cannot_hold_atm_ui(ui):
    token = secrets.token_urlsafe(32)
    with trickling() as other:
        path = ui.home/f'ui-session-{other.port}.token'
        atomic_write(path, token.encode())
        began = time.monotonic()
        fresh(ui, ui.run(ui.home))
        assert time.monotonic() - began < 3 and path.exists()
    received = b''.join(other.received)  # Read once it stopped, so every connection is counted.
    assert received and b'authorization' not in received.lower() and token.encode() not in received


def test_expired_console_is_not_reused(ui):
    with running(ui.home) as server:
        server.expires_at = time.monotonic() - 1
        fresh(ui, ui.run(ui.home))
        assert server.token_path.exists()


@pytest.mark.parametrize('remaining', [8 * 3600 + 120, 10 ** 9], ids=['beyond-8h', 'huge'])
def test_console_claiming_more_than_its_lifetime_is_not_reused(ui, remaining):
    with running(ui.home) as server:
        server.expires_at = time.monotonic() + remaining
        fresh(ui, ui.run(ui.home))
        assert server.token_path.exists() and not server.launch_codes


@pytest.mark.parametrize('version,reused', [(__version__, True), (__version__ + '.other', False)], ids=['same', 'other'])
def test_console_of_another_version_is_not_reused(ui, version, reused):
    token = secrets.token_urlsafe(32)
    identity = {'service': 'atm-console', 'version': version, 'home': str(ui.home), 'expires_in_seconds': 3600}
    ui.home.mkdir(mode=0o700)
    with impostor(token, identity) as other:
        path = ui.home/f'ui-session-{other.port}.token'
        atomic_write(path, token.encode())
        result = ui.run(ui.home, '--no-browser')
        assert result['reused'] is reused and len(ui.started) == (0 if reused else 1)
        assert bearer_sent(other.seen) and leaked(token, other) and path.exists()  # It proved the token; only the version differs.


@pytest.mark.parametrize('pad,length,reused', [(0, True, True), (20000, True, False), (20000, False, False)],
                         ids=['plain', 'padded', 'padded-without-length'])
def test_answer_beyond_a_few_kib_is_refused_before_the_bearer(ui, pad, length, reused):
    token = secrets.token_urlsafe(32)
    identity = {'service': 'atm-console', 'version': __version__, 'home': str(ui.home), 'expires_in_seconds': 3600}
    ui.home.mkdir(mode=0o700)
    # A valid proof either way; only its size differs, framed by Content-Length or by closing the connection.
    with impostor(token, identity, pad, length) as other:
        path = ui.home/f'ui-session-{other.port}.token'
        atomic_write(path, token.encode())
        result = ui.run(ui.home, '--no-browser')
        assert result['reused'] is reused and bearer_sent(other.seen) is reused and path.exists()
        assert leaked(token, other) is reused  # The value itself never reaches a refused listener.


@pytest.mark.parametrize('left,reused', [(15 * 60 - 5, False), (15 * 60 + 30, True)], ids=['short', 'enough'])
def test_console_is_reused_only_with_15_minutes_left(ui, left, reused):
    with running(ui.home) as server:
        server.expires_at = time.monotonic() + left
        result = ui.run(ui.home)
        assert result['reused'] is reused and ('15 minutes' in result['note']) is not reused
        if reused:
            assert ui.started == [] and result['url'] == server.origin and len(server.launch_codes) == 1
        else:
            fresh(ui, result)
            assert not server.launch_codes
        assert server.token_path.exists()


@pytest.mark.parametrize('extra', [(), ('--no-browser',)], ids=['browser', 'no-browser'])
def test_explicit_port_of_this_homes_expiring_console_is_named(ui, extra):
    with running(ui.home) as server:
        server.expires_at = time.monotonic() + 15 * 60 - 5
        error = ui.fail(ui.home, '--port', str(server.server_port), *extra)
        assert error['code'] == 'port_in_use' and server.origin in error['message'] and '15 minutes' in error['message']
        assert ui.started == [] and ui.opened == [] and not server.launch_codes and server.token_path.exists()


def test_console_that_issues_no_launch_code_is_replaced_and_said_so(ui):
    token = secrets.token_urlsafe(32)
    identity = {'service': 'atm-console', 'version': __version__, 'home': str(ui.home), 'expires_in_seconds': 3600}
    ui.home.mkdir(mode=0o700)
    with impostor(token, identity) as other:  # Proves the token and its identity, but its launch-code answer has no code.
        path = ui.home/f'ui-session-{other.port}.token'
        atomic_write(path, token.encode())
        result = ui.run(ui.home)
        fresh(ui, result)
        assert 'did not issue a launch code' in result['note'] and path.exists()
        assert [h.get('Authorization') for h in other.seen][-1] == 'Bearer ' + token  # It was asked, after the proof.
        error = ui.fail(ui.home, '--port', str(other.port))  # Its own port: named, not a generic port_in_use.
        assert error['code'] == 'port_in_use' and f'http://localhost:{other.port}' in error['message']
        assert 'launch code' in error['message'] and len(ui.started) == 1


@pytest.mark.parametrize('unsafe', ['symlink', 'mode', 'oversized', 'empty', 'hardlink'])
def test_unsafe_token_files_are_ignored_and_never_deleted(ui, tmp_path, monkeypatch, unsafe):
    dead = ui.home/f'ui-session-{free_port()}.token'
    if unsafe == 'oversized':  # Token characters past 256 bytes, with no length in the pattern: only the size bound is left.
        monkeypatch.setattr(webapp, 'TOKEN_VALUE', re.compile(r'[A-Za-z0-9_-]+'))
    with running(ui.home) as server:
        for path in (server.token_path, dead):
            value = server.token if path == server.token_path else secrets.token_urlsafe(32)
            path.unlink(missing_ok=True)
            if unsafe == 'symlink':
                target = tmp_path/(path.name + '.target'); atomic_write(target, value.encode()); path.symlink_to(target)
                if hasattr(os, 'lchmod'): os.lchmod(path, 0o600)  # Only the file-type check remains.
            elif unsafe == 'hardlink':
                atomic_write(path, value.encode()); os.link(path, tmp_path/(path.name + '.link'))
            else:
                atomic_write(path, {'mode': value, 'oversized': value + 'A' * 512, 'empty': ''}[unsafe].encode())
                if unsafe == 'mode': path.chmod(0o644)
        fresh(ui, ui.run(ui.home))
        assert server.token_path.is_symlink() == dead.is_symlink() == (unsafe == 'symlink')
        assert os.path.lexists(server.token_path) and os.path.lexists(dead)


def test_token_file_size_and_link_bounds_stand_on_their_own(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'TOKEN_VALUE', re.compile(r'[A-Za-z0-9_-]+'))  # Only the lstat checks remain.
    path = tmp_path/'ui-session-4242.token'
    atomic_write(path, b'A' * 256)
    assert webapp.read_token_file(path)[0] == 'A' * 256
    atomic_write(path, b'A' * 257)
    assert webapp.read_token_file(path) is None
    atomic_write(path, b'A' * 64)
    assert webapp.read_token_file(path)[0] == 'A' * 64
    os.link(path, tmp_path/'second-name')
    assert webapp.read_token_file(path) is None and webapp.read_token_file(tmp_path/'second-name') is None


@pytest.mark.parametrize('mode', [0o770, 0o702, 0o722], ids=['group-write', 'other-write', 'both'])
def test_home_writable_by_others_is_not_searched(ui, mode):
    with running(ui.home) as server:
        ui.home.chmod(mode)
        try:
            fresh(ui, ui.run(ui.home))
        finally:
            ui.home.chmod(0o700)
        assert server.token_path.exists() and not server.launch_codes


def test_home_owned_by_another_account_is_never_probed(ui, monkeypatch):
    calls, original = [], webapp.probe
    monkeypatch.setattr(webapp, 'probe', lambda *args: calls.append(args[0]) or original(*args))
    with running(ui.home) as server:
        assert webapp.running_console(ui.home)[0] == server.server_port and calls == [server.server_port]
        calls.clear(); home, real = ui.home.absolute(), os.lstat

        def lstat(path, *args, **kwargs):  # Only the home itself appears to belong to another uid.
            info = real(path, *args, **kwargs)
            if Path(path) != home:
                return info
            return os.stat_result(info[:4] + (info.st_uid + 1,) + info[5:10])
        with monkeypatch.context() as patched:
            patched.setattr(webapp.os, 'lstat', lstat)
            assert webapp.running_console(ui.home) is None
        assert calls == [] and server.token_path.exists() and not server.launch_codes


def test_explicit_different_port_starts_a_new_console(ui):
    port = free_port()
    with running(ui.home) as server:
        result = ui.run(ui.home, '--port', str(port))
        assert fresh(ui, result).server_port == port and server.token_path.exists()


def test_another_homes_console_is_not_reused(ui, tmp_path):
    with running(tmp_path/'other') as server:
        copied = ui.home/server.token_path.name
        atomic_write(copied, server.token.encode())
        result = ui.run(ui.home)
        fresh(ui, result)
        assert result['url'] != server.origin and copied.read_text() == server.token and server.token_path.exists()
        assert not server.launch_codes


def test_fresh_console_announces_reused_false_without_token(ui):
    result = ui.run(ui.home, '--no-browser')
    new = ui.started[0]
    assert result['reused'] is False and result['expires_after_hours'] == 8 and ui.opened == [] and new.codes == []
    assert result['session_token_file'] == str(new.token_path) and new.token not in json.dumps(result)
