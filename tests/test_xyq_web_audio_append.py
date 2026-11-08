"""Append one approved WAV using isolated native DOM, preserving existing references."""
import json
from pathlib import Path
import pytest
from test_xyq_web_media import native_page,load,media_adapter,prompt_html,prompt_config,audio_config

def test_append_setting_reaches_isolated_cli_subprocess_once(router,workspace,tmp_path):
    import sys
    from test_xyq_web_media import b,SCOPE
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.audio_manifest('audio_reference_upload');manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool))
    install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-reviewed-append';program.write_text(f'''#!{sys.executable}
import sys,json,os
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','audio-reference-upload']
settings=json.loads(sys.argv[sys.argv.index('--settings')+1]);assert settings['mode']=='append' and settings['confirm'] is True
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('append-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fake_fixture','upload_mode':'append','paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *args:pytest.fail('No credential read')
    inputs={**SCOPE,'settings':{'expected_form_sha256':'a'*64,'file':str(workspace/'test.wav'),'file_sha256':'b'*64,
        'request_key':'append-once','purpose':'audio_reference','confirm':True,'mode':'append'}}
    one=router.run(tool['id'],inputs,workspace,request_key='append-once',grants=['execute_code','external_write'])
    two=router.run(tool['id'],inputs,workspace,request_key='append-once',grants=['execute_code','external_write'])
    assert one['status']=='completed' and one['id']==two['id']
    assert (workspace/'append-count').read_text()=='1'

def append_html(*,audio_count=1,image=False,same_name=False,mutation=None):
    html=prompt_html().replace('FAKE_PRIVATE.wav','FAKE_PRIVATE.wav' if same_name else 'OLD_PRIVATE.wav')
    cards=''
    for n in range(2,audio_count+1):
        cards+=f'<div data-reference-type="audio" title="OLD{n}_PRIVATE.wav"><button data-action="mention-audio-reference" data-action-object-id="OLD{n}">@</button><button data-action="remove-audio-reference" data-action-object-id="OLD{n}">X</button></div>'
    if image:cards+='<div data-reference-type="image" title="PRIVATE.png"><button data-action="mention-image-reference" data-action-object-id="OLD_IMAGE">@</button><button data-action="remove-image-reference" data-action-object-id="OLD_IMAGE">X</button></div>'
    # Prepend extra cards; preserve their observed DOM order through the upload.
    html=html.replace('<div id="references">','<div id="references">'+cards)
    if mutation:
        html=html.replace('</body>','<script>document.querySelector("[data-audio-reference-upload]").addEventListener("change",()=>{'+mutation+';});</script></body>')
    return html

def setup(page,**flags):
    load(page,append_html(**flags),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    mention=media_adapter(page,prompt_config(prompt='FAKE_PRIVATE_PROMPT'))
    assert 'error' not in mention,mention
    assert page.evaluate('window.mentioned')==1

@pytest.mark.browser
@pytest.mark.parametrize('audio_count',[1,2])
@pytest.mark.parametrize('image',[False,True])
def test_native_audio_append_preserves_tokens_and_existing_cards(native_page,tmp_path,audio_count,image):
    setup(native_page,audio_count=audio_count,image=image)
    editor=native_page.locator('[data-testid="canvas-generation-prompt-editor"]')
    prompt=editor.inner_html();old=native_page.locator('#references').inner_html()
    config=audio_config(tmp_path,mode='append');out=media_adapter(native_page,config)
    assert 'error' not in out,out
    result=out['result'][0]['result']
    assert result['upload_mode']=='append' and result['references_preserved']
    assert result['previous_reference_count']==audio_count+int(image)
    assert len(result['references'])==audio_count+int(image)+1
    assert sum(r['type']=='audio' for r in result['references'])==audio_count+1
    assert editor.inner_html()==prompt
    assert native_page.locator('#references').inner_html().startswith(old)
    assert editor.locator('[data-type="canvasPippitAssetMention"]').get_attribute('data-id')=='456'
    assert native_page.evaluate('window.mentioned')==1 and native_page.evaluate('window.uploaded')==1
    assert native_page.evaluate('window.submitted')==0
    assert not result['paid_submitted'] and not result['voice_effect_verified']
    assert result['files_known'] and 'PRIVATE' not in json.dumps(out)
    # Stable-key replay returns the receipt, not another upload or current proof.
    config['settings']['expected_form_sha256']=out['before']['form_sha256']
    body=native_page.locator('body').inner_html();again=media_adapter(native_page,config)
    assert 'error' not in again,again
    assert again['result'][0]['result']['reused']
    assert not again['result'][0]['result']['current_form_verified']
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.uploaded')==1

@pytest.mark.browser
@pytest.mark.parametrize('flags,settings,code',[
    ({'audio_count':3},{'mode':'append'},'reference_limit'),
    ({'same_name':True},{'mode':'append'},'reference_name_conflict'),
    ({},{},'draft_not_empty'),
])
def test_native_audio_append_preflight_conflict_has_zero_upload(native_page,tmp_path,flags,settings,code):
    setup(native_page,**flags);body=native_page.locator('body').inner_html()
    config=audio_config(tmp_path,**settings);out=media_adapter(native_page,config)
    assert out['error']['code']==code,out
    assert not out['error']['outcome_uncertain']
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.uploaded+window.submitted')==0
    assert not (tmp_path/'.atm/xyq-audio-uploads/native-once.intent.json').exists()

@pytest.mark.browser
@pytest.mark.parametrize('mutation',[
    "document.querySelector('[data-testid=canvas-generation-prompt-editor]').textContent='CHANGED'",
    "document.querySelector('[data-reference-type=audio]').setAttribute('title','CHANGED.wav')",
    "document.querySelector('[data-reference-type=audio]').remove()",
])
def test_native_audio_append_concurrent_change_retains_uncertainty_lock(native_page,tmp_path,mutation):
    setup(native_page,mutation=mutation)
    config=audio_config(tmp_path,mode='append');out=media_adapter(native_page,config)
    assert out['error']['code']=='upload_readback_changed',out
    assert out['error']['outcome_uncertain']
    assert native_page.evaluate('window.uploaded')==1 and native_page.evaluate('window.submitted')==0
    ledger=tmp_path/'.atm/xyq-audio-uploads'
    assert (ledger/'active.lock').exists() and (ledger/'native-once.intent.json').exists()
    assert not (ledger/'native-once.result.json').exists()
