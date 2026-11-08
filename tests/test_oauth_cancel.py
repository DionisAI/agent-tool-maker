"""The owner cancels a pending ATM login at once instead of waiting for its deadline.

Fake OAuth only: httpx MockTransport, fixture resolver and an injected browser opener. No provider is contacted.
"""
import json
import re
import threading
import time
import uuid
from pathlib import Path

import httpx
import pytest

from agent_tool_maker import oauth_web
from agent_tool_maker.cli import parser
from agent_tool_maker.demo import fixture_resolver
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.network import Network
from agent_tool_maker.oauth import ENDPOINTS, ISSUER, NAME, PROTECTED_METADATA, RESOURCE, SERVER_METADATA, OAuth
from agent_tool_maker.storage import State, canonical
from agent_tool_maker.vault import Vault
from agent_tool_maker.webapp import Console, WebVault

from test_oauth_refresh import Keyring, Provider, begin, connected, oauth  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def row(manager):
    with manager.state.db() as db:
        found = db.execute('SELECT metadata, nonce, ciphertext FROM oauth_connections WHERE name=?', (NAME,)).fetchone()
    return (json.loads(found[0]), bytes(found[1]), bytes(found[2])) if found else None


def events(manager):
    with manager.state.db() as db:
        return [r[0] for r in db.execute("SELECT kind FROM events WHERE kind LIKE 'oauth.%' ORDER BY rowid")]


def token_requests(fixture):
    return [r for r in fixture.requests if str(r.url) == ENDPOINTS['token_endpoint']]


def test_cancel_ends_a_pending_login_and_a_new_one_starts_at_once(oauth):
    manager, fixture, now = oauth
    server, result, query = begin(manager)
    try:
        assert result['status'] == 'pending'
        # Before: a second login is held back until the five-minute deadline.
        _, reused = manager.begin_login(opener=lambda _: pytest.fail('no second browser while one is pending'))
        assert reused['action'] == 'reused' and reused['status'] == 'pending'
        cancelled = manager.cancel_login(NAME)
        assert cancelled['action'] == 'cancelled' and cancelled['status'] == 'needs_login'
        assert cancelled['last_error'] == 'oauth_cancelled' and cancelled['login_deadline'] is None
        assert cancelled['secrets_returned'] is False and 'state' not in json.dumps(cancelled)
        meta, _, _ = row(manager)
        assert not {'claim', 'phase', 'login_deadline'} & set(meta)  # The cancelled login no longer owns the row.
        assert events(manager)[-1] == 'oauth.cancelled'
        # Its callback is refused and nothing is exchanged, even with the right state.
        with pytest.raises(RouterError) as caught:
            manager.callback(server.claim, {'state': query['state'], 'code': 'FIXTURE_CODE', 'iss': ISSUER})
        assert caught.value.code == 'oauth_callback' and token_requests(fixture) == []
    finally:
        server.server_close()
    # A new login starts now, well before the old deadline, and completes.
    second, started, fresh = begin(manager)
    try:
        assert started['action'] == 'started' and started['browser_opened'] is True
        assert manager.callback(second.claim, {'state': fresh['state'], 'code': 'FIXTURE_CODE', 'iss': ISSUER})['status'] == 'ready'
        assert manager.access_token(NAME, RESOURCE) == 'FIXTURE_ACCESS_1'
        assert manager.status()['last_error'] is None
    finally:
        second.server_close()


