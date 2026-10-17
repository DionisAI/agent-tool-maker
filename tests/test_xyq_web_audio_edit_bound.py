"""Audio semantic preparation over the explicit public native browser binding."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_xyq_web_cli import native_page,load
from test_xyq_web_media import b,SCOPE,prompt_html
from test_xyq_web_audio_settings import settings_html

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('operation',b.AUDIO_EDIT_BOUND_OPERATIONS)
def test_audio_edit_bound_changes_only_existing_route_pin_and_notes(operation):
    normal=b.audio_prompt_manifest() if operation=='audio_prompt_prepare' else b.audio_settings_manifest(operation)
    tool=b.audio_edit_bound_manifest(operation)
    assert tool['id']==normal['id'] and tool['permissions']==['execute_code','external_write'] and not tool['paid']
    assert tool['command']['argv'][2]==operation.replace('_','-')+'-bound'
    assert b.bundle_digest(b.AUDIO_EDIT_BOUND_FILES) in tool['command']['argv']
    tool['command']['argv']=normal['command']['argv'];tool['notes']=normal['notes'];assert tool==normal

def test_audio_edit_pin_matches_node_and_preserves_loaded_closures():
    out=subprocess.run(['node','--input-type=module','-e',"import{audioEditBoundDigest}from'./examples/opencli/xyq-web/audio-edit-bound.mjs';console.log(audioEditBoundDigest())"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.AUDIO_EDIT_BOUND_FILES) and len(b.AUDIO_EDIT_BOUND_FILES)==12
    assert b.bundle_digest(b.HOME_BOUND_FILES)=='8f5f2abbb2610665312d4380ccdeeb995f8336cd6aef1cbbd5f647e785ac8d55'
    assert b.bundle_digest(b.AUDIO_QUOTE_BOUND_FILES)=='08d259ea0a951cb9af61de506d2ed8927c418a00911b1b2dd7a1c653a83c13dc'

@pytest.mark.parametrize('combo',[False,True])
def test_audio_edit_explicit_compiler_keeps_eighteen_default_tools(tmp_path,combo):
    base=[sys.executable,str(ROOT/'scripts/build_xyq_web.py')]
    subprocess.run(base+['--out',str(tmp_path/'default')],text=True,capture_output=True,check=True)
    metadata=json.loads(subprocess.run(base+['--out',str(tmp_path/'explicit'),'--bound-audio-edit',*(['--bound-home','--bound-audio-quote'] if combo else [])],text=True,capture_output=True,check=True).stdout)
    assert len(metadata['operations'])==18 and metadata['audio_edit_binding']=='explicit-browser'
    assert metadata['audio_edit_bound_operations']==list(b.AUDIO_EDIT_BOUND_OPERATIONS)
    for operation in metadata['operations']:
        tool=json.loads((tmp_path/'explicit'/operation/'manifest.json').read_text())
        expected=b.audio_edit_bound_manifest(operation) if operation in b.AUDIO_EDIT_BOUND_OPERATIONS else b.home_bound_manifest(operation) if combo and operation in b.HOME_BOUND_OPERATIONS else b.audio_quote_bound_manifest() if combo and operation=='audio_quote' else json.loads((tmp_path/'default'/operation/'manifest.json').read_text())
        assert tool==expected

@pytest.mark.parametrize('operation',b.AUDIO_EDIT_BOUND_OPERATIONS)
def test_audio_edit_fake_subprocess_keeps_stable_request_and_no_vault(router,workspace,tmp_path,operation):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.audio_edit_bound_manifest(operation);manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool))
    install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-bound-audio-edit'
    program.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','{operation.replace('_','-')}-bound']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('edit-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fake_bound_audio_edit_fixture','paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *args:pytest.fail('No credentials')
    inputs=dict(SCOPE)
    if operation=='audio_prepare':inputs['settings']={'expected_form_sha256':'a'*64,'sample_rate_hz':48000}
    if operation=='audio_prompt_prepare':inputs['settings']={'expected_form_sha256':'a'*64,'reference_sha256':'b'*64}
    one=router.run(tool['id'],inputs,workspace,request_key='audio-edit-once',grants=['execute_code','external_write'])
    reused=router.run(tool['id'],inputs,workspace,request_key='audio-edit-once',grants=['execute_code','external_write'])
    assert one['status']=='completed' and reused['id']==one['id']
    assert (workspace/'edit-count').read_text()=='1'

def adapter(page,config):
    config={'scope':dict(SCOPE),**config}
    process=subprocess.Popen(['node','tests/fixtures/xyq_audio_edit_bound_rpc.mjs',json.dumps(config)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    cdp=page.context.new_cdp_session(page)
    try:
        for line in process.stdout:
            req=json.loads(line)
            if req['type']=='done':process.wait(timeout=5);assert process.returncode==0,process.stderr.read();return req
            assert req['type']=='call';response={'id':req['id']}
            try:
                if req['method']=='evaluate':
                    assert any(req['source'].startswith('function '+name+'(') for name in ['readAudioFormDOM','readAudioSettingsMenuDOM','readAudioSettingsTargetDOM','readAudioPromptDOM','readAudioPromptTargetDOM','readAudioPromptCaretDOM','readAudioEditInputDOM'])
                    if config.get('broken_selection') and req.get('arg',{}).get('kind')=='selected':response['value']={'kind':'selection_changed'}
                    else:response['value']=page.evaluate(req['source'],req.get('arg'))
                elif req['method']=='native_click':
                    page.mouse.click(req['x'],req['y']);response['value']=None
                    if config.get('fail_native_click'):raise RuntimeError('FAKE_CLICK_AFTER_DISPATCH')
                elif req['method']=='native_key':
                    assert req['key']=='Escape';page.keyboard.press('Escape');response['value']=None
                elif req['method']=='native_type':
                    assert config['operation']=='audio_prompt_prepare'
                    if config.get('fail_native_type'):raise RuntimeError('FAKE_TYPE_FAILURE')
                    cdp.send('Input.insertText',{'text':req['text']});response['value']=None
                elif req['method']=='native_edit':
                    assert config['operation']=='audio_prompt_prepare' and req['command']=='Input.dispatchKeyEvent'
                    event=req['event'];assert event['type'] in ['keyDown','rawKeyDown','keyUp']
                    expected={'a':['selectAll'],'Backspace':['deleteBackward'],'Enter':['insertLineBreak'],'End':['moveToEndOfDocument']}[event['key']]
                    assert event.get('commands',[])==(expected if event['type']!='keyUp' else [])
                    if event['key']=='Enter':assert event['modifiers']==8
                    cdp.send(req['command'],event);response['value']=None
                else:pytest.fail('Unexpected native method')
            except Exception:response['error']='native_fixture_error'
            process.stdin.write(json.dumps(response)+'\n');process.stdin.flush()
        pytest.fail('Missing native result: '+process.stderr.read())
    finally:
        cdp.detach()
        if process.poll() is None:process.terminate();process.wait(timeout=5)

def setup(page,html):load(page,html,url='https://xyq.jianying.com/project?projectId=1&canvasId=2')

@pytest.mark.browser
def test_native_bound_choices_preserve_complete_form(native_page):
    setup(native_page,settings_html());out=adapter(native_page,{'operation':'audio_choices'})
    assert 'error' not in out,out
    r=out['result'][0]['result'];assert r['form_sha256']==out['before']['form_sha256']
    assert [m['id'] for m in r['models']]==['seed_audio','qwen_tts']
    assert r['browser_session']=='site:xyq-web' and not r['binding_changed']
    assert native_page.evaluate('window.escapes')==2
    assert native_page.evaluate('window.modelInputs+window.rateInputs+window.submitted+window.uploaded')==0

@pytest.mark.browser
@pytest.mark.parametrize('settings',[{'model_id':'qwen_tts'},{'sample_rate_hz':48000},{'model_id':'qwen_tts','sample_rate_hz':48000},{'model_id':'seed_audio','sample_rate_hz':44100}])
def test_native_bound_audio_settings_readback_and_content_preservation(native_page,settings):
    setup(native_page,settings_html());native_page.locator('[contenteditable="true"]').fill('FAKE_PRIVATE_PROMPT')
    content=native_page.locator('[contenteditable="true"]').inner_html()
    out=adapter(native_page,{'operation':'audio_prepare','settings':settings});assert 'error' not in out,out
    assert out['result'][0]['result']['status']=='prepared'
    assert native_page.locator('[contenteditable="true"]').inner_html()==content
    assert native_page.locator('#models').is_hidden() and native_page.locator('#rates').is_hidden()
    assert native_page.evaluate('window.submitted+window.uploaded')==0

@pytest.mark.browser
@pytest.mark.parametrize('prompt',['测试前缀','  literal  ','line 1\nline 2','', 'first\n\nthird'])
def test_native_bound_audio_literal_text_and_structured_reference(native_page,prompt):
    setup(native_page,prompt_html())
    out=adapter(native_page,{'operation':'audio_prompt_prepare','settings':{'prompt':prompt,'reference_sha256':hashlib.sha256(b'FAKE_REF_ID').hexdigest()}})
    assert 'error' not in out,out
    r=out['result'][0]['result'];assert r['status']=='prepared'
    assert r['literal_text_sha256']==hashlib.sha256((prompt+' ').encode()).hexdigest()
    assert r['mentions'][0]['asset_id']=='456' and not r['voice_effect_verified']
    assert native_page.evaluate('window.mentioned')==1
    assert native_page.evaluate('window.submitted+window.uploaded')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
def test_native_bound_existing_reference_is_zero_input(native_page):
    setup(native_page,prompt_html());settings={'reference_sha256':hashlib.sha256(b'FAKE_REF_ID').hexdigest()}
    assert 'error' not in adapter(native_page,{'operation':'audio_prompt_prepare','settings':settings})
    before=native_page.locator('body').inner_html();out=adapter(native_page,{'operation':'audio_prompt_prepare','settings':settings})
    assert 'error' not in out,out
    assert out['result'][0]['result']['completed_steps']==[]
    assert set(out['calls'])=={'evaluate'} and native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.mentioned')==1

@pytest.mark.browser
@pytest.mark.parametrize('flags,code',[({'ignore':True},'settings_changed'),({'mutate':True},'draft_changed'),({'wrong_owner':True},'control_changed')])
def test_native_bound_parameter_failure_keeps_diagnostics(native_page,flags,code):
    setup(native_page,settings_html(**flags));out=adapter(native_page,{'operation':'audio_prepare','settings':{'sample_rate_hz':48000}})
    assert out['error']['code']==code,out
    assert native_page.evaluate('window.rateInputs')==(0 if flags.get('wrong_owner') else 1)
    assert native_page.evaluate('window.submitted+window.uploaded')==0

@pytest.mark.browser
@pytest.mark.parametrize('case',['selection','type','click'])
def test_native_bound_errors_retain_input_phase_uncertainty_and_never_retry(native_page,case):
    setup(native_page,prompt_html() if case!='click' else settings_html())
    config={'operation':'audio_prompt_prepare','settings':{'prompt':'new'}} if case!='click' else {'operation':'audio_prepare','settings':{'sample_rate_hz':48000}}
    config[{'selection':'broken_selection','type':'fail_native_type','click':'fail_native_click'}[case]]=True
    out=adapter(native_page,config)
    assert out['error']['code']==('selection_changed' if case=='selection' else 'bridge_failed'),out
    if case=='selection':assert out['calls'].get('native_type',0)==0 and out['error']['input_phase']=='selected'
    if case=='type':assert out['calls']['native_type']==1 and out['error']['input_phase']=='replace'
    if case=='click':assert out['calls']['native_click']==1
    if case!='selection':assert out['error']['outcome_uncertain'] is True
    assert native_page.evaluate('window.submitted+window.uploaded')==0

@pytest.mark.browser
@pytest.mark.parametrize('case',['generate','wrong-node','covered','rich'])
def test_native_bound_dom_guard_rejects_foreign_and_covered_controls(native_page,case):
    setup(native_page,prompt_html())
    source=subprocess.run(['node','--input-type=module','-e',"import{readAudioEditInputDOM}from'./examples/opencli/xyq-web/audio-edit-bound.mjs';console.log(readAudioEditInputDOM.toString())"],cwd=ROOT,text=True,capture_output=True,check=True).stdout
    prefix='[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"]'
    request={'scope':dict(SCOPE),'kind':'target','selector':prefix+' [data-testid="canvas-generation-prompt-editor"][contenteditable="true"]','nth':0}
    if case=='generate':request['selector']=prefix+' button[data-action="audio-generate-submit"]';expected='invalid_argument'
    if case=='wrong-node':request['scope']['node_id']='9';expected='node_changed'
    if case=='covered':native_page.evaluate("document.body.insertAdjacentHTML('beforeend','<div style=\"position:fixed;inset:0;z-index:999\">FAKE_COVER</div>')");expected='control_obscured'
    if case=='rich':
        assert 'error' not in adapter(native_page,{'operation':'audio_prompt_prepare','settings':{'reference_sha256':hashlib.sha256(b'FAKE_REF_ID').hexdigest()}})
        expected='rich_prompt_present'
    assert native_page.evaluate(source,request)['kind']==expected
    assert native_page.evaluate('window.submitted+window.uploaded')==0
