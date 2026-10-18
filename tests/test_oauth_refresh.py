"""Isolated protocol, durable rotation, subprocess, loopback and launchd fixtures.

No real provider accounts, credential files, browser consent or billing.
"""
import json
import os
import plistlib
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlencode

import httpx
import pytest

from agent_tool_maker.demo import fixture_resolver
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.mcp_bridge import HTTP, bind_server
from agent_tool_maker.network import Network
from agent_tool_maker.oauth import OAuth, NAME, RESOURCE, ISSUER, ENDPOINTS, PROTECTED_METADATA, SERVER_METADATA, SCOPES
from agent_tool_maker.oauth_cli import tick
from agent_tool_maker.oauth_service import install_service
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault


class Keyring:
    def __init__(self):
        self.values = {}
    def set_password(self, service, account, value):
        self.values[service, account] = value
    def get_password(self, service, account):
        return self.values[service, account]


class Provider:
    def __init__(self):
        self.requests = []
        self.token_result = None
        self.metadata_patch = {}
        self.protected_patch = {}
        self.next_access, self.next_refresh = 'FIXTURE_ACCESS_1', 'FIXTURE_REFRESH_1'
        self.expiry = 3600
        self.block = None
        self.entered = threading.Event()
    def __call__(self, request):
        self.requests.append(request)
        url = str(request.url)
        if url == PROTECTED_METADATA:
            data = {'resource': RESOURCE, 'authorization_servers': [ISSUER], 'scopes_supported': sorted(SCOPES), **self.protected_patch}
        elif url == SERVER_METADATA:
            data = {'issuer': ISSUER, **ENDPOINTS, 'grant_types_supported': ['authorization_code', 'refresh_token'],
                    'code_challenge_methods_supported': ['S256'], 'token_endpoint_auth_methods_supported': ['none'],
                    'scopes_supported': sorted(SCOPES), 'authorization_response_iss_parameter_supported': True, **self.metadata_patch}
        elif url == ENDPOINTS['registration_endpoint']:
            body = json.loads(request.content)
            assert body['token_endpoint_auth_method'] == 'none'
            assert body['grant_types'] == ['authorization_code', 'refresh_token']
            data = {'client_id': 'FIXTURE_CLIENT', 'redirect_uris': body['redirect_uris'], 'token_endpoint_auth_method': 'none'}
        elif url == ENDPOINTS['token_endpoint']:
            self.entered.set()
            if self.block:
                assert self.block.wait(5)
            if isinstance(self.token_result, Exception):
                raise self.token_result
            if self.token_result is not None:
                return self.token_result
            data = {'access_token': self.next_access, 'refresh_token': self.next_refresh, 'token_type': 'Bearer',
                    'expires_in': self.expiry, 'scope': ' '.join(sorted(SCOPES))}
        elif url == RESOURCE:
            if self.token_result is not None:
                return self.token_result
            msg = json.loads(request.content)
            data = {'jsonrpc': '2.0', 'id': msg.get('id'), 'result': {}}
        else:
            raise AssertionError('Unexpected fixture endpoint')
        return httpx.Response(200, json=data)


@pytest.fixture
def oauth(tmp_path):
    state = State(tmp_path/'state')
    vault = Vault(state, keyring_backend=Keyring())
    vault.init('keyring')
    vault.put('untouched', 'FIXTURE_ORDINARY_KEY')
    fixture = Provider()
    now = [1800000000.]
    net = Network(httpx.MockTransport(fixture), fixture_resolver)
    manager = OAuth(state, vault, net, clock=lambda: now[0])
    yield manager, fixture, now
    net.close()


def begin(manager, **kwargs):
    urls = []
    server, result = manager.begin_login(opener=lambda url: urls.append(url) or True, **kwargs)
    query = {k: v[0] for k,v in parse_qs(urls[0].split('?',1)[1]).items()} if urls else {}
    return server, result, query


