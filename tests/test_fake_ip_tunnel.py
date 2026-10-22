"""Owner opt-in Fake-IP proxy tunnel (198.18.0.0/15) for the resolved-address check.

Fake resolvers and httpx MockTransports only: no DNS query, no provider, no OAuth host is contacted.
The setting is off by default and nothing changes while it is off.
"""
from functools import partialmethod
import json
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from agent_tool_maker import management as mg
from agent_tool_maker import oauth as oauth_module
from agent_tool_maker import oauth_web
from agent_tool_maker.cli import parser
from agent_tool_maker.demo import FixtureProvider, fixture_resolver
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.health import doctor
from agent_tool_maker.network import (FAKE_IP, Network, fake_ip_answer, fake_ip_tunnel, network_settings,
                                      numeric_host, plain_global, public_address, set_fake_ip_tunnel)
from agent_tool_maker.oauth import ENDPOINTS, ISSUER, OAuth, PROTECTED_METADATA, SERVER_METADATA
from agent_tool_maker.oauth_cli import tick
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault
from agent_tool_maker.webapp import Console

from test_oauth_refresh import Keyring, Provider, begin

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://assets.example.test/file.png'


def answers(*ips):
    """A fake getaddrinfo answering every name with these addresses; never touches the system resolver."""
    def resolve(host, port, *args, **kwargs):
        return [(socket.AF_INET6 if ':' in ip else socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port)) for ip in ips]
    return resolve


def outcome(url, resolver, *, on):
    try:
        public_address(url, resolver, fake_ip=on)
        return 'accepted', None
    except RouterError as error:
        return error.code, error.hint


# ------------------------------------------------------------------ address matrix

FAKE = ['198.18.0.0', '198.18.0.1', '198.18.0.138', '198.18.0.139', '198.19.255.255']
REFUSED = ['127.0.0.1', '10.0.0.1', '172.16.0.1', '192.168.1.1', '169.254.169.254', '100.64.0.1', '100.127.255.254',
           '0.0.0.0', '240.0.0.1', '255.255.255.255', '::1', '::', 'fd00::1', 'fc00::1', 'fe80::1',
           '::ffff:198.18.0.1', '::ffff:198.19.255.255', '::ffff:10.0.0.1', '2002:c612:1::1']
# Outside 198.18.0.0/15 and plain global unicast: the setting never changes how they are treated.
OUTSIDE = ['93.184.216.34', '198.17.255.255', '198.20.0.0', '198.20.0.1', '2606:4700::1', '64:ff9b::5db8:d822']
# Python's is_global admits these, so the unchanged check with the setting off accepts them alone. With the setting
# on, every answer beside a Fake-IP one must be plain global unicast: these refuse the set, and never get the hint.
SPECIAL = ['224.0.0.1', 'ff02::1', '::198.18.0.1', '::127.0.0.1', '::10.0.0.1', '64:ff9b::c612:1', '64:ff9b::7f00:1',
           '64:ff9b::a00:1', '64:ff9b::e000:1', '::ffff:0:a00:1', 'fec0::1', '::ffff:93.184.216.34']


@pytest.mark.parametrize('ip', FAKE)
def test_fake_ip_answers_need_the_setting(ip):
    assert outcome(URL, answers(ip), on=False) == ('unsafe_download', 'fake_ip_tunnel')
    assert outcome(URL, answers(ip), on=True) == ('accepted', None)


@pytest.mark.parametrize('ip', REFUSED)
def test_private_local_and_special_answers_stay_refused_when_on(ip):
    for on in (False, True):
        assert outcome(URL, answers(ip), on=on) == ('unsafe_download', None), (ip, on)


@pytest.mark.parametrize('ip', OUTSIDE)
def test_the_setting_never_changes_an_address_outside_the_range(ip):
    assert outcome(URL, answers(ip), on=True) == outcome(URL, answers(ip), on=False) == ('accepted', None)


@pytest.mark.parametrize('ip', SPECIAL)
def test_with_the_setting_on_only_plain_unicast_stands_beside_fake_ip(ip):
    assert outcome(URL, answers(ip), on=False) == ('accepted', None)  # Unchanged with the setting off.
    assert outcome(URL, answers(ip), on=True) == ('unsafe_download', None)
    for ips in [('198.18.0.5', ip), (ip, '198.18.0.5')]:
        assert outcome(URL, answers(*ips), on=False) == ('unsafe_download', None), ips  # No switch is offered.
        assert outcome(URL, answers(*ips), on=True) == ('unsafe_download', None), ips


