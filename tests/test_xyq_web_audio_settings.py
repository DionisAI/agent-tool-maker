"""Observed audio footer parameter menus via the actual adapter/native RPC."""
import json
import subprocess
import pytest
from test_xyq_web_media import native_page,load,prompt_html,prompt_config,media_adapter,SCOPE,ROOT,b

@pytest.mark.parametrize('operation',b.AUDIO_SETTINGS_OPERATIONS)
def test_audio_settings_manifest(operation):
    from agent_tool_maker.maker import validate_manifest
    tool=b.audio_settings_manifest(operation)
    assert validate_manifest(tool)==tool and tool['permissions']==['execute_code','external_write']
    assert not tool['paid'] and 'credential' not in tool and 'credential_env' not in tool['command']
    assert b.bundle_digest(b.AUDIO_SETTINGS_FILES) in tool['command']['argv']
    if operation=='audio_prepare':
        fields=tool['schema']['properties']['settings']
        assert fields['additionalProperties'] is False
        assert fields['properties']['sample_rate_hz']['type']=='integer'

def test_audio_settings_python_node_pin():
    out=subprocess.run(['node','--input-type=module','-e',"import {audioSettingsDigest} from './examples/opencli/xyq-web/audio-settings.mjs';console.log(audioSettingsDigest())"],cwd=ROOT,capture_output=True,text=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.AUDIO_SETTINGS_FILES)

@pytest.mark.parametrize('operation',b.AUDIO_SETTINGS_OPERATIONS)
def test_audio_settings_fake_subprocess_reuses_request(router,workspace,tmp_path,operation):
    import sys
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.audio_settings_manifest(operation);manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool))
    install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-reviewed-xyq-settings'
    program.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','{operation.replace('_','-')}']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('settings-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fake_fixture','paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *a:pytest.fail('No credential read')
    inputs=dict(SCOPE)
    if operation=='audio_prepare':inputs['settings']={'expected_form_sha256':'a'*64,'sample_rate_hz':48000}
    one=router.run(tool['id'],inputs,workspace,request_key='settings-once',grants=['execute_code','external_write'])
    two=router.run(tool['id'],inputs,workspace,request_key='settings-once',grants=['execute_code','external_write'])
    assert one['status']=='completed' and one['id']==two['id']
    assert (workspace/'settings-count').read_text()=='1'

def settings_html(*,ignore=False,mutate=False,other_layer=False,bad_rate=False,wrong_owner=False):
    html=prompt_html().replace('data-action="select-audio-model"','data-action="select-audio-model" data-state="closed"')
    html=html.replace('data-action="open-audio-parameter"','id="rate-trigger" data-state="closed" data-action="open-audio-parameter"')
    choices=''.join(f'<div role="menuitemradio" data-action="select-audio-parameter" data-action-object-id="sample_rate" data-action-value="{hz if not bad_rate else hz+1}" aria-checked="{str(hz==44100).lower()}">{hz/1000:g}kHz</div>' for hz in [8000,16000,24000,32000,44100,48000])
    ui='''<div id="models" role="dialog" data-slot="popover-content" aria-label="模型选择" hidden>
    <button aria-pressed="true" data-action="select-audio-model-seed_audio"><span data-slot="model-picker-item-title">Seed Audio 1.0</span></button>
    <button aria-pressed="false" data-action="select-audio-model-qwen_tts"><span data-slot="model-picker-item-title">标准生成</span></button></div>'''
    ui+=f'<div id="rates" role="menu" data-slot="dropdown-menu-content" aria-label="采样率" aria-labelledby="{"foreign-trigger" if wrong_owner else "rate-trigger"}" hidden>{choices}</div>'
    script='''<script>
    window.modelInputs=0;window.rateInputs=0;window.escapes=0;
    const modelTrigger=document.querySelector('[data-action="select-audio-model"]'),rateTrigger=document.querySelector('#rate-trigger'),models=document.querySelector('#models'),rates=document.querySelector('#rates');
    function closeMenus(){models.hidden=true;rates.hidden=true;modelTrigger.dataset.state='closed';rateTrigger.dataset.state='closed';}
    modelTrigger.onclick=()=>{models.hidden=false;modelTrigger.dataset.state='open';if(OTHER){const d=document.createElement('div');d.setAttribute('role','menu');d.textContent='FAKE_OTHER';document.body.appendChild(d);}};
    rateTrigger.onclick=()=>{rates.hidden=false;rateTrigger.dataset.state='open';};
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){window.escapes++;closeMenus();}});
    models.querySelectorAll('button').forEach(b=>b.onclick=()=>{window.modelInputs++;if(IGNORE)return;models.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));modelTrigger.textContent=b.querySelector('[data-slot="model-picker-item-title"]').innerText;
    rateTrigger.textContent='16kHz';rates.querySelectorAll('[role=menuitemradio]').forEach(x=>x.setAttribute('aria-checked',String(x.dataset.actionValue==='16000')));if(MUTATE)editor.textContent='CHANGED';closeMenus();});
    rates.querySelectorAll('[role=menuitemradio]').forEach(b=>b.onclick=()=>{window.rateInputs++;if(IGNORE)return;rates.querySelectorAll('[role=menuitemradio]').forEach(x=>x.setAttribute('aria-checked',String(x===b)));rateTrigger.textContent=b.innerText;if(MUTATE)editor.textContent='CHANGED';closeMenus();});
    </script>'''.replace('IGNORE',str(ignore).lower()).replace('MUTATE',str(mutate).lower()).replace('OTHER',str(other_layer).lower())
    return html.replace('</body>',ui+script+'</body>')