def connected(oauth):
    manager, fixture, now = oauth
    server, result, query = begin(manager)
    try:
        assert result['status'] == 'pending'
        manager.callback(server.claim, {'state': query['state'], 'code': 'FIXTURE_CODE', 'iss': ISSUER})
    finally:
        server.server_close()
    return manager, fixture, now


def test_pkce_resource_encryption_and_no_key_scope_expansion(oauth):
    manager, fixture, now = oauth
    manager.state.set_setting('unchanged_project_lease', {'expires_at': now[0]+1800, 'keys':['untouched']})
    before = manager.state.setting('unchanged_project_lease')
    server, result, query = begin(manager, keep_login=True)
    try:
        assert query['code_challenge_method'] == 'S256' and len(query['code_challenge']) == 43
        assert query['resource'] == RESOURCE and set(query['scope'].split()) == SCOPES
        assert 'state' not in json.dumps(result) and 'code_challenge' not in json.dumps(result)
        _, reused = manager.begin_login(opener=lambda _: pytest.fail('duplicate browser'))
        assert reused['action'] == 'reused'
        ready = manager.callback(server.claim, {'state':query['state'], 'code':'FIXTURE_CODE', 'iss':ISSUER})
        assert ready['refreshable'] and ready['keep_login'] and ready['secrets_returned'] is False
        form = parse_qs(fixture.requests[-1].content.decode())
        import hashlib, base64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(form['code_verifier'][0].encode()).digest()).rstrip(b'=').decode()
        assert challenge == query['code_challenge'] and form['redirect_uri'][0] == server.redirect_uri and form['resource'] == [RESOURCE]
        raw = manager.state.path.read_bytes()
        for secret in ['FIXTURE_ACCESS_1', 'FIXTURE_REFRESH_1', query['state'], form['code_verifier'][0]]:
            assert secret.encode() not in raw
        assert manager.state.secret_names() == ['untouched']
        assert manager.state.setting('unchanged_project_lease') == before
        assert manager.vault.get('untouched') == 'FIXTURE_ORDINARY_KEY'
        assert manager.vault.redact({'refresh_token':'x','client_secret':'y','id_token':'z'}) == dict.fromkeys(['refresh_token','client_secret','id_token'],'[REDACTED]')
    finally:
        server.server_close()


@pytest.mark.parametrize('query_patch,code', [({'state':'wrong'},'oauth_state'), ({'state':'测试'},'oauth_state'), ({'iss':'https://wrong.invalid'},'oauth_issuer'), ({'iss':None},'oauth_issuer'), ({'code':''},'oauth_callback')])
def test_bad_callback_never_exchanges(oauth, query_patch, code):
    manager, fixture, _ = oauth
    server, _, query = begin(manager)
    try:
        fields = {'state':query['state'], 'iss':ISSUER, 'code':'FIXTURE_CODE', **query_patch}
        fields = {k:v for k,v in fields.items() if v is not None}
        with pytest.raises(RouterError, match='OAuth') as caught:
            manager.callback(server.claim, fields)
        assert caught.value.code == code
        assert not any(str(r.url)==ENDPOINTS['token_endpoint'] for r in fixture.requests)
        assert manager.status()['status'] == 'pending'
    finally:
        server.server_close()


def test_denial_and_timeout(oauth):
    manager, fixture, _ = oauth
    server, _, query = begin(manager)
    try:
        assert manager.callback(server.claim, {'state':query['state'], 'iss':ISSUER, 'error':'access_denied'})['status'] == 'denied'
        assert manager.status()['status'] == 'denied'
        assert len(fixture.requests) == 3
    finally:
        server.server_close()
    server, _, _ = begin(manager, timeout=.01)
    assert server.run()['status'] == 'needs_login'
    assert manager.status()['last_error'] == 'oauth_login_timeout'