def test_range_is_plain_ipv4_198_18_slash_15():
    import ipaddress
    assert str(FAKE_IP) == '198.18.0.0/15'
    assert fake_ip_answer(ipaddress.ip_address('198.19.255.255'))
    for ip in ['198.17.255.255', '198.20.0.0', '::ffff:198.18.0.1', '::198.18.0.1', '64:ff9b::c612:1', '2002:c612:1::1']:
        assert not fake_ip_answer(ipaddress.ip_address(ip)), ip


def test_plain_global_is_stricter_than_is_global():
    import ipaddress
    for ip in OUTSIDE:
        assert plain_global(ipaddress.ip_address(ip)), ip
    for ip in SPECIAL + REFUSED + FAKE:
        assert not plain_global(ipaddress.ip_address(ip)), ip


@pytest.mark.parametrize('ips,off,on', [
    (('198.18.0.1', '10.0.0.1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.1', '127.0.0.1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.1', '::ffff:198.18.0.1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.1', 'fe80::1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', '224.0.0.1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', 'ff02::1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', '::127.0.0.1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', '::10.0.0.1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', '::198.18.0.1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', '64:ff9b::7f00:1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', '64:ff9b::a00:1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', '::ffff:0:a00:1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', 'fec0::1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.5', '93.184.216.34', '224.0.0.1'), ('unsafe_download', None), ('unsafe_download', None)),
    (('198.18.0.1', '93.184.216.34'), ('unsafe_download', 'fake_ip_tunnel'), ('accepted', None)),
    (('198.18.0.1', '2606:4700::1'), ('unsafe_download', 'fake_ip_tunnel'), ('accepted', None)),
    (('198.18.0.1', '64:ff9b::5db8:d822'), ('unsafe_download', 'fake_ip_tunnel'), ('accepted', None)),
    (('198.18.0.1', '198.19.0.7'), ('unsafe_download', 'fake_ip_tunnel'), ('accepted', None)),
])
def test_one_bad_answer_refuses_the_whole_set(ips, off, on):
    assert outcome(URL, answers(*ips), on=False) == off
    assert outcome(URL, answers(*ips), on=True) == on


@pytest.mark.parametrize('url', ['https://198.18.0.1/x', 'https://198.19.255.255/x', 'https://[::ffff:198.18.0.1]/x',
                                 'https://3323068417/x', 'https://0xc6120001/x', 'https://198.18.1/x', 'https://198.018.0.1/x',
                                 'https://198.18.0.1./x', 'https://10.0.0.08/x', 'https://1.2.3.0x/x'])
def test_an_address_literal_never_uses_the_exemption(url):
    # The fake resolver answers like the system resolver would for the numeral: 198.18.0.1.
    for on in (False, True):
        assert outcome(url, answers('198.18.0.1'), on=on) == ('unsafe_download', None), (url, on)


def test_numeric_host_is_offline_and_exact():
    for host in ['198.18.0.1', '3323068417', '0xc6120001', '198.18.1', '198.018.0.1', '198.18.0.1.', '::ffff:198.18.0.1',
                 '10.0.0.08', '1.2.3.0x', 'example.123']:
        assert numeric_host(host), host
    for host in ['mcp.higgsfield.ai', 'clerk.higgsfield.ai', 'assets.example.test', 'mcp.higgsfield.ai.', '198-18-0-1.example',
                 '123.example', '0x1.example', 'example.0xyz']:
        assert not numeric_host(host), host


def test_numeric_host_does_not_depend_on_the_platform_parser(monkeypatch):
    # glibc refuses notations macOS accepts (198.018.0.1); a numeric last label is a literal either way.
    def refuse(*args, **kwargs):
        raise OSError('fixture: strict platform')
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)
    monkeypatch.setattr(socket, 'inet_aton', refuse)
    for host in ['198.018.0.1', '10.0.0.08', '3323068417', '0xc6120001', '198.18.0.1.']:
        assert numeric_host(host), host
    for host in ['mcp.higgsfield.ai', '198-18-0-1.example']:
        assert not numeric_host(host), host


def test_empty_answer_and_dns_failure_are_unchanged():
    assert outcome(URL, lambda *a, **k: [], on=True) == ('unsafe_download', None)
    def broken(*a, **k):
        raise socket.gaierror('fixture')
    assert outcome(URL, broken, on=True) == ('dns_error', None)


def test_url_shape_checks_do_not_move():
    for url in ['http://mcp.higgsfield.ai/', 'https://mcp.higgsfield.ai:8443/', 'https://u:p@mcp.higgsfield.ai/', 'https://mcp.higgsfield.ai/#f']:
        assert outcome(url, answers('198.18.0.138'), on=True) == ('unsafe_url', None), url


