"""One local consent -> fresh clients -> edited ordinary program; fake Keys only."""
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from agent_tool_maker import quickstart_web, webapp
from agent_tool_maker.broker import call, revoke
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.quickstart import (PENDING_SECONDS, profile_path, scope_plan, ready, start, use, request_record)
from agent_tool_maker.quickstart_web import ApprovalWindow, serve_request
from agent_tool_maker.secrets_provider import fingerprint
from agent_tool_maker.session import owner_call, status, SecretSession, run_service
from agent_tool_maker.storage import State, canonical
from agent_tool_maker.vault import Vault

PASSWORD='fake-only-password-08'
KEY='fake-key-08-do-not-use-in-production'


@pytest.fixture
def window():
    with tempfile.TemporaryDirectory(prefix='aq8-') as td:
        root=Path(td).resolve(); r=Router(root/'s');r.vault=Vault(r.state,password=PASSWORD)
        r.vault.init('passphrase');r.vault.put('fal',KEY)
        w=root/'project';w.mkdir();(w/'app.py').write_text('import os;print(os.environ["FAL_KEY"]);print("SUCCESS")')
        plan=scope_plan(r.state,w,['fal']); ident=uuid.uuid4().hex
        r.state.set_setting('desktop-request:'+ident,{'id':ident,**plan,'status':'needs_unlock','created_at':time.time(),
                            'approval_sha256':fingerprint(plan),'heartbeat':time.time()})
        ui=ApprovalWindow(r.state.home,ident)
        thread=threading.Thread(target=ui.serve_forever,daemon=True);thread.start()
        client=httpx.Client(base_url=ui.origin,headers={'Authorization':'Bearer '+ui.token,'Origin':ui.origin},trust_env=False)
        try:
            yield r,w,ui,client,root
        finally:
            client.close();ui.shutdown();ui.server_close();thread.join(5);r.close()


def approval(ui, **kw):
    return {'approved_sha256':fingerprint(ui.plan),'consent':True,'passphrase':PASSWORD,'credentials':{},**kw}


def approve(window):
    r,w,ui,c,root=window
    response=c.post('/api/desktop/approve',json=approval(ui))
    assert response.status_code==200,response.text
    assert response.json()['status']=='ready'
    return response.json()


def test_unapproved_request_does_not_release_credentials(window):
    r,w,ui,c,root=window
    assert ready(r.state,w) is None
    assert status(r.state.home)['unlocked'] is False
    response=c.get('/api/desktop');assert response.status_code==200
    assert KEY not in response.text and PASSWORD not in response.text
    assert not profile_path(r.state,w).exists()


def test_one_password_two_new_processes_and_edited_program(window):
    r,w,ui,c,root=window; result=approve(window)
    assert 1700 < result['seconds_remaining'] <= 1800
    clean={k:v for k,v in os.environ.items() if k not in {'FAL_KEY','ATM_VAULT_PASSWORD','ATR_VAULT_PASSWORD'}}
    for i in range(2):
        if i: (w/'app.py').write_text('import os;print("NEW_CODE",bool(os.environ["FAL_KEY"]))')
        p=subprocess.run([sys.executable,'-m','agent_tool_maker','--home',str(r.state.home),'use',
              '--workspace',str(w),'--env','FAL_KEY=atm://fal','--request-key','fresh-'+str(i),'--',sys.executable,'app.py'],
              env=clean,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
        assert p.returncode==0,p.stdout+p.stderr
        data=json.loads(p.stdout);assert data['status']=='completed'
        assert KEY not in p.stdout and PASSWORD not in p.stdout
        assert 'SUCCESS' in data['stdout'] if i==0 else 'NEW_CODE True' in data['stdout']
    assert not (w/'.env').exists()
    assert ready(r.state,w,['fal'])['status']=='ready'
    assert len([j for j in r.state.jobs() if j['tool']=='atm.exec'])==2


def test_repeat_start_reuses_consent_does_not_spawn_or_extend(window,monkeypatch):
    r,w,ui,c,root=window;approve(window)
    before=status(r.state.home)['seconds_remaining']
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('should not spawn'))
    result=start(r.state.home,w,names=['fal'])
    assert result['status']=='ready' and result['seconds_remaining']<=before


