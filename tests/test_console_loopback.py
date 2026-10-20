"""A localhost console holds [::1]:port beside 127.0.0.1:port: browsers try ::1 first for localhost."""
import errno
import http.client
import json
import socket
import threading
import time
import uuid

import pytest
from agent_tool_maker import webapp
from agent_tool_maker.cli import main
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.quickstart import scope_plan
from agent_tool_maker.quickstart_web import ApprovalWindow
from agent_tool_maker.secrets_provider import fingerprint
from agent_tool_maker.vault import Vault
from agent_tool_maker.webapp import Console


def require_ipv6_loopback():
    try:
        with socket.socket(socket.AF_INET6) as s:
            s.bind(('::1', 0))
    except OSError as error:
        pytest.fail(f'This host has no IPv6 loopback, so the [::1] hold cannot be exercised: {error}')


def request(address, server, method='GET', path='/api/console', headers=(), body=None):
    """One request over one loopback address, always with the console's own localhost Host."""
    connection = http.client.HTTPConnection(address, server.server_port, timeout=5)
    try:
        connection.request(method, path, body=body, headers={'Host': server.authority, **dict(headers)})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def refused(address, port):
    with socket.socket(socket.AF_INET6 if ':' in address else socket.AF_INET) as s:
        s.settimeout(2)
        return s.connect_ex((address, port)) == errno.ECONNREFUSED


def squat_ipv6():
    """[::1]:P held by another program while 127.0.0.1:P is free."""
    with socket.socket() as ipv4:
        ipv4.bind(('127.0.0.1', 0))
        port = ipv4.getsockname()[1]
    squatter = socket.socket(socket.AF_INET6)
    squatter.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    squatter.bind(('::1', port)); squatter.listen()
    return port, squatter


def serving(server):
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
    thread.start()
    return thread


def test_localhost_console_answers_on_both_loopbacks_with_one_token_and_stops_both(tmp_path, monkeypatch):
    require_ipv6_loopback()
    loops = []
    original = webapp.Loopback6.serve_forever
    def recorded(self, *args, **kwargs):
        loops.append('start'); original(self, *args, **kwargs); loops.append('stop')
    monkeypatch.setattr(webapp.Loopback6, 'serve_forever', recorded)
    server = Console(tmp_path/'state', localhost=True)
    port = server.server_port
    thread = serving(server)
    try:
        assert server.authority == f'localhost:{port}' and server.loopback6.server_address[:2] == ('::1', port)
        assert server.loopback6.socket.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 1
        bearer = {'Authorization': 'Bearer ' + server.token}
        for address in ('127.0.0.1', '::1'):
            status, raw = request(address, server, headers=bearer)
            assert status == 200 and json.loads(raw)['service'] == 'atm-console'
            assert request(address, server, headers={'Authorization': 'Bearer wrong'})[0] == 401
            assert request(address, server, headers={**bearer, 'Host': f'127.0.0.1:{port}'})[0] == 403
    finally:
        server.shutdown()
        # shutdown() returns only once the [::1] loop has stopped too (socketserver's own flag).
        twin_stopped = server.loopback6._BaseServer__is_shut_down.is_set()
        thread.join(5); server.server_close()
    assert twin_stopped and not thread.is_alive() and loops == ['start', 'stop']
    assert server.socket.fileno() == server.loopback6.socket.fileno() == -1
    assert refused('127.0.0.1', port) and refused('::1', port)


def test_squatter_on_the_ipv6_twin_moves_the_console_to_a_port_it_holds_on_both(tmp_path, monkeypatch):
    require_ipv6_loopback()
    taken, squatter = squat_ipv6()
    tried, original = [], Console.server_bind
    def ephemeral_pick_lands_on_the_squatted_port(self):
        if not tried:
            self.server_address = ('127.0.0.1', taken)
        tried.append(self.server_address); original(self)
    monkeypatch.setattr(Console, 'server_bind', ephemeral_pick_lands_on_the_squatted_port)
    try:
        server = Console(tmp_path/'state', localhost=True)
        try:
            port = server.server_port
            assert tried == [('127.0.0.1', taken), ('127.0.0.1', 0)] and port != taken
            assert server.loopback6.server_address[:2] == ('::1', port) and server.authority == f'localhost:{port}'
            assert [p.name for p in (tmp_path/'state').glob('ui-session-*.token')] == [f'ui-session-{port}.token']
            assert squatter.getsockname()[1] == taken
            with socket.socket() as again:
                again.bind(('127.0.0.1', taken))  # The abandoned IPv4 attempt was closed.
        finally:
            server.server_close()
    finally:
        squatter.close()


