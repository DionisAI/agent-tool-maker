"""Observed conversation image contract; native local fixtures, never provider jobs."""
import io
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_xyq_web_cli import builder as b,native_page,load

ROOT=Path(__file__).resolve().parents[1]
THREAD='00000000-0000-0000-0000-000000000001'
RESOURCE='a'*32
URL=f'https://xyq.jianying.com/home?tab_name=integrated-agent&thread_id={THREAD}&agent_name=pippit_nest_agent'
MEDIA=f'https://p3-pippit-business-jianying-sign.byteimg.com/tos-cn-i-wipe09lpyt/{RESOURCE}~tplv-wipe09lpyt-resize-v1:1080:1080.image?FAKE_PRIVATE_SIGNATURE=not-returned'

@pytest.mark.parametrize('operation',b.RESULT_OPERATIONS)
def test_result_factory_and_fixed_bundle(operation,tmp_path):
    from agent_tool_maker.extensions import pack,validate_bundle
    from agent_tool_maker.maker import digest
    t=b.result_manifest(operation);pack(t,tmp_path/operation)
    assert validate_bundle(tmp_path/operation)['sha256']==digest(t)
    assert t['permissions']==['execute_code'] and not t['paid'] and 'credential' not in t
    assert t['schema']['additionalProperties'] is False and t['command']['argv'][1]=='xyq-web'
    assert b.bundle_digest(b.RESULT_FILES) in t['command']['argv']

def test_node_python_result_pin_and_opt_in_compiler(tmp_path):
    p=subprocess.run(['node','--input-type=module','-e',"import {resultDigest} from './examples/opencli/xyq-web/results.mjs';console.log(resultDigest());"],cwd=ROOT,check=True,capture_output=True,text=True)
    assert p.stdout.strip()==b.bundle_digest(b.RESULT_FILES)
    p=subprocess.run([sys.executable,'scripts/build_xyq_web.py','--out',str(tmp_path/'stage'),'--include-delivery','--include-results'],cwd=ROOT,check=True,capture_output=True,text=True)
    meta=json.loads(p.stdout)
    assert len(meta['operations'])==23 and meta['operations'][-3:]==list(b.RESULT_OPERATIONS)
    assert meta['result_adapter_sha256']==b.bundle_digest(b.RESULT_FILES) and not meta['provider_delivery_verified']

def test_results_only_compiler_emits_exactly_the_three_identical_bundles(tmp_path):
    def build(out,*flags):
        return subprocess.run([sys.executable,'scripts/build_xyq_web.py','--out',str(tmp_path/out),*flags],cwd=ROOT,capture_output=True,text=True)
    p=build('only','--results-only');assert p.returncode==0,p.stderr
    meta=json.loads(p.stdout);ids=['xyq.web.'+op for op in b.RESULT_OPERATIONS]
    assert meta['operations']==list(b.RESULT_OPERATIONS) and [x['tool'] for x in meta['bundles']]==ids
    assert sorted(d.name for d in (tmp_path/'only').iterdir())==sorted(b.RESULT_OPERATIONS)
    assert meta['result_adapter_sha256']==b.bundle_digest(b.RESULT_FILES) and not meta['provider_delivery_verified']
    assert build('full','--include-results').returncode==0
    snapshot=lambda d:{f.name:f.read_bytes() for f in d.iterdir()}
    for op in b.RESULT_OPERATIONS:
        assert snapshot(tmp_path/'only'/op)==snapshot(tmp_path/'full'/op) and len(snapshot(tmp_path/'only'/op))==5
    for i,flag in enumerate(('--include-results','--include-delivery','--include-canvas','--bound-home','--bound-audio-quote','--bound-audio-edit','--bound-audio-upload')):
        p=build(f'mixed{i}','--results-only',flag)
        assert p.returncode==2 and 'cannot be combined' in p.stderr and not (tmp_path/f'mixed{i}').exists()

def test_result_command_real_subprocess_never_reads_vault_and_reuses_job(router,workspace,tmp_path):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    t=b.result_manifest('results');p=tmp_path/'manifest.json';p.write_text(json.dumps(t));install(router.state,router.catalog,p,digest(t));router.catalog=Catalog(router.state)
    program=tmp_path/'fixture-opencli';program.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','results-bound']