def test_cancel_restores_a_replacement_that_kept_the_working_tokens_sealed(oauth):
    """A replacement written metadata-only keeps the working connection under `previous`; cancelling resumes it."""
    manager, fixture, now = connected(oauth)
    ready, nonce, cipher = row(manager)
    pending = {'status': 'pending', 'claim': 'f' * 32, 'phase': 'waiting', 'login_deadline': now[0] + 300,
               'keep_login': False, 'last_error': None, 'previous': {**ready, 'last_error_hint': 'fake_ip_tunnel'}}
    with manager.state.db() as db:
        db.execute('UPDATE oauth_connections SET metadata=? WHERE name=?', (canonical(pending), NAME))
    result = manager.cancel_login(NAME)
    assert result['action'] == 'cancelled' and result['status'] == 'ready' and result['last_error'] == 'oauth_cancelled'
    assert 'last_error_hint' not in result
    meta, after_nonce, after_cipher = row(manager)
    assert (after_nonce, after_cipher) == (nonce, cipher)  # The sealed tokens were never touched.
    # The restored connection also names the cancelled login (its random claim id only, never a secret).
    assert meta == {**ready, 'last_error': 'oauth_cancelled', 'cancelled_claims': ['f' * 32]}
    assert manager.access_token(NAME, RESOURCE) == 'FIXTURE_ACCESS_1'


def test_cancel_with_nothing_pending_changes_nothing(oauth):
    manager, fixture, now = oauth
    assert manager.cancel_login(NAME) == {**manager.status(), 'action': 'not_pending'}
    assert manager.status()['status'] == 'missing' and row(manager) is None
    manager, fixture, now = connected(oauth)
    before, count = row(manager), len(events(manager))
    result = manager.cancel_login(NAME)
    assert result['action'] == 'not_pending' and result['status'] == 'ready'
    assert row(manager) == before and len(events(manager)) == count
    # A pending login past its deadline already reads as ended; cancelling it writes nothing.
    server, _, _ = begin(manager, replace=True)
    server.server_close()
    now[0] += 301
    before = row(manager)
    assert manager.cancel_login(NAME)['action'] == 'not_pending' and row(manager) == before
    with pytest.raises(RouterError) as caught:
        manager.cancel_login('other')
    assert caught.value.code == 'oauth_provider'


def test_cancel_waits_for_a_code_already_at_the_token_endpoint(oauth):
    manager, fixture, now = oauth
    server, _, query = begin(manager)
    fixture.block = threading.Event()
    outcome = {}
    def exchange():
        outcome['status'] = manager.callback(server.claim, {'state': query['state'], 'code': 'FIXTURE_CODE', 'iss': ISSUER})['status']
    thread = threading.Thread(target=exchange)
    try:
        thread.start()
        assert fixture.entered.wait(5)
        with pytest.raises(RouterError) as caught:
            manager.cancel_login(NAME)
        assert caught.value.code == 'oauth_exchanging'  # Its outcome is recorded by the exchange, never discarded.
    finally:
        fixture.block.set()
        thread.join(5)
        server.server_close()
    assert outcome == {'status': 'ready'} and len(token_requests(fixture)) == 1
    assert 'oauth.cancelled' not in events(manager)


def test_the_cancelled_login_listener_stops_soon_and_keeps_the_cause(oauth):
    manager, fixture, now = oauth
    server, _, _ = begin(manager)  # The default five-minute listener.
    finals = []
    thread = threading.Thread(target=lambda: finals.append(server.run()), daemon=True)
    thread.start()
    try:
        time.sleep(.3)
        assert thread.is_alive()
        manager.cancel_login(NAME)
        thread.join(5)
        assert not thread.is_alive()
    finally:
        server.done.set()  # Never leave a five-minute listener behind a failed assertion.
        thread.join(5)
    assert finals[0]['status'] == 'needs_login' and finals[0]['last_error'] == 'oauth_cancelled'
    # The stopped listener did not record a timeout over the owner's cancel.
    assert manager.status()['last_error'] == 'oauth_cancelled' and events(manager)[-1] == 'oauth.cancelled'


class Slow(Provider):
    """A provider whose answer at one pinned URL comes only when released (real timeouts allow ~60 s per request)."""
    def __init__(self, at=PROTECTED_METADATA):
        super().__init__()
        self.at, self.gate, self.waiting = at, threading.Event(), threading.Event()

    def __call__(self, request):
        if str(request.url) == self.at:
            self.waiting.set()
            assert self.gate.wait(30)
        return super().__call__(request)


