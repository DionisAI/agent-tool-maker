"""Observed selected/read-only text nodes in isolated native DOM."""
import json
import subprocess
import pytest
from test_xyq_web_cli import native_page,load,ROOT
from test_xyq_web_form import b

def reader():
    out=subprocess.run(['node','--input-type=module','-e',"import {readCanvasDOM} from './examples/opencli/xyq-web/canvas.mjs'; console.log(readCanvasDOM.toString());"],cwd=ROOT,text=True,capture_output=True,check=True)
    return out.stdout.strip()

def test_canvas_manifest_and_source_digest():
    item=b.canvas_manifest()
    assert item['id']=='xyq.web.canvas_inspect' and set(item['permissions'])=={'execute_code'}
    assert not item['paid'] and 'credential_env' not in item['command']
    out=subprocess.run(['node','--input-type=module','-e',"import {canvasDigest} from './examples/opencli/xyq-web/canvas.mjs'; console.log(canvasDigest());"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.CANVAS_FILES)
    assert item['example']=={'project_id':'1','canvas_id':'2'}

def fixture(editable):
    return f'''<!doctype html><meta charset="utf-8"><div aria-label="画布顶部操作区"><h1>FAKE_PRIVATE_TITLE</h1><button aria-label="积分余额 100"></button></div>
    <div role="application" data-testid="rf__wrapper"><div class="react-flow__nodes"><div class="react-flow__node react-flow__node-biz/text" data-id="3" style="transform:translate(10px,20px);width:420px;height:180px"><div class="xyq-text-node-editor" contenteditable="{editable}"><p>FAKE_PRIVATE_TEXT</p></div></div></div><div class="react-flow__edges"></div></div>
    <div aria-label="Canvas viewport toolbar"><button aria-label="网格吸附" aria-pressed="true"></button></div>'''

@pytest.mark.browser
@pytest.mark.parametrize('editable',['true','false'])
def test_native_selected_and_read_only_text_node(native_page,editable):
    load(native_page,fixture(editable),'https://xyq.jianying.com/project?projectId=1&canvasId=2')
    before=native_page.locator('body').inner_html()
    d=native_page.evaluate(reader(),{'project_id':'1','canvas_id':'2'})
    assert d['kind']=='ready' and d['nodes'][0]['text']=='FAKE_PRIVATE_TEXT'
    assert d['nodes'][0]['text_editable']==(editable=='true')
    assert d['credits']==100 and d['controls'][0]['pressed']=='true'
    assert native_page.locator('body').inner_html()==before

@pytest.mark.browser
def test_native_bound_scope_and_loading_are_distinct(native_page):
    load(native_page,fixture('false'),'https://xyq.jianying.com/project?projectId=1&canvasId=2')
    assert native_page.evaluate(reader(),{'project_id':'4','canvas_id':'2'})['kind']=='canvas_changed'
    native_page.set_content('<div></div>')
    assert native_page.evaluate(reader(),{'project_id':'1','canvas_id':'2'})['kind']=='pending'