def config(operation='audio_prepare',**settings):return {'operation':operation,'scope':SCOPE,'settings':settings}

@pytest.mark.browser
def test_native_audio_choices_restore_menus_and_preserve_attached_reference(native_page):
    load(native_page,settings_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=media_adapter(native_page,config('audio_choices'));assert 'error' not in out,out
    r=out['result'][0]['result'];assert [e['id'] for e in r['models']]==['seed_audio','qwen_tts']
    assert [e['hz'] for e in r['sample_rates']]==[8000,16000,24000,32000,44100,48000]
    assert r['form_sha256']==out['before']['form_sha256'] and r['paid_submitted'] is False
    assert native_page.evaluate('window.escapes')==2
    assert native_page.evaluate('window.modelInputs+window.rateInputs+window.submitted+window.uploaded')==0
    assert native_page.locator('#models').is_hidden() and native_page.locator('#rates').is_hidden()
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('settings',[{'model_id':'qwen_tts'},{'sample_rate_hz':48000},{'model_id':'qwen_tts','sample_rate_hz':48000},{'model_id':'seed_audio','sample_rate_hz':44100}])
def test_native_audio_parameters_exact_readback_and_prompt_preservation(native_page,settings):
    load(native_page,settings_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    native_page.locator('[contenteditable="true"]').fill('FAKE_PRIVATE_PROMPT')
    editor=native_page.locator('[contenteditable="true"]');before=editor.inner_html()
    out=media_adapter(native_page,config(**settings));assert 'error' not in out,out
    r=out['result'][0]['result'];assert r['model']==('标准生成' if settings.get('model_id')=='qwen_tts' else 'Seed Audio 1.0')
    assert r['sample_rate']==('48kHz' if settings.get('sample_rate_hz')==48000 else '16kHz' if settings.get('model_id')=='qwen_tts' else '44.1kHz')
    assert editor.inner_html()==before and len(r['references'])==1
    if settings=={'model_id':'qwen_tts'}:assert r['implicit_sample_rate_change']=={'before':'44.1kHz','after':'16kHz'}
    assert native_page.evaluate('window.submitted+window.uploaded')==0

@pytest.mark.browser
@pytest.mark.parametrize('full',[False,True])
def test_native_partial_cover_hit_test_is_not_a_force_click(native_page,full):
    load(native_page,settings_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    native_page.evaluate('''full=>{const e=document.querySelector('#rate-trigger');e.style.width='100px';e.style.height='32px';const r=e.getBoundingClientRect();const d=document.createElement('div');d.style.cssText=`position:fixed;z-index:999;left:${r.x+r.width*(full?0:.45)}px;top:${r.y}px;width:${r.width*(full?1:.55)}px;height:${r.height}px`;document.body.appendChild(d);}''',full)
    out=media_adapter(native_page,config(sample_rate_hz=48000))
    if full:
        assert out['error']['code']=='control_obscured',out
        assert native_page.evaluate('window.rateInputs')==0
    else:
        assert 'error' not in out,out
        assert out['result'][0]['result']['point_input_used'] is True
        assert native_page.evaluate('window.rateInputs')==1
    assert native_page.evaluate('window.submitted+window.uploaded')==0

@pytest.mark.browser
def test_native_rate_preserves_structured_audio_token(native_page):
    load(native_page,settings_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    mention=media_adapter(native_page,prompt_config(prompt='FAKE_PRIVATE_PROMPT'));assert 'error' not in mention,mention
    editor=native_page.locator('[contenteditable="true"]');before=editor.inner_html()
    out=media_adapter(native_page,config(sample_rate_hz=48000));assert 'error' not in out,out
    assert editor.inner_html()==before
    assert editor.locator('[data-type="canvasPippitAssetMention"]').get_attribute('data-id')=='456'
    assert native_page.evaluate('window.mentioned')==1 and native_page.evaluate('window.rateInputs')==1
    assert native_page.evaluate('window.submitted+window.uploaded')==0

@pytest.mark.browser
@pytest.mark.parametrize('flags,settings,code',[({'ignore':True},{'sample_rate_hz':48000},'settings_changed'),({'mutate':True},{'model_id':'qwen_tts'},'draft_changed'),({'other_layer':True},{'model_id':'qwen_tts'},'settings_changed'),({'bad_rate':True},{'sample_rate_hz':48000},'layout_changed'),({'wrong_owner':True},{'sample_rate_hz':48000},'control_changed')])
def test_native_audio_menu_failures_are_explicit(native_page,flags,settings,code):
    load(native_page,settings_html(**flags),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=media_adapter(native_page,config(**settings));assert out['error']['code']==code,out
    if flags.get('other_layer'):
        assert out['error']['cleanup_code']=='cleanup_failed' and native_page.evaluate('window.escapes')==0
    if flags.get('ignore') or flags.get('mutate'):assert out['error']['outcome_uncertain'] is True
    assert native_page.evaluate('window.submitted+window.uploaded')==0