def held_login(manager, at, **kwargs):
    """Start a login whose provider holds the request at `at`; the owner can cancel while it waits there."""
    slow = Slow(at)
    manager.net = Network(httpx.MockTransport(slow), fixture_resolver)
    outcome, opened, phases = {}, [], []
    write = manager._write
    def recorded(db, meta, payload=None):
        phases.append(meta.get('phase'))
        return write(db, meta, payload)
    manager._write = recorded
    def run():
        try:
            outcome['result'] = manager.begin_login(opener=lambda url: opened.append(url) or True, **kwargs)
        except RouterError as error:
            outcome['error'] = error
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert slow.waiting.wait(10)
    return slow, thread, outcome, opened, phases


@pytest.mark.parametrize('replace', [False, True])
def test_a_login_cancelled_during_discovery_registers_no_client(oauth, replace):
    manager, fixture, now = connected(oauth) if replace else oauth
    before = row(manager)
    slow, thread, outcome, opened, _ = held_login(manager, PROTECTED_METADATA, replace=replace)
    try:
        assert manager.status()['status'] == 'pending'
        assert manager.cancel_login(NAME)['action'] == 'cancelled'
    finally:
        slow.gate.set()
        thread.join(10)
        manager.net.close()
    assert not thread.is_alive() and 'result' not in outcome
    assert outcome['error'].code == 'oauth_cancelled' and 'cancel' in str(outcome['error'])
    # Discovery finished after the cancel: no client is registered for a login nobody waits for any more.
    assert [str(r.url) for r in slow.requests] == [PROTECTED_METADATA, SERVER_METADATA]
    assert opened == [] and manager._logins == {}
    status = manager.status()
    assert status['status'] == ('ready' if replace else 'needs_login') and status['last_error'] == 'oauth_cancelled'
    assert events(manager)[-1] == 'oauth.cancelled'  # The stopped login recorded nothing over the owner's cancel.
    if replace:
        assert row(manager)[1:] == before[1:] and manager.access_token(NAME, RESOURCE) == 'FIXTURE_ACCESS_1'


def test_a_login_cancelled_during_registration_never_waits_or_opens_a_browser(oauth):
    manager, fixture, now = oauth
    slow, thread, outcome, opened, phases = held_login(manager, ENDPOINTS['registration_endpoint'])
    try:
        assert manager.cancel_login(NAME)['action'] == 'cancelled'
    finally:
        slow.gate.set()
        thread.join(10)
        manager.net.close()
    assert not thread.is_alive() and 'result' not in outcome and outcome['error'].code == 'oauth_cancelled'
    # The registered client is never used: no 'waiting' row, no PKCE state kept, no browser, no callback to accept.
    assert 'waiting' not in phases and opened == [] and manager._logins == {}
    meta, _, _ = row(manager)
    assert meta['status'] == 'needs_login' and meta['last_error'] == 'oauth_cancelled'
    assert not {'claim', 'phase', 'login_deadline'} & set(meta)
    assert events(manager)[-1] == 'oauth.cancelled' and token_requests(slow) == []


def test_a_login_whose_claim_another_login_took_still_reports_a_conflict(oauth):
    """Only the owner's cancel reads as oauth_cancelled; any other loss of the claim stays oauth_conflict."""
    manager, fixture, now = oauth
    slow, thread, outcome, opened, _ = held_login(manager, PROTECTED_METADATA)
    try:
        with manager.state.db() as db:
            meta = json.loads(db.execute('SELECT metadata FROM oauth_connections WHERE name=?', (NAME,)).fetchone()[0])
            db.execute('UPDATE oauth_connections SET metadata=? WHERE name=?', (canonical({**meta, 'claim': 'e' * 32}), NAME))
    finally:
        slow.gate.set()
        thread.join(10)
        manager.net.close()
    assert outcome['error'].code == 'oauth_conflict' and opened == []
    assert ENDPOINTS['registration_endpoint'] not in [str(r.url) for r in slow.requests]
    assert row(manager)[0]['claim'] == 'e' * 32  # The other login's claim is left alone.


def other_worker(manager, fixture):
    """Another login or refresh on the same state and vault (the console gives every login its own worker)."""
    net = Network(httpx.MockTransport(fixture), fixture_resolver)
    return OAuth(manager.state, manager.vault, net, clock=manager.clock), net


