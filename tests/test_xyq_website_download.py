"""Secure byte delivery and native-receipt protocol; no real website activity."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from PIL import Image,PngImagePlugin
import pytest
from agent_tool_maker import website_download as d
from agent_tool_maker.errors import RouterError
run_bridge=d._run_bridge
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('xyq_download_builder',ROOT/'scripts/build_xyq_download.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
# The reviewed download closure the fixture bridges load; its digest is the compiled --adapter-pin.
ADAPTER=ROOT/'examples/opencli/xyq-web';PIN=b.bundle_digest(b.DOWNLOAD_FILES)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def args(key='one-download'):
    return {'thread_id':'00000000-0000-0000-0000-000000000001','result_id':'b'*32,'expected_result_sha256':'a'*64,'quote_sha256':'c'*64,'request_key':key,'human_confirmed':True}
def native_record(workspace,download_root,settings):
    ledger=workspace/'.atm/xyq-result-downloads';key=d._sha(settings['request_key'].encode());fp=d._sha(d._json(['xyq-existing-image-download-v1',settings]))
    r={'version':1,'status':'download_observed','request_key':settings['request_key'],'fingerprint':fp,'thread_id':settings['thread_id'],'result_id':settings['result_id'],'result_sha256':settings['expected_result_sha256'],'quote_sha256':settings['quote_sha256'],'width':81,'height':108,'filename':'fixture.png',
       'download':{'filename':str(download_root/'fixture.png'),'state':'complete','source_result_id':settings['result_id'],'source_association_verified':True,'download_freshness_verified':False}}
    (ledger/(key+'.json')).write_bytes(d._json(r));(ledger/'active.lock').write_bytes(d._json({'version':1,'request_key':settings['request_key'],'fingerprint':fp}));return r
@pytest.fixture
def setup(tmp_path,workspace,monkeypatch):
    root=tmp_path/'downloads';root.mkdir();source=root/'fixture.png';info=PngImagePlugin.PngInfo();info.add_text('comment','FAKE_PRIVATE_TAG');Image.new('RGB',(81,108),'blue').save(source,pnginfo=info)
    bridge=tmp_path/'fixture-bridge';bridge.write_text('#!/bin/sh\nexit 0\n');bridge.chmod(0o700);calls=[]
    def run(path,pin,adapter,settings,work,download_root):
        assert download_root==str(root);calls.append(settings.copy());p=Path(work);r=json.loads((p/'.atm/xyq-result-downloads'/(d._sha(settings['request_key'].encode())+'.delivery.json')).read_bytes())
        assert r['status']=='dispatch_claimed' and (p/'.atm/xyq-result-downloads/delivery-active.lock').is_file();native_record(p,root,settings)
    monkeypatch.setattr(d,'_run_bridge',run)
    return {'root':root,'source':source,'bridge':bridge,'calls':calls,'run':run,'workspace':workspace}
def invoke(x,settings=None,adapter=ADAPTER):return d.download(str(x['workspace']),args() if settings is None else settings,str(x['bridge']),sha(x['bridge']),PIN,str(x['root']),str(adapter))
def test_exact_arguments_confirmation_and_pin_before_any_dispatch(setup):
    x=setup
    for bad in ['null',[],{}, {**args(),'url':'https://HOST'}, {**args(),'request_key':'../key'}, {**args(),'thread_id':3}]:
        with pytest.raises(RouterError) as e:invoke(x,bad)
        assert e.value.code=='invalid_argument'
    with pytest.raises(RouterError) as e:invoke(x,{**args(),'human_confirmed':False})
    assert e.value.code=='confirmation_required' and not x['calls'] and not (x['workspace']/'.atm').exists();assert d.settings(dict(reversed(list(args().items()))))==args()
def test_observed_exact_source_import_decodes_and_preserves_original_download(setup):
    x=setup;original=x['source'].read_bytes();r=invoke(x)
    assert r['status']=='delivered' and r['download_verified'] and r['complete_decode_verified'] and r['source_association_verified'] and r['locks_finalized']
    assert r['artifact']['media']['width']==81 and r['artifact']['media']['height']==108 and r['provider_task_id'] is None
    assert not r['provider_generation_verified'] and not r['task_association_verified'] and not r['download_freshness_verified']
    assert not r['paid_submitted'] and not r['generation_submitted'] and not r['credentials_read'] and 'FAKE_PRIVATE' not in json.dumps(r) and 'https://' not in json.dumps(r)
    assert x['source'].read_bytes()==original and len(x['calls'])==1
    p=x['workspace']/r['artifact']['file'];assert p.read_bytes()==original and p.stat().st_mode&0o777==0o600
    assert not (p.parent/'active.lock').exists() and not (p.parent/'delivery-active.lock').exists() and len(list(p.parent.glob('*.completed')))==2
def test_same_original_key_and_status_recheck_artifact_without_any_bridge_dispatch(setup):
    x=setup;a=invoke(x);r=invoke(x,dict(reversed(list(args().items()))));s=d.status(str(x['workspace']),'one-download')
    assert r['reused'] and s['status']=='delivered' and r['artifact']['sha256']==a['artifact']['sha256'] and len(x['calls'])==1
    (x['workspace']/a['artifact']['file']).write_bytes(b'changed')
    for call in [lambda:invoke(x),lambda:d.status(str(x['workspace']),'one-download')]:
        with pytest.raises(RouterError) as e:call()
        assert e.value.code=='media_hash_mismatch'
    assert len(x['calls'])==1
def test_unknown_native_or_unobserved_dispatch_does_not_repeat_same_or_new_key(setup,monkeypatch):
    x=setup
    def lost(*a):x['calls'].append('unknown');raise RouterError('download_unknown','FAKE_PRIVATE_MESSAGE')
    monkeypatch.setattr(d,'_run_bridge',lost)
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='delivery_unknown' and e.value.uncertain and 'FAKE_PRIVATE' not in str(e.value)
    before={p.name:p.read_bytes() for p in (x['workspace']/'.atm/xyq-result-downloads').iterdir()}
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='download_unknown'
    with pytest.raises(RouterError) as e:invoke(x,args('new-key'))
    assert e.value.code=='workspace_busy' and len(x['calls'])==1
    after={p.name:p.read_bytes() for p in (x['workspace']/'.atm/xyq-result-downloads').iterdir()};assert before==after
    s=d.status(str(x['workspace']),'one-download');assert not s['native_source_observed'] and not s['local_finalization_available']
def test_observed_original_download_can_finish_locally_after_lost_outer_ack(setup,monkeypatch):
    x=setup
    def lost(*a):x['run'](*a);raise RouterError('download_unknown','outer ack missing')
    monkeypatch.setattr(d,'_run_bridge',lost)
    with pytest.raises(RouterError):invoke(x)
    s=d.status(str(x['workspace']),'one-download');assert s['native_source_observed'] and s['local_finalization_available']
    r=invoke(x);assert r['status']=='delivered' and r['reused'] and len(x['calls'])==1
    assert r['failure_code'] is None and r['failure_phase'] is None and r['previous_failure']=={'code':'download_unknown','phase':'bridge_dispatch'}
    assert d.status(str(x['workspace']),'one-download')['previous_failure']==r['previous_failure']
@pytest.mark.parametrize('case',['root','source_symlink','source_hardlink','html','oversized'])
def test_unknown_or_invalid_download_is_not_delivered_and_bytes_locks_are_retained(setup,monkeypatch,tmp_path,case):
    x=setup
    if case=='root':
        other=tmp_path/'other';other.mkdir();(other/'fixture.png').write_bytes(b'PRIVATE_MUST_NOT_READ')
        def different(*a):x['run'](*a);native_record(x['workspace'],other,args())
        monkeypatch.setattr(d,'_run_bridge',different)
    elif case=='source_symlink':x['source'].rename(x['root']/'original.png');x['source'].symlink_to(x['root']/'original.png')
    elif case=='source_hardlink':os.link(x['source'],x['root']/'linked.png')
    elif case=='html':x['source'].write_bytes(b'<html>FAKE_PRIVATE_ERROR</html>')
    elif case=='oversized':
        with x['source'].open('wb') as f:f.truncate(d.MAX_IMAGE_BYTES+1)
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='delivery_unknown' and e.value.uncertain
    ledger=x['workspace']/'.atm/xyq-result-downloads';assert (ledger/'active.lock').is_file() and (ledger/'delivery-active.lock').is_file()
    r=json.loads(next(ledger.glob('*.delivery.json')).read_bytes());assert r['status']=='delivery_unknown' and r['failure_phase']=='file_import_and_decode'
    if case=='html':assert r['failure_code']=='media_format_mismatch'
    assert 'FAKE_PRIVATE' not in json.dumps(r)
    with pytest.raises(RouterError):invoke(x)
    assert len(x['calls'])==1
def test_preexisting_output_bad_root_and_changed_bridge_are_zero_dispatch(setup,tmp_path):
    x=setup;key=d._sha(args()['request_key'].encode());ledger=x['workspace']/'.atm/xyq-result-downloads';ledger.mkdir(parents=True);output=ledger/(key+'.png');output.write_bytes(b'preserve')
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='artifact_present_unverified' and output.read_bytes()==b'preserve' and not x['calls']
    with pytest.raises(RouterError) as e:d.download(str(x['workspace']),args(),str(x['bridge']),'0'*64,PIN,str(x['root']),str(ADAPTER))
    assert e.value.code=='executable_changed' and not x['calls']
    with pytest.raises(RouterError) as e:d.download(str(x['workspace']),args(),str(x['bridge']),sha(x['bridge']),PIN,str(tmp_path/'missing'),str(ADAPTER))
    assert e.value.code=='unsafe_path' and not x['calls']
def test_wrong_native_resource_fingerprint_is_retained_not_trusted(setup,monkeypatch):
    x=setup
    def wrong(*a):
        x['run'](*a);ledger=x['workspace']/'.atm/xyq-result-downloads';p=next(p for p in ledger.glob('*.json') if not p.name.endswith('.delivery.json'));r=json.loads(p.read_bytes());r['fingerprint']='0'*64;p.write_bytes(d._json(r))
    monkeypatch.setattr(d,'_run_bridge',wrong)
    with pytest.raises(RouterError):invoke(x)
    ledger=x['workspace']/'.atm/xyq-result-downloads';assert not list(ledger.glob('*.png'));r=json.loads(next(ledger.glob('*.delivery.json')).read_bytes());assert r['failure_code']=='receipt_invalid'
def refusal(settings,filename='fixture.png',intent_recorded=False):
    return {'status':'download_target_exists','thread_id':settings['thread_id'],'result_id':settings['result_id'],'request_key':settings['request_key'],'filename':filename,'browser_input':False,'intent_recorded':intent_recorded}
def unsent_record(workspace,settings,status='download_not_sent',filename='fixture.png'):
    # The bridge's durable record of an attempt that stopped after intent and before any observer or input.
    ledger=workspace/'.atm/xyq-result-downloads';key=d._sha(settings['request_key'].encode());fp=d._sha(d._json(['xyq-existing-image-download-v1',settings]))
    r={'version':1,'status':status,'request_key':settings['request_key'],'fingerprint':fp,'thread_id':settings['thread_id'],'result_id':settings['result_id'],'result_sha256':settings['expected_result_sha256'],'quote_sha256':settings['quote_sha256'],'filename':filename,'width':81,'height':108,'failure_code':'download_target_exists'}
    (ledger/(key+'.json')).write_bytes(d._json(r));return r
def test_name_taken_after_native_intent_is_definite_once_the_bridge_recorded_no_input(setup,monkeypatch):
    x=setup;existing=x['source'].read_bytes();key=d._sha(b'one-download')
    def refused(path,pin,adapter,settings,work,root):
        x['calls'].append('unsent');unsent_record(Path(work),settings);return refusal(settings,intent_recorded=True)
    monkeypatch.setattr(d,'_run_bridge',refused)
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='download_target_exists' and not e.value.uncertain
    ledger=x['workspace']/'.atm/xyq-result-downloads';assert sorted(p.name for p in ledger.iterdir())==sorted(['finalize.lock',key+'.json'])
    assert json.loads((ledger/(key+'.json')).read_bytes())['status']=='download_not_sent' and x['source'].read_bytes()==existing
    # Same key, file still there: the bridge refuses before a new intent and the unsent record stays.
    monkeypatch.setattr(d,'_run_bridge',lambda path,pin,adapter,settings,work,root:refusal(settings))
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='download_target_exists' and not e.value.uncertain and sorted(p.name for p in ledger.iterdir())==sorted(['finalize.lock',key+'.json'])
    monkeypatch.setattr(d,'_run_bridge',x['run']);r=invoke(x)
    assert r['status']=='delivered' and r['locks_finalized'] and x['calls'][0]=='unsent' and len(x['calls'])==2
def test_same_name_download_target_is_definite_and_leaves_no_claim_or_lock(setup,monkeypatch):
    # The browser would save "fixture (1).png" or replace the user's file; nothing may stay locked.
    x=setup;existing=x['source'].read_bytes();seen=[]
    def refused(path,pin,adapter,settings,work,root):
        ledger=Path(work)/'.atm/xyq-result-downloads';seen.append(root)
        assert (ledger/'delivery-active.lock').is_file() and not (ledger/'active.lock').exists();return refusal(settings)
    monkeypatch.setattr(d,'_run_bridge',refused)
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='download_target_exists' and not e.value.uncertain and seen==[str(x['root'])]
    ledger=x['workspace']/'.atm/xyq-result-downloads';assert sorted(p.name for p in ledger.iterdir())==['finalize.lock']
    assert x['source'].read_bytes()==existing and sorted(p.name for p in x['root'].iterdir())==['fixture.png']
    with pytest.raises(RouterError) as e:d.status(str(x['workspace']),'one-download')
    assert e.value.code=='request_missing'
    monkeypatch.setattr(d,'_run_bridge',x['run']);r=invoke(x)
    assert r['status']=='delivered' and not r['reused'] and r['locks_finalized'] and len(x['calls'])==1 and x['source'].read_bytes()==existing
def test_in_progress_crdownload_reservation_corroborates_a_definite_name_refusal(setup,monkeypatch):
    # Chrome uniquifies against an in-progress download whose intermediate is "<name>.crdownload".
    x=setup;partial=x['root']/'fixture.png.crdownload';x['source'].rename(partial);existing=partial.read_bytes()
    monkeypatch.setattr(d,'_run_bridge',lambda path,pin,adapter,settings,work,root:refusal(settings))
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='download_target_exists' and not e.value.uncertain and '.crdownload' in str(e.value)
    assert sorted(p.name for p in (x['workspace']/'.atm/xyq-result-downloads').iterdir())==['finalize.lock']
    assert partial.read_bytes()==existing and sorted(p.name for p in x['root'].iterdir())==['fixture.png.crdownload']
def test_name_check_sees_chrome_finishing_its_in_progress_download_between_the_two_checks(tmp_path,monkeypatch):
    # Chrome atomically renames "<name>.crdownload" to "<name>"; checking the reservation
    # first means a rename right after the first check still leaves one name visible.
    root=tmp_path/'downloads';root.mkdir();partial=root/'fixture.png.crdownload';partial.write_bytes(b'USER_OWNED_FILE');stat=os.stat;seen=[]
    def racing(entry,*a,**k):
        try:return stat(entry,*a,**k)
        finally:
            if not seen and 'dir_fd' in k and entry in {'fixture.png','fixture.png.crdownload'}:seen.append(entry);partial.rename(root/'fixture.png')
    monkeypatch.setattr(os,'stat',racing)
    taken=d._name_taken(str(root),'fixture.png');monkeypatch.undo()
    assert taken and seen and (root/'fixture.png').read_bytes()==b'USER_OWNED_FILE' and not partial.exists()
@pytest.mark.parametrize('case',['missing_name','native_lock','native_receipt','shape','other_result','intent_without_receipt','unknown_receipt','unsent_with_lock','unsent_acknowledged','unsent_other_name'])
def test_uncorroborated_name_refusal_keeps_original_intent_and_locks(setup,monkeypatch,case):
    x=setup;ledger=x['workspace']/'.atm/xyq-result-downloads'
    def refused(path,pin,adapter,settings,work,root):
        x['calls'].append(case);v=refusal(settings,'other.png' if case=='missing_name' else 'fixture.png',case in {'intent_without_receipt','unknown_receipt','unsent_with_lock','unsent_acknowledged','unsent_other_name'})
        if case in {'native_lock','unsent_with_lock'}:(ledger/'active.lock').write_bytes(b'{}')
        if case=='native_receipt':(ledger/(d._sha(settings['request_key'].encode())+'.json')).write_bytes(b'{}')
        if case=='unknown_receipt':unsent_record(ledger.parents[1],settings,'download_unknown')
        if case=='unsent_with_lock':unsent_record(ledger.parents[1],settings)
        # The unsent record names another save name than the refused, present one.
        if case=='unsent_other_name':unsent_record(ledger.parents[1],settings,filename='other.png')
        if case=='unsent_acknowledged':r=unsent_record(ledger.parents[1],settings);r['native_input_acknowledged']=False;(ledger/(d._sha(settings['request_key'].encode())+'.json')).write_bytes(d._json(r))
        if case=='shape':v['browser_input']=True
        if case=='other_result':v['result_id']='c'*32
        return v
    monkeypatch.setattr(d,'_run_bridge',refused)
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='delivery_unknown' and e.value.uncertain and (ledger/'delivery-active.lock').is_file() and x['source'].is_file()
    r=json.loads(next(ledger.glob('*.delivery.json')).read_bytes());assert r['status']=='delivery_unknown' and r['failure_phase']=='bridge_dispatch'
    assert r['failure_code']==('bridge_protocol' if case in {'shape','other_result'} else 'download_unknown')
    with pytest.raises(RouterError) as e:invoke(x,args('new-key'))
    assert e.value.code=='workspace_busy' and len(x['calls'])==1
@pytest.mark.integration
def test_real_bridge_subprocess_gets_download_root_and_name_refusal_withdraws_unsent_claim(setup,monkeypatch,tmp_path):
    x=setup;log=tmp_path/'bridge-argv.json';existing=x['source'].read_bytes();monkeypatch.setattr(d,'_run_bridge',run_bridge)
    x['bridge'].write_text('#!'+sys.executable+"""
