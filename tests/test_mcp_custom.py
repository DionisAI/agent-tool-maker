"""Owner-added remote MCP servers (e.g. Wisburg): reviewed endpoint + Key slot, project-session calls, stdio proxy.

Fake Keys and a mock MCP transport only; no real vendor or network.
"""
import io
import json
import tempfile
import threading
import time
import uuid
from pathlib import Path

import httpx
import pytest

from agent_tool_maker import mcp_native, mcp_servers, quickstart
from agent_tool_maker.broker import call
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.demo import fixture_resolver
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.extensions import declare_credential
from agent_tool_maker.factory import key_route
from agent_tool_maker.maker import validate_manifest
from agent_tool_maker.mcp_bridge import BATCH_SCHEMA, TOOLS_SCHEMA, bind_server, custom_definitions
from agent_tool_maker.network import Network
from agent_tool_maker.quickstart import profile_path, scope_plan
from agent_tool_maker.quickstart_web import ApprovalWindow
from agent_tool_maker.secrets_provider import fingerprint
from agent_tool_maker.session import owner_call
from agent_tool_maker.vault import Vault

URL = 'https://mcp.example.com/mcp'
INIT = {'protocolVersion': '2025-06-18', 'serverInfo': {'name': 'fixture', 'version': '1'}, 'capabilities': {'tools': {}}}
TOOLS = [{'name': 'read', 'description': 'Fixture read', 'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
         {'name': 'publish', 'description': 'Not allowed by the owner', 'inputSchema': {'type': 'object'}}]
PAID = {'allow_paid': True, 'grants': ['external_write', 'execute_code']}


class Remote:
    """A Streamable HTTP MCP server on httpx.MockTransport that records what reached it."""
    def __init__(self, tools=TOOLS, call_result=None):
        self.requests, self.tools, self.call_result = [], tools, call_result or {'content': [{'type': 'text', 'text': 'ok'}]}

    def __call__(self, req):
        if req.method == 'DELETE':
            return httpx.Response(204)
        q = json.loads(req.content)
        self.requests.append({'host': req.url.host, 'auth': req.headers.get('authorization'), 'method': q.get('method'), 'params': q.get('params')})
        if q.get('method') == 'notifications/initialized':
            return httpx.Response(202)
        value = INIT if q['method'] == 'initialize' else {'tools': self.tools} if q['method'] == 'tools/list' else self.call_result
        return httpx.Response(200, headers={'Mcp-Session-Id': 'fixture'}, json={'jsonrpc': '2.0', 'id': q['id'], 'result': value})

    def methods(self):
        return [r['method'] for r in self.requests]


def add_wisburg(router, allow=('read',), url=URL):
    declare_credential(router, 'wisburg', label='智堡 Wisburg', apply=True)
    preview = mcp_servers.add(router, 'wisburg', url, 'wisburg', allow_tools=list(allow))
    applied = mcp_servers.add(router, 'wisburg', url, 'wisburg', allow_tools=list(allow), approve=preview['plan_sha256'],
                              expected=preview['previous_sha256'])
    router.catalog = Catalog(router.state)
    return preview, applied


@pytest.fixture
def wisburg(router):
    router.vault.put('wisburg', 'FAKE_wisburg_key')
    remote = Remote()
    router.net.client = httpx.Client(transport=httpx.MockTransport(remote), trust_env=False)
    add_wisburg(router)
    return router, remote


def test_preview_then_approve_writes_both_definitions_and_the_binding(router):
    declare_credential(router, 'wisburg', apply=True)
    preview = mcp_servers.add(router, 'wisburg', URL, 'wisburg', allow_tools=['read'])
    assert preview['applied'] is False and preview['previous_sha256'] is None and preview['credentials_read'] is False
    assert preview['host'] == 'mcp.example.com' and preview['credential'] == 'wisburg' and preview['allow_tools'] == ['read']
    assert {d['id']: (d['paid'], d['permissions']) for d in preview['definitions']} == {
        'wisburg.mcp_batch': (True, ['execute_code', 'external_write']), 'wisburg.mcp_tools': (False, [])}
    assert router.state.setting('mcp:wisburg') is None and not router.state.setting('custom_tools')
    with pytest.raises(RouterError) as e:
        mcp_servers.add(router, 'wisburg', URL, 'wisburg', allow_tools=['read', 'publish'], approve=preview['plan_sha256'])
    assert e.value.code == 'approval_mismatch'  # The approval is bound to these exact options.
    applied = mcp_servers.add(router, 'wisburg', URL, 'wisburg', allow_tools=['read'], approve=preview['plan_sha256'])
    assert applied['applied'] is True and applied['plan_sha256'] == preview['plan_sha256']
    assert router.state.setting('mcp:wisburg') == {'transport': 'http', 'url': URL, 'credential': 'wisburg', 'allow_tools': ['read'], 'timeout': 120}
    tools = {t['id']: t for t in Catalog(router.state).tools.values() if t.get('server') == 'wisburg'}
    assert set(tools) == {'wisburg.mcp_tools', 'wisburg.mcp_batch'}
    assert all(t['url'] == URL and t['credential'] == 'wisburg' and t['user_defined'] and t['implementation'] == 'bridge' for t in tools.values())
    listed = mcp_servers.list_servers(router)['servers']
    assert listed == [{'server': 'wisburg', 'built_in': False, 'transport': 'http', 'credential': 'wisburg', 'allow_tools': ['read'],
                       'definitions': ['wisburg.mcp_batch', 'wisburg.mcp_tools'], 'endpoint': URL, 'matches_review': True}]


def test_an_allowlist_change_is_a_compare_and_swap_on_the_reviewed_state(wisburg):
    router, _ = wisburg
    before = mcp_servers.add(router, 'wisburg', URL, 'wisburg', allow_tools=['read'])
    preview = mcp_servers.add(router, 'wisburg', URL, 'wisburg', allow_tools=['read', 'publish'])
    assert preview['previous_sha256'] == before['plan_sha256']
    with pytest.raises(RouterError) as e:  # No --expected: the owner did not review what it replaces.
        mcp_servers.add(router, 'wisburg', URL, 'wisburg', allow_tools=['read', 'publish'], approve=preview['plan_sha256'])
    assert e.value.code == 'definition_changed'
    applied = mcp_servers.add(router, 'wisburg', URL, 'wisburg', allow_tools=['read', 'publish'],
                              approve=preview['plan_sha256'], expected=preview['previous_sha256'])
    assert applied['applied'] and not applied['unchanged']
    assert router.state.setting('mcp:wisburg')['allow_tools'] == ['publish', 'read']
    # The definitions did not change, so nothing was archived; a new endpoint archives the old pair.
    moved = mcp_servers.add(router, 'wisburg', 'https://mcp2.example.com/mcp', 'wisburg', allow_tools=['read'])
    mcp_servers.add(router, 'wisburg', 'https://mcp2.example.com/mcp', 'wisburg', allow_tools=['read'],
                    approve=moved['plan_sha256'], expected=moved['previous_sha256'])
    with router.state.db() as db:
        history = [r[0] for r in db.execute("SELECT name FROM settings WHERE name LIKE 'tool_history:wisburg.%'")]
    assert len(history) == 2


@pytest.mark.parametrize('name,url,credential,code', [
    ('figma', URL, 'wisburg', 'bad_server'),                                    # A built-in MCP server.
    ('Wisburg', URL, 'wisburg', 'bad_server'),
    ('wisburg', 'http://mcp.example.com/mcp', 'wisburg', None),                 # Not https.
    ('wisburg', URL + '?token=abc', 'wisburg', 'unsafe_origin'),                # No tokens in query strings.
    ('wisburg', 'https://user:pw@mcp.example.com/mcp', 'wisburg', None),
    ('wisburg', URL, 'never_declared', 'unknown_credential'),
    ('wisburg', URL, ['wisburg'], 'invalid_credential_name'),
])
def test_add_refuses_unsafe_or_unknown_inputs(router, name, url, credential, code):
    declare_credential(router, 'wisburg', apply=True)
    with pytest.raises(RouterError) as e:
        mcp_servers.add(router, name, url, credential)
    if code:
        assert e.value.code == code
    assert router.state.setting('mcp:wisburg') is None


def test_remove_is_previewed_and_removes_exactly_the_reviewed_server(wisburg):
    router, _ = wisburg
    preview = mcp_servers.remove(router, 'wisburg')
    assert preview['applied'] is False and preview['remove_definitions'] == ['wisburg.mcp_batch', 'wisburg.mcp_tools']
    with pytest.raises(RouterError):
        mcp_servers.remove(router, 'wisburg', approve='0' * 64)
    assert mcp_servers.remove(router, 'wisburg', approve=preview['plan_sha256'])['applied']
    assert router.state.setting('mcp:wisburg') is None
    assert not [t for t in Catalog(router.state).tools if t.startswith('wisburg.')]
    assert mcp_servers.list_servers(router)['servers'] == []


def test_discovery_and_call_send_the_key_only_to_the_reviewed_endpoint(wisburg, workspace):
    router, remote = wisburg
    found = router.run('wisburg.mcp_tools', {}, workspace)
    assert found['status'] == 'completed' and [t['name'] for t in found['data']['result']['tools']] == ['read', 'publish']
    called = router.run('wisburg.mcp_batch', {'calls': [{'name': 'read', 'arguments': {}}]}, workspace, **PAID)
    assert called['status'] == 'completed', called
    assert {(r['host'], r['auth']) for r in remote.requests} == {('mcp.example.com', 'Bearer FAKE_wisburg_key')}
    refused = router.run('wisburg.mcp_batch', {'calls': [{'name': 'publish', 'arguments': {}}]}, workspace, **PAID)
    assert refused['status'] == 'failed' and refused['data']['error']['code'] == 'mcp_tool_not_approved'
    assert remote.methods().count('tools/call') == 1
    with pytest.raises(RouterError) as e:  # Spending needs the explicit flag; refused before any job exists.
        router.run('wisburg.mcp_batch', {'calls': [{'name': 'read', 'arguments': {}}]}, workspace)
    assert e.value.code == 'paid_confirmation_required' and remote.methods().count('tools/call') == 1


def test_a_rebind_cannot_redirect_the_key(wisburg, workspace):
    router, remote = wisburg
    for cfg in [{'transport': 'http', 'url': 'https://attacker.example/mcp', 'credential': 'wisburg', 'allow_tools': ['read']},
                {'transport': 'http', 'url': URL, 'credential': 'elevenlabs', 'allow_tools': ['read']},
                {'transport': 'http', 'url': URL, 'credential': 'wisburg', 'allow_tools': ['read'], 'allow_local': False, 'env_credentials': {'X_KEY': 'fal'}}]:
        bind_server(router.state, 'wisburg', cfg)
        job = router.run('wisburg.mcp_tools', {}, workspace)
        assert job['status'] == 'failed' and job['data']['error']['code'] == 'mcp_binding_changed'
    assert remote.requests == []  # Refused before the vault was read or anything was sent.
    assert mcp_servers.list_servers(router)['servers'][0]['matches_review'] is False


def test_manifest_validator_accepts_only_the_standard_custom_mcp_shapes():
    tools, batch = custom_definitions('wisburg', URL, 'wisburg')
    assert validate_manifest(tools)['implementation'] == 'bridge'
    downgraded = validate_manifest({**batch, 'paid': False, 'permissions': []})
    assert downgraded['paid'] is True and downgraded['permissions'] == ['execute_code', 'external_write']
    bad = [{**tools, 'server': 'figma', 'id': 'figma.mcp_tools', 'provider': 'figma'},  # Built-in server name.
           {**tools, 'id': 'wisburg.search'},                                          # Not the standard ID.
           {**tools, 'schema': BATCH_SCHEMA},                                          # Wrong operation schema.
           {**batch, 'schema': {**BATCH_SCHEMA, 'properties': {}}},
           {**tools, 'url': URL + '?key=1'}, {**tools, 'url': 'http://mcp.example.com/mcp'},
           {k: v for k, v in tools.items() if k != 'credential'},
           {**tools, 'command': {'argv': ['x']}},
           {**tools, 'mcp_operation': 'call'}]
    for manifest in bad:
        with pytest.raises(RouterError):
            validate_manifest(manifest)
    assert key_route(validate_manifest(tools)) == (URL, 'wisburg')  # Drafts may not change where the Key goes.
    assert tools['schema'] == TOOLS_SCHEMA


def test_bind_refuses_a_credential_that_is_not_one_slot_name(router):
    for credential in [['wisburg', 'fal'], 'FAKE value with spaces', 7]:
        with pytest.raises(RouterError) as e:
            bind_server(router.state, 'figma', {'transport': 'http', 'url': URL, 'credential': credential})
        assert e.value.code == 'invalid_credential_name'


def test_a_tool_without_input_schema_is_validated_not_left_unknown(router, workspace):
    remote = Remote(tools=[{'name': 'bare'}])
    router.net.client = httpx.Client(transport=httpx.MockTransport(remote), trust_env=False)
    bind_server(router.state, 'figma', {'transport': 'http', 'url': URL, 'allow_tools': ['bare']})
    job = router.run('figma.mcp_batch', {'calls': [{'name': 'bare', 'arguments': {}}]}, workspace, **PAID)
    assert job['status'] == 'completed', job  # Before: a KeyError recorded submission_unknown with no call sent.


def test_a_server_error_result_is_kept_for_the_caller(router, workspace):
    remote = Remote(call_result={'content': [{'type': 'text', 'text': 'quota exceeded'}], 'isError': True})
    router.net.client = httpx.Client(transport=httpx.MockTransport(remote), trust_env=False)
    bind_server(router.state, 'figma', {'transport': 'http', 'url': URL, 'allow_tools': ['read']})
    job = router.run('figma.mcp_batch', {'calls': [{'name': 'read', 'arguments': {}}]}, workspace, **PAID)
    assert job['status'] == 'submission_unknown' and job['data']['error']['code'] == 'mcp_tool_error'
    assert job['data']['mcp_error']['result']['content'][0]['text'] == 'quota exceeded'


# Project session: the 30-minute approval, as `atm start` grants it.

PASSWORD = 'fake-only-password-mcp'


@pytest.fixture
def project(monkeypatch):
    with tempfile.TemporaryDirectory(prefix='amcp-') as td:
        root = Path(td).resolve()
        r = Router(root / 's')
        r.vault = Vault(r.state, password=PASSWORD)
        r.vault.init('passphrase')
        r.vault.put('wisburg', 'FAKE_wisburg_key')
        r.vault.put('fal', 'FAKE_fal_key')
        add_wisburg(r)
        w = root / 'project'
        w.mkdir()
        remote = Remote()
        # The session process opens its own Router; give it the fake remote instead of the network.
        monkeypatch.setattr('agent_tool_maker.engine.Network', lambda: Network(httpx.MockTransport(remote), fixture_resolver))
        plan = scope_plan(r.state, w, ['wisburg'])
        ident = uuid.uuid4().hex
        r.state.set_setting('desktop-request:' + ident, {'id': ident, **plan, 'status': 'needs_unlock', 'created_at': time.time(),
                                                         'approval_sha256': fingerprint(plan), 'heartbeat': time.time()})
        ui = ApprovalWindow(r.state.home, ident)
        thread = threading.Thread(target=ui.serve_forever, daemon=True)
        thread.start()
        client = httpx.Client(base_url=ui.origin, headers={'Authorization': 'Bearer ' + ui.token, 'Origin': ui.origin}, trust_env=False)
        try:
            response = client.post('/api/desktop/approve', json={'approved_sha256': fingerprint(ui.plan), 'consent': True,
                                                                 'passphrase': PASSWORD, 'credentials': {}})
            assert response.status_code == 200 and response.json()['status'] == 'ready', response.text
            yield r, w, remote, root
        finally:
            client.close()
            ui.shutdown()
            ui.server_close()
            thread.join(5)
            r.close()


def no_window(monkeypatch):
    opened = []
    monkeypatch.setattr(quickstart, 'start', lambda home, workspace, names=None, open_browser=True: opened.append(names) or {'status': 'needs_unlock', 'secrets_returned': False})
    return opened


def test_session_discovery_and_call_under_the_project_approval(project, monkeypatch):
    r, w, remote, root = project
    opened = no_window(monkeypatch)
    listed = mcp_native.tools(r.state.home, 'wisburg', w)
    assert listed['status'] == 'completed' and [(t['name'], t['allowed']) for t in listed['tools']] == [('read', True), ('publish', False)]
    first = mcp_native.request(r.state.home, 'wisburg', w, 'call', tool='read', arguments={}, request_key='task-1')
    assert first['status'] == 'completed' and first['result']['results'][0]['result']['content'][0]['text'] == 'ok'
    again = mcp_native.request(r.state.home, 'wisburg', w, 'call', tool='read', arguments={}, request_key='task-1')
    assert again['job_id'] == first['job_id'] and remote.methods().count('tools/call') == 1  # Same key: no resend.
    assert {r_['auth'] for r_ in remote.requests} == {'Bearer FAKE_wisburg_key'} and opened == []
    assert 'FAKE_wisburg_key' not in json.dumps([listed, first, again])
    job = call(profile_path(r.state, w), 'job', {'id': first['job_id']})
    assert job['id'] == first['job_id']


def test_session_refuses_another_project_server_or_tool(project, monkeypatch):
    r, w, remote, root = project
    no_window(monkeypatch)
    p = profile_path(r.state, w)
    other = root / 'other'
    other.mkdir()
    base = {'server': 'wisburg', 'operation': 'tools', 'workspace': str(w), 'request_key': 'deny'}
    with pytest.raises(RouterError) as e:
        call(p, 'mcp.run', {**base, 'workspace': str(other)})
    assert e.value.code == 'mcp_denied'
    preview = mcp_servers.add(r, 'falmcp', 'https://fal-mcp.example.com/mcp', 'fal')
    mcp_servers.add(r, 'falmcp', 'https://fal-mcp.example.com/mcp', 'fal', approve=preview['plan_sha256'])
    with pytest.raises(RouterError) as e:  # Its Key (fal) is not in this project's approval.
        call(p, 'mcp.run', {**base, 'server': 'falmcp'})
    assert e.value.code == 'mcp_denied'
    refused = mcp_native.request(r.state.home, 'wisburg', w, 'call', tool='publish', arguments={}, request_key='not-allowed')
    assert refused['status'] == 'failed' and refused['error']['code'] == 'mcp_tool_not_approved'
    assert 'tools/call' not in remote.methods()


def test_after_lock_calls_open_the_window_and_send_nothing(project, monkeypatch):
    r, w, remote, root = project
    opened = no_window(monkeypatch)
    owner_call(r.state.home, 'session.lock')
    result = mcp_native.request(r.state.home, 'wisburg', w, 'call', tool='read', arguments={}, request_key='after-lock')
    assert result['status'] == 'needs_unlock' and result['execution_started'] is False and opened == [['wisburg']]
    assert remote.requests == []


def rpc(proxy, *messages):
    proxy.stdin = io.BytesIO(b''.join((json.dumps(m) + '\n').encode() for m in messages))
    proxy.stdout = io.BytesIO()
    proxy.poll = 3600  # No list_changed notification in the middle of a scripted exchange.
    assert proxy.serve() == 0
    return [json.loads(line) for line in proxy.stdout.getvalue().splitlines()]


def test_stdio_proxy_lists_only_allowed_tools_and_forwards_calls(project, monkeypatch):
    r, w, remote, root = project
    no_window(monkeypatch)
    proxy = mcp_native.Proxy(r.state.home, 'wisburg', w)
    out = rpc(proxy, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26'}},
              {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
              {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
              {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'read', 'arguments': {}}},
              {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'publish', 'arguments': {}}},
              {'jsonrpc': '2.0', 'id': 5, 'method': 'resources/list', 'params': {}})
    assert [m['id'] for m in out] == [1, 2, 3, 4, 5]
    assert out[0]['result']['protocolVersion'] == '2025-03-26' and out[0]['result']['capabilities'] == {'tools': {'listChanged': True}}
    assert [t['name'] for t in out[1]['result']['tools']] == ['read']
    assert out[2]['result'] == {'content': [{'type': 'text', 'text': 'ok'}]}
    assert out[3]['result']['isError'] is True and remote.methods().count('tools/call') == 1
    assert out[4]['error']['code'] == -32601
    assert 'FAKE_wisburg_key' not in json.dumps(out)


def test_stdio_proxy_when_locked_offers_only_the_unlock_tool(project, monkeypatch):
    r, w, remote, root = project
    opened = no_window(monkeypatch)
    owner_call(r.state.home, 'session.lock')
    proxy = mcp_native.Proxy(r.state.home, 'wisburg', w)
    listed = rpc(proxy, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}})
    assert [t['name'] for t in listed[0]['result']['tools']] == [mcp_native.UNLOCK_TOOL]
    assert opened == []  # Clients list tools at startup; listing never opens a window.
    out = rpc(proxy, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'read', 'arguments': {}}},
              {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': mcp_native.UNLOCK_TOOL, 'arguments': {}}})
    assert out[0]['result']['isError'] is True and mcp_native.UNLOCK_TEXT in out[0]['result']['content'][0]['text']
    assert out[1]['result']['isError'] is True and opened == [['wisburg'], ['wisburg']]
    assert remote.requests == []


def test_proxy_announces_a_changed_tool_list(project, monkeypatch):
    r, w, remote, root = project
    no_window(monkeypatch)
    proxy = mcp_native.Proxy(r.state.home, 'wisburg', w, stdout=io.BytesIO(), poll=0.05)
    proxy.unlocked = True
    watcher = threading.Thread(target=proxy.watch, daemon=True)
    watcher.start()
    owner_call(r.state.home, 'session.lock')
    deadline = time.time() + 5
    while b'list_changed' not in proxy.stdout.getvalue() and time.time() < deadline:
        time.sleep(.05)
    proxy.closed.set()
    watcher.join(2)
    assert b'notifications/tools/list_changed' in proxy.stdout.getvalue()


def test_cli_add_list_remove_and_serve_refusal(tmp_path):
    import subprocess
    import sys
    home = tmp_path / 'home'
    atm = [sys.executable, '-m', 'agent_tool_maker', '--home', str(home)]
    def run(*args):
        p = subprocess.run(atm + list(args), capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout, p.stderr
    assert run('credentials', 'declare', 'wisburg', '--label', '智堡 Wisburg', '--apply')[0] == 0
    code, out, _ = run('mcp', 'add', 'wisburg', '--url', URL, '--credential', 'wisburg', '--allow-tool', 'read')
    preview = json.loads(out)
    assert code == 0 and preview['applied'] is False and '--approve ' + preview['plan_sha256'] in preview['next']
    code, out, _ = run('mcp', 'add', 'wisburg', '--url', URL, '--credential', 'wisburg', '--allow-tool', 'read', '--approve', preview['plan_sha256'])
    assert code == 0 and json.loads(out)['applied'] is True
    code, out, _ = run('mcp', 'list')
    assert code == 0 and [s['server'] for s in json.loads(out)['servers']] == ['wisburg']
    code, out, _ = run('describe', 'wisburg.mcp_batch')
    assert code == 0 and json.loads(out)['paid'] is True
    project = tmp_path / 'project'
    project.mkdir()
    code, out, err = run('mcp', 'serve', 'nosuch', '--workspace', str(project))
    assert code == 2 and out == '' and json.loads(err)['error']['code'] == 'mcp_not_configured'  # stdout stays JSON-RPC only.
    code, out, _ = run('mcp', 'remove', 'wisburg')
    sha = json.loads(out)['plan_sha256']
    assert run('mcp', 'remove', 'wisburg', '--approve', sha)[0] == 0
    assert json.loads(run('mcp', 'list')[1])['servers'] == []