def test_hint_is_additive_to_as_dict():
    plain = RouterError('unsafe_download', 'x')
    assert plain.as_dict() == {'code': 'unsafe_download', 'message': 'x', 'outcome_uncertain': False}
    hinted = RouterError('unsafe_download', 'x', hint='fake_ip_tunnel')
    assert hinted.as_dict() == {**plain.as_dict(), 'hint': 'fake_ip_tunnel'}


# ------------------------------------------------------------------ the setting

def test_setting_is_off_by_default_and_only_exact_true_is_on(tmp_path):
    state = State(tmp_path / 'state')
    assert network_settings(state) == {'fake_ip_tunnel': False, 'changed_at': None}
    for value in ['true', 1, {'enabled': True}, None, [True]]:
        state.set_setting('network', {'fake_ip_tunnel': value})
        assert fake_ip_tunnel(state) is False, value
    state.set_setting('network', ['fake_ip_tunnel'])
    assert fake_ip_tunnel(state) is False


def test_a_row_nested_too_deep_reads_as_off_and_the_owner_can_replace_it(router):
    import sqlite3
    with sqlite3.connect(router.state.path) as db:
        db.execute("INSERT OR REPLACE INTO settings VALUES ('network', ?)", ('[' * 100000 + ']' * 100000,))
    assert network_settings(router.state) == {'fake_ip_tunnel': False, 'changed_at': None}
    assert mg.overview(router)['network']['fake_ip_tunnel'] is False
    assert set_fake_ip_tunnel(router.state, True, expected=False)['action'] == 'enable'
    assert fake_ip_tunnel(router.state) is True


def test_a_row_that_is_not_json_reads_as_off_and_the_owner_can_replace_it(router, workspace):
    import sqlite3
    with sqlite3.connect(router.state.path) as db:
        db.execute("INSERT OR REPLACE INTO settings VALUES ('network', '{not json')")
    assert network_settings(router.state) == {'fake_ip_tunnel': False, 'changed_at': None}
    assert mg.overview(router)['network']['fake_ip_tunnel'] is False
    assert doctor(router, tool_ids=['ffmpeg.probe'])['network']['fake_ip_tunnel'] is False
    # Every call site still refuses with a RouterError (not a crash), with the hint, before sending anything.
    with pytest.raises(RouterError) as caught:
        public_address(URL, answers('198.18.0.3'), fake_ip=fake_ip_tunnel(router.state))
    assert caught.value.hint == 'fake_ip_tunnel'
    router.net = Network(httpx.MockTransport(FixtureProvider()), asset_resolver('198.18.0.20'))
    job = router.run('fal.generate', {'endpoint': 'fal-ai/flux/schnell', 'arguments': {'prompt': 'x'}}, workspace, allow_paid=True)
    assert router.refresh(job['id'])['data']['error']['hint'] == 'fake_ip_tunnel'
    # The owner's switch overwrites the row.
    assert set_fake_ip_tunnel(router.state, True, expected=False)['action'] == 'enable'
    assert fake_ip_tunnel(router.state) is True


def test_oauth_refresh_with_a_row_that_is_not_json_fails_cleanly(tunnel):
    import sqlite3
    manager, provider, now = tunnel
    now[0], provider.expiry = time.time(), 60
    keep_connected(manager)
    with sqlite3.connect(manager.state.path) as db:
        db.execute("INSERT OR REPLACE INTO settings VALUES ('network', 'not json')")
    before = len(provider.requests)
    worker = SimpleNamespace(state=State(manager.state.home), vault=manager.vault, net=manager.net)
    result = tick(worker)
    assert result['action'] == 'paused' and result['error']['code'] == 'oauth_dns_policy', result
    assert len(provider.requests) == before
    status = manager.status()  # Recorded as a failed refresh, not left 'refreshing' by a crash.
    assert status['status'] == 'needs_login' and status['last_error'] == 'oauth_dns_policy'


def test_set_compares_and_writes_once(tmp_path):
    state = State(tmp_path / 'state')
    first = set_fake_ip_tunnel(state, True, expected=False)
    assert first['fake_ip_tunnel'] is True and first['previous'] is False and first['action'] == 'enable'
    assert isinstance(first['changed_at'], float)
    # A second process (a separate State) reads it without any restart.
    assert fake_ip_tunnel(State(tmp_path / 'state')) is True
    again = set_fake_ip_tunnel(state, True)
    assert again['action'] == 'unchanged' and again['changed_at'] == first['changed_at']
    with pytest.raises(RouterError) as caught:
        set_fake_ip_tunnel(state, False, expected=False)
    assert caught.value.code == 'state_changed' and fake_ip_tunnel(state) is True
    for bad in [('yes', None), (1, None), (True, 'no')]:
        with pytest.raises(RouterError):
            set_fake_ip_tunnel(state, bad[0], expected=bad[1])
    assert set_fake_ip_tunnel(state, False)['action'] == 'disable' and fake_ip_tunnel(state) is False