import json,sys
a=sys.argv[1:];s=json.loads(a[a.index('--settings')+1])
open(LOG,'w').write(json.dumps(a))
print(json.dumps([{'result':{'status':'download_target_exists','thread_id':s['thread_id'],'result_id':s['result_id'],'request_key':s['request_key'],'filename':'fixture.png','browser_input':False,'intent_recorded':False}}]))
""".replace('LOG',repr(str(log))))
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='download_target_exists' and not e.value.uncertain
    argv=json.loads(log.read_text());assert argv[:3]==['__opencli_shim','xyq-web','result-download-bound'] and argv[argv.index('--download-root')+1]==str(x['root'])
    assert sorted(p.name for p in (x['workspace']/'.atm/xyq-result-downloads').iterdir())==['finalize.lock'] and x['source'].read_bytes()==existing
def installed_tools(router,tmp_path,bridge,root,adapter=ADAPTER):
    # Both reviewed definitions installed and the bound, hash-pinned source ATM child,
    # exactly as generated tool.py -> Router -> cli_adapter -> `atm delivery` runs them.
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.extensions import pack
    from agent_tool_maker.maker import install,digest
    source=tmp_path/'source-atm';source.write_text(f'#!{sys.executable}\nimport sys\nsys.path.insert(0,{str(ROOT/"src")!r})\nfrom agent_tool_maker.cli import main\nraise SystemExit(main())\n');source.chmod(0o700)
    bundles={}
    for op in b.OPERATIONS:
        t=b.manifest(op,str(bridge),str(root),str(adapter));bundles[op]=Path(pack(t,tmp_path/('bundle-'+op))['directory'])
        install(router.state,router.catalog,bundles[op]/'manifest.json',digest(t))
    router.catalog=Catalog(router.state);bind_cli(router.state,'atm',str(source))
    def tool(op,job_key,inputs,workspace):
        inp=tmp_path/(job_key+'.json');inp.write_text(json.dumps(inputs))
        p=subprocess.run([sys.executable,str(bundles[op]/'tool.py'),'--atm',str(source),'--home',str(router.state.home),'--workspace',str(workspace),
            '--input',str(inp),'--request-key',job_key,'--allow-code',*(['--allow-write'] if op=='result_download' else [])],cwd=ROOT,capture_output=True,text=True)
        return p.returncode,json.loads(p.stdout)
    return tool
@pytest.mark.integration
def test_installed_tool_name_refusal_is_a_definite_failed_job_with_no_lock_left(setup,router,tmp_path):
    x=setup;existing=x['source'].read_bytes();calls=tmp_path/'bridge-calls'
    x['bridge'].write_text('#!'+sys.executable+"""
