"""Generated web CLI contracts and native fake DOM, not supplier integration."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_xyq_web',ROOT/'scripts/build_xyq_web.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

@pytest.mark.parametrize('operation',builder.OPERATIONS)
def test_fixed_web_manifest(operation):
    item=builder.manifest(operation)
    assert item['id']=='xyq.web.'+operation
    assert item['executable']=='opencliapp' and not item['paid']
    assert 'execute_code' in item['permissions']
    assert not item['schema']['properties'] and item['schema']['additionalProperties'] is False
    assert item['command']['argv']==['__opencli_shim','xyq-web',operation.replace('_','-'),'--pin',builder.bundle_digest(),'-f','json']
    assert 'credential' not in item and 'credential_env' not in item['command']

def test_node_and_python_source_digests_match():
    result=subprocess.run(['node','--input-type=module','-e',
        "import {bundleDigest} from './examples/opencli/xyq-web/core.mjs'; console.log(bundleDigest());"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert result.stdout.strip()==builder.bundle_digest()

def test_compiled_bundle_retains_existing_output(tmp_path):
    from agent_tool_maker.extensions import pack,validate_bundle
    dest=tmp_path/'account'
    pack(builder.manifest('account'),dest)
    assert validate_bundle(dest)['valid']
    original={p.name:p.read_bytes() for p in dest.iterdir() if p.is_file()}
    with pytest.raises(Exception):pack(builder.manifest('account'),dest)
    assert original=={p.name:p.read_bytes() for p in dest.iterdir() if p.is_file()}
    assert subprocess.run(['python3',str(dest/'tool.py'),'--help'],text=True,capture_output=True).returncode==0

def test_protocol_node_regressions():
    subprocess.run(['node','--test','tests/xyq_web_core.test.mjs'],cwd=ROOT,check=True,capture_output=True,text=True)

@pytest.mark.parametrize('include_canvas',[False,True])
def test_compiler_defaults_to_media_scope_and_preserves_parked_canvas(tmp_path,include_canvas):
    import sys
    args=[sys.executable,str(ROOT/'scripts/build_xyq_web.py'),'--out',str(tmp_path/'stage')]
    if include_canvas:args.append('--include-canvas')
    result=json.loads(subprocess.run(args,cwd=ROOT,check=True,capture_output=True,text=True).stdout)
    expected=list(builder.OPERATIONS+builder.FORM_OPERATIONS+builder.MODE_OPERATIONS+builder.AUDIO_OPERATIONS+builder.AUDIO_BOUND_OPERATIONS+builder.AUDIO_PROMPT_OPERATIONS+builder.AUDIO_SETTINGS_OPERATIONS+builder.AUDIO_QUOTE_OPERATIONS+builder.HOME_QUOTE_OPERATIONS+builder.HISTORY_OPERATIONS)
    if include_canvas:expected+=['canvas_inspect',*builder.TEXT_OPERATIONS]
    assert result['operations']==expected
    assert sorted(p.name for p in (tmp_path/'stage').iterdir())==sorted(expected)
    assert result['scope']==('media-foundation+parked-canvas' if include_canvas else 'media-foundation')

def fixture_html(*,credits='100',login=False,agent='创作',mode='图片生成',opened=False):
    identity='<button>登录</button>' if login else '<button aria-label="打开个人导航">FAKE_USER_NOT_RETURNED</button>'
    tabs=''.join(f'<button role="tab" aria-selected="{str(x==agent).lower()}">{x}</button>' for x in ['创作','短剧','营销'])
    opts='''<section aria-label="模型选择"><button role="checkbox" aria-checked="true">FAKE_MODEL</button></section>
    <section aria-label="偏好设置"><div role="radiogroup" aria-label="选择画面比例"><button role="radio" aria-checked="true" aria-label="1:1">1:1</button></div>
    <input type="number" aria-label="视频时长秒数" value="30" min="4" max="30"><button role="checkbox" aria-checked="true">随机生成</button></section>''' if opened else ''
    form='' if agent=='短剧' else f'''<button aria-label="选择创作模式">{mode}</button>
    <button aria-label="模型选择和偏好设置：FAKE_MODEL" data-state="{'open' if opened else 'closed'}">FAKE_MODEL</button>
    <div role="textbox" contenteditable="true">FAKE_PRIVATE_PROMPT_NOT_RETURNED</div>
    <button role="switch" aria-label="画布" aria-checked="true" disabled></button>
    <button aria-label="开始生成" disabled></button>
    <span aria-label="积分消耗 0.33">0.33 /秒</span>
    <input type="file" accept="image/*" multiple>'''
    return f'''<!doctype html><html><head><meta charset="utf-8"></head><body>{identity}<header><button aria-haspopup="dialog">{credits}</button><button aria-haspopup="dialog" aria-label="任务中心">5</button></header>
    <nav aria-label="功能导航"><button>创作</button><button>短剧 Agent</button><button>营销 Agent</button><button>创建画布</button></nav>
    <main><div id="title-section-prompt-container"><div role="tablist" aria-label="Agent 类型">{tabs}</div>{form}
    <nav aria-label="创作快捷入口"><button>图片生成</button><button>视频生成</button><button>音频生成</button></nav></div></main>{opts}
    <aside><button aria-label="打开会话 PRIVATE_HISTORY_NOT_RETURNED">PRIVATE_HISTORY_NOT_RETURNED</button></aside></body></html>'''

@pytest.fixture
def native_page():
    from playwright.sync_api import sync_playwright
    executable=os.environ.get('ATM_CHROMIUM')
    if not executable:pytest.skip('Provide reviewed native Chromium for isolated DOM test')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=executable,headless=True)
        page=browser.new_page()
        # Every app request is fulfilled by the fixture or aborted. No provider traffic.
        page.route('**/*',lambda route:route.abort())
        yield page
        browser.close()

def load(page,html,url='https://xyq.jianying.com/home'):
    page.route(url,lambda route:route.fulfill(status=200,content_type='text/html',body=html))
    page.goto(url)

def source(name):
    result=subprocess.run(['node','--input-type=module','-e',
        f"import {{{name}}} from './examples/opencli/xyq-web/core.mjs'; console.log({name}.toString());"],cwd=ROOT,text=True,capture_output=True,check=True)
    return result.stdout.strip()

@pytest.mark.browser
@pytest.mark.parametrize('mode',['图片生成','视频生成','音频生成'])
def test_native_visible_form_and_privacy(native_page,mode):
    load(native_page,fixture_html(credits='6,396.5',mode=mode))
    data=native_page.evaluate(source('readHomeDOM'))
    assert data['kind']=='ready' and data['credits']==6396.5
    assert data['form']['mode']==mode and data['form']['prompt_characters']>0
    assert data['form']['visible_cost_observations']==[{'label':'积分消耗 0.33','text':'0.33 /秒'}]
    assert data['form']['quote_status']=='not_final'
    assert data['form']['canvas']=={'checked':True,'disabled':True}
    serialized=json.dumps(data)
    assert all(x not in serialized for x in ['FAKE_USER','FAKE_PRIVATE','PRIVATE_HISTORY'])

@pytest.mark.browser
@pytest.mark.parametrize('credits',['20k','1,23','-1','NaN','9007199254740992'])
def test_native_malformed_credit_contract(native_page,credits):
    load(native_page,fixture_html(credits=credits))
    assert native_page.evaluate(source('readHomeDOM'))['kind']=='layout_changed'

@pytest.mark.browser
@pytest.mark.parametrize('url,expected',[('https://example.test/home','origin_mismatch'),('https://xyq.jianying.com/login','login_required'),('https://xyq.jianying.com/unknown','unsupported_surface')])
def test_native_origin_and_surface(native_page,url,expected):
    load(native_page,fixture_html(),url)
    assert native_page.evaluate(source('readHomeDOM'))['kind']==expected

@pytest.mark.browser
def test_native_login_and_domain_gap(native_page):
    load(native_page,fixture_html(login=True))
    assert native_page.evaluate(source('readHomeDOM'))['kind']=='login_required'
    native_page.set_content(fixture_html(agent='短剧'))
    data=native_page.evaluate(source('readHomeDOM'))
    assert data['kind']=='ready' and data['agent']=='短剧' and data['form'] is None

@pytest.mark.browser
def test_native_options_observe_without_editing(native_page):
    load(native_page,fixture_html(opened=True))
    before=native_page.locator('body').inner_html()
    data=native_page.evaluate(source('readOptionsDOM'))
    assert data['kind']=='ready' and data['all_options'] is False
    assert data['radios'][0]['group']=='选择画面比例'
    assert data['numbers'][0]['value']=='30'
    assert data['toggles']==[{'label':'随机生成','checked':True}]
    assert native_page.locator('body').inner_html()==before