def test_missing_key_is_added_in_same_password_window(window):
    r,w,ui,c,root=window
    ui.plan=scope_plan(r.state,w,['newservice.production'])
    ui.record.update(credentials=ui.plan['credentials'],approval_sha256=fingerprint(ui.plan))
    data=c.get('/api/desktop').json();assert data['connections'][0]['state']=='missing_credential'
    response=c.post('/api/desktop/approve',json=approval(ui,credentials={'newservice.production':'fake-new-v08'}))
    assert response.status_code==200,response.text
    assert Vault(r.state,password=PASSWORD).get('newservice.production')=='fake-new-v08'
    assert 'fake-new-v08' not in response.text
    assert ready(r.state,w,['newservice.production'])['status']=='ready'


def test_first_run_initializes_without_terminal_commands(tmp_path):
    with tempfile.TemporaryDirectory(prefix='first8-') as td:
        root=Path(td);r=Router(root/'s');w=root/'p';w.mkdir()
        plan=scope_plan(r.state,w,['fal']);ident=uuid.uuid4().hex
        r.state.set_setting('desktop-request:'+ident,{'id':ident,**plan,'status':'needs_unlock','created_at':time.time(),'approval_sha256':fingerprint(plan)})
        ui=ApprovalWindow(r.state.home,ident);t=threading.Thread(target=ui.serve_forever,daemon=True);t.start()
        try:
            with httpx.Client(base_url=ui.origin,headers={'Authorization':'Bearer '+ui.token,'Origin':ui.origin},trust_env=False) as c:
                response=c.post('/api/desktop/approve',json=approval(ui,confirm_password=PASSWORD,credentials={'fal':KEY}))
                assert response.status_code==200,response.text
                assert Vault(r.state,password=PASSWORD).get('fal')==KEY
        finally:
            ui.shutdown();ui.server_close();t.join(5)


@pytest.mark.parametrize('change',[
    {'passphrase':'wrong-password-long'}, {'approved_sha256':'0'*64}, {'consent':False},
    {'credentials':{'unexpected':'fake'}}, {'credentials':{'fal':'replacement-not-authorized'}},
])
def test_bad_approval_does_not_unlock_or_replace(window,change):
    r,w,ui,c,root=window
    response=c.post('/api/desktop/approve',json=approval(ui,**change))
    assert response.status_code>=400
    assert status(r.state.home)['unlocked'] is False
    assert not profile_path(r.state,w).exists()
    assert r.vault.get('fal')==KEY


@pytest.mark.parametrize('header,value',[('Origin','https://evil.example'),('Host','evil.example'),('Authorization','Bearer fake')])
def test_window_rejects_csrf_and_wrong_bearer(window,header,value):
    r,w,ui,c,root=window
    response=c.post('/api/desktop/approve',json=approval(ui),headers={header:value})
    assert response.status_code in (401,403)
    assert not profile_path(r.state,w).exists()


def test_window_trades_a_launch_code_once_at_its_exact_origin(window):
    r,w,ui,c,root=window
    code=ui.launch_code()
    with httpx.Client(base_url=ui.origin,trust_env=False) as plain:
        redeem=lambda **headers:plain.post('/api/console/redeem',json={'code':code},headers=headers)
        # No bearer, but the exact Origin and Host; a refused attempt does not use the code up.
        assert redeem().status_code==403
        assert redeem(Origin='http://localhost:1').status_code==403
        assert redeem(Origin=ui.origin,Host='localhost:'+str(ui.server_port)).status_code==403
        response=redeem(Origin=ui.origin)
        assert response.status_code==200 and response.json()=={'token':ui.token}
        assert response.headers['cache-control']=='no-store'
        again=redeem(Origin=ui.origin)
        assert again.status_code==401 and again.json()['error']['code']=='launch_expired' and ui.token not in again.text
    # The window mints no codes over HTTP and never answers as an `atm ui` console.
    assert c.post('/api/console/launch-code',json={}).status_code==404
    assert c.get('/api/console').status_code==404
    assert c.get('/api/console',headers={'X-ATM-Challenge':'0'*64,'Authorization':''}).status_code==404


