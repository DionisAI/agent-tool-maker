import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import httpx
import pytest
from agent_tool_maker.broker import Broker, call, grant, list_grants, revoke
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.network import Network
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault


@pytest.fixture
def broker_env(tmp_path):
    # Unix socket path limits are independent of pytest's long per-test directory.
    with tempfile.TemporaryDirectory(prefix='atm-b-') as runtime:
        state=State(tmp_path/'state');v=Vault(state,password='fake-long-broker-password');v.init('passphrase');v.put('github','FAKE-SECRET-DONT-RETURN')
        calls=[]
        def handler(request):
            calls.append(request)
            assert request.headers['authorization']=='Bearer FAKE-SECRET-DONT-RETURN'
            return httpx.Response(200,json={'id':7,'login':'fixture-user'})
        def factory():
            r=Router(state.home,network=Network(httpx.MockTransport(handler),lambda h:['93.184.216.34']))
            r.vault._key=v._key
            return r
        owner=factory();owner.vault._key=v._key
        sock=Path(runtime)/'s'
        server=Broker(state.home,socket_file=sock,vault=v,router_factory=factory)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        workspace=tmp_path/'project';workspace.mkdir()
        try:yield owner,server,workspace,calls
        finally:server.shutdown();thread.join(10);server.server_close();owner.close()


def create_profile(env,tmp_path,tools=('github.user',),**kwargs):
    # Actual repository action id is discovered once from the catalog, not invented.
    owner,server,workspace,calls=env
    if tools==('github.user',):
        tools=('gh.repo_view',)
    return grant(owner,'claude',tools=list(tools),workspace=workspace,output=tmp_path/'claude.json',socket_file=server.path,apply=True,**kwargs)


def test_grant_preview_does_not_create_profile(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    result=grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=tmp_path/'p.json',socket_file=server.path)
    assert not result['applied'] and not (tmp_path/'p.json').exists()
    assert list_grants(owner.state)['grants']==[]


