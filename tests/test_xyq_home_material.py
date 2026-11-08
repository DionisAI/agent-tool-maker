"""Observed homepage intake metadata, isolated manifests/processes/native DOM."""
import importlib.util,json,subprocess,sys
from pathlib import Path
import pytest
from test_xyq_web_cli import native_page,load
from test_xyq_web_home_quote import quote_html
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('xyq_material_builder',ROOT/'scripts/build_xyq_material.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
ACCEPT='.jpg,.jpeg,.png,.webp,.bmp,.gif,image/png,.mp4,.mov,video/mp4,.wav,.mp3,audio/wav,audio/mpeg,.pdf,application/pdf'

@pytest.mark.parametrize('operation',b.OPERATIONS)
def test_fixed_readonly_manifest_and_generated_bundle(operation,tmp_path):
    from agent_tool_maker.extensions import pack,validate_bundle
    from agent_tool_maker.maker import digest
    t=b.manifest(operation);assert t['paid'] is False and t['permissions']==['execute_code']
    assert t['schema']['properties']=={} and t['schema']['additionalProperties'] is False
    assert t['command']['argv']==['__opencli_shim','xyq-material',operation.replace('_','-'),'--pin',b.bundle_digest(b.FILES),'-f','json']
    assert 'credential' not in t and 'credential_env' not in t['command'];pack(t,tmp_path/operation)
    assert validate_bundle(tmp_path/operation)['sha256']==digest(t)

def test_python_node_source_pin_and_prior_media_runtime_pins():
    import build_xyq_runtime as runtime
    output=subprocess.run(['node','--input-type=module','-e',"import{HOME_MATERIAL_FILES,homeMaterialDigest}from'./examples/opencli/xyq-web/material-home.mjs';console.log(JSON.stringify([HOME_MATERIAL_FILES,homeMaterialDigest()]));"],cwd=ROOT,capture_output=True,text=True,check=True)
    files,pin=json.loads(output.stdout);assert files==list(b.FILES) and pin==b.bundle_digest(b.FILES) and len(files)==12
    assert runtime.bundle_digest(runtime.MEDIA_RUNTIME_FILES)=='06d6591e8239ed0efa216b242dac86a0900bc6d40df2392fc70809837111fd23'

@pytest.mark.parametrize('operation',b.OPERATIONS)
def test_router_real_fake_subprocess_and_same_key_same_job(router,workspace,tmp_path,operation):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    from agent_tool_maker.extensions import pack
    tool=b.manifest(operation);bundle=tmp_path/'bundle';pack(tool,bundle);install(router.state,router.catalog,bundle/'manifest.json',digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fixture-opencliapp';program.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-material',{operation.replace('_','-')!r}]
assert not any('KEY' in x or 'TOKEN' in x for x in os.environ)
p=Path('dispatch-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fixture-only','provider_called':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *a:pytest.fail('No vault reads')
    first=router.run(tool['id'],{},workspace,request_key='material-once',grants=['execute_code'])
    second=router.run(tool['id'],{},workspace,request_key='material-once',grants=['execute_code'])
    assert first['id']==second['id'] and first['status']=='completed' and (workspace/'dispatch-count').read_text()=='1'
    assert first['data']['result'][0]['result']['provider_called'] is False

def material_html(opened=False):
    html=quote_html('音频生成','0.33/秒',None)
    html=html.replace('<input type="file" accept="image/*" multiple hidden>','')
    trigger=f'''<button id="material-trigger" aria-label="上传素材" data-slot="home-input-composer-add-material-button" aria-haspopup="menu" aria-expanded="{'true' if opened else 'false'}" data-state="{'open' if opened else 'closed'}" {'aria-controls="material-menu"' if opened else ''}>+</button>
    <div class="uploadInputArea-fixture"><input type="file" multiple accept="{ACCEPT}"><input type="file" aria-label="替换素材文件"></div>'''
    html=html.replace('<div data-slot="prompt-composer">','<div data-slot="prompt-composer">'+trigger)
    if opened:
        html=html.replace('<div id="title-section-prompt-container">','<div id="title-section-prompt-container" aria-hidden="true">')
        menu='''<div role="menu" id="material-menu" aria-labelledby="material-trigger" data-slot="dropdown-menu-content" data-state="open">'''
        for label,slot in [('本地上传','dropdown-menu-item'),('资产库','dropdown-menu-item'),('预设提示词','popover-anchor')]:
            menu+=f'<div role="menuitem" data-size="home-upload" data-slot="{slot}"><span data-slot="dropdown-menu-item-title">{label}</span></div>'
        html=html.replace('</body>',menu+'</div></body>')
    return html

def rpc(page,operation):
    process=subprocess.Popen(['node','tests/fixtures/xyq_home_material_rpc.mjs',json.dumps({'operation':operation})],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    reads=0
    try:
        for line in process.stdout:
            request=json.loads(line)
            if request['type']=='done':process.wait(timeout=5);assert process.returncode==0,process.stderr.read();return request,reads
            assert request['type']=='evaluate' and any(request['source'].startswith('function '+n+'(') for n in ('readHomeMaterialsDOM','readHomeDOM','readDraftDOM'))
            reads+=1;response={'id':request['id']}
            try:response['value']=page.evaluate(request['source'],request.get('arg'))
            except Exception:response['error']='native_fixture_evaluate_failed'
            process.stdin.write(json.dumps(response,ensure_ascii=False)+'\n');process.stdin.flush()
        pytest.fail('Material fixture returned no terminal result')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)

@pytest.mark.browser
@pytest.mark.parametrize('operation',b.OPERATIONS)
def test_native_discovery_preserves_body_and_never_reads_private_prompt_or_selects_asset(native_page,operation):
    load(native_page,material_html(operation=='home_material_choices'));before=native_page.locator('body').inner_html()
    result,reads=rpc(native_page,operation);assert 'error' not in result,result
    row=result['result'][0]['result'];assert row['status']=='material_metadata_ready'
    assert row['declared_media_extensions']['video']==['.mp4','.mov'] and row['declared_media_extensions']['audio']==['.wav','.mp3']
    assert row['draft_bound'] is (operation=='home_material_state')
    assert not any(row[k] for k in ('upload_started','file_input_sent','asset_selected','generation_submitted','paid_submitted'))
    assert not result['provider_called'] and 'FAKE_PRIVATE' not in json.dumps(result)
    assert native_page.locator('body').inner_html()==before and reads>0

@pytest.mark.browser
@pytest.mark.parametrize('change,code',[
    ("document.getElementById('material-menu').setAttribute('aria-labelledby','wrong')",'material_context_changed'),
    ("document.querySelector('[role=menuitem]').setAttribute('data-size','wrong')",'material_menu_changed'),
    ("document.querySelector('[role=menuitem]').after(document.querySelector('[role=menuitem]').cloneNode(true))",'material_menu_changed'),
    ("document.body.insertAdjacentHTML('beforeend','<div role=dialog>Unrelated</div>')",'dialog_open'),
    ("document.querySelector('.uploadInputArea-fixture').append(document.querySelector('.uploadInputArea-fixture input').cloneNode(true))",'material_input_changed'),
    ("document.querySelector('.uploadInputArea-fixture input').setAttribute('accept','https://HOST/?TOKEN')",'accept_changed'),
])
def test_native_wrong_owned_context_input_or_accept_stops_without_input(native_page,change,code):
    load(native_page,material_html(True));native_page.evaluate(change);before=native_page.locator('body').inner_html()
    result,reads=rpc(native_page,'home_material_choices');assert result['error']['code']==code
    assert native_page.locator('body').inner_html()==before and reads==1

@pytest.mark.browser
def test_native_closed_choices_and_preexisting_material_menu_fail_fast(native_page):
    load(native_page,material_html(False));result,reads=rpc(native_page,'home_material_choices');assert result['error']['code']=='material_menu_closed' and reads==1
    load(native_page,material_html(True));result,reads=rpc(native_page,'home_material_state');assert result['error']['code']=='dialog_open' and reads==1
