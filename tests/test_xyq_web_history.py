"""Project history view contract; fixture records are deliberately not parsed."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_xyq_web_cli import builder as b,native_page,load

ROOT=Path(__file__).resolve().parents[1];SCOPE={'project_id':'1','canvas_id':'2'}
def test_history_manifest_has_exact_scope_read_permission_and_no_credentials():
    t=b.history_manifest();assert t['id']=='xyq.web.project_history_state'
    assert t['permissions']==['execute_code'] and not t['paid'] and 'credential' not in t
    assert t['schema']['required']==['project_id','canvas_id'] and t['schema']['additionalProperties'] is False
    assert t['command']['argv'][1:3]==['xyq-web','project-history-state-bound'] and b.bundle_digest(b.HISTORY_FILES) in t['command']['argv']

def test_history_pin_matches_node_preserving_other_source_pins():
    p=subprocess.run(['node','--input-type=module','-e',"import {historyDigest} from './examples/opencli/xyq-web/history.mjs';console.log(historyDigest());"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert p.stdout.strip()==b.bundle_digest(b.HISTORY_FILES) and len(b.HISTORY_FILES)==8
    assert b.bundle_digest(b.HOME_QUOTE_FILES)=='d062a39013b959559401b89ac8438a95a82e18e5a2f23906fd45fa0686072d75'
    assert b.bundle_digest(b.AUDIO_UPLOAD_BOUND_FILES)=='f33eecb64e8a6cb2b744235ea38e70b5d81b6847f0050a94a67141290d097d27'

@pytest.mark.parametrize('combo',[False,True])
def test_history_default_compile_preserves_existing_seventeen_tools(tmp_path,combo):
    out=tmp_path/'stage';p=subprocess.run([sys.executable,str(ROOT/'scripts/build_xyq_web.py'),'--out',str(out),*(['--bound-home','--bound-audio-quote','--bound-audio-edit','--bound-audio-upload'] if combo else [])],cwd=ROOT,capture_output=True,text=True,check=True)
    m=json.loads(p.stdout);assert len(m['operations'])==18 and m['history_binding']=='explicit-browser'
    assert m['history_adapter_sha256']==b.bundle_digest(b.HISTORY_FILES)
    assert json.loads((out/'project_history_state/manifest.json').read_bytes())==b.history_manifest()
    from agent_tool_maker.extensions import validate_bundle
    for item in m['bundles']:assert validate_bundle(Path(item['directory']))['sha256']==item['sha256']

def test_fake_real_subprocess_history_reuses_same_key_without_vault(router,workspace,tmp_path):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.history_manifest();path=tmp_path/'manifest.json';path.write_text(json.dumps(tool))
    install(router.state,router.catalog,path,digest(tool));router.catalog=Catalog(router.state)
    app=tmp_path/'fake-history-reader'
    app.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','project-history-state-bound']
assert not any('TOKEN' in k or 'KEY' in k for k in os.environ)
p=Path('history-call-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fixture_history_read','task_count':None,'all_records':False,'paid_submitted':False}}}}]))
''');app.chmod(0o700);bind_cli(router.state,'opencliapp',str(app));router.vault.get=lambda *a:pytest.fail('No credential read')
    one=router.run(tool['id'],SCOPE,workspace,request_key='history-once',grants=['execute_code'])
    reuse=router.run(tool['id'],SCOPE,workspace,request_key='history-once',grants=['execute_code'])
    assert one['status']=='completed' and reuse['id']==one['id'] and (workspace/'history-call-count').read_text()=='1'
    fresh=router.run(tool['id'],SCOPE,workspace,request_key='history-fresh',grants=['execute_code'])
    assert fresh['status']=='completed' and fresh['id']!=one['id'] and (workspace/'history-call-count').read_text()=='2'

def history_html(*,view='empty',media='全部',status='成功',records=False):
    labels=['全部','图片','视频','音频'];names=['all','image','video','audio'];selected=names[labels.index(media)]
    tabs=''.join(f'<button role="tab" data-slot="tabs-trigger" id="tab-{name}" aria-controls="content-{name}" aria-selected="{str(label==media).lower()}">{label}</button>' for name,label in zip(names,labels))
    content='<article data-task-id="FAKE_PRIVATE_ID"><p>FAKE_PRIVATE_PROMPT</p><a href="https://example.test/media?TOKEN=FAKE_PRIVATE_SIGNED_URL">FAKE_PRIVATE_TITLE</a></article>' if records else '<div role="status" data-slot="empty"><div data-slot="empty-description">暂无符合筛选条件的生成记录</div></div>'
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>[hidden]{{display:none!important}}</style></head><body>
    <button id="history" aria-label="生成历史" data-slot="popover-trigger" aria-haspopup="dialog" aria-controls="history-panel" aria-expanded="{str(view!='closed').lower()}" data-state="{'closed' if view=='closed' else 'open'}" onclick="window.inputs++">History</button>
    <div role="application" data-testid="rf__wrapper"><div role="dialog" aria-label="音频节点音频生成面板" data-xyq-selected-audio-footer-panel="true">FAKE_PRIVATE_DRAFT</div></div>
    <div id="history-panel" role="dialog" aria-label="生成历史" data-slot="popover-content" data-state="open" {'hidden' if view=='closed' else ''}>
    <h2 data-slot="popover-title">生成历史</h2><div role="tablist" aria-label="筛选生成历史">{tabs}</div>
    <button id="filter" data-slot="dropdown-menu-trigger" aria-haspopup="menu" aria-expanded="false" data-state="closed" aria-label="{status}，筛选生成状态">{status}</button>
    <div id="content-{selected}" role="tabpanel" data-slot="tabs-content" data-state="active" aria-labelledby="tab-{selected}" aria-busy="{str(view=='loading').lower()}" class="xyq-generation-history-content"><div class="xyq-generation-history-viewport">{content}</div></div>
    <button aria-label="关闭生成历史" onclick="window.inputs++">Close</button></div><aside>FAKE_PRIVATE_OTHER_PROJECT_HISTORY</aside>
    <script>window.inputs=0;window.generated=0;</script></body></html>'''

def adapter(page,config=None):
    config=config or {};p=subprocess.Popen(['node','tests/fixtures/xyq_history_rpc.mjs',json.dumps({'scope':SCOPE})],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);reads=0
    try:
        for line in p.stdout:
            r=json.loads(line)
            if r['type']=='done':p.wait(timeout=5);assert p.returncode==0,p.stderr.read();return r
            assert r['type']=='call' and r['method']=='evaluate' and r['source'].startswith('function readProjectHistoryDOM(') and r['arg']==SCOPE
            reads+=1;response={'id':r['id']}
            if reads==2 and config.get('race'):
                if config['race']=='status':page.locator('#filter').evaluate("e=>{e.innerText='失败';e.setAttribute('aria-label','失败，筛选生成状态');}")
                elif config['race']=='closed':
                    page.locator('#history-panel').evaluate("e=>e.hidden=true")
                    page.locator('#history').evaluate("e=>{e.setAttribute('aria-expanded','false');e.setAttribute('data-state','closed');}")
            try:response['value']=page.evaluate(r['source'],r['arg'])
            except Exception:response['error']='native_fixture_error'
            p.stdin.write(json.dumps(response,ensure_ascii=False)+'\n');p.stdin.flush()
        pytest.fail('No terminal fixture result')
    finally:
        if p.poll() is None:p.terminate();p.wait(timeout=5)

@pytest.mark.browser
@pytest.mark.parametrize('view,status,count',[('empty','history_empty',0),('closed','history_closed',None),('loading','history_pending',None)])
def test_native_closed_pending_empty_keep_counts_distinct_and_preserve_body(native_page,view,status,count):
    load(native_page,history_html(view=view),url='https://xyq.jianying.com/project?projectId=1&canvasId=2');body=native_page.locator('body').inner_html();out=adapter(native_page)
    assert 'error' not in out,out;r=out['result'][0]['result'];assert r['status']==status and r['visible_record_count']==count
    assert r['task_count'] is None and not r['all_records'] and not r['row_scope_verified'] and not r['task_rows_parsed']
    assert r['browser_session']=='site:xyq-web' and not r['binding_changed']
    assert native_page.locator('body').inner_html()==body and native_page.evaluate('window.inputs+window.generated')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('media',['图片','视频','音频'])
def test_native_observed_media_filter_associations(native_page,media):
    load(native_page,history_html(media=media),url='https://xyq.jianying.com/project?projectId=1&canvasId=2');out=adapter(native_page)
    assert 'error' not in out,out;r=out['result'][0]['result'];assert r['selected_media']==media and r['selected_status']=='成功'
    assert [t['label'] for t in r['media_filters'] if t['selected']]==[media] and native_page.evaluate('window.inputs')==0

@pytest.mark.browser
@pytest.mark.parametrize('status',['全部状态','生成中','失败'])
def test_native_actual_status_menu_labels_are_not_task_lifecycle_claims(native_page,status):
    load(native_page,history_html(status=status),url='https://xyq.jianying.com/project?projectId=1&canvasId=2');out=adapter(native_page)
    assert 'error' not in out,out;r=out['result'][0]['result'];assert r['selected_status']==status and r['task_count'] is None

@pytest.mark.browser
@pytest.mark.parametrize('selector,change,code',[
    ('#history',"e=>e.setAttribute('aria-controls','other')",'history_context_changed'),
    ('#history',"e=>e.setAttribute('aria-expanded','wrong')",'history_context_changed'),
    ('#history-panel',"e=>e.after(e.cloneNode(true))",'history_context_changed'),
    ('[role=tabpanel]',"e=>e.setAttribute('aria-labelledby','other')",'history_context_changed'),
    ('#filter',"e=>e.setAttribute('aria-label','other')",'history_filter_changed'),
    ('[data-slot=empty-description]',"e=>e.innerText='FAKE_PRIVATE_UNKNOWN'",'history_empty_changed'),
    ('body',"e=>{const d=document.createElement('div');d.setAttribute('role','menu');d.innerText='FAKE_PRIVATE_OTHER_MENU';e.append(d);}",'dialog_open'),
    ('.xyq-generation-history-viewport',"e=>{const d=document.createElement('div');d.innerText='FAKE_PRIVATE_ROW';e.append(d);}",'history_layout_changed'),
])
def test_native_ambiguity_masks_and_wrong_context_never_become_empty_success(native_page,selector,change,code):
    load(native_page,history_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2');native_page.locator(selector).evaluate(change);body=native_page.locator('body').inner_html();out=adapter(native_page)
    assert out['error']['code']==code,out
    assert native_page.locator('body').inner_html()==body and native_page.evaluate('window.inputs+window.generated')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('url,code',[
    ('https://example.test/project?projectId=1&canvasId=2','origin_mismatch'),('https://xyq.jianying.com/login','login_required'),
    ('https://xyq.jianying.com/home','unsupported_surface'),('https://xyq.jianying.com/project?projectId=3&canvasId=2','project_changed'),
    ('https://xyq.jianying.com/project?projectId=1&canvasId=3','canvas_changed'),('https://xyq.jianying.com/project?projectId=1&projectId=1&canvasId=2','project_changed'),
])
def test_native_wrong_project_canvas_origin_stops_without_actions(native_page,url,code):
    load(native_page,history_html(),url=url);body=native_page.locator('body').inner_html();out=adapter(native_page)
    assert out['error']['code']==code and native_page.locator('body').inner_html()==body

@pytest.mark.browser
def test_native_unverified_record_rows_are_not_extracted_or_treated_as_no_tasks(native_page):
    load(native_page,history_html(records=True),url='https://xyq.jianying.com/project?projectId=1&canvasId=2');body=native_page.locator('body').inner_html();out=adapter(native_page)
    assert out['error']['code']=='unsupported_history_records' and 'FAKE_PRIVATE' not in json.dumps(out)
    assert native_page.locator('body').inner_html()==body and native_page.evaluate('window.inputs+window.generated')==0

@pytest.mark.browser
@pytest.mark.parametrize('race',['status','closed'])
def test_native_history_races_stay_errors_without_input(native_page,race):
    load(native_page,history_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2');out=adapter(native_page,{'race':race})
    assert out['error']['code']=='history_changed' and native_page.evaluate('window.inputs+window.generated')==0
