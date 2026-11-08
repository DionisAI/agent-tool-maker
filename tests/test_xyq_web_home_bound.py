"""Explicit homepage routing, isolated native menu input and bundle selection."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest
from test_xyq_web_cli import native_page,load
from test_xyq_web_media import mode_html

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('xyq_home_bound_builder',ROOT/'scripts/build_xyq_web.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

@pytest.mark.parametrize('operation',b.HOME_BOUND_OPERATIONS)
def test_bound_home_manifest_changes_route_not_id_or_scope(operation):
    original=b.form_manifest(operation) if operation in b.FORM_OPERATIONS else b.mode_manifest(operation)
    bound=b.home_bound_manifest(operation)
    assert bound['id']==original['id'] and bound['schema']==original['schema']
    assert bound['permissions']==original['permissions'] and not bound['paid']
    assert bound['command']['argv'][2]==operation.replace('_','-')+'-bound'
    assert b.bundle_digest(b.HOME_BOUND_FILES) in bound['command']['argv']
    assert original['command']['argv'][2]==operation.replace('_','-')
    assert 'credential' not in bound

def test_home_bound_digest_and_protocol():
    out=subprocess.run(['node','--input-type=module','-e',"import{homeBoundDigest}from'./examples/opencli/xyq-web/home-bound.mjs';console.log(homeBoundDigest())"],cwd=ROOT,check=True,capture_output=True,text=True)
    assert out.stdout.strip()==b.bundle_digest(b.HOME_BOUND_FILES)
    subprocess.run(['node','--test','tests/xyq_web_home_bound.test.mjs'],cwd=ROOT,check=True,capture_output=True,text=True)

def test_compiler_home_flag_selects_only_five_existing_definitions(tmp_path):
    from agent_tool_maker.extensions import validate_bundle
    out=subprocess.run([__import__('sys').executable,'scripts/build_xyq_web.py','--out',str(tmp_path/'bundles'),'--bound-home'],cwd=ROOT,check=True,capture_output=True,text=True)
    meta=json.loads(out.stdout)
    assert len(meta['operations'])==18 and meta['home_bound_operations']==list(b.HOME_BOUND_OPERATIONS)
    for bundle in meta['bundles']:
        assert validate_bundle(Path(bundle['directory']))['valid']
        definition=json.loads((Path(bundle['directory'])/'manifest.json').read_text())
        assert definition['command']['argv'][2].endswith('-bound')==(definition['id'].removeprefix('xyq.web.') in b.HOME_BOUND_OPERATIONS or definition['id'] in ['xyq.web.audio_form_state_bound','xyq.web.home_quote','xyq.web.project_history_state'])

def html(*,prompt=False,attached=False):
    raw=mode_html(prompt=prompt,attached=attached,modal=True)
    raw=raw.replace('id="pref" aria-label=', 'id="pref" aria-controls="prefs" aria-expanded="false" aria-label=')
    raw=raw.replace('id="prefs" role="dialog" hidden', 'id="prefs" role="dialog" data-slot="generation-preferences-panel-positioner" data-state="closed" hidden')
    script='''<script>document.addEventListener('click',e=>{if(e.target.closest('#pref')){document.querySelector('#pref').setAttribute('aria-expanded',String(!document.querySelector('#prefs').hidden));document.querySelector('#prefs').dataset.state=document.querySelector('#prefs').hidden?'closed':'open';}});document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.querySelector('#pref').setAttribute('aria-expanded','false');document.querySelector('#prefs').dataset.state='closed';}});window.trustedClicks=0;document.addEventListener('click',e=>{if(e.isTrusted)window.trustedClicks++});</script>'''
    return raw.replace('</body>',script+'</body>')

def adapter(page,config):
    process=subprocess.Popen(['node','tests/fixtures/xyq_home_bound_rpc.mjs',json.dumps(config)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    cdp=page.context.new_cdp_session(page)
    try:
        for line in process.stdout:
            request=json.loads(line)
            if request['type']=='done':
                process.wait(timeout=5);assert process.returncode==0,process.stderr.read();return request
            response={'id':request['id']}
            try:
                if request['method']=='evaluate':
                    assert any(request['source'].startswith('function '+name+'(') for name in ['readHomeDOM','readDraftDOM','readModeMenuDOM','readModeTargetDOM','readOptionsDOM','readTargetDOM','readHomeBoundInputDOM','readHomeBoundTextDOM','readHomeBoundSurfaceDOM'])
                    response['value']=page.evaluate(request['source'],request.get('arg'))
                elif request['method']=='native_click':
                    page.mouse.click(request['x'],request['y']);response['value']=None
                elif request['method']=='native_key':
                    assert request['key'] in ['Escape','a','Backspace']
                    modifiers=request['modifiers']
                    assert modifiers in [[],['Control'],['Meta']]
                    assert (request['key']=='a') == bool(modifiers)
                    flags=sum({'Control':2,'Meta':4}[value] for value in modifiers)
                    for kind in ['keyDown','keyUp']:
                        cdp.send('Input.dispatchKeyEvent',{'type':kind,'key':request['key'],'modifiers':flags})
                    response['value']=None
                elif request['method']=='native_type':
                    assert config['operation']=='form_prepare'
                    if config.get('fail_native_type'):raise RuntimeError('FAKE_NATIVE_FAILURE')
                    cdp.send('Input.insertText',{'text':request['text']});response['value']=None
                elif request['method']=='native_edit':
                    assert config['operation']=='form_prepare' and request['command']=='Input.dispatchKeyEvent'
                    assert request['event']['type'] in ['keyDown','keyUp']
                    event=request['event'];assert event['key'] in ['a','Backspace','Enter']
                    expected={'a':['selectAll'],'Backspace':['deleteBackward'],'Enter':['insertLineBreak']}[event['key']]
                    assert event.get('commands',[]) == (expected if event['type']=='keyDown' else [])
                    if event['key']=='Enter':assert event['modifiers']==8
                    cdp.send('Input.dispatchKeyEvent',event);response['value']=None
                else:pytest.fail('Unexpected native method')
            except Exception:
                response['error']='native_fixture_error'
            process.stdin.write(json.dumps(response)+'\n');process.stdin.flush()
        pytest.fail('Missing native result: '+process.stderr.read())
    finally:
        cdp.detach()
        if process.poll() is None:process.terminate();process.wait(timeout=5)

def prepare_html(*,rich=False):
    from test_xyq_web_form import expanded_preferences_html
    # CUA observed the real editor/paragraph white-space:break-spaces and p margins 0.
    raw=expanded_preferences_html().replace('</style>','#editor{white-space:break-spaces}#editor p{margin:0}</style>')
    if rich:
        raw=raw.replace('FAKE_PRIVATE_PROMPT</p>','FAKE_PRIVATE_PROMPT<span contenteditable="false" data-reference-id="FAKE_PRIVATE_REFERENCE">REF</span></p>')
    return raw.replace('</body>','''<script>window.trustedClicks=0;window.trustedInputs=0;document.addEventListener('click',e=>{if(e.isTrusted)window.trustedClicks++});document.addEventListener('input',e=>{if(e.isTrusted)window.trustedInputs++});</script></body>''')

@pytest.mark.browser
def test_native_bound_prepare_all_semantic_fields(native_page):
    load(native_page,prepare_html())
    settings={'model':'M1','radios':{'采样率':'48kHz'},'duration_seconds':12,'canvas':True,'prompt':'中文测试\n第二行 😀'}
    out=adapter(native_page,{'operation':'form_prepare','settings':settings})
    assert 'error' not in out,(out,repr(native_page.locator('#editor').inner_text()),native_page.locator('#editor').inner_html())
    result=out['result'][0]['result']
    assert result['status']=='ready' and result['prepared'] is True
    assert result['browser_session']=='site:xyq-home' and result['paid_submitted'] is False
    assert result['completed_steps']==['model','radio:采样率','duration_seconds','canvas','prompt']
    assert native_page.locator('#editor').inner_text()==settings['prompt']
    assert native_page.locator('#duration').input_value()=='12'
    assert native_page.locator('#canvas').get_attribute('aria-checked')=='true'
    assert native_page.locator('#prefs').is_hidden()
    assert native_page.evaluate('window.trustedInputs')==4
    assert native_page.evaluate('window.trustedClicks')==7
    assert native_page.evaluate('window.submitted')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('prompt',['','中文\n换行','  两端空格  '])
def test_native_bound_plain_prompt_literal_replacement(native_page,prompt):
    load(native_page,prepare_html())
    out=adapter(native_page,{'operation':'form_prepare','settings':{'prompt':prompt}})
    assert 'error' not in out,(out,repr(native_page.locator('#editor').inner_text()),native_page.locator('#editor').inner_html())
    if prompt:
        assert native_page.locator('#editor').inner_text()==prompt
    else:
        assert native_page.locator('#editor').inner_html()=='<p><br></p>'
        assert out['result'][0]['result']['form']['prompt_empty'] is True
        assert out['result'][0]['result']['prompt_sha256']=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    assert out['result'][0]['result']['completed_steps']==['prompt']
    assert out['calls'].get('native_type',0)==sum(bool(line) for line in prompt.split('\n'))
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('settings,rich,code',[({'expected_draft_sha256':'0'*64,'prompt':'new'},False,'draft_changed'),({'prompt':''},True,'rich_prompt_present')])
def test_native_bound_prepare_rejects_stale_or_rich_draft_before_input(native_page,settings,rich,code):
    load(native_page,prepare_html(rich=rich));before=native_page.locator('body').inner_html()
    out=adapter(native_page,{'operation':'form_prepare','settings':settings})
    assert out['error']['code']==code,out
    assert out['calls'].get('native_click',0)==0 and out['calls'].get('native_type',0)==0
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_bound_prepare_selection_interruption_preserves_prompt(native_page):
    load(native_page,prepare_html())
    native_page.evaluate("document.addEventListener('keydown',e=>{if(e.key==='a'&&(e.metaKey||e.ctrlKey))e.preventDefault()})")
    out=adapter(native_page,{'operation':'form_prepare','settings':{'prompt':'new'}})
    assert out['error']['code']=='selection_changed' and out['error']['input_phase']=='selected',out
    assert out['calls'].get('native_type',0)==0
    assert native_page.locator('#editor').inner_text()=='FAKE_PRIVATE_PROMPT'
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_bound_prepare_uncertain_native_failure_has_no_retry(native_page):
    load(native_page,prepare_html())
    out=adapter(native_page,{'operation':'form_prepare','settings':{'prompt':'new'},'fail_native_type':True})
    assert out['error']['code']=='bridge_failed' and out['error']['outcome_uncertain'] is True,out
    assert out['error']['phase']=='prompt' and out['error']['input_phase']=='replace'
    assert out['calls']['native_type']==1 and out['calls']['native_click']==1
    assert native_page.locator('#editor').inner_text()=='FAKE_PRIVATE_PROMPT'
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_bound_prepare_digest_only_is_zero_input(native_page):
    load(native_page,prepare_html());before=native_page.locator('body').inner_html()
    out=adapter(native_page,{'operation':'form_prepare','settings':{}})
    assert 'error' not in out and out['result'][0]['result']['prepared'] is True,out
    assert out['result'][0]['result']['draft_sha256']==out['before']['draft_sha256']
    assert out['calls'].get('native_click',0)==0 and out['calls'].get('native_type',0)==0
    assert native_page.locator('body').inner_html()==before

@pytest.mark.browser
def test_native_bound_prepare_preserves_existing_attachment_rail(native_page):
    raw=prepare_html().replace('<div id="editor"','<div data-slot="home-input-composer-attachments"><div title="FAKE.wav" data-reference-type="audio"><button data-action-object-id="FAKE-ID">@</button></div></div><div id="editor"')
    load(native_page,raw);before=native_page.locator('[data-slot="home-input-composer-attachments"]').inner_html()
    out=adapter(native_page,{'operation':'form_prepare','settings':{'radios':{'采样率':'48kHz'},'prompt':'FAKE NEW DRAFT'}})
    assert 'error' not in out,out
    assert out['result'][0]['result']['references']==out['before']['references']
    assert out['result'][0]['result']['references']['attachment_present'] is True
    assert native_page.locator('[data-slot="home-input-composer-attachments"]').inner_html()==before
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_bound_prepare_focus_change_after_selection_stops_replacement(native_page):
    load(native_page,prepare_html())
    native_page.evaluate("document.addEventListener('keyup',e=>{if(e.key==='a'&&(e.metaKey||e.ctrlKey))document.querySelector('#canvas').focus()})")
    out=adapter(native_page,{'operation':'form_prepare','settings':{'prompt':'new'}})
    assert out['error']['code']=='selection_changed' and out['error']['input_phase']=='selected',out
    assert out['calls'].get('native_type',0)==0
    assert native_page.locator('#editor').inner_text()=='FAKE_PRIVATE_PROMPT'
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_bound_number_input_selection_is_explicitly_unverified(native_page):
    load(native_page,prepare_html().replace('id="duration" aria-label=','id="duration" type="number" aria-label='))
    out=adapter(native_page,{'operation':'form_prepare','settings':{'duration_seconds':12}})
    assert out['error']['code']=='selection_unverifiable' and out['error']['input_phase']=='selected',out
    assert out['calls'].get('native_type',0)==0 and native_page.locator('#duration').input_value()=='30'
    assert native_page.locator('#prefs').is_hidden()
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_bound_literal_space_drift_is_not_normalized_or_retried(native_page):
    load(native_page,prepare_html().replace('#editor{white-space:break-spaces}','#editor{white-space:normal}'))
    out=adapter(native_page,{'operation':'form_prepare','settings':{'prompt':'  FAKE  '}})
    assert out['error']['code']=='settings_changed' and out['error']['input_phase']=='readback',out
    assert out['error']['outcome_uncertain'] is True and out['calls']['native_type']==1
    assert '\u00a0' in native_page.locator('#editor').inner_text()
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_bound_control_modifier_path_keeps_literal_prompt(native_page):
    load(native_page,prepare_html())
    native_page.evaluate("Object.defineProperty(navigator,'platform',{value:'Linux x86_64'})")
    out=adapter(native_page,{'operation':'form_prepare','settings':{'prompt':'FAKE LINUX BRANCH'}})
    assert 'error' not in out,out
    assert native_page.locator('#editor').inner_text()=='FAKE LINUX BRANCH'
    assert native_page.evaluate('window.submitted')==0

def test_bound_prepare_fake_subprocess_and_stable_request(router,workspace,tmp_path):
    import sys
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.home_bound_manifest('form_prepare');manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool))
    install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-bound-prepare'
    program.write_text(f'''#!{sys.executable}
import sys,json
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','form-prepare-bound']
settings=json.loads(sys.argv[sys.argv.index('--settings')+1])
assert settings['prompt']=='FAKE DRAFT' and settings['expected_draft_sha256']=='a'*64
p=Path('bound-prepare-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'prepared':True,'paid_submitted':False,'upload_started':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *a:pytest.fail('No credential read')
    inputs={'settings':{'expected_draft_sha256':'a'*64,'prompt':'FAKE DRAFT'}}
    grants=['execute_code','external_write']
    one=router.run(tool['id'],inputs,workspace,request_key='bound-prepare-once',grants=grants)
    two=router.run(tool['id'],inputs,workspace,request_key='bound-prepare-once',grants=grants)
    assert one['status']=='completed' and one['id']==two['id']
    assert (workspace/'bound-prepare-count').read_text()=='1'

@pytest.mark.browser
@pytest.mark.parametrize('operation',['form_state','form_choices','mode_choices'])
def test_native_bound_discovery_preserves_exact_draft(native_page,operation):
    load(native_page,html(prompt=True,attached=True));before=native_page.locator('body').inner_html()
    out=adapter(native_page,{'operation':operation});assert 'error' not in out,out
    assert out['result'][0]['result']['draft_sha256']==out['before']['draft_sha256']
    assert out['result'][0]['result']['browser_session']=='site:xyq-home'
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0
    assert native_page.evaluate('window.trustedClicks')==(0 if operation=='form_state' else 1)

@pytest.mark.browser
@pytest.mark.parametrize('mode',['图片生成','音频生成'])
def test_native_bound_empty_mode_uses_real_pointer_and_restores_menu(native_page,mode):
    load(native_page,html());out=adapter(native_page,{'operation':'mode_prepare','settings':{'mode':mode}})
    assert 'error' not in out,out
    assert out['result'][0]['result']['mode']==mode
    assert native_page.locator('#modes').is_hidden()
    assert native_page.locator('#mode-background').get_attribute('aria-hidden') is None
    assert native_page.evaluate('window.trustedClicks')==2
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('settings,code',[({'expected_draft_sha256':'0'*64,'mode':'图片生成'},'draft_changed'),({'mode':'图片生成'},'draft_not_empty')])
def test_native_bound_switch_rejects_changed_or_nonempty_draft(native_page,settings,code):
    load(native_page,html(prompt=True));out=adapter(native_page,{'operation':'mode_prepare','settings':settings})
    assert out['error']['code']==code,out
    assert native_page.evaluate('window.trustedClicks')==0
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('case',['generate-selector','bad-association','covered-target'])
def test_native_bound_transport_rejects_nonowned_input(native_page,case):
    load(native_page,html())
    result=subprocess.run(['node','--input-type=module','-e',"import{readHomeBoundInputDOM}from'./examples/opencli/xyq-web/home-bound.mjs';console.log(readHomeBoundInputDOM.toString())"],cwd=ROOT,check=True,capture_output=True,text=True)
    target={'kind':'click','selector':'#title-section-prompt-container button[aria-label="选择创作模式"]','nth':0}
    expected='control_obscured'
    if case=='generate-selector':
        target['selector']='button[aria-label="开始生成"]';expected='invalid_argument'
    elif case=='bad-association':
        native_page.locator('#mode').click()
        native_page.evaluate("document.querySelector('#modes').setAttribute('aria-labelledby','OTHER')")
        target={'kind':'escape'};expected='dialog_open'
    else:
        native_page.evaluate("document.body.insertAdjacentHTML('beforeend','<div style=\"position:fixed;inset:0;z-index:1000\"></div>')")
    before=native_page.locator('body').inner_html()
    assert native_page.evaluate(result.stdout,target)['kind']==expected
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('operation',['form_state','mode_choices'])
def test_native_existing_masked_mode_menu_is_preserved_and_reported(native_page,operation):
    load(native_page,html());native_page.locator('#mode').click()
    before=native_page.locator('body').inner_html()
    out=adapter(native_page,{'operation':operation,'skip_before':True})
    assert out['error']['code']=='dialog_open',out
    assert native_page.locator('body').inner_html()==before
    assert native_page.locator('#modes').is_visible()
    assert native_page.evaluate('window.trustedClicks')==1
    assert native_page.evaluate('window.submitted')==0