def test_each_change_is_an_event_without_identity(tmp_path):
    state = State(tmp_path / 'state')
    def events():
        with state.db() as db:
            return [tuple(row) for row in db.execute("SELECT job_id, kind FROM events WHERE kind LIKE 'network.%' ORDER BY seq")]
    set_fake_ip_tunnel(state, True, expected=False)
    set_fake_ip_tunnel(state, True)  # Unchanged: no event.
    with pytest.raises(RouterError):
        set_fake_ip_tunnel(state, False, expected=False)  # Refused: no event.
    set_fake_ip_tunnel(state, False, expected=True)
    assert events() == [(None, 'network.fake_ip_tunnel.enabled'), (None, 'network.fake_ip_tunnel.disabled')]


def test_doctor_and_overview_show_it_read_only(router):
    assert doctor(router, tool_ids=['ffmpeg.probe'])['network'] == {'fake_ip_tunnel': False, 'write_path': 'console_only'}
    assert mg.overview(router)['network'] == {'fake_ip_tunnel': False, 'changed_at': None}
    set_fake_ip_tunnel(router.state, True)
    assert doctor(router, tool_ids=['ffmpeg.probe'])['network']['fake_ip_tunnel'] is True
    assert mg.overview(router)['network']['fake_ip_tunnel'] is True


def walk(p):
    import argparse
    for action in p._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                yield name, child
                yield from walk(child)


def test_no_cli_command_can_write_the_setting():
    commands = dict(walk(parser()))
    assert not [name for name in commands if any(word in name for word in ('network', 'fake', 'proxy', 'tunnel', 'dns', 'setting'))]
    options = [o for _, p in [('atm', parser()), *commands.items()] for a in p._actions for o in a.option_strings]
    assert '--allow-network' in options  # `atm verify` consent flag, unrelated to the address check.
    assert not [o for o in options if any(word in o for word in ('fake', 'proxy', 'tunnel', 'trust-env', 'dns', '198'))]
    # The only writer outside network.py is the console endpoint.
    writers = sorted(path.name for path in (ROOT / 'src/agent_tool_maker').glob('*.py') if 'set_fake_ip_tunnel' in path.read_text())
    assert writers == ['network.py', 'webapp.py'], writers
    assert '"network"' not in (ROOT / 'src/agent_tool_maker/sync.py').read_text()


def test_atm_doctor_prints_the_read_only_line(tmp_path):
    home = tmp_path / 'state'
    run = lambda *args: subprocess.run([sys.executable, '-m', 'agent_tool_maker', '--home', str(home), *args],
                                       capture_output=True, text=True, timeout=60)
    assert run('init').returncode == 0
    set_fake_ip_tunnel(State(home), True)
    result = run('doctor', '--tool', 'ffmpeg.probe')
    assert json.loads(result.stdout)['network'] == {'fake_ip_tunnel': True, 'write_path': 'console_only'}


# ------------------------------------------------------------------ OAuth: discovery, login and background refresh

def higgsfield_fake_ip(host, port, *args, **kwargs):
    """What Shadowrocket's Fake-IP DNS answers on the owner's Mac."""
    ip = {'mcp.higgsfield.ai': '198.18.0.138', 'clerk.higgsfield.ai': '198.18.0.139'}[host]
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]


@pytest.fixture
def tunnel(tmp_path):
    state = State(tmp_path / 'state')
    vault = Vault(state, keyring_backend=Keyring())
    vault.init('keyring')
    provider = Provider()
    now = [1800000000.]
    net = Network(httpx.MockTransport(provider), higgsfield_fake_ip)
    manager = OAuth(state, vault, net, clock=lambda: now[0])
    yield manager, provider, now
    net.close()


def test_off_oauth_refuses_with_the_hint_and_sends_nothing(tunnel):
    manager, provider, _ = tunnel
    with pytest.raises(RouterError) as caught:
        manager.discovery()
    assert caught.value.code == 'oauth_dns_policy' and caught.value.hint == 'fake_ip_tunnel' and not caught.value.uncertain
    assert caught.value.as_dict()['hint'] == 'fake_ip_tunnel'
    assert '198.18' not in json.dumps(caught.value.as_dict())  # No resolved address beyond what was already shown.
    with pytest.raises(RouterError) as caught:
        begin(manager)
    assert caught.value.code == 'oauth_dns_policy' and caught.value.hint == 'fake_ip_tunnel'
    assert provider.requests == []
    status = manager.status()
    assert status['status'] == 'needs_login' and status['last_error'] == 'oauth_dns_policy'
    assert status['last_error_hint'] == 'fake_ip_tunnel'