import json,sys
a=sys.argv[1:];s=json.loads(a[a.index('--settings')+1])
open(CALLS,'a').write('x')
print(json.dumps([{'result':{'status':'download_target_exists','thread_id':s['thread_id'],'result_id':s['result_id'],'request_key':s['request_key'],'filename':'fixture.png','browser_input':False,'intent_recorded':False}}]))
""".replace('CALLS',repr(str(calls))))
    tool=installed_tools(router,tmp_path,x['bridge'],x['root'])
    code,job=tool('result_download','job-one',{'settings':args()},x['workspace'])
    assert code==2 and job['status']=='failed',job
    assert job['data']['error']['code']=='download_target_exists' and job['data']['error']['outcome_uncertain'] is False
    assert sorted(p.name for p in (x['workspace']/'.atm/xyq-result-downloads').iterdir())==['finalize.lock']
    assert x['source'].read_bytes()==existing and sorted(p.name for p in x['root'].iterdir())==['fixture.png'] and calls.read_text()=='x'
    code,status=tool('result_download_status','status-one',{'request_key':'one-download'},x['workspace'])
    assert code==2 and status['status']=='failed' and status['data']['error']['code']=='request_missing' and status['data']['error']['outcome_uncertain'] is False
    # The failed job is final for its job key; nothing is re-run.
    code,again=tool('result_download','job-one',{'settings':args()},x['workspace'])
    assert again['id']==job['id'] and again['status']=='failed' and calls.read_text()=='x'
def test_partial_lock_finalization_resumes_only_local_validation_and_retained_lock_rename(setup,monkeypatch):
    x=setup;release=d._release;calls=[]
    def interrupted(fd,name,key,fp):
        calls.append(name)
        if len(calls)==2:raise RouterError('receipt_invalid','fixture lock ack lost')
        return release(fd,name,key,fp)
    monkeypatch.setattr(d,'_release',interrupted)
    with pytest.raises(RouterError):invoke(x)
    s=d.status(str(x['workspace']),'one-download');assert s['status']=='file_verified' and s['complete_decode_verified'] and not s['locks_finalized']
    monkeypatch.setattr(d,'_release',release);r=invoke(x);assert r['status']=='delivered' and r['locks_finalized'] and len(x['calls'])==1
    assert r['failure_code'] is None and r['failure_phase'] is None and r['previous_failure']=={'code':'receipt_invalid','phase':'lock_finalization'}
def closure_copy(tmp_path):
    # A loader laid out as installed: <loader>/reviewed/ holds the exact reviewed closure.
    copy=tmp_path/'xyq-download-bound/reviewed';copy.mkdir(parents=True)
    for name in b.DOWNLOAD_FILES:(copy/name).write_bytes((ADAPTER/name).read_bytes())
    return copy
@pytest.mark.parametrize('case',['stale','missing','linked_file','linked_dir','not_canonical','absent'])
def test_stale_or_unreviewed_loader_closure_is_a_definite_refusal_before_any_ledger_or_dispatch(setup,tmp_path,case):
    # The bridge would refuse its pin only after this pipeline's claim, leaving
    # delivery_unknown and delivery-active.lock; the closure is checked first, read-only.
    x=setup;copy=closure_copy(tmp_path);adapter=copy
    if case=='stale':(copy/'download.mjs').write_bytes((copy/'download.mjs').read_bytes()+b'\n')
    if case=='missing':(copy/'download.js').unlink()
    if case=='linked_file':(copy/'core.mjs').unlink();(copy/'core.mjs').symlink_to(ADAPTER/'core.mjs')
    if case=='linked_dir':adapter=tmp_path/'linked-reviewed';adapter.symlink_to(copy)
    if case=='not_canonical':adapter=str(copy)+'/../reviewed'
    if case=='absent':adapter=None
    before={p.name:p.read_bytes() for p in copy.iterdir() if not p.is_symlink()}
    with pytest.raises(RouterError) as e:d.download(str(x['workspace']),args(),str(x['bridge']),sha(x['bridge']),PIN,str(x['root']),None if adapter is None else str(adapter))
    assert e.value.code==('invalid_argument' if case in {'not_canonical','absent'} else 'definition_changed') and not e.value.uncertain
    assert not x['calls'] and not (x['workspace']/'.atm').exists() and before=={p.name:p.read_bytes() for p in copy.iterdir() if not p.is_symlink()}
    # Reinstalling the exact closure lets the next run claim and dispatch normally.
    r=invoke(x,adapter=closure_copy(tmp_path/'reinstalled'));assert r['status']=='delivered' and len(x['calls'])==1
def test_python_loader_check_and_documented_node_check_agree_with_the_pin(tmp_path):
    copy=closure_copy(tmp_path);before={p.name:p.read_bytes() for p in copy.iterdir()}
    assert d.ADAPTER_FILES==b.DOWNLOAD_FILES and d.adapter_digest(str(ADAPTER))==d.adapter_digest(str(copy))==PIN
    # The read-only check the upgrade contract tells the human to run against <loader>/reviewed/.
    out=subprocess.run(['node','--input-type=module','-e',f"import {{downloadDigest}} from '{copy}/download.mjs'; console.log(downloadDigest())"],cwd=tmp_path,capture_output=True,text=True,check=True)
    assert out.stdout.strip()==PIN and before=={p.name:p.read_bytes() for p in copy.iterdir()}
@pytest.mark.integration
def test_installed_tool_with_a_stale_loader_closure_is_a_definite_failed_job_that_leaves_no_lock(setup,router,tmp_path):
    # New definitions over an old xyq-download-bound reviewed/ closure: no claim, no
    # delivery_unknown, nothing that blocks the workspace; reinstalling it then works.
    x=setup;calls=tmp_path/'bridge-calls';copy=closure_copy(tmp_path);fresh=(copy/'download.mjs').read_bytes();(copy/'download.mjs').write_bytes(fresh+b'// stale\n')
    x['bridge'].write_text('#!'+sys.executable+"""