@pytest.mark.parametrize('patch', [{'issuer':'https://other.invalid'}, {'token_endpoint':'https://other.invalid/token'}, {'code_challenge_methods_supported':['plain']}, {'grant_types_supported':['authorization_code']}, {'scopes_supported':None}])
def test_metadata_pins_and_required_capabilities(oauth, patch):
    manager, fixture, _ = oauth
    fixture.metadata_patch = patch
    with pytest.raises(RouterError) as caught:
        begin(manager)
    assert caught.value.code == 'oauth_metadata'
    assert len(fixture.requests) == 2


def test_resource_metadata_pin(oauth):
    manager, fixture, _ = oauth
    fixture.protected_patch = {'resource':'https://other.invalid/mcp'}
    with pytest.raises(RouterError) as caught:
        manager.discovery()
    assert caught.value.code == 'oauth_metadata' and len(fixture.requests) == 1


def test_refresh_rotation_reopen_and_resource_before_unlock(oauth):
    manager, fixture, now = connected(oauth)
    assert manager.refresh()['action'] == 'not_due'
    fixture.next_access, fixture.next_refresh = 'FIXTURE_ACCESS_2', 'FIXTURE_REFRESH_2'
    now[0] += 3550
    assert manager.refresh()['action'] == 'refreshed'
    form = parse_qs(fixture.requests[-1].content.decode())
    assert form == {'grant_type':['refresh_token'], 'client_id':['FIXTURE_CLIENT'], 'resource':[RESOURCE], 'refresh_token':['FIXTURE_REFRESH_1']}
    reopened = OAuth(State(manager.state.home), Vault(manager.state, keyring_backend=manager.vault.keyring_backend), manager.net, clock=manager.clock)
    assert reopened.access_token(NAME, RESOURCE) == 'FIXTURE_ACCESS_2'
    with pytest.raises(RouterError) as caught:
        reopened.access_token(NAME, 'https://other.invalid')
    assert caught.value.code == 'oauth_resource'
    now[0] += 3550
    reopened.refresh()
    assert parse_qs(fixture.requests[-1].content.decode())['refresh_token'] == ['FIXTURE_REFRESH_2']


@pytest.mark.parametrize('response,expected', [(httpx.Response(400,json={'error':'invalid_grant','error_description':'FIXTURE_REFRESH_1'}),'needs_login'),
    (httpx.Response(503,json={'error':'server_error','secret':'FIXTURE_ACCESS_1'}),'refresh_unknown'),
    (httpx.ReadTimeout('fixture'),'refresh_unknown'), (httpx.Response(200,content='not JSON'),'refresh_unknown'),
    (httpx.Response(200,json={'access_token':'bad\nheader','refresh_token':'next','expires_in':3600,'token_type':'Bearer'}),'refresh_unknown'),
    (httpx.Response(200,content='{"access_token":"next","expires_in":Infinity,"token_type":"Bearer"}'),'refresh_unknown'),
    (httpx.Response(200,content=b'['*60000),'refresh_unknown')])
def test_refresh_errors_and_no_blind_retry(oauth, response, expected):
    manager, fixture, now = connected(oauth)
    fixture.token_result = response
    now[0] += 3600
    with pytest.raises(RouterError) as caught:
        manager.refresh()
    assert 'FIXTURE_' not in json.dumps(caught.value.as_dict())
    assert manager.status()['status'] == expected
    count = len(fixture.requests)
    with pytest.raises(RouterError):
        manager.refresh(force=True)
    assert len(fixture.requests) == count


def test_refresh_no_scope_expansion_or_redirect(oauth):
    manager, fixture, now = connected(oauth)
    fixture.token_result = httpx.Response(200,json={'access_token':'next','refresh_token':'next-refresh','expires_in':3600,'token_type':'Bearer','scope':'openid email offline_access user:org:read'})
    with pytest.raises(RouterError) as caught:
        manager.refresh(force=True)
    assert caught.value.code == 'oauth_scope' and manager.status()['status'] == 'refresh_unknown'