def test_explicit_port_with_a_squatted_ipv6_twin_fails_clearly(tmp_path, capsys):
    require_ipv6_loopback()
    taken, squatter = squat_ipv6()
    exe = tmp_path/'atm'; exe.write_text('#!/bin/sh\nexit 0\n'); exe.chmod(0o700)
    try:
        with pytest.raises(RouterError) as error:
            Console(tmp_path/'state', port=taken, localhost=True)
        assert error.value.code == 'port_in_use' and f'[::1]:{taken}' in str(error.value)
        with socket.socket() as again:
            again.bind(('127.0.0.1', taken))
        code = main(['--home', str(tmp_path/'state'), 'ui', '--no-browser', '--port', str(taken), '--atm-executable', str(exe)])
        assert code == 2 and json.loads(capsys.readouterr().out)['error']['code'] == 'port_in_use'
        assert not list((tmp_path/'state').glob('ui-session-*.token'))
    finally:
        squatter.close()


@pytest.mark.parametrize('missing', [errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT], ids=['no-address', 'no-family'])
def test_without_ipv6_loopback_the_console_stays_ipv4_only(tmp_path, monkeypatch, missing):
    def unavailable(primary):
        raise OSError(missing, 'IPv6 loopback unavailable in this test')
    monkeypatch.setattr(webapp, 'Loopback6', unavailable)
    server = Console(tmp_path/'state', localhost=True)
    thread = serving(server)
    try:
        assert server.loopback6 is None
        assert request('127.0.0.1', server, headers={'Authorization': 'Bearer ' + server.token})[0] == 200
    finally:
        server.shutdown(); thread.join(5); server.server_close()


def test_other_ipv6_bind_failures_are_not_silently_ignored(tmp_path, monkeypatch):
    def denied(primary):
        raise OSError(errno.EACCES, 'denied in this test')
    monkeypatch.setattr(webapp, 'Loopback6', denied)
    with pytest.raises(OSError) as error:
        Console(tmp_path/'state', localhost=True)
    assert error.value.errno == errno.EACCES


def test_ip_literal_console_does_not_take_ipv6(tmp_path):
    server = Console(tmp_path/'state')
    try:
        assert server.authority == f'127.0.0.1:{server.server_port}' and server.loopback6 is None
    finally:
        server.server_close()


def test_approval_window_holds_ipv6_twin_with_its_own_handler(tmp_path):
    require_ipv6_loopback()
    root = tmp_path.resolve(); r = Router(root/'s')
    r.vault = Vault(r.state, password='fake-loopback-password'); r.vault.init('passphrase'); r.vault.put('fal', 'fake-loopback-key')
    workspace = root/'project'; workspace.mkdir()
    plan = scope_plan(r.state, workspace, ['fal']); identifier = uuid.uuid4().hex
    r.state.set_setting('desktop-request:' + identifier, {'id': identifier, **plan, 'status': 'needs_unlock',
                        'created_at': time.time(), 'approval_sha256': fingerprint(plan)})
    window = ApprovalWindow(r.state.home, identifier, localhost=True)
    thread = serving(window)
    try:
        assert window.loopback6.server_address[:2] == ('::1', window.server_port)
        for address in ('127.0.0.1', '::1'):
            status, raw = request(address, window, path='/')
            assert status == 200 and b'/assets/quickstart.js' in raw
            status, raw = request(address, window, path='/api/desktop', headers={'Authorization': 'Bearer ' + window.token})
            assert status == 200 and json.loads(raw)['plan']['workspace'] == str(workspace)
    finally:
        window.shutdown(); thread.join(5); window.server_close(); r.close()
    assert refused('::1', window.server_port)