import json,sys
a=sys.argv[1:];s=json.loads(a[a.index('--settings')+1])
open(CALLS,'a').write('x')
print(json.dumps([{'result':{'status':'download_target_exists','thread_id':s['thread_id'],'result_id':s['result_id'],'request_key':s['request_key'],'filename':'fixture.png','browser_input':False,'intent_recorded':False}}]))
""".replace('CALLS',repr(str(calls))))
    tool=installed_tools(router,tmp_path,x['bridge'],x['root'],copy)
    code,job=tool('result_download','job-stale',{'settings':args()},x['workspace'])
    assert code==2 and job['status']=='failed' and job['data']['error']['code']=='definition_changed' and job['data']['error']['outcome_uncertain'] is False,job
    # The job runner keeps only its own artifact directory; no download ledger, claim or lock.
    assert not (x['workspace']/'.atm/xyq-result-downloads').exists() and not calls.exists()
    (copy/'download.mjs').write_bytes(fresh)
    code,job=tool('result_download','job-reinstalled',{'settings':args()},x['workspace'])
    assert job['data']['error']['code']=='download_target_exists' and calls.read_text()=='x',job
def test_definition_compiled_without_a_loader_closure_reaches_the_pin_check_first(workspace,tmp_path,setup):
    # Older definitions lack --adapter-dir: their stale --pin is still definition_changed, and a
    # current pin without the closure is a definite argument error; neither creates a ledger.
    x=setup;base=[sys.executable,'-m','agent_tool_maker','--home',str(tmp_path/'unused-home'),'delivery','xyq-image','--workspace',str(workspace),'--settings',json.dumps(args()),
        '--bridge',str(x['bridge']),'--bridge-sha256',sha(x['bridge']),'--adapter-pin',PIN,'--download-root',str(x['root']),'--pin']
    for pin,code in [('0'*64,'definition_changed'),(d.source_digest(),'invalid_argument')]:
        p=subprocess.run(base+[pin],cwd=ROOT,capture_output=True,text=True);error=json.loads(p.stdout)['error']
        assert p.returncode==2 and error['code']==code and error['outcome_uncertain'] is False and not (workspace/'.atm').exists()
def test_factory_requires_the_exact_existing_loader_closure_directory(setup,tmp_path):
    x=setup;linked=tmp_path/'linked-reviewed';linked.symlink_to(ADAPTER)
    for adapter in [None,'relative/reviewed','/',str(ADAPTER)+'/../xyq-web',str(tmp_path/'missing'),str(linked)]:
        with pytest.raises(ValueError):b.manifest('result_download',str(x['bridge']),str(x['root']),adapter)
def test_status_missing_never_creates_a_ledger_or_router_home(workspace,tmp_path):
    with pytest.raises(RouterError) as e:d.status(str(workspace),'missing')
    assert e.value.code=='request_missing' and not (workspace/'.atm').exists();home=tmp_path/'unused-home'
    p=subprocess.run([sys.executable,'-m','agent_tool_maker','--home',str(home),'delivery','status','--pin',d.source_digest(),'--workspace',str(workspace),'--request-key','missing'],cwd=ROOT,capture_output=True,text=True)
    assert p.returncode==2 and json.loads(p.stdout)['error']['code']=='request_missing' and not home.exists()
def test_hardlinked_receipt_write_stops_before_truncation(setup):
    x=setup
    with d._ledger(str(x['workspace'])) as fd:
        p=x['workspace']/'.atm/xyq-result-downloads/receipt.json';p.write_bytes(b'original');os.link(p,p.with_suffix('.linked'))
        with pytest.raises(RouterError) as e:d._write(fd,'receipt.json',{'changed':True})
        assert e.value.code=='unsafe_path' and p.read_bytes()==b'original'
@pytest.mark.parametrize('operation',b.OPERATIONS)
def test_fixed_factory_hashes_permissions_and_compiled_definition(setup,tmp_path,operation):
    from agent_tool_maker.extensions import pack,validate_bundle
    from agent_tool_maker.maker import digest
    x=setup;t=b.manifest(operation,str(x['bridge']),str(x['root']),str(ADAPTER));pack(t,tmp_path/operation)
    assert validate_bundle(tmp_path/operation)['sha256']==digest(t) and not t['paid'] and t['executable']=='atm'
    assert t['permissions']==(['execute_code','external_write'] if operation=='result_download' else ['execute_code'])
    assert 'credential' not in t and 'credential_env' not in t['command'] and d.source_digest() in t['command']['argv']
    argv=t['command']['argv']
    if operation=='result_download':assert argv[argv.index('--adapter-dir')+1]==str(ADAPTER) and argv[argv.index('--adapter-pin')+1]==PIN
    else:assert '--adapter-dir' not in argv
def test_node_python_download_pin_agrees_and_registered_reads_are_unchanged():
    out=subprocess.run(['node','--input-type=module','-e',"import {downloadDigest} from './examples/opencli/xyq-web/download.mjs';import {resultDigest} from './examples/opencli/xyq-web/results.mjs';console.log(JSON.stringify([downloadDigest(),resultDigest()]));"],cwd=ROOT,capture_output=True,text=True,check=True)
    pins=json.loads(out.stdout);assert pins[0]==b.bundle_digest(b.DOWNLOAD_FILES) and pins[1]=='99e0f848f994e3f030f257d9b7894660e70f96c311a28a1ae158810f40eb3dda'

def test_imported_manual_unknown_blocks_same_resource_with_any_new_key_before_dispatch(setup):
    x=setup;a=args();r=d.record_unknown(str(x['workspace']),a['thread_id'],a['result_id'],'original-manual-key')
    assert r['recorded'] and not r['browser_input']
    marker=x['workspace']/'.atm/xyq-result-downloads/external-unknown.json';old=marker.read_bytes()
    for key in ['one-download','another-new-key']:
        with pytest.raises(RouterError) as e:invoke(x,args(key))
        assert e.value.code=='download_unknown' and e.value.uncertain and not x['calls']
    assert marker.read_bytes()==old
    s=d.status(str(x['workspace']),'original-manual-key');assert s['external_unknown'] and not s['download_verified']
    assert d.record_unknown(str(x['workspace']),a['thread_id'],a['result_id'],'original-manual-key')['reused']

def test_imported_unknown_malformed_or_duplicate_keys_are_errors_not_empty_state(setup):
    x=setup;a=args();d.record_unknown(str(x['workspace']),a['thread_id'],a['result_id'],'original-manual-key')
    with pytest.raises(RouterError) as e:d.record_unknown(str(x['workspace']),a['thread_id'],'c'*32,'original-manual-key')
    assert e.value.code=='request_conflict'
    marker=x['workspace']/'.atm/xyq-result-downloads/external-unknown.json';marker.write_text('{"version":1,"records":[],"records":[]}')
    with pytest.raises(RouterError) as e:invoke(x)
    assert e.value.code=='receipt_invalid' and not x['calls']