def test_missing_refresh_token_is_observable(oauth):
    manager, fixture, _ = oauth
    fixture.token_result = httpx.Response(200,json={'access_token':'ACCESS_ONLY','token_type':'Bearer','expires_in':3600})
    server, _, query = begin(manager)
    try:
        result = manager.callback(server.claim, {'state':query['state'],'code':'FIXTURE_CODE','iss':ISSUER})
        assert not result['refreshable'] and result['last_error']=='oauth_refresh_token_missing'
        with pytest.raises(RouterError) as caught:
            manager.refresh(force=True)
        assert caught.value.code == 'oauth_needs_login'
    finally:
        server.server_close()


def test_singleflight_and_crash_claim_never_reuses_rotation(oauth, monkeypatch):
    manager, fixture, now = connected(oauth)
    fixture.block = threading.Event()
    fixture.entered.clear()
    results = []
    thread = threading.Thread(target=lambda: results.append(manager.refresh(force=True)))
    thread.start()
    assert fixture.entered.wait(5)
    with pytest.raises(RouterError):
        manager.refresh(force=True)
    fixture.block.set()
    thread.join(5)
    assert len(results) == 1
    assert sum(str(r.url)==ENDPOINTS['token_endpoint'] for r in fixture.requests)==2  # login + one rotation
    monkeypatch.setattr(manager,'_finish',lambda *a,**kw: (_ for _ in ()).throw(OSError('fixture persistence failure')))
    with pytest.raises(OSError):
        manager.refresh(force=True)
    assert manager.status()['status'] == 'refreshing'
    now[0] += 121
    assert manager.status()['status'] == 'refresh_unknown'
    count = len(fixture.requests)
    with pytest.raises(RouterError):
        manager.refresh(force=True)
    assert len(fixture.requests) == count
    server, _, _ = begin(manager, replace=True)
    server.server_close()


def test_watch_disabled_passphrase_and_keyring_failure(oauth, monkeypatch):
    manager, fixture, now = connected(oauth)
    router = Router(manager.state.home, vault=manager.vault, network=manager.net)
    assert tick(router)['action'] == 'disabled'
    cfg = manager.state.setting('vault')
    manager.state.set_setting('vault',{**cfg,'backend':'passphrase'})
    with pytest.raises(RouterError) as caught:
        manager.keep_login(enabled=True)
    assert caught.value.code == 'oauth_needs_keyring'
    manager.state.set_setting('vault',cfg)
    manager.keep_login(enabled=True)
    now[0] += 3600
    monkeypatch.setattr('agent_tool_maker.oauth_cli.OAuth',lambda *args: manager)
    monkeypatch.setattr(manager.vault,'unlock',lambda: (_ for _ in ()).throw(RouterError('keyring_unavailable','fixture keyring locked')))
    # Native clock for tick is already past this fixture expiry; no request dispatched.
    before=len(fixture.requests)
    assert tick(router)['action'] == 'paused'
    assert len(fixture.requests)==before and manager.status()['status']=='expired'


@pytest.mark.integration
def test_real_loopback_receiver_rejects_bad_host_duplicates_and_accepts_once(oauth):
    manager, fixture, _ = oauth
    server, _, query = begin(manager)
    thread=threading.Thread(target=server.run)
    thread.start()
    callback={'state':query['state'],'code':'FIXTURE_CODE','iss':ISSUER}
    with httpx.Client(trust_env=False) as client:
        assert client.get(server.redirect_uri,params=callback,headers={'Host':'evil.invalid'}).status_code==400
        assert client.get(server.redirect_uri+'?'+urlencode(callback)+'&state=second').status_code==400
        assert client.get(server.redirect_uri,params={**callback,'state':'wrong'}).status_code==400
        response=client.get(server.redirect_uri,params=callback)
        assert response.status_code==200 and response.headers['Referrer-Policy']=='no-referrer'
        assert 'FIXTURE_' not in response.text
    thread.join(5)
    assert not thread.is_alive() and manager.status()['status']=='ready'
    with pytest.raises(RouterError):
        manager.callback(server.claim,callback)