@pytest.mark.parametrize('replace', [False, True])
@pytest.mark.parametrize('end', ['waiting', 'connected', 'denied', 'failed', 'timed_out'])
def test_a_cancelled_login_hears_so_after_the_owner_logged_in_again(oauth, replace, end):
    """取消登录, then 重新登录 while the first login's discovery is slow: the row now belongs to the second login,
    whose own outcome (still waiting, connected, denied, failed exchange or past its deadline) rewrote last_error."""
    manager, fixture, now = connected(oauth) if replace else oauth
    slow, thread, outcome, opened, _ = held_login(manager, PROTECTED_METADATA, replace=replace)
    first = row(manager)[0]['claim']
    again, net = other_worker(manager, fixture)
    second = None
    try:
        assert manager.cancel_login(NAME)['action'] == 'cancelled'
        second, started, query = begin(again, replace=replace)
        assert started['action'] == 'started' and started['browser_opened'] is True
        if end in {'connected', 'denied'}:
            answer = {'code': 'FIXTURE_CODE'} if end == 'connected' else {'error': 'access_denied'}
            again.callback(second.claim, {'state': query['state'], 'iss': ISSUER, **answer})
        if end == 'failed':
            fixture.token_result = httpx.Response(400, json={'error': 'invalid_grant'})
            with pytest.raises(RouterError) as caught:
                again.callback(second.claim, {'state': query['state'], 'code': 'FIXTURE_CODE', 'iss': ISSUER})
            assert caught.value.code == 'oauth_invalid_grant'
            fixture.token_result = None
        if end == 'timed_out':
            now[0] += 301
        slow.gate.set()
        thread.join(10)
        assert not thread.is_alive() and 'result' not in outcome
        # Before: the first login read the second login's row as a conflict ("an ATM login already exists").
        assert outcome['error'].code == 'oauth_cancelled'
        assert [str(r.url) for r in slow.requests] == [PROTECTED_METADATA, SERVER_METADATA] and opened == []
        # The first login's end leaves the second login's row alone.
        meta = row(manager)[0]
        assert meta['cancelled_claims'] == [first] and first != second.claim
        expected = {'waiting': 'pending', 'connected': 'ready', 'denied': 'ready' if replace else 'denied',
                    'failed': 'ready' if replace else 'needs_login', 'timed_out': 'ready' if replace else 'needs_login'}[end]
        assert manager.status()['status'] == expected
        if end == 'waiting':
            assert meta['claim'] == second.claim and meta['phase'] == 'waiting'
            assert again.callback(second.claim, {'state': query['state'], 'code': 'FIXTURE_CODE', 'iss': ISSUER})['status'] == 'ready'
        if manager.status()['status'] == 'ready':
            assert manager.access_token(NAME, RESOURCE) == 'FIXTURE_ACCESS_1'
    finally:
        slow.gate.set()
        thread.join(10)
        if second:
            second.server_close()
        manager.net.close()
        net.close()


def test_a_cancelled_replacement_hears_so_after_a_refresh_rewrote_the_row(oauth):
    """Cancelling a replacement restores the working connection; its refresh can rewrite the row (last_error None)
    before the cancelled login's discovery returns."""
    manager, fixture, now = connected(oauth)
    slow, thread, outcome, opened, _ = held_login(manager, PROTECTED_METADATA, replace=True)
    first = row(manager)[0]['claim']
    refresher, net = other_worker(manager, fixture)
    fixture.next_access, fixture.next_refresh = 'FIXTURE_ACCESS_2', 'FIXTURE_REFRESH_2'
    try:
        assert manager.cancel_login(NAME)['status'] == 'ready'
        assert refresher.refresh(NAME, force=True)['action'] == 'refreshed'
        assert manager.status()['last_error'] is None  # The refresh no longer says oauth_cancelled.
    finally:
        slow.gate.set()
        thread.join(10)
        manager.net.close()
        net.close()
    assert not thread.is_alive() and 'result' not in outcome
    assert outcome['error'].code == 'oauth_cancelled'  # Before: oauth_conflict.
    assert ENDPOINTS['registration_endpoint'] not in [str(r.url) for r in slow.requests] and opened == []
    meta = row(manager)[0]
    assert meta['status'] == 'ready' and meta['cancelled_claims'] == [first] and 'claim' not in meta
    assert events(manager)[-1] == 'oauth.refreshed'  # The cancelled login recorded nothing over the refresh.
    assert manager.access_token(NAME, RESOURCE) == 'FIXTURE_ACCESS_2'


