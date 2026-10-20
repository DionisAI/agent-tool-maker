import json
import os
from pathlib import Path
import socket
import threading
import time

import httpx
import pytest
from agent_tool_maker.engine import Router
from agent_tool_maker import management as mg
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault
from agent_tool_maker.webapp import Console, MAX_BODY


@pytest.fixture
def console(tmp_path,monkeypatch):
    monkeypatch.delenv('CLAUDE_CONFIG_DIR',raising=False)
    exe=tmp_path/'atm';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o700)
    server=Console(tmp_path/'state',executable=str(exe),user_home=tmp_path/'user')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with httpx.Client(base_url=server.origin,timeout=20,trust_env=False) as client:
        yield server,client
    token_path=server.token_path
    server.shutdown();server.server_close();thread.join(timeout=5)
    assert not token_path.exists()


def get(console,path='/api/overview',**kw):
    server,client=console
    headers={'Authorization':'Bearer '+server.token,**kw.pop('headers',{})}
    return client.get(path,headers=headers,**kw)


def post(console,path,body,**kw):
    server,client=console
    headers={'Authorization':'Bearer '+server.token,'Origin':server.origin,**kw.pop('headers',{})}
    return client.post(path,json=body,headers=headers,**kw)


def test_public_shell_contains_no_local_data_or_token(console):
    server,client=console
    r=client.get('/')
    assert r.status_code==200 and 'Agent Tool Maker' in r.text
    assert str(server.home) not in r.text and server.token not in r.text
    assert r.headers['Cache-Control']=='no-store' and "frame-ancestors 'none'" in r.headers['Content-Security-Policy']
    assert 'Access-Control-Allow-Origin' not in r.headers
    for route in ['/assets/app.js','/assets/app.css','/assets/brands.js','/assets/brand-data.js']:
        r=client.get(route);assert r.status_code==200 and server.token not in r.text
    if os.name=='posix':assert server.token_path.stat().st_mode & 0o777==0o600


def test_bootstrap_connection_burst_is_queued_before_accept(tmp_path):
    """The UI opens ten metadata requests; accept scheduling must not reset them."""
    import http.client
    server=Console(tmp_path/'state',localhost=True)
    clients=[];thread=None
    try:
        # Hold accept until the complete bounded browser bootstrap is queued.
        # This makes a backlog smaller than the burst fail without a race/retry.
        for _ in range(10):
            clients.append(socket.create_connection(('127.0.0.1',server.server_port),timeout=2))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        for connection in clients:
            connection.sendall(('GET / HTTP/1.0\r\nHost: '+server.authority+'\r\n\r\n').encode())
        for connection in clients:
            response=http.client.HTTPResponse(connection);response.begin()
            assert response.status==200
            assert b'/assets/passkeys.js' in response.read()
            response.close()
    finally:
        for connection in clients:connection.close()
        if thread:server.shutdown();thread.join(5)
        server.server_close()


@pytest.mark.parametrize('path',['/api/overview','/api/agents','/api/tools','/api/connections','/api/clis','/api/jobs'])
def test_private_data_requires_per_process_bearer(console,path):
    server,client=console
    assert client.get(path).status_code==401
    assert get(console,path,headers={'Authorization':'Bearer wrong'}).status_code==401
    assert get(console,path).status_code==200


@pytest.mark.parametrize('headers',[
    {'Host':'evil.example'}, {'Origin':'https://evil.example'}, {'Origin':'null'},
    {'Origin':'http://127.0.0.1:1'}, {'Sec-Fetch-Site':'cross-site'}, {'Sec-Fetch-Site':'same-site'},
])
def test_localhost_security_rejects_wrong_host_or_origin(console,headers):
    assert get(console,headers=headers).status_code==403
    assert post(console,'/api/tools/toggle',{'tool':'fal.generate','enabled':False,'expected_enabled':True},headers=headers).status_code==403


def test_post_requires_origin_and_no_form_or_query_token(console):
    server,client=console
    r=client.post('/api/setup/preview',json={},headers={'Authorization':'Bearer '+server.token})
    assert r.status_code==403
    r=client.post('/api/setup/preview',content='agents=claude',headers={'Authorization':'Bearer '+server.token,'Origin':server.origin,'Content-Type':'application/x-www-form-urlencoded'})
    assert r.status_code==400
    assert get(console,'/api/overview?token='+server.token).status_code==403
    assert client.options('/api/tools/toggle').status_code==403