@pytest.mark.parametrize('patch',[{'url':RESOURCE+'/wrong'},{'credential':'untouched'},{'transport':'stdio'},{'allow_local':True},{'oauth':'other'}])
def test_mcp_oauth_binding_exact_resource(oauth, patch):
    manager, _, _ = oauth
    with pytest.raises(RouterError) as caught:
        bind_server(manager.state,'fixture',{'transport':'http','url':RESOURCE,'oauth':NAME,'allow_tools':[],**patch})
    assert caught.value.code=='oauth_resource'


def test_mcp_internal_bearer_never_replays_401(oauth):
    manager, fixture, _ = connected(oauth)
    cfg={'transport':'http','url':RESOURCE,'oauth':NAME,'allow_tools':[]}
    bind_server(manager.state,'fixture',cfg)
    # Use fixture clock for pre-request admission.
    conn=HTTP(cfg,manager.vault,manager.net)
    conn.oauth=manager
    assert conn.exchange({'id':1,'method':'initialize'})['result']=={}
    assert fixture.requests[-1].headers['Authorization']=='Bearer FIXTURE_ACCESS_1'
    fixture.token_result=httpx.Response(401,json={'secret':'FIXTURE_ACCESS_1'})
    before=len(fixture.requests)
    with pytest.raises(RouterError) as caught:
        conn.exchange({'id':2,'method':'tools/call'})
    assert caught.value.code=='mcp_http' and caught.value.uncertain
    assert len(fixture.requests)==before+1


def test_launchd_explicit_idempotent_no_secrets_and_conflict(oauth,tmp_path):
    manager, _, _ = oauth
    exe=tmp_path/'atm';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o700)
    calls=[]
    loaded=[False]
    def runner(args,**kwargs):
        calls.append(args)
        if args[1]=='bootstrap':
            loaded[0]=True
        output='arguments = {\n'+ '\n'.join([str(exe),'--home',str(manager.state.home),'oauth','watch','--once'])+'\n}\n'
        return subprocess.CompletedProcess(args,0 if loaded[0] else 1,output.encode(),b'')
    kwargs={'executable':str(exe),'user_home':tmp_path/'user','platform':'darwin','runner':runner}
    plan=install_service(manager.state,**kwargs)
    assert not Path(plan['path']).exists() and not calls
    result=install_service(manager.state,apply=True,**kwargs)
    content=Path(result['path']).read_bytes()
    cfg=plistlib.loads(content)
    assert cfg['ProgramArguments']==[str(exe),'--home',str(manager.state.home),'oauth','watch','--once']
    assert cfg['StartInterval']==60 and 'FIXTURE_' not in content.decode()
    assert Path(result['path']).stat().st_mode & 0o777 == 0o600
    install_service(manager.state,apply=True,**kwargs)
    Path(result['path']).write_bytes(b'fixture changed plist')
    with pytest.raises(RouterError) as caught:
        install_service(manager.state,apply=True,**kwargs)
    assert caught.value.code=='oauth_service_conflict'


@pytest.mark.integration
def test_subprocess_metadata_only_restart(tmp_path):
    home=tmp_path/'restart'
    state=State(home)
    vault=Vault(state,password='fixture-long-passphrase')
    vault.init('passphrase')
    fixture=Provider()
    network=Network(httpx.MockTransport(fixture),fixture_resolver)
    manager=OAuth(state,vault,network)
    connected((manager,fixture,None))
    script='''import json, sys, httpx
from pathlib import Path
from urllib.parse import parse_qs
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault
from agent_tool_maker.network import Network
from agent_tool_maker.demo import fixture_resolver
from agent_tool_maker.oauth import OAuth, RESOURCE
state=State(Path(sys.argv[1]));vault=Vault(state,password="fixture-long-passphrase")
calls=[]
def fixture(request):
    calls.append(parse_qs(request.content.decode()))
    return httpx.Response(200,json={"access_token":"RESTART_ACCESS","refresh_token":"RESTART_REFRESH","expires_in":3600,"token_type":"Bearer"})
network=Network(httpx.MockTransport(fixture),fixture_resolver)
connection=OAuth(state,vault,network)
connection.refresh(force=True)
print(json.dumps({"status":connection.status()["status"],"rotated":connection.access_token("higgsfield",RESOURCE)=="RESTART_ACCESS","used_previous":calls[0]["refresh_token"]==["FIXTURE_REFRESH_1"]}))
network.close()
'''
    child=tmp_path/'restart.py';child.write_text(script)
    result=subprocess.run([sys.executable,str(child),str(home)],capture_output=True,text=True,env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'status':'ready','rotated':True,'used_previous':True}
    assert 'RESTART_ACCESS' not in state.path.read_bytes().decode(errors='ignore')
    network.close()


