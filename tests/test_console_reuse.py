"""`atm ui` reopens this home's live console; never a foreign listener or another home."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import socket
import threading
import time
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
            started.append(SimpleNamespace(origin=self.origin, token=self.token, token_path=self.token_path, server_port=self.server_port))
            raise KeyboardInterrupt
    monkeypatch.setattr(webapp, 'Console', Once)

    def run(home, *extra):
        code = main(['--home', str(home), 'ui', '--atm-executable', str(exe), *extra])
        out = capsys.readouterr()
        assert code == 0 and out.err == '', out
        result = json.loads(out.out)
        assert set(result) == KEYS and result['scope'] == 'loopback_only'
        return result
    return SimpleNamespace(run=run, opened=opened, started=started, home=tmp_path/'state')


@contextmanager
def running(home, **kw):
    server = Console(home, localhost=True, **kw)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True); thread.start()
    try:
        yield server
    finally:
        server.shutdown(); server.server_close(); thread.join(5)


@contextmanager
def foreign(status, ctype, body, location=None):
    class Other(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            raw = body.encode()
            self.send_response(status); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(raw)))
            if location: self.send_header('Location', location)
            self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Other)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown(); server.server_close(); thread.join(5)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


def fresh(ui, result):
    assert len(ui.started) == 1 and result['reused'] is False
    new = ui.started[0]
    assert result['url'] == new.origin and ui.opened == [new.origin + '/#token=' + new.token]
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
        assert ui.opened == ([] if '--no-browser' in extra else [server.origin + '/#token=' + server.token])
        assert server.token_path.read_bytes() == before
        with httpx.Client(base_url=server.origin, trust_env=False) as client:
            assert client.get('/api/overview', headers={'Authorization': 'Bearer ' + server.token}).status_code == 200


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
        with foreign(status, ctype, body.replace('HOME', str(server.home)), location) as port:
            other = ui.home/f'ui-session-{port}.token'
            atomic_write(other, server.token.encode())
            result = ui.run(ui.home)
            fresh(ui, result)
            assert result['url'] != f'http://localhost:{port}'
            assert other.read_text() == server.token


def test_expired_console_is_not_reused(ui):
    with running(ui.home) as server:
        server.expires_at = time.monotonic() - 1
        fresh(ui, ui.run(ui.home))
        assert server.token_path.exists()


@pytest.mark.parametrize('unsafe', ['symlink', 'mode', 'oversized', 'empty'])
def test_unsafe_token_files_are_ignored_and_never_deleted(ui, tmp_path, unsafe):
    dead = ui.home/f'ui-session-{free_port()}.token'
    with running(ui.home) as server:
        for path in (server.token_path, dead):
            value = server.token if path == server.token_path else secrets.token_urlsafe(32)
            path.unlink(missing_ok=True)
            if unsafe == 'symlink':
                target = tmp_path/(path.name + '.target'); atomic_write(target, value.encode()); path.symlink_to(target)
                if hasattr(os, 'lchmod'): os.lchmod(path, 0o600)  # Only the file-type check remains.
            else:
                atomic_write(path, {'mode': value, 'oversized': value + ' ' * 512, 'empty': ''}[unsafe].encode())
                if unsafe == 'mode': path.chmod(0o644)
        fresh(ui, ui.run(ui.home))
        assert server.token_path.is_symlink() == dead.is_symlink() == (unsafe == 'symlink')
        assert os.path.lexists(server.token_path) and os.path.lexists(dead)


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


def test_fresh_console_announces_reused_false_without_token(ui):
    result = ui.run(ui.home, '--no-browser')
    new = ui.started[0]
    assert result['reused'] is False and result['expires_after_hours'] == 8 and ui.opened == []
    assert result['session_token_file'] == str(new.token_path) and new.token not in json.dumps(result)