assert sys.argv[sys.argv.index('--thread')+1]=='{THREAD}'
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('fixture-read-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fixture_result_observed','provider_task_id':None,'download_verified':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *a:pytest.fail('No vault read')
    a=router.run(t['id'],{'thread_id':THREAD},workspace,request_key='fixture-result-read-once',grants=['execute_code'])
    reused=router.run(t['id'],{'thread_id':THREAD},workspace,request_key='fixture-result-read-once',grants=['execute_code'])
    assert a['status']=='completed' and a['id']==reused['id'] and (workspace/'fixture-read-count').read_text()=='1'
    assert a['data']['result'][0]['result']['status']=='fixture_result_observed'

def html(preview=True):
    card=f'<div class="ag-ui-assistant-message"><div class="ag-ui-x-biz-image-part"><img src="{MEDIA}" width="30" height="40"></div><p>FAKE_PRIVATE_PROMPT_DO_NOT_READ</p></div>'
    aside=f'''<aside class="artifactPanel-fixture"><div class="text-heading-h3 truncate">fixture.png</div>
      <button aria-label="返回资源列表" data-slot="button">back</button><button data-slot="button" id="download">下载</button>
      <div class="artifactPreviewMediaContext-fixture"><img src="{MEDIA}" width="60" height="80"></div></aside>''' if preview else ''
    return f'<!doctype html><html><head><meta charset="utf-8"></head><body>{card}{aside}<script>window.inputs=0;document.addEventListener("click",()=>window.inputs++);</script></body></html>'

def setup(page,*,preview=True,url=URL):
    # Route all requests to in-memory local fixture bytes. No provider connection.
    from PIL import Image
    out=io.BytesIO();Image.new('RGB',(81,108),'blue').save(out,format='PNG')
    page.route('https://p3-pippit-business-jianying-sign.byteimg.com/**',lambda route:route.fulfill(status=200,content_type='image/png',body=out.getvalue()))
    load(page,html(preview),url=url)
    page.wait_for_function("Array.from(document.querySelectorAll('img')).every(i=>i.complete&&i.naturalWidth>0)")

def rpc(page):
    proc=subprocess.Popen(['node','tests/fixtures/xyq_results_rpc.mjs',json.dumps({'thread_id':THREAD})],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for line in proc.stdout:
            r=json.loads(line)
            if r['type']=='done':proc.wait(timeout=5);assert proc.returncode==0,proc.stderr.read();return r
            assert r['method']=='evaluate' and r['source'].startswith('function readConversationResultsDOM(')
            value=page.evaluate(r['source'],r['arg']);proc.stdin.write(json.dumps({'id':r['id'],'value':value})+'\n');proc.stdin.flush()
        pytest.fail('No terminal result read')
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

@pytest.mark.browser
def test_native_result_inspect_and_download_plan_are_zero_input(native_page):
    setup(native_page);before=native_page.locator('body').inner_html();r=rpc(native_page)
    assert 'error' not in r,r
    a=r['results'][0]['result'];assert a['visible_result_count']==1 and a['visible_card_count']==1
    assert a['results'][0]['result_id']==RESOURCE and a['results'][0]['width']==81 and a['results'][0]['height']==108
    assert a['provider_task_id'] is None and not a['all_results'] and not a['download_verified']
    assert r['quote'][0]['result']['status']=='download_control_ready'
    assert 'FAKE_PRIVATE' not in json.dumps(r) and MEDIA not in json.dumps(r)
    assert native_page.evaluate('window.inputs')==0 and native_page.locator('body').inner_html()==before

@pytest.mark.browser
def test_native_closed_preview_is_card_metadata_only(native_page):
    setup(native_page,preview=False);r=rpc(native_page);assert 'error' not in r,r
    assert r['quote'] is None and r['inspect'][0]['result']['surface']=='conversation_card'
    assert native_page.evaluate('window.inputs')==0

@pytest.mark.browser
@pytest.mark.parametrize('url,code',[
    ('https://example.test/home','origin_mismatch'),('https://xyq.jianying.com/login','login_required'),
    (URL.replace(THREAD,'00000000-0000-0000-0000-000000000002'),'thread_changed'),
    (URL+'&thread_id='+THREAD,'thread_changed'),(URL.replace('integrated-agent','home'),'unsupported_surface'),
    (URL+'&agent_name=pippit_nest_agent','unsupported_surface'),
])
def test_native_wrong_thread_route_origin_stops_with_zero_input(native_page,url,code):
    setup(native_page,url=url);r=rpc(native_page);assert r['error']['code']==code and native_page.evaluate('window.inputs')==0

@pytest.mark.browser
@pytest.mark.parametrize('case,code',[
    ('covered','control_obscured'),('disabled','download_unavailable'),('layer','dialog_open'),
    ('duplicate_preview','preview_ambiguous'),('duplicate_download','download_control_changed'),
    ('filename','unsupported_filename'),('title','filename_changed'),('unexpected_source','unsupported_media_source'),
    ('duplicate_card_image','result_layout_changed'),
])
def test_native_changed_result_contract_stops_without_clicks(native_page,case,code):
    setup(native_page)
    scripts={
      'covered':"document.body.insertAdjacentHTML('beforeend','<div style=\"position:fixed;inset:0;z-index:99\"></div>')",
      'disabled':"document.querySelector('#download').disabled=true",
      'layer':"document.body.insertAdjacentHTML('beforeend','<div role=\"dialog\">fixture layer</div>')",
      'duplicate_preview':"const e=document.querySelector('aside');e.after(e.cloneNode(true))",
      'duplicate_download':"const e=document.querySelector('#download');e.after(e.cloneNode(true))",
      'filename':"document.querySelector('.text-heading-h3').textContent='../fixture.png'",
      'title':"document.querySelector('.text-heading-h3').className='changed'",
      'unexpected_source':"document.querySelector('.ag-ui-x-biz-image-part img').src='data:image/png;base64,iVBORw0KGgo='",
      'duplicate_card_image':"const e=document.querySelector('.ag-ui-x-biz-image-part img');e.after(e.cloneNode(true))",
    }
    native_page.evaluate('()=>{'+scripts[case]+'}');r=rpc(native_page)
    assert r['error']['code']==code and native_page.evaluate('window.inputs')==0
