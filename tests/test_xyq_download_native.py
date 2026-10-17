"""Intercepted Chrome downloads + generated CLI chain; not provider acceptance."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import pytest
from test_xyq_web_cli import native_page
from test_xyq_website_download import b
from agent_tool_maker import website_download as d
from agent_tool_maker.errors import RouterError
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests/fixtures'))
from xyq_download_fixture import prepare,rpc,THREAD,RESOURCE

def quote(page,root):
    out,clicks=rpc(page,{'operation':'quote','scope':{'thread_id':THREAD,'result_id':RESOURCE}},root)
    assert 'error' not in out and clicks==0,out
    return out['result'][0]['result']

def settings(q,key):return {'thread_id':THREAD,'result_id':RESOURCE,'expected_result_sha256':q['result_sha256'],'quote_sha256':q['quote_sha256'],'request_key':key,'human_confirmed':True}

@pytest.mark.browser
@pytest.mark.parametrize('scenario',['normal','lost_ack','blob'])
def test_native_once_download_intent_event_identity_and_unknown_lock(native_page,tmp_path,workspace,scenario):
    root=tmp_path/'downloads';root.mkdir();prepare(native_page);q=quote(native_page,root)
    out,clicks=rpc(native_page,{'operation':'download','settings':settings(q,'native-once'),'workspace':str(workspace)},root,scenario)
    assert clicks==1 and (root/'fixture.png').is_file() and native_page.evaluate('window.inputs')==1
    ledger=workspace/'.atm/xyq-result-downloads';r=json.loads(next(ledger.glob('*.json')).read_bytes());assert (ledger/'active.lock').is_file()
    assert 'FAKE_PRIVATE' not in json.dumps(r) and 'https://' not in json.dumps(r)
    if scenario=='blob':assert out['error']['code']=='download_unknown' and r['status']=='download_unknown' and r['failure_code']=='download_source_unverified'
    else:
        assert out['result'][0]['result']['status']=='download_observed' and r['download']['source_result_id']==RESOURCE
        assert r['native_input_acknowledged'] is (scenario=='normal')
    again,count=rpc(native_page,{'operation':'download','settings':settings(q,'native-once'),'workspace':str(workspace)},root,scenario)
    assert count==0 and native_page.evaluate('window.inputs')==1
    assert ('error' in again) is (scenario=='blob')

@pytest.mark.browser
@pytest.mark.parametrize('scenario',['covered','disabled'])
def test_native_obscured_or_disabled_download_is_zero_input(native_page,tmp_path,workspace,scenario):
    root=tmp_path/'downloads';root.mkdir();prepare(native_page);q=quote(native_page,root)
    if scenario=='covered':native_page.evaluate("document.body.insertAdjacentHTML('beforeend','<div style=\"position:fixed;inset:0;z-index:99\"></div>')")
    else:native_page.locator('#download').evaluate('e=>e.disabled=true')
    out,count=rpc(native_page,{'operation':'download','settings':settings(q,'preflight-once'),'workspace':str(workspace)},root,scenario)
    assert 'error' in out and count==0 and not list(root.iterdir()) and not (workspace/'.atm').exists()

@pytest.mark.browser
def test_generated_cli_source_atm_fixed_bridge_native_download_and_full_decode(native_page,tmp_path,router,workspace,record_testsuite_property):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.extensions import pack
    from agent_tool_maker.maker import install,digest
    root=tmp_path/'downloads';root.mkdir();prepare(native_page);q=quote(native_page,root)
    # The bridge reuses native_page's isolated Chromium (ATM_CHROMIUM), never an installed browser app.
    bridge=tmp_path/'fixture-bridge';bridge.write_text(f'''#!{sys.executable}
import sys
sys.path.insert(0,{str(ROOT/'tests/fixtures')!r})
from xyq_download_fixture import bridge_main
raise SystemExit(bridge_main({str(root)!r},{os.environ['ATM_CHROMIUM']!r}))
''');bridge.chmod(0o700)
    source=tmp_path/'source-atm';source.write_text(f'''#!{sys.executable}
import sys
sys.path.insert(0,{str(ROOT/'src')!r})
from agent_tool_maker.cli import main
raise SystemExit(main())
''');source.chmod(0o700)
    t=b.manifest('result_download',str(bridge),str(root));bundle=pack(t,tmp_path/'bundle');p=Path(bundle['directory'])/'manifest.json'
    install(router.state,router.catalog,p,digest(t));router.catalog=Catalog(router.state);bind_cli(router.state,'atm',str(source))
    inp=tmp_path/'input.json';inp.write_text(json.dumps({'settings':settings(q,'generated-native-once')}))
    command=[sys.executable,str(Path(bundle['directory'])/'tool.py'),'--atm',str(source),'--home',str(router.state.home),'--workspace',str(workspace),
             '--input',str(inp),'--request-key','generated-native-once','--allow-code']
    denied=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);assert denied.returncode==2 and json.loads(denied.stdout)['error']['code']=='permission_required' and not (workspace/'.atm').exists()
    command.append('--allow-write');first=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);assert first.returncode==0,first.stdout
    job=json.loads(first.stdout);assert job['status']=='completed' and job['data']['paid_granted'] is False
    r=job['data']['result'][0]['result'];assert r['status']=='delivered' and r['download_verified'] and r['complete_decode_verified'] and r['locks_finalized']
    assert r['artifact']['media']['width']==81 and r['artifact']['media']['height']==108 and r['provider_task_id'] is None
    artifact=workspace/r['artifact']['file'];assert hashlib.sha256(artifact.read_bytes()).hexdigest()==r['artifact']['sha256']
    assert (workspace/'fixture-native-click-count').read_text()=='1' and 'FAKE_PRIVATE' not in first.stdout
    again=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);assert again.returncode==0 and json.loads(again.stdout)['id']==job['id'] and (workspace/'fixture-native-click-count').read_text()=='1'
    status=d.status(str(workspace),'generated-native-once');assert status['status']=='delivered' and status['artifact']['sha256']==r['artifact']['sha256']
    receipt=workspace/'fixture-download-verification.json';receipt.write_text(json.dumps({'status':'fixture_generated_cli_delivery_verified',
        'provider_called':False,'scope':'intercepted_native_fixture','job_id':job['id'],'native_click_count':1,'request_reuse_same_job':True,
        'artifact':r['artifact'],'source_association_verified':r['source_association_verified'],'provider_generation_verified':False,
        'paid_granted':False,'production_atm_changed':False},indent=2));receipt.chmod(0o600)
    record_testsuite_property('xyq_download_fixture_verification',str(receipt))