def test_on_oauth_login_is_sent_and_succeeds(tunnel):
    manager, provider, _ = tunnel
    set_fake_ip_tunnel(State(manager.state.home), True)  # The console's process, not this object: read at check time.
    server, result, query = begin(manager)
    try:
        assert result['status'] == 'pending' and result['browser_opened'] is True
        assert [str(r.url) for r in provider.requests] == [PROTECTED_METADATA, SERVER_METADATA, ENDPOINTS['registration_endpoint']]
        ready = manager.callback(server.claim, {'state': query['state'], 'code': 'FIXTURE_CODE', 'iss': ISSUER})
        assert ready['status'] == 'ready' and 'last_error_hint' not in ready
        assert str(provider.requests[-1].url) == ENDPOINTS['token_endpoint']
    finally:
        server.server_close()


def test_a_later_login_clears_an_old_hint(tunnel):
    manager, provider, _ = tunnel
    with pytest.raises(RouterError):
        begin(manager)
    assert manager.status()['last_error_hint'] == 'fake_ip_tunnel'
    set_fake_ip_tunnel(manager.state, True)
    server, result, query = begin(manager)
    try:
        assert 'last_error_hint' not in manager.status()
        manager.callback(server.claim, {'state': query['state'], 'iss': ISSUER, 'error': 'access_denied'})
        assert manager.status()['status'] == 'denied' and 'last_error_hint' not in manager.status()
    finally:
        server.server_close()


def keep_connected(manager):
    set_fake_ip_tunnel(manager.state, True)
    server, _, query = begin(manager, keep_login=True)
    try:
        manager.callback(server.claim, {'state': query['state'], 'code': 'FIXTURE_CODE', 'iss': ISSUER})
    finally:
        server.server_close()
    assert manager.status()['keep_login'] is True


def test_background_refresh_reads_the_setting_from_state(tunnel):
    manager, provider, now = tunnel
    # The worker's tick uses the real clock: tokens that are always within the refresh margin are always due.
    now[0], provider.expiry = time.time(), 60
    keep_connected(manager)
    # The launchd worker is its own process: its own State object, the same file.
    worker = SimpleNamespace(state=State(manager.state.home), vault=manager.vault, net=manager.net)
    before = len(provider.requests)
    assert tick(worker)['action'] == 'refreshed'
    assert [str(r.url) for r in provider.requests[before:]] == [ENDPOINTS['token_endpoint']]
    # Off again (from the console): the next due refresh stops before sending anything.
    set_fake_ip_tunnel(State(manager.state.home), False)
    before = len(provider.requests)
    result = tick(worker)
    assert result['action'] == 'paused' and result['error']['code'] == 'oauth_dns_policy'
    assert result['error']['hint'] == 'fake_ip_tunnel' and result['last_error_hint'] == 'fake_ip_tunnel'
    assert len(provider.requests) == before


# ------------------------------------------------------------------ MCP bridge, downloads, recipe and REST origins

def test_mcp_bridge_exchange_honours_the_setting(router, workspace):
    from agent_tool_maker.mcp_bridge import bind_server
    from test_mcp_bridge import INIT, TOOLS
    calls = []
    bind_server(router.state, 'figma', {'transport': 'http', 'url': 'https://mcp.example.com/mcp', 'allow_tools': ['read']})
    def handler(req):
        if req.method == 'DELETE':
            return httpx.Response(204)
        q = json.loads(req.content); calls.append(q['method'])
        if q['method'] == 'notifications/initialized':
            return httpx.Response(202)
        value = INIT if q['method'] == 'initialize' else {'tools': TOOLS} if q['method'] == 'tools/list' else {'content': [{'type': 'text', 'text': 'ok'}]}
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': q['id'], 'result': value})
    router.net.client = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
    router.net.resolver = answers('198.18.0.40')
    run = lambda key: router.run('figma.mcp_batch', {'calls': [{'name': 'read', 'arguments': {}}]}, workspace, allow_paid=True,
                                 grants=['external_write', 'execute_code'], request_key=key)
    off = run('off')
    assert off['status'] == 'failed' and off['data']['error']['code'] == 'unsafe_download'
    assert off['data']['error']['hint'] == 'fake_ip_tunnel' and calls == []
    set_fake_ip_tunnel(router.state, True)
    assert run('on')['status'] == 'completed' and calls[0] == 'initialize'
    router.net.resolver = answers('198.18.0.40', '10.0.0.1')
    mixed = run('mixed')
    assert mixed['status'] == 'failed' and 'hint' not in mixed['data']['error']


