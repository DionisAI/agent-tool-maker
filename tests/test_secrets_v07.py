"""Independent negative/positive tests for the credential-first contract; fake keys only."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from urllib.parse import quote

import httpx
import pytest

from agent_tool_maker.broker import call, revoke
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.extensions import declare_credential
from agent_tool_maker.secrets_provider import (alias, captured_process, command_plan, credential_rows,
    find_keys, parse_mapping, permit_exec, redact_output)
from agent_tool_maker.session import SecretSession, run_service, owner_call, status, ttl_seconds
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault

KEY = 'fake-v07/key+not-a-real-credential'

@pytest.fixture
def env(tmp_path):
    # Socket path length is a kernel limit, independent of the project/test name.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='atm7-') as tmp:
        root = Path(tmp)
        r = Router(root/'state'); r.vault = Vault(r.state, password='test-only-passphrase-long')
        r.vault.init('passphrase'); r.vault.put('fal', KEY)
        w = root/'project'; w.mkdir()
        app = w/'app.py'
        app.write_text('import os,sys\nprint("KEY_PRESENT=" + str(bool(os.environ["FAL_KEY"])))\nprint(os.environ["FAL_KEY"])\nprint("NO_MASTER=" + str("ATM_VAULT_PASSWORD" not in os.environ))\n')
        server = SecretSession(r.state.home, vault=r.vault)
        t = threading.Thread(target=run_service, args=(server,), daemon=True); t.start()
        try:
            yield r, w, server, root
        finally:
            server.closing.set(); t.join(10); r.close()


def permit(env, agent='claude', **kwargs):
    r,w,s,root=env
    opts = dict(mappings=['FAL_KEY=atm://fal'], argv=[sys.executable, 'app.py'], workspace=w,
                output=root/(agent+'.json'), **kwargs)
    plan = permit_exec(r, agent, **opts)
    result = permit_exec(r, agent, **opts, apply=True, approve=plan['sha256'])
    return Path(result['profile']), result, opts


def request(w, **kw):
    return {'argv':[os.path.abspath(sys.executable),'app.py'], 'environment':{'FAL_KEY':'fal'},
            'workspace':str(w), 'request_key':'test-1', **kw}


def test_no_catalog_or_manifest_needed(env):
    r,w,s,root=env
    before=set(r.catalog.tools)
    p,g,_=permit(env)
    result=call(p,'exec',request(w))
    assert result['status']=='completed' and 'KEY_PRESENT=True' in result['stdout']
    assert 'NO_MASTER=True' in result['stdout'] and KEY not in json.dumps(result)
    assert set(r.catalog.tools)==before and not (w/'.env').exists()
    data=r.state.path.read_bytes()
    assert KEY.encode() not in data and b'KEY_PRESENT=True' not in data


def test_discovery_only_scoped_no_password(env):
    r,w,s,root=env; r.vault.put('stripe','fake-stripe')
    p,g,_=permit(env)
    result=call(p,'keys.find',{'query':'FAL_KEY'})
    assert result['status']=='found' and result['matches'][0]['name']=='fal'
    assert KEY not in json.dumps(result)
    assert call(p,'keys.find',{'query':'stripe'})['status']=='not_found'
    assert [x['name'] for x in call(p,'keys.list',{})['matches']]==['fal']


def test_dev_production_ambiguity_never_used_for_exec(env):
    r,w,s,root=env
    for n in ['acme.production','acme.development']:
        declare_credential(r,n,apply=True); r.vault.put(n,'fake_'+n)
    alias(r.state,'ACME_KEY',['acme.production','acme.development'],apply=True)
    assert find_keys(r.state,'ACME_KEY')['status']=='ambiguous'
    with pytest.raises(RouterError): parse_mapping(['ACME_KEY'])
    with pytest.raises(RouterError): parse_mapping(['ACME_KEY=literal-secret'])


def test_alias_retarget_requires_revision_and_never_changes_exec_map(env):
    r,w,s,root=env
    p,g,_=permit(env)
    a=alias(r.state,'FAL_KEY',['fal'],apply=True)
    with pytest.raises(RouterError):alias(r.state,'FAL_KEY',['stripe'],apply=True)
    b=alias(r.state,'FAL_KEY',['stripe'],expected=a['previous_sha256'],apply=False)
    alias(r.state,'FAL_KEY',['stripe'],expected=b['previous_sha256'],apply=True)
    assert call(p,'exec',request(w))['status']=='completed'


@pytest.mark.parametrize('op,args', [('get-secret',{}),('session.put',{'provider':'fal','value':'evil'}),
    ('session.remove',{'provider':'fal','confirm':'fal'}),('session.lock',{}),('session.status',{}),('shell',{}),('sync',{})])
def test_agents_cannot_manage_or_export(env,op,args):
    p,_,_=permit(env)
    with pytest.raises(RouterError) as e:call(p,op,args)
    assert e.value.code=='operation_denied'


@pytest.mark.parametrize('change', [ {'environment':{'FAL_KEY':'stripe'}}, {'environment':{'OTHER_KEY':'fal'}},
    {'argv':['/bin/sh','-c','env']}, {'workspace':'/'}, {'extra':'value'}])
def test_scope_denied_before_spawn(env,change):
    r,w,s,_=env; p,_,_=permit(env)
    with pytest.raises(RouterError):call(p,'exec',request(w,**change))
    assert r.state.jobs()==[]


@pytest.mark.parametrize('name',['PATH','HOME','LD_PRELOAD','DYLD_INSERT_LIBRARIES','PYTHONPATH','PYTHONSTARTUP',
    'NODE_OPTIONS','BASH_ENV','ENV','ATM_VAULT_PASSWORD','ATR_HOME','HTTP_PROXY','SSL_CERT_FILE','GIT_SSH_COMMAND',
    'JAVA_TOOL_OPTIONS','DOTNET_STARTUP_HOOKS','LC_ALL','PERL5OPT','RUBYOPT','NPM_CONFIG_USERCONFIG'])
def test_environment_control_rejected(name):
    with pytest.raises(RouterError) as e:parse_mapping([name+'=atm://fal'])
    assert e.value.code=='unsafe_environment'


def test_unknown_credential_reports_missing_not_prompt(env):
    r,w,s,root=env
    opts=dict(mappings=['FAL_KEY=atm://unlisted.production'],argv=[sys.executable,'app.py'],workspace=w,output=root/'new.json')
    plan=permit_exec(r,'claude',**opts);permit_exec(r,'claude',**opts,apply=True,approve=plan['sha256'])
    found=call(root/'new.json','keys.find',{'query':'unlisted.production'})
    assert found['matches'][0]['state']=='missing_credential'
    with pytest.raises(RouterError) as e:call(root/'new.json','exec',request(w,environment={'FAL_KEY':'unlisted.production'}))
    assert e.value.code=='missing_credential'


@pytest.mark.parametrize('blocked',['sync_conflict','credential_expired','missing_credential'])
def test_invalid_connection_no_fallback(env,blocked):
    r,w,s,_=env;p,_,_=permit(env)
    if blocked=='sync_conflict':r.state.set_setting('sync_conflict:fal',True)
    elif blocked=='credential_expired':r.state.set_setting('credential_meta:fal',{'expires_at':time.time()-1})
    else:r.vault.delete('fal')
    with pytest.raises(RouterError) as e:call(p,'exec',request(w))
    assert e.value.code==blocked and r.state.jobs()==[]


def test_modified_script_pin_stale_then_owner_reapproval(env):
    r,w,s,_=env;p,g,opts=permit(env)
    (w/'app.py').write_text('print("modified")')
    with pytest.raises(RouterError) as e:call(p,'exec',request(w))
    assert e.value.code=='grant_stale'
    plan=permit_exec(r,'claude',**opts)
    permit_exec(r,'claude',**opts,apply=True,approve=plan['sha256'])
    assert call(p,'exec',request(w))['stdout']=='modified\n'


def test_symlink_script_and_workspace_refused(env):
    r,w,s,root=env
    (w/'linked.py').symlink_to(w/'app.py')
    with pytest.raises(RouterError):command_plan(r,[sys.executable,'linked.py'],{'FAL_KEY':'fal'},w)
    (root/'link').symlink_to(w,target_is_directory=True)
    with pytest.raises(RouterError):command_plan(r,[sys.executable,'app.py'],{'FAL_KEY':'fal'},root/'link')


def test_plan_approval_and_double_apply(env):
    r,w,s,_=env;p,g,opts=permit(env)
    plan=permit_exec(r,'claude',**opts)
    assert plan['action']=='unchanged'
    with pytest.raises(RouterError):permit_exec(r,'claude',**opts,apply=True,approve='bad')
    result=permit_exec(r,'claude',**opts,apply=True,approve=plan['sha256'])
    assert result['action']=='unchanged'


def test_revocation_and_expiry(env):
    r,w,s,_=env;p,g,_=permit(env)
    revoke(r.state,g['grant_id'],apply=True)
    with pytest.raises(RouterError) as e:call(p,'exec',request(w))
    assert e.value.code=='unauthorized'


def test_expired_agent_grant(env):
    r,w,s,_=env;p,g,_=permit(env)
    data=r.state.setting('access:'+g['grant_id']);data['expires_at']=0;r.state.set_setting('access:'+g['grant_id'],data)
    with pytest.raises(RouterError) as e:call(p,'exec',request(w))
    assert e.value.code=='unauthorized'


def test_lock_revokes_new_use_not_reconfigure(env):
    r,w,s,_=env;p,_,_=permit(env)
    assert status(r.state.home)['unlocked']
    assert owner_call(r.state.home,'session.lock')['unlocked'] is False
    with pytest.raises(RouterError):call(p,'exec',request(w))
    assert r.state.secret_names()==['fal']


def test_exact_request_key_no_rerun_and_output_not_stored(env):
    r,w,s,_=env;p,_,_=permit(env)
    a=call(p,'exec',request(w));b=call(p,'exec',request(w))
    assert a['id']==b['id'] and b['reused_request']
    assert 'stdout' not in b and len(r.state.jobs())==1
    assert 'stdout' not in r.state.jobs()[0]['data']


def test_parent_environment_is_not_inherited(env,monkeypatch):
    r,w,s,_=env
    monkeypatch.setenv('ATM_VAULT_PASSWORD','fake-master');monkeypatch.setenv('OTHER_SECRET','fake-other')
    (w/'app.py').write_text('import os,json\nprint(json.dumps(sorted(os.environ)))')
    p,_,_=permit(env)
    data=call(p,'exec',request(w));names=json.loads(data['stdout'])
    assert 'FAL_KEY' in names and 'ATM_VAULT_PASSWORD' not in names and 'OTHER_SECRET' not in names


def test_secret_output_spanning_writes_and_stderr(env):
    r,w,s,_=env
    (w/'app.py').write_text('import os,sys,base64\nx=os.environ["FAL_KEY"]\nsys.stdout.write(x[:5]);sys.stdout.flush();sys.stdout.write(x[5:]);print(base64.b64encode(x.encode()).decode());sys.stderr.write(x)')
    p,_,_=permit(env);out=call(p,'exec',request(w))
    assert KEY not in json.dumps(out) and base64.b64encode(KEY.encode()).decode() not in out['stdout']
    assert '[REDACTED]' in out['stdout'] and '[REDACTED]' in out['stderr']


@pytest.mark.parametrize('program,timeout,code', [ ('print("x"*300000)',5,'exec_output_limit'), ('import time;time.sleep(3)',1,'exec_timeout')])
def test_output_limit_and_timeout_no_raw_capture(env,program,timeout,code):
    r,w,s,_=env;(w/'app.py').write_text(program);p,_,_=permit(env,timeout=timeout)
    with pytest.raises(RouterError) as e:call(p,'exec',request(w))
    assert e.value.code==code
    assert r.state.jobs()[0]['status']=='submission_unknown'
    assert list(w.iterdir())==[w/'app.py']


def test_session_fixed_not_sliding_and_preview_no_secret(env):
    r,w,s,_=env;p,_,_=permit(env);deadline=s.deadline
    for _ in range(3):call(p,'keys.find',{'query':'FAL_KEY'})
    assert s.deadline==deadline
    result=call(p,'exec',request(w,dry_run=True))
    assert result['credentials_read'] is False and not r.state.jobs()


def test_expiry_after_pin_hash_before_admission_fails(env,monkeypatch):
    import agent_tool_maker.secrets_provider as sp
    r,w,s,_=env;p,_,_=permit(env)
    original=sp.file_pin
    def changed(*a,**k):
        result=original(*a,**k);s.deadline=0;return result
    monkeypatch.setattr(sp,'file_pin',changed)
    with pytest.raises(RouterError):call(p,'exec',request(w))
    assert not r.state.jobs()


def test_web_and_cli_share_one_unlock_for_key_crud(env):
    from agent_tool_maker.webapp import Console
    r,w,s,root=env
    ui=Console(r.state.home);thread=threading.Thread(target=ui.serve_forever,daemon=True);thread.start()
    headers={'Authorization':'Bearer '+ui.token,'Origin':ui.origin}
    try:
        with httpx.Client(base_url=ui.origin,headers=headers,trust_env=False) as c:
            assert c.get('/api/session').json()['unlocked']
            response=c.post('/api/connections/save',json={'provider':'fal','value':'replacement-fake','replace':True})
            assert response.status_code==200 and response.json()['saved_encrypted']
            assert r.vault.get('fal')=='replacement-fake'
            denied=c.post('/api/session/lock',json={},headers={'Origin':'https://attacker.invalid'})
            assert denied.status_code==403
            assert c.post('/api/session/lock',json={}).json()['unlocked'] is False
    finally:
        ui.shutdown();thread.join(5);ui.server_close()


@pytest.mark.parametrize('value',['0m','-1s','NaNh','1.5h','999999h','forever','1d'])
def test_bad_ttl_rejected(value):
    with pytest.raises(RouterError):ttl_seconds(value)


def test_30m_ttl():assert ttl_seconds('30m')==1800


def test_owned_exec_job_receipts_not_other_clients(env):
    r,w,s,_=env;p,_,_=permit(env);q,_,_=permit(env,'codex')
    result=call(p,'exec',request(w))
    receipt=call(p,'job',{'id':result['id']})
    assert receipt['status']=='completed' and 'stdout' not in receipt['data']
    with pytest.raises(RouterError) as e:call(q,'job',{'id':result['id']})
    assert e.value.code=='job_denied'


def test_direct_vault_expiry_is_also_enforced(env):
    r,w,s,_=env;r.state.set_setting('credential_meta:fal',{'expires_at':time.time()-10})
    with pytest.raises(RouterError) as e:r.vault.get('fal')
    assert e.value.code=='credential_expired'


def test_legacy_tool_grant_does_not_implicitly_grant_exec(env):
    from agent_tool_maker.broker import grant
    r,w,s,root=env
    grant(r,'claude',tools=['ffmpeg.probe'],workspace=w,output=root/'old.json',apply=True)
    with pytest.raises(RouterError) as e:call(root/'old.json','exec',request(w))
    assert e.value.code=='exec_denied'


def test_metadata_discovery_never_reads_key(env,monkeypatch):
    r,w,s,_=env;p,_,_=permit(env)
    monkeypatch.setattr(Vault,'get',lambda *a:pytest.fail('Metadata attempted a secret read'))
    assert call(p,'keys.find',{'query':'fal'})['status']=='found'


def test_cross_uid_generic_execution_explicitly_not_supported(env):
    r,w,s,_=env;p,g,_=permit(env)
    cfg=json.loads(p.read_text());policy=r.state.setting('access:'+g['grant_id'])
    policy['client_uid']=65534;r.state.set_setting('access:'+g['grant_id'],policy)
    with pytest.raises(RouterError) as e:s.handle({'id':cfg['id'],'token':cfg['token'],'operation':'exec','args':request(w)},peer_uid=65534)
    assert e.value.code=='exec_uid_unsupported'


def test_removed_session_profile_does_not_downgrade_to_direct_vault(env):
    from agent_tool_maker.session import owner_path, exists
    r,w,s,_=env;owner_path(r.state.home).unlink()
    assert exists(r.state.home)
    with pytest.raises(RouterError) as e:owner_call(r.state.home,'session.put',{'provider':'fal','value':'fake'})
    assert e.value.code=='session_locked'


def test_web_unlock_reused_by_new_cli_without_password(tmp_path):
    import tempfile,subprocess
    from agent_tool_maker.webapp import Console
    with tempfile.TemporaryDirectory(prefix='atm7-web-') as td:
        root=Path(td);r=Router(root/'s');r.vault=Vault(r.state,password='fake-web-passphrase');r.vault.init('passphrase');r.vault.put('fal',KEY)
        w=root/'w';w.mkdir();(w/'app.py').write_text('import os;print(bool(os.environ["FAL_KEY"]))')
        opts=dict(mappings=['FAL_KEY=atm://fal'],argv=[sys.executable,'app.py'],workspace=w,output=root/'c.json')
        plan=permit_exec(r,'claude',**opts);permit_exec(r,'claude',**opts,apply=True,approve=plan['sha256'])
        ui=Console(r.state.home);t=threading.Thread(target=ui.serve_forever,daemon=True);t.start()
        try:
            with httpx.Client(base_url=ui.origin,headers={'Authorization':'Bearer '+ui.token,'Origin':ui.origin},trust_env=False) as c:
                bad=c.post('/api/session/unlock',json={'passphrase':'wrong-password','ttl':'30m'})
                assert bad.status_code==400 and not (r.state.home/'broker.sock').exists()
                good=c.post('/api/session/unlock',json={'passphrase':'fake-web-passphrase','ttl':'30m'})
                assert good.status_code==200 and good.json()['unlocked']
                env={k:v for k,v in os.environ.items() if not any(x in k for x in ('PASSWORD','KEY','TOKEN'))}
                result=subprocess.run([shutil.which('atm'),'--client-profile',str(root/'c.json'),'exec','--env','FAL_KEY=atm://fal','--workspace',str(w),'--',sys.executable,'app.py'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=20)
                assert result.returncode==0 and json.loads(result.stdout)['stdout']=='True\n'
                assert c.post('/api/session/unlock',json={'ttl':'1h'}).json()['action']=='unchanged'
                c.post('/api/session/lock',json={})
        finally:
            ui.shutdown();t.join(5);ui.server_close();r.close()


def test_dry_run_does_not_need_plaintext_value(env,monkeypatch):
    r,w,s,_=env;p,_,_=permit(env)
    monkeypatch.setattr(Vault,'get',lambda *a:pytest.fail('Dry run decrypted a credential'))
    assert call(p,'exec',request(w,dry_run=True))['credentials_read'] is False


def test_scope_status_exposes_exact_permit_not_bearer(env):
    r,w,s,_=env;p,g,_=permit(env)
    result=call(p,'status',{})
    assert result['exec_permits'][0]['environment']=={'FAL_KEY':'fal'}
    assert result['exec_permits'][0]['argv']==[os.path.abspath(sys.executable),'app.py']
    assert 'token' not in json.dumps(result) and KEY not in json.dumps(result)


def test_key_rotation_reuses_grant_but_reads_fresh_value(env):
    r,w,s,_=env;(w/'app.py').write_text('import os;print(len(os.environ["FAL_KEY"]))')
    p,_,_=permit(env);a=call(p,'exec',request(w))
    owner_call(r.state.home,'session.put',{'provider':'fal','value':'fake-new-rotated-value','replace':True})
    b=call(p,'exec',request(w,request_key='second'))
    assert int(a['stdout'])==len(KEY) and int(b['stdout'])==len('fake-new-rotated-value')


def test_default_local_exec_also_needs_scope_and_session(env):
    from agent_tool_maker.cli import main
    import subprocess
    r,w,s,_=env
    opts=dict(mappings=['FAL_KEY=atm://fal'],argv=[sys.executable,'app.py'],workspace=w)
    p=permit_exec(r,'local',**opts);permit_exec(r,'local',**opts,apply=True,approve=p['sha256'])
    run=subprocess.run([shutil.which('atm'),'--home',str(r.state.home),'exec','--env','FAL_KEY=atm://fal',
                        '--workspace',str(w),'--',sys.executable,'app.py'],capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=20)
    assert run.returncode==0 and json.loads(run.stdout)['status']=='completed'


@pytest.mark.parametrize('mutation', ['rotation', 'expiry', 'rule_removal', 'revoke'])
def test_change_during_decryption_never_admitted(env, monkeypatch, mutation):
    r,w,s,_=env;p,g,_=permit(env)
    original=Vault.get
    def changed(vault, name):
        value=original(vault,name)
        if mutation=='rotation':
            r.vault.put('fal','new-fake-key')
        elif mutation=='expiry':
            r.state.set_setting('credential_meta:fal', {'expires_at':time.time()-1})
        else:
            policy=r.state.setting('access:'+g['grant_id'])
            if mutation=='rule_removal':policy['exec_rules']=[]
            else:policy['revoked']=True
            r.state.set_setting('access:'+g['grant_id'],policy)
        return value
    monkeypatch.setattr(Vault,'get',changed)
    with pytest.raises(RouterError) as error:call(p,'exec',request(w))
    assert error.value.code in {'connection_changed','credential_expired','grant_stale','unauthorized'}
    assert r.state.jobs()==[]


def test_session_capacity_refuses_without_new_job(env):
    r,w,s,_=env;p,_,_=permit(env)
    assert s.capacity.acquire(False) and s.capacity.acquire(False)
    try:
        with pytest.raises(RouterError) as error:call(p,'exec',request(w))
        assert error.value.code=='session_busy' and not r.state.jobs()
    finally:
        s.capacity.release();s.capacity.release()


def test_dotdot_workspace_cannot_target_vault(env):
    r,w,s,_=env
    disguised=w/'..'/'state'
    with pytest.raises(RouterError) as error:command_plan(r,[sys.executable,'-c','print(1)'],{'FAL_KEY':'fal'},disguised)
    assert error.value.code=='unsafe_workspace'


def test_dotdot_file_cannot_escape_project(env):
    r,w,s,root=env;(root/'outside.py').write_text('print(1)')
    with pytest.raises(RouterError) as error:command_plan(r,[sys.executable,'../outside.py'],{'FAL_KEY':'fal'},w)
    assert error.value.code=='unsafe_command_file'


def test_lock_between_authentication_and_router_open_never_reprompts(env,monkeypatch):
    r,w,s,_=env;p,_,_=permit(env)
    original=s.open_router
    def race():
        s._key=None  # Simulate a simultaneous lock just after first authorization.
        return original()
    monkeypatch.setattr(s,'open_router',race)
    monkeypatch.setattr(Vault,'unlock',lambda *_:pytest.fail('Forbidden prompt/keyring fallback'))
    with pytest.raises(RouterError) as error:call(p,'exec',request(w))
    assert error.value.code=='broker_locked' and not r.state.jobs()


def test_cleared_request_vault_never_uses_password_or_keyring(env,monkeypatch):
    from agent_tool_maker.session import SessionVault
    r,w,s,_=env
    vault=SessionVault(r.state,None)
    monkeypatch.setattr(Vault,'unlock',lambda *_:pytest.fail('Forbidden direct unlock'))
    monkeypatch.setenv('ATM_VAULT_PASSWORD','not-to-be-used')
    with pytest.raises(RouterError) as error:vault.get('fal')
    assert error.value.code=='broker_locked'


def test_python_venv_invocation_preserved_with_installed_dependency(env):
    import venv
    from agent_tool_maker.secrets_provider import normalized_argv
    r,w,s,root=env
    v=w/'.venv';venv.EnvBuilder(with_pip=False,symlinks=True).create(v)
    dep=v/'lib'/('python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor))/'site-packages'/'atm_venv_fixture'
    dep.mkdir(parents=True);(dep/'__init__.py').write_text('VALUE="dependency-loaded"')
    (w/'app.py').write_text('import os,atm_venv_fixture\nprint(atm_venv_fixture.VALUE, bool(os.environ["FAL_KEY"]))')
    invoked=str(v/'bin'/'python')
    options=dict(mappings=['FAL_KEY=atm://fal'],argv=[invoked,'app.py'],workspace=w,output=root/'venv.json')
    plan=permit_exec(r,'claude',**options);permit_exec(r,'claude',**options,apply=True,approve=plan['sha256'])
    argv=normalized_argv([invoked,'app.py']);assert argv[0]==invoked
    out=call(root/'venv.json','exec',request(w,argv=argv))
    assert out['status']=='completed' and out['stdout']=='dependency-loaded True\n'
    (v/'pyvenv.cfg').write_text((v/'pyvenv.cfg').read_text()+'\n# changed configuration\n')
    with pytest.raises(RouterError) as error:call(root/'venv.json','exec',request(w,argv=argv,request_key='changed-venv'))
    assert error.value.code=='grant_stale'


def test_executable_symlink_retarget_invalidates_permit(env):
    from agent_tool_maker.secrets_provider import normalized_argv
    r,w,s,root=env
    link=w/'runner';link.symlink_to('/bin/echo')
    options=dict(mappings=['FAL_KEY=atm://fal'],argv=[str(link),'ok'],workspace=w,output=root/'link.json')
    plan=permit_exec(r,'claude',**options);permit_exec(r,'claude',**options,apply=True,approve=plan['sha256'])
    link.unlink();link.symlink_to('/bin/false')
    with pytest.raises(RouterError) as error:call(root/'link.json','exec',request(w,argv=normalized_argv([str(link),'ok'])))
    assert error.value.code=='grant_stale'
