"""Exact adapter/native DOM with local RPC. All supplier requests intercepted."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest
from test_xyq_web_cli import native_page,load,source as core_source

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('xyq_form_builder',ROOT/'scripts/build_xyq_web.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

@pytest.mark.parametrize('op',b.FORM_OPERATIONS)
def test_form_manifest(op):
    from agent_tool_maker.maker import validate_manifest
    tool=b.form_manifest(op)
    assert validate_manifest(tool)==tool
    assert tool['id']=='xyq.web.'+op and not tool['paid']
    assert set(tool['permissions'])==({'execute_code'} if op=='form_state' else {'execute_code','external_write'})
    assert b.bundle_digest(b.FORM_FILES) in tool['command']['argv']
    assert 'credential' not in tool and 'credential_env' not in tool['command']
    if op=='form_prepare':
        schema=tool['schema']['properties']['settings']
        assert schema['required']==['expected_draft_sha256'] and schema['additionalProperties'] is False
        assert schema['properties']['radios']['maxProperties']==10

def test_form_source_digest_matches_node():
    out=subprocess.run(['node','--input-type=module','-e',"import {formDigest} from './examples/opencli/xyq-web/form.mjs'; console.log(formDigest());"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.FORM_FILES)

@pytest.mark.parametrize('op',b.FORM_OPERATIONS)
def test_form_fake_real_subprocess_and_exact_request_reuse(router,workspace,tmp_path,op):
    import sys
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.form_manifest(op);path=tmp_path/'manifest.json';path.write_text(json.dumps(tool))
    install(router.state,router.catalog,path,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-xyq-opencliapp'
    program.write_text(f'''#!{sys.executable}
import sys,json,os
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','{op.replace('_','-')}']
assert not any('TOKEN' in k or 'KEY' in k for k in os.environ)
p=Path('xyq-form-count.txt');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'prepared':{op=='form_prepare'},'paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program))
    router.vault.get=lambda *args:pytest.fail('No credential read')
    inputs={'settings':{'expected_draft_sha256':'a'*64,'radios':{'采样率':'48kHz'}}} if op=='form_prepare' else {}
    grants=['execute_code',*(['external_write'] if op!='form_state' else [])]
    one=router.run(tool['id'],inputs,workspace,request_key='xyq-form-once',grants=grants)
    two=router.run(tool['id'],inputs,workspace,request_key='xyq-form-once',grants=grants)
    assert one['status']=='completed' and one['id']==two['id']
    assert (workspace/'xyq-form-count.txt').read_text()=='1'

def form_html(*,rich=False,obscured=False):
    reference='<span contenteditable="false" data-reference-id="FAKE_PRIVATE_REFERENCE">REFERENCE</span>' if rich else ''
    cover='<div style="position:fixed;inset:0;z-index:100"></div>' if obscured else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>button{{padding:4px}} section{{padding:10px}} #editor{{min-height:30px;width:500px}} [hidden]{{display:none!important}}</style></head><body>
    <button aria-label="打开个人导航">FAKE_USER</button><header><button aria-haspopup="dialog">100</button></header>
    <nav aria-label="功能导航"><button>创作</button></nav>
    <div id="title-section-prompt-container"><div role="tablist" aria-label="Agent 类型"><button role="tab" aria-selected="true">创作</button><button role="tab" aria-selected="false">短剧</button></div>
    <div data-slot="prompt-composer"><button aria-label="选择创作模式">视频生成</button>
    <div id="editor" role="textbox" contenteditable="true"><p>FAKE_PRIVATE_PROMPT{reference}</p></div>
    <input type="file" accept="image/*" multiple hidden>
    <button id="pref" aria-label="模型选择和偏好设置：M0、44.1kHz、30秒" data-state="closed">偏好</button>
    <button id="canvas" role="switch" aria-label="画布" aria-checked="false">画布</button>
    <button aria-label="开始生成" onclick="window.submitted++">Generate trap</button></div>
    <nav aria-label="创作快捷入口"><button>视频生成</button></nav></div>
    <div id="prefs" role="dialog" hidden><section aria-label="模型选择">
    <button aria-pressed="true" data-selected="true" data-model="M0"><span data-slot="model-picker-item-title">M0</span><span>FAKE_DESCRIPTION</span></button>
    <button aria-pressed="false" data-model="M1"><span data-slot="model-picker-item-title">M1</span><span>FAKE_DESCRIPTION</span></button></section>
    <section aria-label="偏好设置"><div data-slot="home-direct-generic-parameter-field"><div data-slot="home-direct-parameter-label">采样率</div><div role="radiogroup"><button role="radio" aria-checked="true">44.1kHz</button><button role="radio" aria-checked="false">48kHz</button></div></div>
    <input id="duration" aria-label="视频时长秒数" value="30" style="width:100px"><span role="slider" aria-label="视频秒数" aria-valuemin="4" aria-valuemax="30" aria-valuenow="30">时长</span>
    </section></div>{cover}<script>
    window.submitted=0;
    const pref=document.querySelector('#pref'),prefs=document.querySelector('#prefs');
    function summary(){{pref.setAttribute('aria-label','模型选择和偏好设置：'+document.querySelector('[data-model][aria-pressed="true"]').dataset.model+'、'+document.querySelector('[role="radio"][aria-checked="true"]').innerText+'、'+document.querySelector('#duration').value+'秒');}}
    pref.onclick=()=>{{prefs.hidden=!prefs.hidden;pref.dataset.state=prefs.hidden?'closed':'open';}};
    document.addEventListener('keydown',e=>{{if(e.key==='Escape'){{prefs.hidden=true;pref.dataset.state='closed';}}}});
    document.querySelectorAll('[data-model]').forEach(b=>b.onclick=()=>{{document.querySelectorAll('[data-model]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));summary();}});
    document.querySelectorAll('[role="radio"]').forEach(b=>b.onclick=()=>{{document.querySelectorAll('[role="radio"]').forEach(x=>x.setAttribute('aria-checked',String(x===b)));summary();}});
    document.querySelector('#duration').oninput=e=>{{document.querySelector('[role="slider"]').setAttribute('aria-valuenow',e.target.value);summary();}};
    document.querySelector('#canvas').onclick=e=>e.target.setAttribute('aria-checked',String(e.target.getAttribute('aria-checked')!=='true'));
    </script></body></html>'''

def adapter(native_page,config):
    process=subprocess.Popen(['node','tests/fixtures/xyq_form_rpc.mjs',json.dumps(config,ensure_ascii=False)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for line in process.stdout:
            request=json.loads(line)
            if request['type']=='done':
                process.wait(timeout=5)
                assert process.returncode==0,process.stderr.read()
                return request
            assert request['type']=='call'
            response={'id':request['id']}
            try:
                if request['method']=='evaluate':
                    assert any(request['source'].startswith('function '+name+'(') for name in ['readHomeDOM','readOptionsDOM','readDraftDOM','readTargetDOM'])
                    response['value']=native_page.evaluate(request['source'],request.get('arg'))
                elif request['method']=='key':
                    assert request['key']=='Escape'
                    native_page.keyboard.press('Escape');response['value']=None
                else:
                    selector=request['selector']
                    assert '开始生成' not in selector and '上传' not in selector
                    locator=native_page.locator(selector).nth(request['options']['nth'])
                    if request['method']=='click':locator.click(timeout=2000)
                    elif request['method']=='fill':locator.fill(request['value'],timeout=2000)
                    else:pytest.fail('Unexpected native bridge method')
                    response['value']=None
            except Exception:
                response['error']='native_fixture_error'
            process.stdin.write(json.dumps(response,ensure_ascii=False)+'\n');process.stdin.flush()
        pytest.fail('Native adapter returned no final result: '+process.stderr.read())
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)

@pytest.mark.browser
def test_native_exact_pressed_model_and_group_reader(native_page):
    load(native_page,form_html());native_page.locator('#pref').click()
    data=native_page.evaluate(core_source('readOptionsDOM'))
    assert [x['label'] for x in data['models']]==['M0','M1']
    assert data['models'][0]['checked'] and not data['models'][1]['checked']
    assert data['radios'][0]['group']=='采样率'
    assert 'FAKE_DESCRIPTION' not in json.dumps(data)

@pytest.mark.browser
def test_native_exact_full_form_adapter(native_page):
    load(native_page,form_html())
    out=adapter(native_page,{'operation':'prepare','settings':{'model':'M1','radios':{'采样率':'48kHz'},'duration_seconds':12,'canvas':True,'prompt':'仅测试草稿'}})
    assert 'error' not in out,out
    result=out['result'][0]['result']
    assert result['prepared'] and result['paid_submitted'] is False
    assert result['form']['canvas']['checked']
    assert native_page.locator('#editor').inner_text()=='仅测试草稿'
    assert native_page.locator('#prefs').is_hidden()
    assert native_page.locator('#duration').input_value()=='12'
    assert native_page.evaluate('window.submitted')==0
    assert 'FAKE_PRIVATE_PROMPT' not in json.dumps(out)

@pytest.mark.browser
def test_native_owned_options_restore_exact_draft(native_page):
    load(native_page,form_html());before=native_page.locator('body').inner_html()
    out=adapter(native_page,{'operation':'choices'})
    assert 'error' not in out,out
    assert out['result'][0]['result']['draft_sha256']==out['before']['draft_sha256']
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('settings,code',[({'expected_draft_sha256':'0'*64,'prompt':'x'},'draft_changed'),({'radios':{'other':'48kHz'}},'setting_unavailable'),({'duration_seconds':31},'setting_unavailable')])
def test_native_errors_close_owned_menu_and_never_generate(native_page,settings,code):
    load(native_page,form_html())
    out=adapter(native_page,{'operation':'prepare','settings':settings})
    assert out['error']['code']==code,out
    assert native_page.locator('#prefs').is_hidden()
    assert native_page.locator('#editor').inner_text()=='FAKE_PRIVATE_PROMPT'
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_rich_reference_preserved(native_page):
    load(native_page,form_html(rich=True))
    out=adapter(native_page,{'operation':'prepare','settings':{'prompt':''}})
    assert out['error']['code']=='rich_prompt_present'
    assert native_page.locator('[data-reference-id]').count()==1
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_covered_control_receives_no_input(native_page):
    load(native_page,form_html(obscured=True))
    out=adapter(native_page,{'operation':'prepare','settings':{'canvas':True}})
    assert out['error']['code']=='control_obscured'
    assert native_page.locator('#canvas').get_attribute('aria-checked')=='false'
    assert native_page.evaluate('window.submitted')==0


def expanded_preferences_html():
    """Observed popover: aria-expanded changes, trigger data-state stays closed."""
    html = form_html().replace(
        'id="pref" aria-label=',
        'id="pref" aria-expanded="false" aria-label=',
    ).replace(
        'id="prefs" role="dialog" hidden',
        'id="prefs" role="dialog" data-slot="generation-preferences-panel-positioner" data-state="closed" hidden',
    )
    html = html.replace(
        "pref.dataset.state=prefs.hidden?'closed':'open';",
        "pref.setAttribute('aria-expanded',String(!prefs.hidden));prefs.dataset.state=prefs.hidden?'closed':'open';if(prefs.hidden){pref.removeAttribute('aria-controls');}else{pref.setAttribute('aria-controls','prefs');}",
    ).replace(
        "pref.dataset.state='closed';",
        "pref.setAttribute('aria-expanded','false');pref.removeAttribute('aria-controls');prefs.dataset.state='closed';",
    )
    return html


@pytest.mark.browser
def test_native_expanded_popover_choices_close_and_preserve_draft(native_page):
    load(native_page,expanded_preferences_html())
    before=native_page.locator('body').inner_html()
    out=adapter(native_page,{'operation':'choices'})
    assert 'error' not in out,out
    assert out['result'][0]['result']['draft_sha256']==out['before']['draft_sha256']
    assert [x['label'] for x in out['result'][0]['result']['options']['models']]==['M0','M1']
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0


@pytest.mark.browser
def test_native_expanded_popover_preparation_and_cleanup(native_page):
    load(native_page,expanded_preferences_html())
    out=adapter(native_page,{'operation':'prepare','settings':{'radios':{'采样率':'48kHz'}}})
    assert 'error' not in out,out
    assert native_page.locator('#prefs').is_hidden()
    assert native_page.locator('#pref').get_attribute('data-state')=='closed'
    assert native_page.locator('#pref').get_attribute('aria-expanded')=='false'
    assert native_page.locator('#editor').inner_text()=='FAKE_PRIVATE_PROMPT'
    assert native_page.evaluate('window.submitted')==0


@pytest.mark.browser
@pytest.mark.parametrize('mutation',[
    "document.querySelector('#pref').setAttribute('aria-expanded','yes')",
    "document.querySelector('#pref').removeAttribute('aria-controls')",
    "document.querySelector('#prefs').removeAttribute('data-slot')",
    "document.querySelector('#prefs').setAttribute('data-state','closed')",
    "document.querySelector('#pref').setAttribute('aria-expanded','false')",
    "document.querySelector('#prefs').append(document.querySelector('section[aria-label=\"偏好设置\"]').cloneNode(true))",
])
def test_native_expanded_popover_invalid_association_preserves_dom(native_page,mutation):
    load(native_page,expanded_preferences_html());native_page.locator('#pref').click()
    native_page.evaluate(mutation)
    before=native_page.locator('body').inner_html()
    assert native_page.evaluate(core_source('readHomeDOM'))['kind']=='preferences_context_changed'
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0


@pytest.mark.browser
def test_native_expanded_popover_pending_panel_is_not_fake_success(native_page):
    load(native_page,expanded_preferences_html());native_page.locator('#pref').click()
    native_page.evaluate("document.querySelector('#pref').setAttribute('aria-controls','not-present')")
    assert native_page.evaluate(core_source('readHomeDOM'))['kind']=='pending'


def range_preferences_html():
    html=expanded_preferences_html().replace(
        '<span role="slider" aria-label="视频秒数" aria-valuemin="4" aria-valuemax="30" aria-valuenow="30">时长</span>',
        '<input type="range" aria-label="视频秒数" min="4" max="30" step="1" value="30">',
    ).replace(
        "document.querySelector('[role=\"slider\"]').setAttribute('aria-valuenow',e.target.value);",
        "document.querySelector('input[type=\"range\"]').value=e.target.value;",
    ).replace(
        '</section></div>',
        '<div><span>Seed</span><div data-selection-mode="point"><button aria-pressed="true">随机生成</button><button aria-pressed="false">自定义生成</button></div></div></section></div>',
    )
    return html


@pytest.mark.browser
def test_native_range_and_pressed_seed_controls_read_without_mutation(native_page):
    load(native_page,range_preferences_html());native_page.locator('#pref').click()
    before=native_page.locator('body').inner_html()
    data=native_page.evaluate(core_source('readOptionsDOM'))
    assert data['sliders']==[{'label':'视频秒数','min':'4','max':'30','value':'30'}]
    assert data['pressed_buttons']==[
        {'label':'随机生成','checked':True,'disabled':False},
        {'label':'自定义生成','checked':False,'disabled':False},
    ]
    assert not data['all_options']
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0


@pytest.mark.browser
def test_native_range_duration_input_uses_real_bounds_and_readback(native_page):
    load(native_page,range_preferences_html())
    out=adapter(native_page,{'operation':'prepare','settings':{'duration_seconds':12}})
    assert 'error' not in out,out
    assert native_page.locator('#duration').input_value()=='12'
    assert native_page.locator('input[type="range"]').input_value()=='12'
    assert native_page.locator('#prefs').is_hidden()
    assert native_page.locator('#editor').inner_text()=='FAKE_PRIVATE_PROMPT'
    assert native_page.evaluate('window.submitted')==0


@pytest.mark.browser
def test_native_range_out_of_bounds_preserves_duration_and_seed(native_page):
    load(native_page,range_preferences_html())
    out=adapter(native_page,{'operation':'prepare','settings':{'duration_seconds':31}})
    assert out['error']['code']=='setting_unavailable'
    assert native_page.locator('#duration').input_value()=='30'
    assert native_page.locator('input[type="range"]').input_value()=='30'
    assert native_page.locator('button[aria-pressed=true]').all_text_contents()==['M0FAKE_DESCRIPTION','随机生成']
    assert native_page.locator('#prefs').is_hidden()
    assert native_page.evaluate('window.submitted')==0


@pytest.mark.browser
@pytest.mark.parametrize('pressed',['mixed','unknown',''])
def test_native_unrecognized_seed_state_is_not_unchecked_success(native_page,pressed):
    load(native_page,range_preferences_html());native_page.locator('#pref').click()
    native_page.locator('[data-selection-mode="point"] button').first.evaluate(
        '(e,v)=>e.setAttribute("aria-pressed",v)',pressed,
    )
    before=native_page.locator('body').inner_html()
    assert native_page.evaluate(core_source('readOptionsDOM'))['kind']=='layout_changed'
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0