def asset_resolver(ip):
    def resolve(host, port, *args, **kwargs):
        return answers(ip)(host, port) if host == 'assets.example.test' else fixture_resolver()
    return resolve


def test_artifact_download_honours_the_setting(router, workspace):
    seen = []
    fixture = FixtureProvider()
    def handler(r):
        seen.append(r.url.host)
        return fixture(r)
    router.net = Network(httpx.MockTransport(handler), asset_resolver('198.18.0.20'))
    job = router.run('fal.generate', {'endpoint': 'fal-ai/flux/schnell', 'arguments': {'prompt': 'x'}}, workspace, allow_paid=True)
    failed = router.refresh(job['id'])
    assert failed['status'] == 'download_failed' and failed['data']['error']['code'] == 'unsafe_download'
    assert failed['data']['error']['hint'] == 'fake_ip_tunnel' and 'assets.example.test' not in seen
    row = next(j for j in mg.recent_jobs(router)['jobs'] if j['id'] == job['id'])
    assert row['error_hint'] == 'fake_ip_tunnel'
    assert '198.18' not in json.dumps(mg.recent_jobs(router)) and 'assets.example.test' not in json.dumps(mg.recent_jobs(router))
    set_fake_ip_tunnel(router.state, True)
    done = router.refresh(job['id'])  # The documented retry: refresh the job; generation is not repeated.
    assert done['status'] == 'completed' and 'assets.example.test' in seen
    assert 'error_hint' not in next(j for j in mg.recent_jobs(router)['jobs'] if j['id'] == job['id'])


def test_every_redirect_hop_is_checked_even_when_on():
    def resolver(host, port, *args, **kwargs):
        return answers({'public.test': '198.18.0.9', 'internal.test': '10.0.0.1', 'next.test': '198.18.0.10'}[host])(host, port)
    hops = []
    def handler(r):
        hops.append(r.url.host)
        if r.url.host == 'public.test':
            return httpx.Response(302, headers={'location': 'https://internal.test/secret'})
        return httpx.Response(200, content=b'never')
    n = Network(httpx.MockTransport(handler), resolver)
    try:
        with pytest.raises(RouterError) as caught:
            n.download('https://public.test/file', fake_ip=lambda: True)
        assert caught.value.code == 'unsafe_download' and caught.value.hint is None and hops == ['public.test']
        with pytest.raises(RouterError) as caught:
            n.download('https://public.test/file')
        assert caught.value.hint == 'fake_ip_tunnel' and hops == ['public.test']
    finally:
        n.close()
    n = Network(httpx.MockTransport(lambda r: httpx.Response(302, headers={'location': 'https://next.test/f'}) if r.url.host == 'public.test'
                                    else httpx.Response(200, content=b'ok', headers={'content-type': 'image/png'})), resolver)
    try:
        assert n.download('https://public.test/file', fake_ip=lambda: True) == (b'ok', 'image/png')
    finally:
        n.close()


def test_each_redirect_hop_reads_the_setting_again(router, workspace):
    """Turned off between two hops: the next hop is checked with the setting off, so it is refused."""
    fixture = FixtureProvider()
    def resolver(host, port, *args, **kwargs):
        return answers('198.18.0.21')(host, port) if host.endswith('example.test') else fixture_resolver()
    hops = []
    def handler(r):
        if r.url.host == 'assets.example.test':
            hops.append(r.url.host)
            set_fake_ip_tunnel(State(router.state.home), False)  # The owner's console, meanwhile.
            return httpx.Response(302, headers={'location': 'https://cdn.example.test/image.png'})
        if r.url.host == 'cdn.example.test':
            hops.append(r.url.host)
            return httpx.Response(200, content=b'never', headers={'content-type': 'image/png'})
        return fixture(r)
    router.net = Network(httpx.MockTransport(handler), resolver)
    set_fake_ip_tunnel(router.state, True)
    job = router.run('fal.generate', {'endpoint': 'fal-ai/flux/schnell', 'arguments': {'prompt': 'x'}}, workspace, allow_paid=True)
    failed = router.refresh(job['id'])
    assert hops == ['assets.example.test'], hops
    assert failed['status'] == 'download_failed' and failed['data']['error']['code'] == 'unsafe_download'
    assert failed['data']['error']['hint'] == 'fake_ip_tunnel'