def test_no_arbitrary_execution_or_file_endpoint(console):
    for path in ['/api/run','/api/shell','/api/jobs/refresh','/api/files','/api/secret/get']:
        assert post(console,path,{}).status_code==404
    assert get(console,'/state.sqlite3').status_code==404


def test_malformed_large_json_and_unknown_fields(console):
    server,client=console
    h={'Authorization':'Bearer '+server.token,'Origin':server.origin,'Content-Type':'application/json'}
    for body in ['[]','{"x":NaN}','{','x'*(MAX_BODY+1)]:
        assert client.post('/api/setup/preview',content=body,headers=h).status_code==400
    assert post(console,'/api/setup/preview',{'command':'evil'}).status_code==400
    assert post(console,'/api/setup/preview',{'agents':['evil']}).status_code==400
    assert post(console,'/api/tools/toggle',{'tool':'fal.generate','enabled':'false','expected_enabled':True}).status_code==400


def test_duplicate_sensitive_headers_are_rejected(console):
    server,client=console
    r=client.get('/api/overview',headers=[('Authorization','Bearer '+server.token),('Authorization','Bearer '+server.token)])
    assert r.status_code==403


def test_expired_session_cannot_read_state(console):
    server,client=console
    server.expires_at=time.monotonic()-1
    assert get(console).status_code==401


def test_expiry_is_reported_only_to_the_matching_bearer(console):
    server,client=console
    server.expires_at=time.monotonic()-1
    r=get(console)
    assert r.status_code==401 and r.json()['error']['code']=='session_expired'
    for wrong in ({'Authorization':'Bearer wrong'},{}):
        r=client.get('/api/overview',headers=wrong)
        assert r.status_code==401 and r.json()['error']['code']=='unauthorized'


def test_web_setup_uses_default_agents_and_shared_state(console):
    server,client=console
    plan=post(console,'/api/setup/preview',{}).json()
    assert [x['agent'] for x in plan['skills']]==['claude','codex']
    assert not Path(plan['skills'][0]['path']).exists()
    assert post(console,'/api/setup/apply',{'approved_sha256':'wrong'}).status_code==409
    r=post(console,'/api/setup/apply',{'approved_sha256':plan['plan_sha256']})
    assert r.status_code==200 and r.json()['applied']
    plan2=post(console,'/api/setup/preview',{}).json()
    assert all(x['action']=='unchanged' for x in plan2['skills'])
    assert post(console,'/api/setup/apply',{'approved_sha256':plan2['plan_sha256']}).status_code==200
    r=Router(server.home)
    try:assert all(a['state']=='registered_not_host_verified' for a in mg.agents(r)['agents'])
    finally:r.close()
    assert post(console,'/api/agents/unregister',{'agent':'codex','confirm':'not-codex'}).status_code==400
    assert post(console,'/api/agents/unregister',{'agent':'codex','confirm':'codex'}).status_code==200


def test_tool_toggle_is_enforced_and_visible_to_separate_router(console):
    server,client=console
    body={'tool':'fal.generate','enabled':False,'expected_enabled':True}
    assert post(console,'/api/tools/toggle',body).status_code==200
    assert post(console,'/api/tools/toggle',body).status_code==409
    r=Router(server.home)
    try:
        assert r.readiness(r.catalog.get('fal.generate'))=='disabled'
        mg.set_enabled(r,'fal.generate',True,apply=True)
    finally:r.close()
    assert get(console,'/api/tools/fal.generate').json()['enabled'] is True