def test_real_ffprobe_two_fresh_processes_no_password_or_key_env(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    executable=shutil.which('ffprobe');assert executable
    bind_cli(owner.state,'ffprobe',executable)
    profile=tmp_path/'p.json'
    grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=profile,socket_file=server.path,apply=True)
    shutil.copy(Path(__file__).parent/'fixtures/tone.wav',workspace/'tone.wav')
    input_file=workspace/'input.json';input_file.write_text('{"path":"tone.wav"}')
    env={k:v for k,v in os.environ.items() if not any(x in k for x in ['API_KEY','TOKEN','VAULT_PASSWORD'])}
    runs=[]
    for _ in range(2):
        result=subprocess.run([sys.executable,'-m','agent_tool_maker','--client-profile',str(profile),'run','ffmpeg.probe','--workspace',str(workspace),'--input',str(input_file),'--request-key','same-task'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,cwd=workspace)
        assert result.returncode==0,result.stdout+result.stderr
        runs.append(json.loads(result.stdout))
    assert runs[0]['id']==runs[1]['id'] and runs[0]['status']=='completed'
    assert 'FAKE-SECRET' not in json.dumps(runs)
    assert len(owner.state.jobs())==1


def test_wrong_token_revoked_and_expired_are_denied(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    profile=tmp_path/'p.json'
    record=grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=profile,socket_file=server.path,apply=True)
    assert call(profile,'status',{})['agent']=='claude'
    data=json.loads(profile.read_text());old=data['token'];data['token']='wrong';profile.write_text(json.dumps(data))
    with pytest.raises(RouterError) as err:call(profile,'status',{})
    assert err.value.code=='unauthorized'
    data['token']=old;profile.write_text(json.dumps(data))
    policy=owner.state.setting('access:'+record['id']);policy['expires_at']=time.time()-1;owner.state.set_setting('access:'+record['id'],policy)
    with pytest.raises(RouterError):call(profile,'status',{})
    policy['expires_at']=time.time()+300;owner.state.set_setting('access:'+record['id'],policy)
    revoke(owner.state,record['id'],apply=True)
    with pytest.raises(RouterError):call(profile,'status',{})


def test_broker_lease_expiry_no_fallback(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    p=tmp_path/'p.json';grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    server.deadline=0
    with pytest.raises(RouterError) as e:call(p,'status',{})
    assert e.value.code=='broker_locked'


@pytest.mark.parametrize('operation',['get-secret','sync','grant','shell','connect','lock','setup'])
def test_management_never_exposed_to_agent(broker_env,tmp_path,operation):
    owner,server,workspace,_=broker_env;p=tmp_path/'p.json'
    grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    with pytest.raises(RouterError) as e:call(p,operation,{})
    assert e.value.code=='operation_denied'


def test_tool_and_workspace_denied(broker_env,tmp_path):
    owner,server,workspace,_=broker_env;p=tmp_path/'p.json'
    grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    with pytest.raises(RouterError) as e:call(p,'describe',{'tool':'fal.generate'})
    assert e.value.code=='tool_denied'
    with pytest.raises(RouterError) as e:call(p,'run',{'tool':'ffmpeg.probe','inputs':{'path':'x'},'workspace':str(tmp_path),'request_key':'x'})
    assert e.value.code=='workspace_denied'


def test_runtime_flags_cannot_escalate(broker_env,tmp_path):
    owner,server,workspace,_=broker_env;p=tmp_path/'p.json'
    grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    result=subprocess.run([sys.executable,'-m','agent_tool_maker','--client-profile',str(p),'run','fal.generate','--input','-','--allow-paid'],input='{}',text=True,capture_output=True)
    assert result.returncode==2 and 'grant_escalation_denied' in result.stdout
    assert not owner.state.jobs()


def test_pins_origin_and_cli_changes_require_new_authorization(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    exe=tmp_path/'tool';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o700);bind_cli(owner.state,'ffprobe',str(exe))
    p=tmp_path/'p.json';grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    owner.state.set_setting('cli:ffprobe','/some/other/exe')
    with pytest.raises(RouterError) as e:call(p,'describe',{'tool':'ffmpeg.probe'})
    assert e.value.code=='grant_stale'


def test_profile_world_readable_refused(broker_env,tmp_path):
    owner,server,workspace,_=broker_env;p=tmp_path/'p.json'
    grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    p.chmod(0o644)
    with pytest.raises(RouterError) as e:call(p,'status',{})
    assert e.value.code=='unsafe_profile_permissions'


def test_discovery_only_reveals_granted_tools(broker_env,tmp_path):
    owner,server,workspace,_=broker_env;p=tmp_path/'p.json'
    grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    result=call(p,'search',{'query':''})
    assert [t['id'] for t in result['tools']]==['ffmpeg.probe']


def test_no_spend_grant_for_paid_tool_without_explicit_permission(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    with pytest.raises(RouterError) as e:grant(owner,'claude',tools=['fal.generate'],workspace=workspace,output=tmp_path/'p',socket_file=server.path,apply=True)
    assert e.value.code=='insufficient_grant'


@pytest.mark.parametrize('tool',['notion.mcp_batch','tripo.web','marvelous_designer.handoff'])
def test_transitive_tools_fail_closed(broker_env,tmp_path,tool):
    owner,server,workspace,_=broker_env
    with pytest.raises(RouterError) as e:grant(owner,'claude',tools=[tool],workspace=workspace,output=tmp_path/'p',socket_file=server.path,apply=True)
    assert e.value.code=='broker_unsupported_tool'


def test_no_grant_can_write_vault_directory(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    for path in (owner.state.home,owner.state.home.parent):
        with pytest.raises(RouterError) as e:grant(owner,'claude',tools=['ffmpeg.probe'],workspace=path,output=tmp_path/'p',socket_file=server.path,apply=True)
        assert e.value.code=='unsafe_workspace'


def test_scoped_skill_uses_profile_never_direct_vault(broker_env,tmp_path):
    from agent_tool_maker.onboarding import setup
    owner,server,workspace,_=broker_env
    out=setup(owner,agents=['claude','codex'],executable=shutil.which('atm'),user_home=tmp_path/'user',broker=True,apply=True)
    for a in out['skills']:
        text=Path(a['path']).read_text()
        assert '--client '+a['agent'] in text
        assert '--home' not in text and 'Do NOT fall back to direct ATM' in text
        assert 'Never add --allow-* flags' in text
        assert 'FAKE-SECRET' not in text
    again=setup(owner,agents=['claude','codex'],executable=shutil.which('atm'),user_home=tmp_path/'user',broker=True,apply=True)
    assert all(a['action']=='unchanged' for a in again['skills'])


def test_two_agents_cannot_read_each_others_jobs(broker_env,tmp_path):
    owner,server,workspace,_=broker_env
    bind_cli(owner.state,'ffprobe',shutil.which('ffprobe'));shutil.copy(Path(__file__).parent/'fixtures/tone.wav',workspace/'tone.wav')
    paths=[]
    for name in ['claude','codex']:
        p=tmp_path/(name+'.json');paths.append(p)
        grant(owner,name,tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    job=call(paths[0],'run',{'tool':'ffmpeg.probe','inputs':{'path':'tone.wav'},'workspace':str(workspace),'request_key':'mine'})
    with pytest.raises(RouterError) as e:call(paths[1],'job',{'id':job['id']})
    assert e.value.code=='job_denied'


def test_native_api_secret_injection_and_rotation_without_regrant(tmp_path):
    # Controlled backend, not an actual OS keychain. Assert only one get_password.
    from agent_tool_maker.demo import fixture_assets,fixture_resolver
    class MemoryKeyring:
        value=None;reads=0
        def set_password(self,*args):self.value=args[-1]
        def get_password(self,*args):self.reads+=1;return self.value
    keyring=MemoryKeyring();state=State(tmp_path/'state');v=Vault(state,keyring_backend=keyring);v.init('keyring');v.put('elevenlabs','FAKE-before')
    owner=Router(state.home,vault=v);v._key=None;received=[]
    def handler(req):received.append(req.headers['xi-api-key']);return httpx.Response(200,content=fixture_assets()['tone.mp3'],headers={'content-type':'audio/mpeg'})
    with tempfile.TemporaryDirectory(prefix='atm-b-') as runtime:
        server=Broker(state.home,socket_file=Path(runtime)/'s',vault=v)
        def factory():
            r=Router(state.home,network=Network(httpx.MockTransport(handler),fixture_resolver));r.vault._key=server._key;return r
        server.router_factory=factory
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        workspace=tmp_path/'work';workspace.mkdir();p=tmp_path/'p.json'
        try:
            grant(owner,'claude',tools=['elevenlabs.tts'],workspace=workspace,output=p,socket_file=server.path,allow_paid=True,apply=True)
            for i in range(3):
                if i==2:v.put('elevenlabs','FAKE-after')
                result=call(p,'run',{'tool':'elevenlabs.tts','inputs':{'text':'Test','voice_id':'testvoice'},'workspace':str(workspace),'request_key':'key'+str(i)})
                assert result['status']=='completed'
                assert 'FAKE-' not in json.dumps(result)
            assert received==['FAKE-before','FAKE-before','FAKE-after'] and keyring.reads==1
        finally:server.shutdown();thread.join();server.server_close();owner.close()


def test_global_disable_enforced_for_broker(broker_env,tmp_path):
    from agent_tool_maker.management import set_enabled
    owner,server,workspace,_=broker_env;p=tmp_path/'p.json'
    grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,socket_file=server.path,apply=True)
    set_enabled(owner,'ffmpeg.probe',False,apply=True)
    with pytest.raises(RouterError):call(p,'run',{'tool':'ffmpeg.probe','inputs':{'path':'x'},'workspace':str(workspace),'request_key':'x'})
    assert not owner.state.jobs()


def test_actual_peer_uid_must_match_scoped_grant(broker_env,tmp_path):
    owner,server,workspace,_=broker_env;p=tmp_path/'wrong-uid.json'
    grant(owner,'claude',tools=['ffmpeg.probe'],workspace=workspace,output=p,
          socket_file=server.path,client_uid=os.getuid()+1,apply=True)
    with pytest.raises(RouterError) as e:call(p,'status',{})
    assert e.value.code=='peer_uid_denied'


def test_live_broker_blocks_conflict_and_expired_credential(broker_env,tmp_path):
    from agent_tool_maker.sync import Sync
    owner,server,workspace,requests=broker_env
    a=Sync(owner.vault);a.initialize('owner')
    state=State(tmp_path/'other');v=Vault(state,password='other-fake-long-password');v.init('passphrase')
    b=Sync(v);b.initialize('other')
    for x,y in [(a,b),(b,a)]:x.trust(y.identity(),y.identity()['id'],send=['fal'],receive=['fal'],apply=True)
    a.vault.put('fal','FAKE-base');b.import_packet(a.export_packet(b.identity()['id']),apply=True)
    p=tmp_path/'scoped.json';grant(owner,'claude',tools=['fal.generate'],workspace=workspace,output=p,
          socket_file=server.path,allow_paid=True,apply=True)
    a.vault.put('fal','FAKE-left');b.vault.put('fal','FAKE-right')
    a.import_packet(b.export_packet(a.identity()['id']),apply=True)
    with pytest.raises(RouterError) as e:call(p,'describe',{'tool':'fal.generate'})
    assert e.value.code=='sync_conflict' and not requests
    record=next(r for r in a.status()['records'] if r['provider']=='fal')
    a.resolve('fal',record['heads'][0]['revision'],record['expected'],apply=True)
    a.vault.put('fal','FAKE-expired',expires_at=time.time()-1)
    with pytest.raises(RouterError) as e:call(p,'describe',{'tool':'fal.generate'})
    assert e.value.code=='credential_expired' and not requests
