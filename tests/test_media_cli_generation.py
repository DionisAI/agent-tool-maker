"""Staged definition, fake subprocess and native fixture evidence, no real billing."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_xyq_web_cli import native_page, load
from test_xyq_web_home_quote import quote_html

ROOT=Path(__file__).resolve().parents[1]
def builder(name):
    spec=importlib.util.spec_from_file_location('delivery_'+name,ROOT/'scripts'/('build_'+name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
xyq=builder('xyq_web');tripo=builder('tripo_studio')

@pytest.mark.parametrize('provider,op', [('xyq',x) for x in xyq.GENERATION_OPERATIONS]+[('tripo',x) for x in tripo.DELIVERY_OPERATIONS])
def test_new_bundle_factory_pins_and_permissions(tmp_path,provider,op):
    from agent_tool_maker.extensions import pack,validate_bundle
    from agent_tool_maker.maker import digest
    t=xyq.generation_manifest(op) if provider=='xyq' else tripo.delivery_manifest(op)
    dest=tmp_path/op;pack(t,dest);assert validate_bundle(dest)['sha256']==digest(t)
    assert t['paid'] is (op in {'generate','texture'})
    assert 'execute_code' in t['permissions']
    assert ('external_write' in t['permissions']) is (op in {'generate','texture','texture_quote'})
    assert 'credential_env' not in t['command'] and 'credential' not in t
    if t['paid']:
        props=t['schema']['properties']['settings']['properties'] if provider=='xyq' else t['schema']['properties']
        assert props['human_confirmed']['const'] is True

def test_node_and_python_transitive_pins_agree():
    command="import {generationDigest} from './examples/opencli/xyq-web/generation.mjs';import {deliveryDigest} from './examples/opencli/tripo-studio/delivery.mjs';console.log(JSON.stringify([generationDigest(),deliveryDigest()]));"
    pins=json.loads(subprocess.run(['node','--input-type=module','-e',command],cwd=ROOT,check=True,capture_output=True,text=True).stdout)
    assert pins[0]==xyq.bundle_digest(xyq.GENERATION_FILES)
    assert pins[1] in tripo.delivery_manifest('operation_status')['command']['argv']

def test_xyq_paid_grant_required_and_real_fake_subprocess_request_reuse(router,workspace,tmp_path):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.errors import RouterError
    from agent_tool_maker.maker import install,digest
    t=xyq.generation_manifest('generate');p=tmp_path/'manifest.json';p.write_text(json.dumps(t));install(router.state,router.catalog,p,digest(t));router.catalog=Catalog(router.state)
    settings={'expected_draft_sha256':'a'*64,'quote_sha256':'b'*64,'max_credits':6,'human_confirmed':True,'estimated_cost_confirmed':True,'request_key':'fake-once'}
    program=tmp_path/'fake-opencliapp';program.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','generate-home-bound']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
settings=json.loads(sys.argv[sys.argv.index('--settings')+1]);assert settings['request_key']=='fake-once'
p=Path('fixture-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fixture_submitted','provider_task_id':None,'task_completed':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *a:pytest.fail('No vault reads')
    with pytest.raises(RouterError) as denied:router.run(t['id'],{'settings':settings},workspace,request_key='fake-once',grants=['execute_code','external_write'])
    assert denied.value.code=='paid_confirmation_required' and not (workspace/'fixture-count').exists()
    a=router.run(t['id'],{'settings':settings},workspace,request_key='fake-once',grants=['execute_code','external_write'],allow_paid=True)
    b=router.run(t['id'],{'settings':settings},workspace,request_key='fake-once',grants=['execute_code','external_write'],allow_paid=True)
    assert a['status']=='completed' and a['id']==b['id'] and (workspace/'fixture-count').read_text()=='1'
    assert a['data']['result'][0]['result']['status']=='fixture_submitted'

def rpc(page,workspace,settings=None,disconnect=False,runtime=False):
    config={'workspace':str(workspace),'settings':settings or {},'runtime':runtime}
    proc=subprocess.Popen(['node','tests/fixtures/xyq_generation_rpc.mjs',json.dumps(config)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    clicks=0
    try:
        for line in proc.stdout:
            r=json.loads(line)
            if r['type']=='done':proc.wait(timeout=5);assert proc.returncode==0,proc.stderr.read();return r,clicks
            response={'id':r['id']}
            if r['method']=='evaluate':
                assert any(r['source'].startswith('function '+n+'(') for n in ['readHomeDOM','readDraftDOM','readHomeQuoteDOM','readGenerationInputDOM','readGenerationAcceptedDOM'])
                try:response['value']=page.evaluate(r['source'],r.get('arg'))
                except Exception:response['error']='fixture_evaluate_error'
            else:
                assert r['method']=='nativeClick';clicks+=1
                assert (workspace/'.atm/xyq-generation/active.lock').is_file()
                page.mouse.click(r['x'],r['y'])
                if disconnect:response['error']='fixture_lost_ack'
                else:
                    assert page.evaluate('window.submitted')==1
                    page.evaluate("history.replaceState(null,'','/project?projectId=123&canvasId=456');document.body.innerHTML='<div role=\"application\" data-testid=\"rf__wrapper\">fixture result route</div>'")
                    response['value']=None
            proc.stdin.write(json.dumps(response,ensure_ascii=False)+'\n');proc.stdin.flush()
        pytest.fail('No terminal fixture result')
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

@pytest.mark.browser
def test_native_submit_hits_exact_control_once_and_queries_original_local_receipt(native_page,workspace):
    load(native_page,quote_html('图片生成','6',None));result,clicks=rpc(native_page,workspace)
    assert 'error' not in result,result;r=result['result'][0]['result']
    assert clicks==1 and r['status']=='submitted' and r['project_id']=='123' and r['canvas_id']=='456'
    assert r['provider_task_id'] is None and not r['task_completed'] and not r['spend_ceiling_verified']
    assert result['reused'][0]['result']['reused'] and not result['status'][0]['result']['provider_checked']
    assert 'FAKE_PRIVATE' not in json.dumps(result)

@pytest.mark.browser
@pytest.mark.parametrize('case',['covered','budget','confirmation','rate','duplicate','slot'])
def test_native_generation_preflight_failure_is_zero_input(native_page,workspace,case):
    html=quote_html('图片生成','6',None)
    if case=='covered':html=html.replace('</body>','<div style="position:fixed;inset:0;z-index:100"></div></body>')
    if case=='rate':html=quote_html('音频生成','0.33/秒',None)
    load(native_page,html)
    if case=='duplicate':native_page.locator('button[aria-label="开始生成"]').evaluate('e=>e.after(e.cloneNode(true))')
    if case=='slot':native_page.locator('button[aria-label="开始生成"]').evaluate("e=>e.setAttribute('data-slot','changed')")
    result,clicks=rpc(native_page,workspace,{'max_credits':5} if case=='budget' else {'human_confirmed':False} if case=='confirmation' else None)
    assert 'error' in result and clicks==0 and not (workspace/'.atm/xyq-generation/active.lock').exists()
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_lost_ack_retains_unknown_operation_and_does_not_resubmit(native_page,workspace):
    load(native_page,quote_html('图片生成','6',None));result,clicks=rpc(native_page,workspace,disconnect=True)
    assert clicks==1 and result['error']['code']=='submission_unknown' and native_page.evaluate('window.submitted')==1
    ledger=workspace/'.atm/xyq-generation';assert (ledger/'active.lock').is_file()
    record=json.loads(next(ledger.glob('*.json')).read_text());assert record['status']=='submission_unknown' and record['failure_code']=='bridge_failed'