def test_recipe_origins_honour_the_setting(router):
    from agent_tool_maker.web_recipe import restrict_context
    from test_web_recipe_v06 import recipe_tool
    class Context:
        routed = False
        def route(self, pattern, handler): self.routed = True
        def route_web_socket(self, pattern, handler): pass
    router.net.resolver = answers('198.18.0.77')
    context = Context()
    with pytest.raises(RouterError) as caught:
        restrict_context(context, router, recipe_tool()['recipe'])
    assert caught.value.code == 'unsafe_download' and caught.value.hint == 'fake_ip_tunnel' and not context.routed
    set_fake_ip_tunnel(router.state, True)
    assert restrict_context(context, router, recipe_tool()['recipe']) == [] and context.routed
    router.net.resolver = answers('198.18.0.77', '192.168.1.1')
    with pytest.raises(RouterError) as caught:
        restrict_context(Context(), router, recipe_tool()['recipe'])
    assert caught.value.hint is None


def test_owner_configured_rest_origins_honour_the_setting(router, workspace):
    from test_v02_actions import REST, prepare
    row = next(r for r in REST if r['request'].get('origin_setting') and not r['request'].get('local') and r['provider'] != 'shopify_admin')
    prepare(router, workspace, row)
    seen = []
    router.net.client.close()
    router.net.client = httpx.Client(transport=httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(200, json={'ok': True, 'data': {'id': 'f'}, 'items': []})), trust_env=False)
    router.net.resolver = answers('198.18.0.55')
    run = lambda key: router.run(row['id'], row['example'], workspace, allow_paid=True, grants=['external_write', 'production', 'execute_code'], request_key=key)
    off = run('off')
    assert off['status'] == 'failed' and off['data']['error']['code'] == 'unsafe_download'
    assert off['data']['error']['hint'] == 'fake_ip_tunnel' and seen == []
    set_fake_ip_tunnel(router.state, True)
    assert run('on')['status'] == 'completed' and len(seen) == 1


def test_fixed_host_rest_tools_never_resolve(router, workspace):
    router.net.resolver = lambda *a, **k: pytest.fail('fixed-host tools do not run the address check')
    assert router.run('tripo.text_to_3d', {'prompt': 'x'}, workspace, allow_paid=True)['status'] != 'failed'


# ------------------------------------------------------------------ console endpoint

@pytest.fixture
def console(tmp_path, monkeypatch):
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    exe = tmp_path / 'atm'; exe.write_text('#!/bin/sh\nexit 0\n'); exe.chmod(0o700)
    server = Console(tmp_path / 'state', executable=str(exe), user_home=tmp_path / 'user')
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    with httpx.Client(base_url=server.origin, timeout=20, trust_env=False) as client:
        yield server, client
    server.shutdown(); server.server_close(); thread.join(timeout=5)


def call(console, path, body=None, **headers):
    server, client = console
    base = {'Authorization': 'Bearer ' + server.token, 'Origin': server.origin}
    merged = {k: v for k, v in {**base, **headers}.items() if v is not None}
    return client.get(path, headers=merged) if body is None else client.post(path, json=body, headers=merged)


def test_endpoint_is_owner_only_and_validated(console):
    server, client = console
    assert client.post('/api/settings/network', json={'fake_ip_tunnel': True}, headers={'Origin': server.origin}).status_code == 401
    assert call(console, '/api/settings/network', {'fake_ip_tunnel': True}, Authorization='Bearer wrong').status_code == 401
    assert call(console, '/api/settings/network', {'fake_ip_tunnel': True}, Origin='https://evil.example').status_code == 403
    assert call(console, '/api/settings/network', {'fake_ip_tunnel': True}, Origin=None).status_code == 403
    assert call(console, '/api/settings/network', {'fake_ip_tunnel': True}, Host='evil.example').status_code == 403
    for body in [{}, {'fake_ip_tunnel': 'true'}, {'fake_ip_tunnel': 1}, {'fake_ip_tunnel': True, 'expected': 'no'},
                 {'fake_ip_tunnel': True, 'extra': 1}, {'fake_ip_tunnel': True, 'passphrase': 'x'}]:
        response = call(console, '/api/settings/network', body)
        assert response.status_code == 400 and response.json()['error']['code'] == 'invalid_request', body
    assert fake_ip_tunnel(State(server.home)) is False
    assert client.get('/api/settings/network', headers={'Authorization': 'Bearer ' + server.token}).status_code == 404


def test_endpoint_round_trip_and_get_payload(console):
    server, _ = console
    assert call(console, '/api/overview').json()['network'] == {'fake_ip_tunnel': False, 'changed_at': None}
    on = call(console, '/api/settings/network', {'fake_ip_tunnel': True, 'expected': False})
    assert on.status_code == 200 and on.json()['fake_ip_tunnel'] is True and on.json()['action'] == 'enable'
    assert call(console, '/api/overview').json()['network']['fake_ip_tunnel'] is True
    assert fake_ip_tunnel(State(server.home)) is True
    stale = call(console, '/api/settings/network', {'fake_ip_tunnel': False, 'expected': False})
    assert stale.status_code == 409 and stale.json()['error']['code'] == 'state_changed'
    off = call(console, '/api/settings/network', {'fake_ip_tunnel': False})
    assert off.status_code == 200 and off.json()['fake_ip_tunnel'] is False
    assert call(console, '/api/overview').json()['network']['fake_ip_tunnel'] is False