def test_refresh_omitted_rotation_retains_old_token(oauth):
    manager, fixture, _ = connected(oauth)
    fixture.token_result=httpx.Response(200,json={'access_token':'FIXTURE_NEW_ACCESS','expires_in':3600,'token_type':'Bearer'})
    manager.refresh(force=True)
    manager.refresh(force=True)
    assert parse_qs(fixture.requests[-1].content.decode())['refresh_token']==['FIXTURE_REFRESH_1']


def test_cookie_redirect_and_bounded_json(oauth):
    manager, fixture, _ = connected(oauth)
    manager.net.client.cookies.set('session','FIXTURE_COOKIE',domain='clerk.higgsfield.ai')
    fixture.token_result=httpx.Response(302,json={'error':'unknown'},headers={'Location':'https://other.invalid/token'})
    count=len(fixture.requests)
    with pytest.raises(RouterError):
        manager.refresh(force=True)
    assert len(fixture.requests)==count+1
    assert 'Cookie' not in fixture.requests[-1].headers
    fixture.token_result=httpx.Response(200,content=b' '*65537)
    with pytest.raises(RouterError) as caught:
        manager._request('POST',ENDPOINTS['token_endpoint'],body={})
    assert caught.value.code=='oauth_response' and caught.value.uncertain


@pytest.mark.integration
def test_web_owner_login_worker_and_contracts(oauth,tmp_path,monkeypatch):
    from agent_tool_maker.webapp import Console
    manager, fixture, _ = oauth
    opened=[]
    monkeypatch.setattr('agent_tool_maker.oauth.webbrowser.open',lambda url: opened.append(url) or True)
    def factory(password=None):
        vault=Vault(manager.state,keyring_backend=manager.vault.keyring_backend,password=password)
        return Router(manager.state.home,vault=vault,network=Network(httpx.MockTransport(fixture),fixture_resolver))
    monkeypatch.setattr('agent_tool_maker.oauth_web.Router',lambda _: factory())
    exe=tmp_path/'atm';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o700)
    console=Console(manager.state.home,executable=str(exe),user_home=tmp_path/'user',router_factory=factory)
    thread=threading.Thread(target=console.serve_forever,daemon=True);thread.start()
    headers={'Authorization':'Bearer '+console.token,'Origin':console.origin}
    try:
        with httpx.Client(base_url=console.origin,trust_env=False) as client:
            assert client.post('/api/oauth/login',json={'provider':NAME}).status_code==401
            assert client.post('/api/oauth/login',headers=headers,json={'provider':NAME,'access_token':'bad'}).status_code==400
            assert client.post('/api/oauth/login',headers=headers,json={'provider':'other'}).status_code==400
            response=client.post('/api/oauth/login',headers=headers,json={'provider':NAME})
            assert response.status_code==200 and response.json()['browser_opened']
            query={k:v[0] for k,v in parse_qs(opened[0].split('?',1)[1]).items()}
            assert client.post('/api/oauth/login',headers=headers,json={'provider':NAME}).json()['browser_opened'] is False
            assert len(opened)==1
            assert httpx.get(query['redirect_uri'],params={'code':'FIXTURE_CODE','state':query['state'],'iss':ISSUER},trust_env=False).status_code==200
            result=client.get('/api/connections',headers=headers)
            assert result.json()['oauth'][0]['status']=='ready'
            assert 'FIXTURE_ACCESS' not in result.text and 'FIXTURE_REFRESH' not in result.text
            assert client.post('/api/oauth/keep-login',headers=headers,json={'provider':NAME,'enabled':False}).json()['keep_login'] is False
            source=client.get('/assets/app.js').text
            assert 'ATM OAuth' in source and '/api/oauth/login' in source
    finally:
        console.shutdown();console.server_close();thread.join(5)