def test_a_login_that_lost_its_claim_to_a_later_cancelled_login_reports_a_conflict(oauth):
    """last_error names the latest cancel, which may be another login's: only its own claim makes a login cancelled."""
    manager, fixture, now = oauth
    slow, thread, outcome, opened, _ = held_login(manager, PROTECTED_METADATA)
    first = row(manager)[0]['claim']
    other, net = other_worker(manager, fixture)
    try:
        now[0] += 301  # The first login's deadline passes while its discovery hangs; another login takes the row.
        second, started, _ = begin(other)
        second.server_close()
        assert started['action'] == 'started'
        assert manager.cancel_login(NAME)['action'] == 'cancelled'  # The owner cancels that second login.
        assert manager.status()['last_error'] == 'oauth_cancelled'
    finally:
        slow.gate.set()
        thread.join(10)
        manager.net.close()
        net.close()
    assert outcome['error'].code == 'oauth_conflict'  # Before: it read the second login's cancel as its own.
    assert row(manager)[0]['cancelled_claims'] == [second.claim] and first != second.claim
    assert manager.status()['last_error'] == 'oauth_cancelled' and events(manager)[-1] == 'oauth.cancelled'


@pytest.mark.parametrize('end', ['failed', 'denied', 'lapsed'])
def test_a_replacement_that_ends_keeps_the_cancelled_claims(oauth, end):
    """Restoring `previous` (a failed exchange, a denial, a lapsed deadline) keeps the cancelled logins' claims."""
    manager, fixture, now = connected(oauth)
    server, _, query = begin(manager, replace=True)
    try:
        meta, _, _ = row(manager)
        # Hand-written: the claims only beside `previous`, so restoring `previous` alone would drop them.
        with manager.state.db() as db:
            db.execute('UPDATE oauth_connections SET metadata=? WHERE name=?', (canonical({**meta, 'cancelled_claims': ['c' * 32]}), NAME))
        if end == 'failed':
            manager._failed(server.claim, RouterError('oauth_http', 'Fake provider refusal.'))
        elif end == 'denied':
            manager.callback(server.claim, {'state': query['state'], 'error': 'access_denied', 'iss': ISSUER})
        else:
            now[0] += 301
    finally:
        server.server_close()
    with manager.state.db() as db:
        _, restored = manager._row(db)
    assert restored['status'] == 'ready' and 'previous' not in restored and restored['cancelled_claims'] == ['c' * 32]
    with pytest.raises(RouterError) as caught:
        OAuth._still_claimed(restored, 'c' * 32)
    assert caught.value.code == 'oauth_cancelled'
    assert manager.access_token(NAME, RESOURCE) == 'FIXTURE_ACCESS_1'


@pytest.mark.parametrize('replace', [False, True])
def test_the_cancelled_claims_stay_few_and_carry_no_secret(oauth, replace):
    manager, fixture, now = connected(oauth) if replace else oauth
    claims, states = [], []
    for _ in range(10):
        server, _, query = begin(manager, replace=replace)
        server.server_close()
        claims.append(server.claim)
        states.append(query['state'])
        assert manager.cancel_login(NAME)['action'] == 'cancelled'
    meta = row(manager)[0]
    assert meta['cancelled_claims'] == claims[-8:]  # The newest eight, oldest first.
    assert all(re.fullmatch('[0-9a-f]{32}', claim) for claim in meta['cancelled_claims'])
    assert 'previous' not in meta and manager.status()['status'] == ('ready' if replace else 'needs_login')
    raw = manager.state.path.read_bytes()
    assert not [state for state in states if state.encode() in raw]
    assert 'cancelled_claims' not in manager.status()  # Status never lists them.
    # A login cancelled more than eight cancels ago that returns only now reads as a conflict.
    with pytest.raises(RouterError) as caught:
        OAuth._still_claimed(meta, claims[0])
    assert caught.value.code == 'oauth_conflict'
    with pytest.raises(RouterError) as caught:
        OAuth._still_claimed(meta, claims[-1])
    assert caught.value.code == 'oauth_cancelled'
    if replace:
        assert manager.access_token(NAME, RESOURCE) == 'FIXTURE_ACCESS_1'