def test_agent_window_opens_a_one_time_launch_code_never_the_bearer(monkeypatch,tmp_path):
    root=tmp_path.resolve();r=Router(root/'s');r.vault=Vault(r.state,password=PASSWORD)
    r.vault.init('passphrase');r.vault.put('fal',KEY)
    w=root/'p';w.mkdir();plan=scope_plan(r.state,w,['fal']);ident=uuid.uuid4().hex
    r.state.set_setting('desktop-request:'+ident,{'id':ident,**plan,'status':'starting','created_at':time.time(),
                        'heartbeat':time.time(),'open_browser':True,'approval_sha256':fingerprint(plan)})
    monkeypatch.setattr(signal,'signal',lambda *args:None)  # serve_request's handlers must not outlive this test.
    seen={}
    def browser(url):
        def visit():  # What the opened page does: trade the code at the exact Origin, then use the bearer.
            origin=url.split('/#',1)[0];code=url.partition('/#launch=')[2]
            token=(r.state.home/('ui-session-'+origin.rsplit(':',1)[1]+'.token')).read_text()  # Test harness only.
            with httpx.Client(base_url=origin,trust_env=False) as client:
                try:
                    seen['redeem']=client.post('/api/console/redeem',json={'code':code},headers={'Origin':origin}).json()
                    seen['view']=client.get('/api/desktop',headers={'Authorization':'Bearer '+seen['redeem'].get('token','')}).status_code
                    seen['again']=client.post('/api/console/redeem',json={'code':code},headers={'Origin':origin}).status_code
                finally:
                    seen['token']=token
                    client.post('/api/desktop/cancel',json={},headers={'Authorization':'Bearer '+token,'Origin':origin})
        seen['url']=url;threading.Thread(target=visit,daemon=True).start()
        return True
    monkeypatch.setattr(quickstart_web.webbrowser,'open',browser)
    lifetimes=[];mint=webapp.Console.launch_code
    def launch_code(server,seconds=webapp.LAUNCH_SECONDS):
        lifetimes.append(seconds);return mint(server,seconds)
    monkeypatch.setattr(webapp.Console,'launch_code',launch_code)
    try:
        assert serve_request(r.state.home,ident)==0
    finally:
        r.close()
    record=request_record(State(r.state.home),ident)
    # Rerunning `atm start` reuses this window and mints no new code: a late browser must still get in, once.
    assert len(lifetimes)==1 and webapp.LAUNCH_SECONDS<lifetimes[0]<=PENDING_SECONDS
    assert seen['url'].startswith(record['url']+'/#launch=') and seen['token'] not in seen['url']
    assert seen['redeem']=={'token':seen['token']} and seen['view']==200 and seen['again']==401
    assert record['status']=='denied' and record['browser_opened'] is True
    assert seen['token'] not in canonical(record) and seen['url'].partition('#launch=')[2] not in canonical(record)


@pytest.mark.parametrize('endpoint',['/api/connections','/api/session','/api/access','/api/sync'])
def test_window_is_not_general_management_api(window,endpoint):
    r,w,ui,c,root=window
    assert c.get(endpoint).status_code==404


def test_project_scope_rejects_another_key_or_directory(window):
    r,w,ui,c,root=window;approve(window)
    p=profile_path(r.state,w)
    base={'argv':[sys.executable,'app.py'],'environment':{'FAL_KEY':'fal'},'workspace':str(w),'request_key':'deny'}
    other=root/'other';other.mkdir();(other/'app.py').write_text('print(1)')
    for patch in [{'environment':{'FAL_KEY':'stripe'}},{'workspace':str(other)}]:
        with pytest.raises(RouterError) as e:call(p,'exec',{**base,**patch})
        assert e.value.code=='exec_denied'
    assert not r.state.jobs()


