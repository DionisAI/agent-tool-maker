import hashlib
import json
from pathlib import Path
import threading

import httpx
import pytest
from agent_tool_maker.webapp import Console
from agent_tool_maker.storage import State,canonical
from agent_tool_maker.vault import Vault
from agent_tool_maker.sync import Sync

PW='Only-Test-MultiDevice-Password'

@pytest.fixture
def web(tmp_path):
    server=Console(tmp_path/'state',executable=__import__('shutil').which('atm'),user_home=tmp_path/'user')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with httpx.Client(base_url=server.origin,trust_env=False,timeout=30,headers={'Authorization':'Bearer '+server.token,'Origin':server.origin}) as client:
        assert client.post('/api/vault/init',json={'backend':'passphrase','passphrase':PW}).status_code==200
        yield server,client
    server.shutdown();thread.join(10);server.server_close()


def test_sync_ui_import_export_and_conflict_resolution(web,tmp_path):
    server,client=web
    remote=Sync(Vault(State(tmp_path/'remote'),password=PW));remote.vault.init('passphrase');remote.initialize('server');remote.vault.put('fal','FAKE-server')
    r=client.post('/api/sync/init',json={'name':'laptop','passphrase':PW});assert r.status_code==200
    own=r.json()['device']
    remote.trust(own,own['id'],send=['fal'],receive=['fal'],apply=True)
    trust={'card':remote.identity(),'fingerprint':remote.identity()['id'],'send':['fal'],'receive':['fal']}
    assert client.post('/api/sync/trust',json=trust).json()['applied'] is False
    assert client.post('/api/sync/trust',json={**trust,'apply':True}).status_code==200
    assert client.post('/api/connections/save',json={'provider':'fal','value':'FAKE-local','passphrase':PW}).status_code==200
    packet=remote.export_packet(own['id'])
    preview=client.post('/api/sync/import',json={'packet':packet,'passphrase':PW}).json()
    assert preview['conflicts']==1 and not preview['applied']
    assert client.post('/api/sync/import',json={'packet':packet,'passphrase':PW,'apply':True}).status_code==200
    summary=client.get('/api/sync').json();assert summary['conflicts']==1 and 'FAKE-' not in canonical(summary)
    conflict=summary['records'][0]
    result=client.post('/api/sync/resolve',json={'provider':'fal','choose':conflict['heads'][0]['revision'],'expected':conflict['expected'],'apply':True,'passphrase':PW})
    assert result.status_code==200
    assert client.get('/api/sync').json()['conflicts']==0
    out=client.post('/api/sync/export',json={'device':remote.identity()['id'],'passphrase':PW})
    assert out.status_code==200 and 'FAKE-' not in out.text and 'private' not in canonical(out.json()['encrypted_packet'])
    remote.import_packet(out.json()['encrypted_packet'],apply=True)
    assert remote.status()['conflicts']==0


def test_access_ui_digest_bound_grant_no_token_response(web,tmp_path):
    server,client=web;work=tmp_path/'project';work.mkdir()
    body={'agent':'claude','tools':['ffmpeg.probe'],'workspace':str(work),'ttl_hours':24}
    preview=client.post('/api/access/grant',json=body).json()
    assert not preview['applied']
    bad=client.post('/api/access/grant',json={**body,'apply':True,'approved_sha256':'0'*64})
    assert bad.status_code==400
    response=client.post('/api/access/grant',json={**body,'apply':True,'approved_sha256':preview['approval_sha256']})
    assert response.status_code==200
    data=response.json();profile=Path(data['profile']);secret=json.loads(profile.read_text())['token']
    assert secret not in response.text and secret not in client.get('/api/access').text
    assert profile.stat().st_mode&0o077==0
    revoked=client.post('/api/access/revoke',json={'id':data['id'],'confirm':data['id']})
    assert revoked.status_code==200 and client.get('/api/access').json()['grants'][0]['revoked']


@pytest.mark.parametrize('path',['/api/sync','/api/access'])
def test_metadata_requires_owner_console_auth(web,path):
    server,client=web
    assert client.get(path,headers={'Authorization':'Bearer nope'}).status_code==401


def test_sync_owner_mutation_rejects_cross_origin(web):
    _,c=web
    assert c.post('/api/sync/init',json={'name':'x','passphrase':PW},headers={'Origin':'https://evil.example'}).status_code==403


def test_secret_conflict_does_not_return_key_to_web(web,tmp_path):
    _,c=web
    assert c.post('/api/sync/init',json={'name':'local','passphrase':PW}).status_code==200
    assert c.post('/api/sync/resolve',json={'provider':'fal','choose':'x','expected':'x','apply':True,'passphrase':PW}).status_code==400
    assert PW not in c.get('/api/access').text


def test_new_owner_routes_do_not_run_broker_or_shell(web):
    _,c=web
    for path in ['/api/broker/start','/api/access/run','/api/sync/shell']:
        assert c.post(path,json={}).status_code==404


def test_access_preview_binds_tool_configuration_not_only_names(web,tmp_path):
    server,client=web;work=tmp_path/'project';work.mkdir()
    body={'agent':'claude','tools':['ffmpeg.probe'],'workspace':str(work),'ttl_hours':24}
    preview=client.post('/api/access/grant',json=body).json()
    # Another owner-side operation changes the approved executable after preview.
    State(server.home).set_setting('cli:ffprobe','/different/review-required-program')
    response=client.post('/api/access/grant',json={**body,'apply':True,'approved_sha256':preview['approval_sha256']})
    assert response.status_code==400 and response.json()['error']['code']=='plan_changed'
    assert client.get('/api/access').json()['grants']==[]


def test_access_lists_pending_window_requests_and_the_console_cannot_answer_them(web,tmp_path):
    import time
    from test_quickstart_v08 import seed_requests
    server,client=web;root=tmp_path.resolve()
    assert client.get('/api/access').json()['requests']==[]
    made=seed_requests(State(server.home),root,time.time())
    access=client.get('/api/access')
    assert access.status_code==200
    rows=access.json()['requests']
    # The malformed records seeded alongside are skipped; /api/access still answers 200.
    assert [row['id'] for row in rows]==[made['stale'][0],made['fresh'][0],made['odd-beat'][0]]
    assert [row['live'] for row in rows]==[False,True,False]
    assert all(set(row)=={'id','workspace','credentials','status','created_at','expires_at','live'} for row in rows)
    for leak in ('FAKE-LAUNCH','FAKE-WINDOW-TOKEN','localhost:1','approval_sha256'):
        assert leak not in access.text
    # No console endpoint takes a request id: the approval window's API is not served on the console port.
    for path in ['/api/desktop','/api/desktop/approve','/api/desktop/cancel','/api/desktop/lock','/api/desktop/passkey/begin']:
        body={'id':made['fresh'][0],'approved_sha256':'0'*64,'consent':True}
        assert client.post(path,json=body).status_code==404
    assert client.get('/api/desktop').status_code==404
    assert State(server.home).setting('desktop-request:'+made['fresh'][0])['status']=='needs_unlock'