# ------------------------------------------------------------------ console endpoint

@pytest.fixture
def console(tmp_path, monkeypatch):
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    fixture = Provider()
    fixture.opened = []
    monkeypatch.setattr(oauth_web, 'Router', lambda home: Router(home, network=Network(httpx.MockTransport(fixture), fixture_resolver)))
    monkeypatch.setattr('agent_tool_maker.oauth.webbrowser.open', lambda url: fixture.opened.append(url) or True)
    exe = tmp_path / 'atm'; exe.write_text('#!/bin/sh\nexit 0\n'); exe.chmod(0o700)
    server = Console(tmp_path / 'state', executable=str(exe), user_home=tmp_path / 'user')
    WebVault(State(server.home), password='fake-console-password').init('passphrase')
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    with httpx.Client(base_url=server.origin, timeout=20, trust_env=False) as client:
        yield server, client, fixture
    server.shutdown(); server.server_close(); thread.join(timeout=5)


def call(console, path, body=None, **headers):
    server, client, _ = console
    base = {'Authorization': 'Bearer ' + server.token, 'Origin': server.origin}
    merged = {k: v for k, v in {**base, **headers}.items() if v is not None}
    return client.get(path, headers=merged) if body is None else client.post(path, json=body, headers=merged)


def workers():
    return [t for t in threading.enumerate() if t.name == 'atm-oauth-login']


def login(console):
    return call(console, '/api/oauth/login', {'provider': NAME, 'passphrase': 'fake-console-password'})


def test_cancel_endpoint_is_owner_only_and_validated(console):
    server, client, fixture = console
    assert login(console).json()['status'] == 'pending'
    path = '/api/oauth/cancel'
    assert client.post(path, json={'provider': NAME}, headers={'Origin': server.origin}).status_code == 401
    assert call(console, path, {'provider': NAME}, Authorization='Bearer wrong').status_code == 401
    assert call(console, path, {'provider': NAME}, Origin='https://evil.example').status_code == 403
    assert call(console, path, {'provider': NAME}, Origin=None).status_code == 403
    assert call(console, path, {'provider': NAME}, Host='evil.example').status_code == 403
    for body in [{}, {'provider': 1}, {'provider': NAME, 'extra': 1}, {'provider': NAME, 'confirm': NAME},
                 {'provider': NAME, 'passphrase': 'fake-console-password'}]:
        response = call(console, path, body)
        assert response.status_code == 400 and response.json()['error']['code'] == 'invalid_request', body
    response = call(console, path, {'provider': 'other'})
    assert response.status_code == 400 and response.json()['error']['code'] == 'oauth_provider'
    assert client.get(path, headers={'Authorization': 'Bearer ' + server.token}).status_code == 404
    assert call(console, '/api/connections').json()['oauth'][0]['status'] == 'pending'  # None of these cancelled it.
    assert call(console, path, {'provider': NAME}).json()['action'] == 'cancelled'