def test_project_cannot_manage_or_read_raw_keys(window):
    r,w,ui,c,root=window;approve(window);p=profile_path(r.state,w)
    for op,args in [('session.put',{'provider':'fal','value':'fake','replace':True}),('session.project',{'workspace':str(w)}),('session.lock',{}),('get_secret',{'name':'fal'})]:
        with pytest.raises(RouterError):call(p,op,args)
    result=call(p,'keys.find',{'query':'fal'});assert KEY not in json.dumps(result)
    assert len(result['matches'])==1


def test_revocation_and_lock_fail_closed(window):
    r,w,ui,c,root=window;approve(window);p=profile_path(r.state,w)
    policy=json.loads(p.read_text());revoke(r.state,policy['id'],apply=True)
    assert ready(r.state,w,['fal']) is None
    owner_call(r.state.home,'session.lock')
    with pytest.raises(RouterError):call(p,'exec',{'argv':[sys.executable,'app.py'],'environment':{'FAL_KEY':'fal'},'workspace':str(w),'request_key':'after-lock'})
    assert not r.state.jobs()


@pytest.mark.parametrize('iteration', range(4))
def test_immediate_lock_returns_needs_unlock_without_starting_a_child(window, iteration):
    r,w,ui,c,root=window;approve(window)
    marker=w/'unexpected-execution'
    (w/'app.py').write_text('from pathlib import Path;Path("unexpected-execution").write_text("ran")')
    locked=owner_call(r.state.home,'session.lock')
    assert locked['status']=='locked' and locked['unlocked'] is False
    # No sleep/join: exercise the original shutdown window rather than hiding it.
    result=use(r.state.home,w,['FAL_KEY=atm://fal'],[sys.executable,'app.py'],
               request_key='immediate-lock-'+str(iteration),dry_run=True,open_browser=False)
    assert result['status']=='needs_unlock'
    assert result['execution_started'] is False and result['credentials_read'] is False
    process=subprocess.run([sys.executable,'-m','agent_tool_maker','--home',str(r.state.home),
        'use','--workspace',str(w),'--env','FAL_KEY=atm://fal','--dry-run','--no-browser',
        '--request-key','immediate-lock-cli-'+str(iteration),'--',sys.executable,'app.py'],
        stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
    assert process.returncode==3,process.stdout+process.stderr
    pending=json.loads(process.stdout)
    assert pending['status']=='needs_unlock' and pending['execution_started'] is False
    with pytest.raises(RouterError) as error:
        call(profile_path(r.state,w),'exec',{'argv':[sys.executable,'app.py'],
            'environment':{'FAL_KEY':'fal'},'workspace':str(w),'request_key':'locked-exec'})
    assert error.value.code in {'broker_locked','broker_unavailable','session_locked'}
    assert not marker.exists() and not r.state.jobs()
    assert status(r.state.home)['unlocked'] is False


def test_old_project_approval_not_revived_by_new_unlock(window):
    r,w,ui,c,root=window;approve(window);p=profile_path(r.state,w)
    owner_call(r.state.home,'session.lock');ui.secret_session_thread.join(5)
    second=SecretSession(r.state.home,vault=Vault(r.state,password=PASSWORD));t=threading.Thread(target=run_service,args=(second,),daemon=True);t.start()
    try:
        with pytest.raises(RouterError) as e:call(p,'status',{})
        assert e.value.code=='unauthorized'
    finally:second.closing.set();t.join(5)


@pytest.mark.parametrize('state_name',['sync_conflict','credential_expired'])
def test_conflict_and_expiry_never_reinterpreted_as_missing(window,state_name):
    r,w,ui,c,root=window
    if state_name=='sync_conflict':r.state.set_setting('sync_conflict:fal',True)
    else:r.state.set_setting('credential_meta:fal',{'expires_at':1})
    response=c.post('/api/desktop/approve',json=approval(ui))
    assert response.json()['error']['code']==state_name
    assert not profile_path(r.state,w).exists()


def test_duplicate_command_preserves_request_identity(window):
    r,w,ui,c,root=window;approve(window)
    args=(r.state.home,w,['FAL_KEY=atm://fal'],[sys.executable,'app.py'])
    first=use(*args,request_key='unique');second=use(*args,request_key='unique')
    assert first['id']==second['id'] and second['reused_request'] is True
    assert len(r.state.jobs())==1


def test_new_project_can_reuse_existing_unlock_without_password(window):
    r,w,ui,c,root=window;approve(window)
    original=status(r.state.home)['seconds_remaining']
    other=root/'second';other.mkdir();plan=scope_plan(r.state,other,['fal'])
    identifier=uuid.uuid4().hex
    r.state.set_setting('desktop-request:'+identifier,{'id':identifier,**plan,'status':'needs_approval',
                      'created_at':time.time(),'approval_sha256':fingerprint(plan)})
    ui2=ApprovalWindow(r.state.home,identifier)
    router=ui2.open_router()
    try:
        result=ui2.approve(router,{'approved_sha256':fingerprint(plan),'consent':True,'credentials':{}})
        assert result['status']=='ready' and result['seconds_remaining']<=original
        assert ui2.secret_session is None
    finally:router.close();ui2.server_close()


def test_decline_is_retained_without_popup_loop(window,monkeypatch):
    r,w,ui,c,root=window
    from agent_tool_maker.quickstart import project_id
    r.state.set_setting('desktop-active:'+project_id(w),ui.request_id)
    assert c.post('/api/desktop/cancel',json={}).json()['status']=='denied'
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('no relaunch'))
    assert start(r.state.home,w,names=['fal'])['status']=='denied'