def test_web_secret_is_write_only_encrypted_and_not_cached(console):
    server,client=console
    password='private-test-passphrase-v04'
    assert post(console,'/api/vault/init',{'backend':'passphrase','passphrase':password}).status_code==200
    secret='PRIVATE-VENDOR-CREDENTIAL-v04'
    body={'provider':'elevenlabs','value':secret,'passphrase':password}
    saved=post(console,'/api/connections/save',body)
    assert saved.status_code==200 and saved.json()['saved_encrypted']
    for route in ['/api/overview','/api/connections','/api/tools','/api/jobs']:
        r=get(console,route);assert r.status_code==200
        assert secret not in r.text and password not in r.text
    assert secret.encode() not in (server.home/'state.sqlite3').read_bytes()
    state=State(server.home)
    assert Vault(state,password=password).get('elevenlabs')==secret
    assert post(console,'/api/connections/save',{'provider':'elevenlabs','value':'SHOULD-NOT-REPLACE'}).json()['status']=='already_configured'
    # Unlock is request-scoped, not retained by the server.
    rejected=post(console,'/api/connections/save',{'provider':'fal','value':'test-new'})
    assert rejected.status_code==400 and rejected.json()['error']['code']=='needs_unlock'
    assert get(console,'/api/connections').json()['vault']['state']=='needs_unlock'
    assert post(console,'/api/connections/remove',{'provider':'elevenlabs','confirm':'elevenlabs','passphrase':password}).status_code==200
    assert 'elevenlabs' not in state.secret_names()
    assert post(console,'/api/vault/init',{'backend':'passphrase','passphrase':password}).status_code==400


def test_verification_is_preview_only_without_opt_in(console):
    r=post(console,'/api/verify',{'provider':'elevenlabs'}).json()
    assert r['status']=='planned' and r['network_calls']==0 and not r['secrets_read']
    r=post(console,'/api/verify',{'provider':'fal','allow_network':True}).json()
    assert r['status']=='unsupported_probe' and r['network_calls']==0


def test_sensitive_job_details_never_reach_web(console,tmp_path):
    server,_=console
    r=Router(server.home)
    try:
        job,_=r.state.create_job('fal.generate',{'prompt':'PRIVATE-PROMPT'},tmp_path,None)
        r.state.update_job(job['id'],'running',payload={'authorization':'PRIVATE-TOKEN'},status_url='PRIVATE-URL')
    finally:r.close()
    response=get(console,'/api/jobs')
    assert response.status_code==200
    assert all(x not in response.text for x in ['PRIVATE-PROMPT','PRIVATE-TOKEN','PRIVATE-URL'])


@pytest.mark.parametrize('port',[-1,65536,'8080',True])
def test_invalid_bind_configuration_cannot_expose_network(tmp_path,port):
    with pytest.raises(Exception):Console(tmp_path/'state',port=port)


def test_server_never_logs_token_or_secret(console,capsys):
    server,client=console
    get(console,headers={'Authorization':'Bearer SHOULD-NOT-LOG'})
    post(console,'/api/connections/save',{'provider':'not-real','value':'SHOULD-NOT-LOG'})
    out=capsys.readouterr()
    assert 'SHOULD-NOT-LOG' not in out.out+out.err and server.token not in out.out+out.err


def test_secret_export_and_bulk_environment_import_are_not_exposed(console):
    for path in ['/api/connections/export','/api/vault/export','/api/env/import']:
        assert post(console,path,{}).status_code==404


@pytest.mark.parametrize('failure', [BrokenPipeError, ConnectionResetError])
@pytest.mark.parametrize('phase', ['headers', 'body'])
def test_response_client_disconnect_is_not_retried(failure,phase):
    from agent_tool_maker.webapp import Handler
    from types import SimpleNamespace
    handler=object.__new__(Handler)
    events=[]
    def disconnect():
        events.append('disconnect')
        raise failure('client closed')
    handler.send_response=lambda status:events.append(status)
    handler.send_header=lambda *args:None
    handler.end_headers=disconnect if phase=='headers' else lambda:None
    handler.wfile=SimpleNamespace(write=lambda raw:disconnect())
    handler.respond(200,{'ok':True})
    assert events==[200,'disconnect']
    assert handler.close_connection is True


@pytest.mark.parametrize('route', ['/', '/assets/app.js', '/assets/app.css', '/assets/brands.js', '/assets/brand-data.js'])
def test_static_assets_work_with_python311_single_child_traversable(console, monkeypatch, route):
    # CPython 3.11 namespace resources accept exactly one joinpath child.
    # Keep actual files/HTTP execution, replacing only that versioned interface.
    from agent_tool_maker import webapp
    original_files = webapp.files
    class SingleChildPath:
        def __init__(self, path): self.path = path
        def joinpath(self, child): return SingleChildPath(self.path.joinpath(child))
        def read_bytes(self): return self.path.read_bytes()
    monkeypatch.setattr(webapp, 'files', lambda package: SingleChildPath(original_files(package)))
    response = console[1].get(route)
    assert response.status_code == 200
    assert len(response.content) > 100