def test_encrypted_payload_tamper_is_exposed(oauth):
    manager, fixture, _ = connected(oauth)
    with manager.state.db() as db:
        db.execute('UPDATE oauth_connections SET ciphertext=?',(b'fixture corrupted cipher',))
    count=len(fixture.requests)
    with pytest.raises(RouterError) as caught:
        manager.refresh(force=True)
    assert caught.value.code=='oauth_corrupt' and len(fixture.requests)==count
    assert manager.state.secret_names()==['untouched']


def test_login_race_preserves_newly_connected_tokens(oauth,monkeypatch):
    import agent_tool_maker.oauth as module
    manager, fixture, _ = oauth
    b, _, query = begin(manager)
    original_status=manager.status
    first=[True]
    def stale_status(*args):
        if first[0]:
            first[0]=False
            return {'status':'missing'}
        return original_status(*args)
    monkeypatch.setattr(manager,'status',stale_status)
    original_server=module.LoginServer
    def interleave(*args,**kwargs):
        manager.callback(b.claim,{'state':query['state'],'code':'FIXTURE_CODE','iss':ISSUER})
        return original_server(*args,**kwargs)
    monkeypatch.setattr(module,'LoginServer',interleave)
    try:
        with pytest.raises(RouterError) as caught:
            begin(manager)
        assert caught.value.code=='oauth_conflict'
        assert manager.access_token(NAME,RESOURCE)=='FIXTURE_ACCESS_1'
        assert len(fixture.requests)==4
    finally:
        b.server_close()


def test_service_race_and_loaded_arguments_are_not_success(oauth,tmp_path,monkeypatch):
    manager, _, _ = oauth
    exe=tmp_path/'atm';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o700)
    kwargs={'executable':str(exe),'user_home':tmp_path/'user','platform':'darwin'}
    plan=install_service(manager.state,**kwargs)
    target=Path(plan['path'])
    original=Path.exists
    count=[0]
    def exists(path):
        if path==target:
            count[0]+=1
            if count[0]==2:
                target.write_bytes(b'fixture concurrent different program')
        return original(path)
    monkeypatch.setattr(Path,'exists',exists)
    with pytest.raises(RouterError) as caught:
        install_service(manager.state,apply=True,runner=lambda *a,**kw: pytest.fail('must not load'),**kwargs)
    assert caught.value.code=='oauth_service_conflict'
    assert manager.state.setting('oauth_service') is None
    # Preserve the conflicting plist as a fixture receipt, then simulate a wrong loaded service.
    target.rename(target.with_suffix('.conflict-fixture'))
    monkeypatch.setattr(Path,'exists',original)
    runner=lambda args,**kw: subprocess.CompletedProcess(args,0,b'arguments = {\n/OTHER/atm\n}\n',b'')
    with pytest.raises(RouterError) as caught:
        install_service(manager.state,apply=True,runner=runner,**kwargs)
    assert caught.value.code=='oauth_service_conflict'
    assert manager.state.setting('oauth_service')['status']=='load_conflict'


def test_proxy_reserved_dns_is_explicit_and_sends_nothing(oauth,monkeypatch):
    import socket
    manager, fixture, _ = oauth
    monkeypatch.setattr(manager.net,'resolver',lambda *a,**kw:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('198.18.0.144',443))])
    with pytest.raises(RouterError) as caught:
        manager.discovery()
    assert caught.value.code=='oauth_dns_policy' and not caught.value.uncertain
    assert not fixture.requests
