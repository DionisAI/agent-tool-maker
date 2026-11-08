"""New production namespace, fake processes and native fixtures; no real account."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.errors import RouterError
from agent_tool_maker.extensions import pack,validate_bundle
from agent_tool_maker.maker import digest,install
from test_xyq_web_cli import native_page,load,fixture_html
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('media_runtime_builder',ROOT/'scripts/build_xyq_runtime.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

@pytest.mark.parametrize('operation',b.MEDIA_RUNTIME_OPERATIONS)
def test_runtime_definition_keeps_exact_existing_schema_grants_and_billing(operation,tmp_path):
    original=b.original_manifest(operation);tool=b.runtime_manifest(operation)
    for key in ('id','schema','permissions','paid','executable'):assert tool[key]==original[key]
    assert tool['command']['argv'][1:3]==['xyq-media',operation.replace('_','-')]
    assert b.bundle_digest(b.MEDIA_RUNTIME_FILES) in tool['command']['argv']
    assert tool['command']['argv'][7:]==original['command']['argv'][7:]
    assert 'credential' not in tool and 'credential_env' not in tool['command']
    pack(tool,tmp_path/operation);assert validate_bundle(tmp_path/operation)['sha256']==digest(tool)

def test_node_python_pins_and_dispatch_operations_match():
    command="import{MEDIA_RUNTIME_FILES,MEDIA_RUNTIME_OPERATIONS,mediaRuntimeDigest}from'./examples/opencli/xyq-web/media-runtime.mjs';console.log(JSON.stringify([MEDIA_RUNTIME_FILES,MEDIA_RUNTIME_OPERATIONS,mediaRuntimeDigest()]));"
    files,ops,pin=json.loads(subprocess.run(['node','--input-type=module','-e',command],cwd=ROOT,check=True,capture_output=True,text=True).stdout)
    assert files==list(b.MEDIA_RUNTIME_FILES) and ops==list(b.MEDIA_RUNTIME_OPERATIONS) and pin==b.bundle_digest(b.MEDIA_RUNTIME_FILES)
    assert not any(n.startswith(('canvas.','text.')) for n in files)

def test_runtime_compilation_does_not_modify_default_eighteen_or_existing_result_download_pins(tmp_path):
    out=json.loads(subprocess.run([sys.executable,'scripts/build_xyq_runtime.py','--out',str(tmp_path/'runtime')],cwd=ROOT,check=True,capture_output=True,text=True).stdout)
    assert len(out['bundles'])==20 and not out['installed'] and not out['provider_execution_verified']
    original=json.loads(subprocess.run([sys.executable,'scripts/build_xyq_web.py','--out',str(tmp_path/'default')],cwd=ROOT,check=True,capture_output=True,text=True).stdout)
    assert len(original['bundles'])==18
    import build_xyq_web as web
    assert web.bundle_digest(web.RESULT_FILES)=='99e0f848f994e3f030f257d9b7894660e70f96c311a28a1ae158810f40eb3dda'

@pytest.mark.parametrize('operation',b.MEDIA_RUNTIME_OPERATIONS)
def test_generated_runtime_manifest_drives_real_fake_subprocess_with_permissions_and_same_job(router,workspace,tmp_path,operation):
    tool=b.runtime_manifest(operation);p=tmp_path/'manifest.json';p.write_text(json.dumps(tool));install(router.state,router.catalog,p,digest(tool));router.catalog=Catalog(router.state)
    def value(schema):
        if 'const' in schema:return schema['const']
        if 'enum' in schema:return schema['enum'][0]
        if schema.get('type')=='object':return {k:value(schema['properties'][k]) for k in schema.get('required',[])}
        if schema.get('type') in ('integer','number'):return max(6,schema.get('minimum',0))
        if schema.get('type')=='boolean':return True
        if '64' in schema.get('pattern',''):return 'a'*64
        if '0-9' in schema.get('pattern','') and 'A-Za-z' not in schema.get('pattern',''):return '1'
        if schema.get('pattern')=='^/':return str(workspace/'fixture.wav')
        return 'fixture-once'
    inputs=value(tool['schema']);program=tmp_path/'fixture-opencliapp'
    if operation=='audio_prepare':inputs['settings']['sample_rate_hz']=44100
    if operation=='audio_prompt_prepare':inputs['settings']['prompt']='fixture text'
    program.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-media',{operation.replace('_','-')!r}]
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('fixture-dispatch-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fixture-only','operation':{operation!r},'provider_called':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *a:pytest.fail('No vault reads')
    if tool['paid']:
        with pytest.raises(RouterError) as denied:router.run(tool['id'],inputs,workspace,request_key='fixture-once',grants=tool['permissions'])
        assert denied.value.code=='paid_confirmation_required' and not (workspace/'fixture-dispatch-count').exists()
    a=router.run(tool['id'],inputs,workspace,request_key='fixture-once',grants=tool['permissions'],allow_paid=tool['paid'])
    again=router.run(tool['id'],inputs,workspace,request_key='fixture-once',grants=tool['permissions'],allow_paid=tool['paid'])
    assert a['status']=='completed' and a['id']==again['id'] and (workspace/'fixture-dispatch-count').read_text()=='1'
    assert a['data']['result'][0]['result']['status']=='fixture-only' and not a['data']['result'][0]['result']['provider_called']

@pytest.mark.browser
@pytest.mark.parametrize('operation',['account','surface','form_inspect','form_options','form_state'])
def test_runtime_read_dispatch_uses_actual_intercepted_dom_without_input(native_page,operation):
    if operation=='form_state':
        from test_xyq_web_home_quote import quote_html
        html=quote_html('图片生成','6',None)
    else:html=fixture_html(opened=operation=='form_options')
    load(native_page,html)
    process=subprocess.Popen(['node','tests/fixtures/xyq_media_runtime_read_rpc.mjs',json.dumps({'operation':operation})],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    reads=0
    try:
        for line in process.stdout:
            request=json.loads(line)
            if request['type']=='done':
                process.wait(timeout=5);assert process.returncode==0,process.stderr.read()
                assert 'error' not in request,request
                assert not request['provider_called'] and request['result'][0]['result']['status']=='ready'
                assert 'PRIVATE_HISTORY' not in json.dumps(request) and 'PRIVATE_PROMPT' not in json.dumps(request)
                assert reads>0;return
            assert request['type']=='evaluate'
            assert any(request['source'].startswith('function '+name+'(') for name in ('readHomeDOM','readOptionsDOM','readDraftDOM','readHomeBoundSurfaceDOM'))
            reads+=1;response={'id':request['id']}
            try:response['value']=native_page.evaluate(request['source'],request.get('arg'))
            except Exception:response['error']='fixture_evaluate_error'
            process.stdin.write(json.dumps(response,ensure_ascii=False)+'\n');process.stdin.flush()
        pytest.fail('Native media reader returned no terminal result')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)

@pytest.mark.browser
def test_runtime_generate_and_local_status_dispatch_one_native_fixture_click(native_page,workspace,record_property,tmp_path):
    from test_media_cli_generation import rpc
    from test_xyq_web_home_quote import quote_html
    load(native_page,quote_html('图片生成','6',None));result,clicks=rpc(native_page,workspace,runtime=True)
    assert 'error' not in result and result['runtime'] and clicks==1
    row=result['result'][0]['result'];assert row['status']=='submitted' and not row['task_completed'] and row['provider_task_id'] is None
    assert result['reused'][0]['result']['reused'] and not result['status'][0]['result']['provider_checked']
    assert (workspace/'.atm/xyq-generation').is_dir()
    receipt=tmp_path/'runtime-native-fixture.json';receipt.write_text(json.dumps({'provider_called':False,'native_clicks':clicks,'workspace':str(workspace),'result':result},indent=2))
    record_property('xyq_media_runtime_native_fixture',str(receipt))