def test_a_slow_provider_does_not_block_the_console(console, monkeypatch):
    server, client, fixture = console
    slow, routers = Slow(), []
    def worker_router(home):
        routers.append(Router(home, network=Network(httpx.MockTransport(slow), fixture_resolver)))
        return routers[-1]
    monkeypatch.setattr(oauth_web, 'Router', worker_router)
    results = []
    worker = threading.Thread(target=lambda: results.append(login(console)))
    worker.start()
    try:
        assert slow.waiting.wait(10)  # The login request is in discovery and holds the pending claim.
        headers = {'Authorization': 'Bearer ' + server.token, 'Origin': server.origin}
        started = time.monotonic()
        with httpx.Client(base_url=server.origin, timeout=5, trust_env=False) as quick:
            assert quick.get('/api/connections', headers=headers).json()['oauth'][0]['status'] == 'pending'
            # The claim is the login's lease: a second login opens nothing while the first is in flight.
            again = quick.post('/api/oauth/login', json={'provider': NAME, 'passphrase': 'fake-console-password'}, headers=headers)
            assert again.status_code == 200 and again.json()['action'] == 'preserved' and again.json()['browser_opened'] is False
            assert quick.post('/api/session/lock', json={}, headers=headers).status_code == 200
            cancelled = quick.post('/api/oauth/cancel', json={'provider': NAME}, headers=headers)
        assert cancelled.status_code == 200 and cancelled.json()['action'] == 'cancelled'
        assert time.monotonic() - started < 5 and worker.is_alive()
    finally:
        slow.gate.set()
        worker.join(30)
    # The cancelled login stops after discovery: it says it was cancelled, registers no client, records nothing over
    # the owner's cancel, opens no browser and drops its key snapshot.
    assert results[0].status_code == 400 and results[0].json()['error']['code'] == 'oauth_cancelled'
    oauth = call(console, '/api/connections').json()['oauth'][0]
    assert oauth['status'] == 'needs_login' and oauth['last_error'] == 'oauth_cancelled'
    assert fixture.opened == [] and not workers()  # The browser opener of every console login records here.
    assert [str(r.url) for r in slow.requests] == [PROTECTED_METADATA, SERVER_METADATA]
    assert len(routers) == 1 and routers[0].vault._key is None and routers[0].vault._used_secrets == []


def test_console_cancel_then_login_again_while_the_first_is_slow(console, monkeypatch):
    """取消登录 then 重新登录: the first request still says it was cancelled, the second opens the browser."""
    server, client, fixture = console
    slow, routers = Slow(), []
    def worker_router(home):
        transport = slow if not routers else fixture  # Only the first login's provider is slow.
        routers.append(Router(home, network=Network(httpx.MockTransport(transport), fixture_resolver)))
        return routers[-1]
    monkeypatch.setattr(oauth_web, 'Router', worker_router)
    results = []
    worker = threading.Thread(target=lambda: results.append(login(console)))
    worker.start()
    try:
        assert slow.waiting.wait(10)
        headers = {'Authorization': 'Bearer ' + server.token, 'Origin': server.origin}
        with httpx.Client(base_url=server.origin, timeout=5, trust_env=False) as quick:
            assert quick.post('/api/oauth/cancel', json={'provider': NAME}, headers=headers).json()['action'] == 'cancelled'
            again = quick.post('/api/oauth/login', json={'provider': NAME, 'passphrase': 'fake-console-password'}, headers=headers)
        assert again.status_code == 200 and again.json()['action'] == 'started' and len(fixture.opened) == 1
        slow.gate.set()
        worker.join(30)
        assert results[0].status_code == 400 and results[0].json()['error']['code'] == 'oauth_cancelled'  # Before: oauth_conflict.
        assert ENDPOINTS['registration_endpoint'] not in [str(r.url) for r in slow.requests] and len(fixture.opened) == 1
        assert routers[0].vault._key is None and routers[0].vault._used_secrets == []
        # The second login still waits for the owner in the browser.
        assert call(console, '/api/connections').json()['oauth'][0]['status'] == 'pending'
    finally:
        slow.gate.set()
        worker.join(30)
        # Cancelling the second login stops its five-minute listener.
        call(console, '/api/oauth/cancel', {'provider': NAME})
        deadline = time.monotonic() + 10
        while workers() and time.monotonic() < deadline:
            time.sleep(.05)
    assert not workers() and len(routers) == 2