def test_actual_agent_started_daemon_and_http_approval():
    with tempfile.TemporaryDirectory(prefix='daemon8-') as td:
        root=Path(td);r=Router(root/'s');r.vault=Vault(r.state,password=PASSWORD);r.vault.init('passphrase');r.vault.put('fal',KEY)
        w=root/'p';w.mkdir();(w/'app.py').write_text('import os;print(bool(os.environ["FAL_KEY"]))')
        record=start(r.state.home,w,names=['fal'],open_browser=False)
        assert record['status']=='needs_unlock',record
        assert 'token' not in canonical(record) and PASSWORD not in canonical(record)
        port=record['url'].rsplit(':',1)[1]
        token=(r.state.home/('ui-session-'+port+'.token')).read_text() # Test harness only, never Agent workflow.
        try:
            with httpx.Client(base_url=record['url'],headers={'Authorization':'Bearer '+token,'Origin':record['url']},trust_env=False) as c:
                plan=c.get('/api/desktop').json()
                response=c.post('/api/desktop/approve',json={'consent':True,'approved_sha256':plan['approved_sha256'],'passphrase':PASSWORD,'credentials':{}})
                assert response.status_code==200,response.text
                result=use(r.state.home,w,['FAL_KEY=atm://fal'],[sys.executable,'app.py'],request_key='daemon')
                assert result['stdout']=='True\n'
                assert c.post('/api/desktop/lock',json={}).status_code==200
        finally:
            try:owner_call(r.state.home,'session.lock')
            except RouterError:pass
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and (r.state.home/('ui-session-'+port+'.token')).exists():time.sleep(.05)
        assert not (r.state.home/('ui-session-'+port+'.token')).exists()


def test_legacy_encrypted_vault_still_unlocks_without_old_cli_alias(window):
    r,w,ui,c,root=window
    cfg=r.state.setting('vault');key=r.vault.unlock();nonce=os.urandom(12)
    cfg['check_nonce']=base64.b64encode(nonce).decode();cfg['check']=base64.b64encode(AESGCM(key).encrypt(nonce,b'ATR-v1',b'vault-check')).decode()
    r.state.set_setting('vault',cfg)
    assert Vault(r.state,password=PASSWORD).get('fal')==KEY


