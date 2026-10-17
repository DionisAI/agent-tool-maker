"""Text-node native fixture, exact JS workflow and isolated ATM subprocesses."""
import json
import subprocess
import pytest
from test_xyq_web_cli import native_page,load,ROOT
from test_xyq_web_form import b

@pytest.mark.parametrize('op',b.TEXT_OPERATIONS)
def test_text_manifest_and_pin(op):
    item=b.text_manifest(op)
    assert item['paid'] is False and 'credential_env' not in item['command']
    assert set(item['permissions'])==({'execute_code'} if op.endswith('inspect') else {'execute_code','external_write'})
    assert item['schema']['required']==list(item['schema']['properties'])
    assert b.bundle_digest(b.TEXT_FILES) in item['command']['argv']
    out=subprocess.run(['node','--input-type=module','-e',"import {textDigest} from './examples/opencli/xyq-web/text.mjs'; console.log(textDigest());"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.TEXT_FILES)

@pytest.mark.parametrize('op',b.TEXT_OPERATIONS)
def test_text_real_fake_subprocess_permissions_and_reuse(router,workspace,tmp_path,op):
    import sys
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    from agent_tool_maker.errors import RouterError
    tool=b.text_manifest(op);path=tmp_path/'manifest.json';path.write_text(json.dumps(tool))
    install(router.state,router.catalog,path,digest(tool));router.catalog=Catalog(router.state)
    p=tmp_path/'fake-text-bridge'
    p.write_text(f'''#!{sys.executable}
import sys,json,os
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','{op.replace('_','-')}']
assert not any('TOKEN' in k or 'KEY' in k for k in os.environ)
c=Path('text-count');c.write_text(str(int(c.read_text())+1) if c.exists() else '1')
print(json.dumps([{{'result':{{'status':'prepared','paid_submitted':False}}}}]))
''');p.chmod(0o700);bind_cli(router.state,'opencliapp',str(p));router.vault.get=lambda *args:pytest.fail('No vault access')
    inputs={'project_id':'1','canvas_id':'2','node_id':'3'}
    if op.endswith('prepare'):inputs['settings']={'expected_content_sha256':'a'*64,'text':'fake'}
    grants=['execute_code',*(['external_write'] if op.endswith('prepare') else [])]
    if op.endswith('prepare'):
        with pytest.raises(RouterError) as error:router.run(tool['id'],inputs,workspace,request_key='missing-write',grants=['execute_code'])
        assert error.value.code=='permission_required' and not (workspace/'text-count').exists()
    first=router.run(tool['id'],inputs,workspace,request_key='text-once',grants=grants)
    second=router.run(tool['id'],inputs,workspace,request_key='text-once',grants=grants)
    assert first['status']=='completed' and first['id']==second['id']
    assert (workspace/'text-count').read_text()=='1'

def fixture(*,editable='true',caret_only=False,footer=False):
    labels=['H1','H2','H3','Quote','粗体','斜体','下划线','删除线']
    buttons=''.join(f'<button aria-label="{x}" aria-pressed="false">{x}</button>' for x in labels)
    footer_html='''<div role="dialog" aria-label="节点浮动操作面板" data-xyq-selected-node-footer-panel="true" data-xyq-text-prompt-generation-footer="true"><div contenteditable="true">FAKE_FOOTER_DRAFT</div><button aria-label="生成文本" onclick="window.submitted++">Generate trap</button></div>''' if footer else ''
    return f'''<!doctype html><meta charset="utf-8"><style>#editor{{width:450px;min-height:60px}}#editor h1,#editor h2,#editor h3{{font-weight:normal}}button{{padding:6px}}[hidden]{{display:none!important}}</style>
    <div aria-label="画布顶部操作区"><h1>FAKE_PRIVATE_TITLE</h1><button aria-label="积分余额 100"></button></div>
    <div role="application" data-testid="rf__wrapper"><div class="react-flow__nodes"><div class="react-flow__node react-flow__node-biz/text" data-id="3" style="width:450px;height:100px"><div id="editor" class="xyq-text-node-editor" contenteditable="{editable}"><p>FAKE_PRIVATE_TEXT</p></div></div></div></div>
    <div aria-label="Canvas viewport toolbar"><button aria-label="网格吸附" aria-pressed="true"></button></div>
    <div data-xyq-text-toolbar="true">{buttons}</div><div data-slot="agent-conversation-editor" contenteditable="true">FAKE_PRIVATE_DRAFT</div>
    {footer_html}<button aria-label="生成文本" onclick="window.submitted++">Generate trap</button>
    <script>window.submitted=0;const editor=document.querySelector('#editor');editor.onclick=()=>editor.contentEditable='true';
    document.querySelectorAll('[data-xyq-text-toolbar] button').forEach(b=>{{b.onmousedown=e=>e.preventDefault();b.onclick=()=>{{
      const label=b.getAttribute('aria-label'),commands={{'粗体':'bold','斜体':'italic','下划线':'underline','删除线':'strikeThrough'}};
      if(!{str(caret_only).lower()}){{if(commands[label])document.execCommand(commands[label]);
        else if(/^H[1-3]$/.test(label))document.execCommand('formatBlock',false,editor.querySelector(label.toLowerCase())?'p':label.toLowerCase());
        // Native editing preserves the selection, unlike replacing innerHTML
        // (which collapses its live Range while Chrome may retain selected text).
        else if(label==='Quote')document.execCommand(editor.querySelector('blockquote')?'outdent':'indent');
      }}
      b.setAttribute('aria-pressed',String(b.getAttribute('aria-pressed')!=='true'));
    }};}});</script>'''

def adapter(page,config):
    process=subprocess.Popen(['node','tests/fixtures/xyq_text_rpc.mjs',json.dumps(config,ensure_ascii=False)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    cdp=page.context.new_cdp_session(page);selection_reads=[]
    try:
        for line in process.stdout:
            r=json.loads(line)
            if r['type']=='done':
                process.wait(timeout=5);assert process.returncode==0,process.stderr.read()
                if 'error' in r:
                    r['selection_reads']=selection_reads
                    r['native_debug']=page.evaluate('''()=>{const e=document.querySelector('#editor'),s=document.getSelection(),range=s?.rangeCount?s.getRangeAt(0):null;return{active_id:document.activeElement.id,editor_characters:e.textContent.length,selection_characters:s?.toString().replace(/\\n/g,'').length,range_count:s?.rangeCount,within:range?e.contains(range.startContainer)&&e.contains(range.endContainer):null,start_parent:range?.startContainer.parentElement?.tagName,end_parent:range?.endContainer.parentElement?.tagName,start_offset:range?.startOffset,end_offset:range?.endOffset,collapsed:range?.collapsed,selection_collapsed:s?.isCollapsed,anchor:s?.anchorNode?.nodeName,focus:s?.focusNode?.nodeName,anchor_offset:s?.anchorOffset,focus_offset:s?.focusOffset,anchor_connected:s?.anchorNode?.isConnected,focus_connected:s?.focusNode?.isConnected,range_start:range?.startContainer.nodeName,range_end:range?.endContainer.nodeName,selected_codes:Array.from(s?.toString()||'').map(x=>x.charCodeAt(0)),content_codes:Array.from(e.textContent).map(x=>x.charCodeAt(0))};}''')
                return r
            assert r['type']=='call';response={'id':r['id']}
            try:
                if r['method']=='evaluate':
                    assert any(r['source'].startswith('function '+n+'(') for n in ['readCanvasDOM','readTextNodeDOM','readTextSelectionDOM','readTextTargetDOM'])
                    response['value']=page.evaluate(r['source'],r.get('arg'))
                    if r['source'].startswith('function readTextSelectionDOM('):selection_reads.append(response['value'])
                elif r['method']=='cdp':
                    assert r['cdp_method']=='Input.dispatchKeyEvent' and r['params']['key']=='a' and r['params'].get('commands',[]) in [[],['selectAll']]
                    response['value']=cdp.send(r['cdp_method'],r['params'])
                else:
                    assert '生成' not in r['selector'] and '上传' not in r['selector']
                    loc=page.locator(r['selector']).nth(r['options']['nth'])
                    if r['method']=='click':loc.click(timeout=2000)
                    elif r['method']=='fill':loc.fill(r['value'],timeout=2000)
                    elif r['method']=='focus':loc.focus(timeout=2000)
                    else:pytest.fail('Unknown native test method')
                    response['value']=None
            except Exception:response['error']='native_fixture_error'
            process.stdin.write(json.dumps(response,ensure_ascii=False)+'\n');process.stdin.flush()
        pytest.fail('No final native result: '+process.stderr.read())
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)

@pytest.mark.browser
def test_native_text_replacement_and_entire_body_formats(native_page):
    load(native_page,fixture(),'https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=adapter(native_page,{'settings':{'text':'Native text smoke','heading':2,'quote':True,'bold':True,'italic':True,'underline':True,'strike':True}})
    assert 'error' not in out,json.dumps(out,ensure_ascii=False)
    result=out['result'][0]['result'];assert result['status']=='prepared' and result['formats']=={'heading':2,'quote':True,'bold':True,'italic':True,'underline':True,'strike':True}
    assert native_page.locator('#editor').inner_text()=='Native text smoke'
    assert native_page.locator('[data-slot="agent-conversation-editor"]').inner_text()=='FAKE_PRIVATE_DRAFT'
    assert native_page.evaluate('window.submitted')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('editable',['true','false'])
def test_native_read_and_activate_target(native_page,editable):
    load(native_page,fixture(editable=editable),'https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=adapter(native_page,{'settings':{'text':'new'}})
    assert 'error' not in out,out
    assert native_page.locator('#editor').inner_text()=='new'
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_caret_only_and_stale_content_are_failures(native_page):
    load(native_page,fixture(caret_only=True),'https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=adapter(native_page,{'settings':{'bold':True}})
    assert out['error']['code']=='settings_changed',out
    assert native_page.locator('#editor').inner_html()=='<p>FAKE_PRIVATE_TEXT</p>'
    out=adapter(native_page,{'settings':{'expected_content_sha256':'0'*64,'text':'new'}})
    assert out['error']['code']=='content_changed'
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_text_is_typed_not_html_executed(native_page):
    load(native_page,fixture(),'https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=adapter(native_page,{'settings':{'text':'<script>window.submitted=1</script>'}})
    assert 'error' not in out,out
    assert native_page.locator('#editor script').count()==0
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_owned_footer_preserved_but_other_layers_block(native_page):
    load(native_page,fixture(footer=True),'https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=adapter(native_page,{'settings':{'text':'footer preserved','bold':True}})
    assert 'error' not in out,out
    assert native_page.locator('[data-xyq-text-prompt-generation-footer] [contenteditable]').inner_text()=='FAKE_FOOTER_DRAFT'
    assert native_page.evaluate('window.submitted')==0
    # A look-alike dialog lacking the observed attributes is never exempted.
    native_page.evaluate("()=>{const d=document.createElement('div');d.setAttribute('role','dialog');d.setAttribute('aria-label','节点浮动操作面板');d.textContent='FAKE_DIALOG';document.body.append(d);}")
    before=native_page.locator('#editor').inner_html()
    out=adapter(native_page,{'settings':{'text':'should not replace'}})
    assert out['error']['code']=='dialog_open' and out['error']['completed_steps']==[]
    assert native_page.locator('#editor').inner_html()==before

@pytest.mark.browser
def test_native_collapsed_or_partial_selection_never_counts_as_full(native_page):
    load(native_page,fixture(),'https://xyq.jianying.com/project?projectId=1&canvasId=2')
    source=subprocess.run(['node','--input-type=module','-e',"import {readTextSelectionDOM} from './examples/opencli/xyq-web/text.mjs';console.log(readTextSelectionDOM.toString());"],cwd=ROOT,text=True,capture_output=True,check=True).stdout
    scope={'project_id':'1','canvas_id':'2','node_id':'3'}
    # Fake page only: explicit ranges exercise the reader, not writer input.
    native_page.evaluate("()=>{const e=document.querySelector('#editor');e.focus();const r=document.createRange();r.selectNodeContents(e);r.collapse(true);const s=document.getSelection();s.removeAllRanges();s.addRange(r);}")
    assert native_page.evaluate(source,scope)['full'] is False
    native_page.evaluate("()=>{const e=document.querySelector('#editor'),r=document.createRange();r.setStart(e.querySelector('p').firstChild,0);r.setEnd(e.querySelector('p').firstChild,4);const s=document.getSelection();s.removeAllRanges();s.addRange(r);}")
    assert native_page.evaluate(source,scope)['full'] is False