def fake_oauth_router(provider):
    def build(home):
        return Router(home, network=Network(httpx.MockTransport(provider), higgsfield_fake_ip))
    return build


def test_console_login_error_payload_carries_the_hint(console, monkeypatch):
    server, _ = console
    provider = Provider()
    monkeypatch.setattr(oauth_web, 'Router', fake_oauth_router(provider))
    monkeypatch.setattr(oauth_module.webbrowser, 'open', lambda url: pytest.fail('no browser while the check refuses'))
    from agent_tool_maker.webapp import WebVault  # Passphrase vault: the console sends it for this one request.
    WebVault(State(server.home), password='fake-console-password').init('passphrase')
    response = call(console, '/api/oauth/login', {'provider': 'higgsfield', 'passphrase': 'fake-console-password'})
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'oauth_dns_policy' and response.json()['error']['hint'] == 'fake_ip_tunnel'
    assert '198.18' not in response.text and provider.requests == []
    oauth = call(console, '/api/connections').json()['oauth'][0]
    assert oauth['last_error'] == 'oauth_dns_policy' and oauth['last_error_hint'] == 'fake_ip_tunnel'


def test_console_login_is_sent_after_the_owner_allows_it(console, monkeypatch):
    server, _ = console
    provider = Provider()
    opened = []
    monkeypatch.setattr(oauth_web, 'Router', fake_oauth_router(provider))
    monkeypatch.setattr(oauth_module.webbrowser, 'open', lambda url: opened.append(url) or True)
    monkeypatch.setattr(OAuth, 'begin_login', partialmethod(OAuth.begin_login, timeout=1))  # The callback listener ends quickly.
    from agent_tool_maker.webapp import WebVault
    WebVault(State(server.home), password='fake-console-password').init('passphrase')
    assert call(console, '/api/settings/network', {'fake_ip_tunnel': True, 'expected': False}).status_code == 200
    response = call(console, '/api/oauth/login', {'provider': 'higgsfield', 'passphrase': 'fake-console-password'})
    assert response.status_code == 200 and response.json()['status'] == 'pending' and response.json()['browser_opened'] is True
    assert [str(r.url) for r in provider.requests] == [PROTECTED_METADATA, SERVER_METADATA, ENDPOINTS['registration_endpoint']]
    assert len(opened) == 1 and opened[0].startswith(ENDPOINTS['authorization_endpoint'] + '?')
    deadline = time.monotonic() + 10
    while any(t.name == 'atm-oauth-login' for t in threading.enumerate()) and time.monotonic() < deadline:
        time.sleep(.05)
    assert not any(t.name == 'atm-oauth-login' for t in threading.enumerate())


# ------------------------------------------------------------------ the approval window gets nothing new

def test_approval_window_has_no_network_endpoint(tmp_path):
    from agent_tool_maker.quickstart import scope_plan
    from agent_tool_maker.quickstart_web import ApprovalWindow
    from agent_tool_maker.secrets_provider import fingerprint
    r = Router(tmp_path / 's'); r.vault = Vault(r.state, password='fake-only-password-fip')
    r.vault.init('passphrase'); r.vault.put('fal', 'fake-key-fip')
    w = tmp_path / 'project'; w.mkdir()
    plan = scope_plan(r.state, w, ['fal']); ident = uuid.uuid4().hex
    r.state.set_setting('desktop-request:' + ident, {'id': ident, **plan, 'status': 'needs_unlock', 'created_at': time.time(),
                        'approval_sha256': fingerprint(plan), 'heartbeat': time.time()})
    ui = ApprovalWindow(r.state.home, ident)
    thread = threading.Thread(target=ui.serve_forever, daemon=True); thread.start()
    try:
        with httpx.Client(base_url=ui.origin, headers={'Authorization': 'Bearer ' + ui.token, 'Origin': ui.origin}, trust_env=False) as c:
            response = c.post('/api/settings/network', json={'fake_ip_tunnel': True})
            assert response.status_code == 404
            assert 'network' not in c.get('/api/desktop').json()
        assert fake_ip_tunnel(r.state) is False
    finally:
        ui.shutdown(); ui.server_close(); thread.join(5); r.close()
    for name in ('quickstart.js', 'quickstart.html'):
        source = (ROOT / 'src/agent_tool_maker/data/web' / name).read_text()
        assert '/api/settings/network' not in source and '198.18' not in source and 'fake_ip' not in source