def test_console_cancel_frees_the_login_at_once(console):
    server, client, fixture = console
    first = login(console)
    assert first.status_code == 200 and first.json()['status'] == 'pending' and len(fixture.opened) == 1
    # Before: while it is pending, another login opens nothing until the deadline.
    again = login(console)
    assert again.json()['status'] == 'pending' and again.json()['browser_opened'] is False and len(fixture.opened) == 1
    # Cancelling needs no ATM password: it writes connection metadata only.
    cancelled = call(console, '/api/oauth/cancel', {'provider': NAME})
    assert cancelled.status_code == 200 and cancelled.json()['action'] == 'cancelled'
    assert cancelled.json()['status'] == 'needs_login' and cancelled.json()['last_error'] == 'oauth_cancelled'
    oauth = call(console, '/api/connections').json()['oauth'][0]
    assert oauth['status'] == 'needs_login' and oauth['last_error'] == 'oauth_cancelled'
    # The five-minute callback listener stops within seconds and drops its key snapshot.
    deadline = time.monotonic() + 10
    while workers() and time.monotonic() < deadline:
        time.sleep(.05)
    assert not workers()
    # The owner logs in again at once: the pinned requests are sent again and the browser opens again.
    second = login(console)
    assert second.status_code == 200 and second.json()['action'] == 'started' and len(fixture.opened) == 2
    assert [str(r.url) for r in fixture.requests].count(ENDPOINTS['registration_endpoint']) == 2
    assert not [r for r in fixture.requests if str(r.url) == ENDPOINTS['token_endpoint']]
    again = call(console, '/api/oauth/cancel', {'provider': NAME})
    assert again.json()['action'] == 'cancelled'
    assert call(console, '/api/oauth/cancel', {'provider': NAME}).json()['action'] == 'not_pending'


# ------------------------------------------------------------------ no Agent write path

def walk(p):
    import argparse
    for action in p._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                yield name, child
                yield from walk(child)


def test_no_cli_command_can_cancel_a_login():
    commands = dict(walk(parser()))
    oauth_ops = next(a for a in commands['oauth']._actions if a.__class__.__name__ == '_SubParsersAction')
    assert sorted(oauth_ops.choices) == ['keep-login', 'login', 'refresh', 'status', 'watch']
    assert not [name for name in commands if 'cancel' in name]
    options = [o for p in [parser(), *commands.values()] for a in p._actions for o in a.option_strings]
    assert not [o for o in options if 'cancel' in o]
    # The only caller outside oauth.py is the console endpoint.
    callers = sorted(path.name for path in (ROOT / 'src/agent_tool_maker').glob('*.py') if 'cancel_login' in path.read_text())
    assert callers == ['oauth.py', 'webapp.py'], callers


def test_approval_window_cannot_cancel_a_login(tmp_path):
    from agent_tool_maker.quickstart import scope_plan
    from agent_tool_maker.quickstart_web import ApprovalWindow
    from agent_tool_maker.secrets_provider import fingerprint
    r = Router(tmp_path / 's'); r.vault = Vault(r.state, password='fake-only-password-oc')
    r.vault.init('passphrase'); r.vault.put('fal', 'fake-key-oc')
    w = tmp_path / 'project'; w.mkdir()
    plan = scope_plan(r.state, w, ['fal']); ident = uuid.uuid4().hex
    r.state.set_setting('desktop-request:' + ident, {'id': ident, **plan, 'status': 'needs_unlock', 'created_at': time.time(),
                        'approval_sha256': fingerprint(plan), 'heartbeat': time.time()})
    ui = ApprovalWindow(r.state.home, ident)
    thread = threading.Thread(target=ui.serve_forever, daemon=True); thread.start()
    try:
        with httpx.Client(base_url=ui.origin, headers={'Authorization': 'Bearer ' + ui.token, 'Origin': ui.origin}, trust_env=False) as c:
            assert c.post('/api/oauth/cancel', json={'provider': NAME}).status_code == 404
    finally:
        ui.shutdown(); ui.server_close(); thread.join(5); r.close()
    for name in ('quickstart.js', 'quickstart.html'):
        assert '/api/oauth/cancel' not in (ROOT / 'src/agent_tool_maker/data/web' / name).read_text()