def test_only_atm_installed_and_old_environment_fallbacks_removed(monkeypatch,tmp_path):
    import tomllib
    from agent_tool_maker.cli import parser
    r=Path(__file__).resolve().parents[1]
    config=tomllib.loads((r/'pyproject.toml').read_text())
    assert set(config['project']['scripts'])=={'atm'}
    monkeypatch.delenv('ATM_HOME',raising=False);monkeypatch.setenv('ATR_HOME',str(tmp_path/'ignored'))
    assert parser().parse_args(['session','status']).home!=tmp_path/'ignored'
    monkeypatch.delenv('ATM_VAULT_PASSWORD',raising=False);monkeypatch.setenv('ATR_VAULT_PASSWORD',PASSWORD)
    monkeypatch.setattr('agent_tool_maker.vault.prompt_secret',lambda *_:'new-interactive-value')
    assert Vault(State(tmp_path/'s'))._password()=='new-interactive-value'


def test_readme_is_short_and_skill_owns_commands():
    r=Path(__file__).resolve().parents[1]
    readme=(r/'README.md').read_text();skill=(r/'SKILL.md').read_text()
    assert len(readme.splitlines())<=90
    assert 'ATR' not in readme and '`atr`' not in readme
    assert 'atm start' in skill and 'atm use' in skill and 'self-approve' in skill
    assert skill==(r/'src/agent_tool_maker/data/SKILL.md').read_text()


def seed_requests(state, root, now):
    """Approval-window records in every state; only fresh pending ones are still waiting for the human."""
    made = {}
    cases = [('fresh', 'needs_unlock', 60, 2), ('stale', 'needs_approval', 30, 45), ('denied', 'denied', 20, 1),
             ('ready', 'ready', 10, 1), ('expired', 'expired', 5, 1), ('old', 'needs_unlock', 660, 1)]
    for name, status_name, age, beat in cases:
        workspace = root / ('project-' + name); workspace.mkdir()
        plan = scope_plan(state, workspace, ['fal', 'replicate'])
        ident = uuid.uuid4().hex
        state.set_setting('desktop-request:' + ident, {'id': ident, **plan, 'status': status_name, 'created_at': now - age,
                          'heartbeat': now - beat, 'approval_sha256': fingerprint(plan),
                          'url': 'http://localhost:1/#launch=FAKE-LAUNCH-' + name, 'open_browser': True,
                          'token': 'FAKE-WINDOW-TOKEN-' + name, 'origin': 'http://localhost:1'})
        state.set_setting('desktop-active:' + uuid.uuid4().hex[:24], ident)
        made[name] = (ident, workspace)
    state.set_setting('desktop-active:' + 'f' * 24, 12345)  # A malformed pointer is ignored.
    return made


def test_pending_requests_lists_only_live_window_requests_newest_first(tmp_path):
    from agent_tool_maker.quickstart import pending_requests
    root = tmp_path.resolve(); state = State(root / 's'); now = time.time()
    made = seed_requests(state, root, now)
    rows = pending_requests(state)
    assert [row['id'] for row in rows] == [made['stale'][0], made['fresh'][0]]  # created 30 s ago, then 60 s ago
    assert [row['live'] for row in rows] == [False, True]
    for row in rows:
        assert set(row) == {'id', 'workspace', 'credentials', 'status', 'created_at', 'expires_at', 'live'}
        assert row['expires_at'] == row['created_at'] + PENDING_SECONDS
        assert row['credentials'] == ['fal', 'replicate']
    assert rows[1]['workspace'] == str(made['fresh'][1]) and rows[1]['status'] == 'needs_unlock'
    text = json.dumps(rows)
    for leak in ('FAKE-LAUNCH', 'FAKE-WINDOW-TOKEN', 'localhost:1', 'approval_sha256', 'launch', 'token', 'origin', 'url'):
        assert leak not in text
    record = state.setting('desktop-request:' + made['fresh'][0])
    assert record['approval_sha256'] not in text
