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
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('xyq_download_builder',ROOT/'scripts/build_xyq_download.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
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
    def run(path,pin,adapter,settings,work):
        calls.append(settings.copy());p=Path(work);r=json.loads((p/'.atm/xyq-result-downloads'/(d._sha(settings['request_key'].encode())+'.delivery.json')).read_bytes())
        assert r['status']=='dispatch_claimed' and (p/'.atm/xyq-result-downloads/delivery-active.lock').is_file();native_record(p,root,settings)
    monkeypatch.setattr(d,'_run_bridge',run)
    return {'root':root,'source':source,'bridge':bridge,'calls':calls,'run':run,'workspace':workspace}
def invoke(x,settings=None):return d.download(str(x['workspace']),args() if settings is None else settings,str(x['bridge']),sha(x['bridge']),'f'*64,str(x['root']))
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
    with pytest.raises(RouterError) as e:d.download(str(x['workspace']),args(),str(x['bridge']),'0'*64,'f'*64,str(x['root']))
    assert e.value.code=='executable_changed' and not x['calls']
    with pytest.raises(RouterError) as e:d.download(str(x['workspace']),args(),str(x['bridge']),sha(x['bridge']),'f'*64,str(tmp_path/'missing'))
    assert e.value.code=='unsafe_path' and not x['calls']
def test_wrong_native_resource_fingerprint_is_retained_not_trusted(setup,monkeypatch):
    x=setup
    def wrong(*a):
        x['run'](*a);ledger=x['workspace']/'.atm/xyq-result-downloads';p=next(p for p in ledger.glob('*.json') if not p.name.endswith('.delivery.json'));r=json.loads(p.read_bytes());r['fingerprint']='0'*64;p.write_bytes(d._json(r))
    monkeypatch.setattr(d,'_run_bridge',wrong)
    with pytest.raises(RouterError):invoke(x)
    ledger=x['workspace']/'.atm/xyq-result-downloads';assert not list(ledger.glob('*.png'));r=json.loads(next(ledger.glob('*.delivery.json')).read_bytes());assert r['failure_code']=='receipt_invalid'
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
    x=setup;t=b.manifest(operation,str(x['bridge']),str(x['root']));pack(t,tmp_path/operation)
    assert validate_bundle(tmp_path/operation)['sha256']==digest(t) and not t['paid'] and t['executable']=='atm'
    assert t['permissions']==(['execute_code','external_write'] if operation=='result_download' else ['execute_code'])
    assert 'credential' not in t and 'credential_env' not in t['command'] and d.source_digest() in t['command']['argv']
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
