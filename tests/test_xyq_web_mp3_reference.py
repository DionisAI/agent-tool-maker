"""Real local MP3 encodings and native fixture uploads; no live provider activity."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from agent_tool_maker import media
from test_xyq_media_delivery import tools
from test_xyq_web_cli import native_page
from test_xyq_web_media import b,SCOPE,audio_html,media_adapter,prompt_config
from test_xyq_web_audio_append import append_html
from test_xyq_web_audio_upload_bound import adapter,setup

ROOT=Path(__file__).resolve().parents[1]

def encode(root,tools,rate=16000,channels=1,vbr=False):
    file=root.resolve()/'FAKE_PRIVATE.mp3'
    subprocess.run([tools['ffmpeg']['path'],'-nostdin','-v','error','-n','-f','lavfi','-i',
                    f'sine=frequency=440:sample_rate={rate}:duration=1','-ac',str(channels),
                    '-c:a','libmp3lame',*(['-q:a','4'] if vbr else ['-b:a','64k']),
                    '-metadata','comment=FAKE_PRIVATE_TAG',str(file)],check=True,capture_output=True)
    return file

def inspect(file):
    command="""import{inspectAudioFile}from'./examples/opencli/xyq-web/audio.mjs';
    import{createHash}from'node:crypto';import{readFileSync}from'node:fs';
    const f=process.argv[1],w=process.argv[2],sha=createHash('sha256').update(readFileSync(f)).digest('hex');
    console.log(JSON.stringify(inspectAudioFile(f,w,sha)));"""
    return json.loads(subprocess.run(['node','--input-type=module','-e',command,str(file),str(file.parent)],
                                    cwd=ROOT,check=True,capture_output=True,text=True).stdout)

def config(file,**settings):
    return {'scope':SCOPE,'workspace':str(file.parent),'settings':{'file':str(file),
            'file_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'request_key':'native-once',
            'confirm':True,'purpose':'audio_reference',**settings}}

@pytest.mark.parametrize('rate,channels,vbr',[(8000,1,False),(16000,1,False),(22050,2,True),(44100,2,False),(48000,2,True)])
def test_real_encoded_mp3_intake_matches_independent_complete_decoder(tmp_path,tools,rate,channels,vbr):
    file=encode(tmp_path,tools,rate,channels,vbr);out=inspect(file)
    decoded=media.inspect_media(str(file.parent),file.name,'audio',out['sha256'],tools)
    assert out['format']=='mp3' and out['sample_rate']==rate and out['channels']==channels
    assert out['duration_basis']=='encoded_frame_samples' and out['decoder_verified'] is False
    assert 1<=out['duration_seconds']<=1.3
    assert decoded['valid'] and decoded['complete_decode_verified']
    assert 0.9<=decoded['media']['decoded_output_time_seconds']<=out['duration_seconds']
    assert 'FAKE_PRIVATE_TAG' not in json.dumps(out)+json.dumps(decoded)
    assert not decoded['provider_generation_verified'] and not decoded['download_verified']

def test_mp3_upload_schema_does_not_add_decoder_commands_or_new_permissions():
    for manifest in [b.audio_manifest('audio_reference_upload'),b.audio_upload_bound_manifest()]:
        fields=manifest['schema']['properties']['settings']
        assert list(fields['properties'])==['expected_form_sha256','file','file_sha256','request_key','purpose','confirm','mode']
        assert fields['additionalProperties'] is False and fields['properties']['mode']['enum']==['empty','append']
        assert manifest['permissions']==['execute_code','external_write'] and manifest['paid'] is False
        assert 'MP3' in manifest['notes'] and manifest['id']=='xyq.web.audio_reference_upload'
        assert 'ffmpeg' not in json.dumps(manifest['command'])

@pytest.mark.browser
def test_native_real_encoded_mp3_input_intent_card_readback_and_historical_reuse(native_page,tmp_path,tools):
    file=encode(tmp_path,tools);setup(native_page,audio_html());cfg=config(file)
    out=adapter(native_page,cfg);assert 'error' not in out,out
    result=out['result'][0]['result']
    assert result['status']=='attached' and result['file_format']=='mp3' and result['decoder_verified'] is False
    assert result['duration_basis']=='encoded_frame_samples' and not result['voice_effect_verified']
    assert not result['paid_submitted'] and not result['generation_submitted'] and not result['persistence_verified']
    assert result['file_sha256']==cfg['settings']['file_sha256'] and 'FAKE_PRIVATE' not in json.dumps(out)
    assert native_page.evaluate('window.uploaded')==1 and native_page.evaluate('window.submitted')==0
    assert native_page.locator('[data-audio-reference-upload]').evaluate('(e)=>e.files.length')==0
    cfg['settings']['expected_form_sha256']=out['before']['form_sha256']
    body=native_page.locator('body').inner_html();again=adapter(native_page,cfg)
    assert 'error' not in again and again['result'][0]['result']['reused']
    assert not again['result'][0]['result']['current_form_verified']
    assert set(again['calls'])=={'evaluate'} and native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.uploaded')==1

@pytest.mark.browser
@pytest.mark.parametrize('audio_count',[1,2])
def test_native_mp3_append_preserves_existing_wav_token_image_and_card_order(native_page,tmp_path,tools,audio_count):
    file=encode(tmp_path,tools,44100,2,True);setup(native_page,append_html(audio_count=audio_count,image=True))
    mention=media_adapter(native_page,prompt_config(prompt='FAKE_PRIVATE_PROMPT'));assert 'error' not in mention,mention
    editor=native_page.locator('[data-testid="canvas-generation-prompt-editor"]')
    original_prompt=editor.inner_html();original_cards=native_page.locator('#references').inner_html()
    out=adapter(native_page,config(file,mode='append'));assert 'error' not in out,out
    result=out['result'][0]['result'];assert result['status']=='attached' and result['file_format']=='mp3'
    assert result['references_preserved'] and result['previous_reference_count']==audio_count+1
    assert sum(r['type']=='audio' for r in result['references'])==audio_count+1
    assert editor.inner_html()==original_prompt and native_page.locator('#references').inner_html().startswith(original_cards)
    assert editor.locator('[data-type="canvasPippitAssetMention"]').get_attribute('data-id')=='456'
    assert native_page.evaluate('window.uploaded')==1 and native_page.evaluate('window.mentioned')==1
    assert native_page.evaluate('window.submitted')==0 and 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
def test_native_mp3_full_reference_slots_reject_before_intent_or_file_input(native_page,tmp_path,tools):
    file=encode(tmp_path,tools);setup(native_page,append_html(audio_count=3));body=native_page.locator('body').inner_html()
    out=adapter(native_page,config(file,mode='append'));assert 'error' not in out,out
    result=out['result'][0]['result'];assert result['status']=='upload_rejected' and result['reason']=='reference_limit'
    assert not result['native_file_input_sent'] and out['calls'].get('cdp',0)==0
    assert native_page.locator('body').inner_html()==body and native_page.evaluate('window.uploaded+window.submitted')==0
    assert not (file.parent/'.atm/xyq-audio-uploads/native-once.intent.json').exists()

@pytest.mark.browser
def test_native_mp3_truncated_bytes_do_not_reach_file_input(native_page,tmp_path,tools):
    file=encode(tmp_path,tools);file.write_bytes(file.read_bytes()[:-1]);setup(native_page,audio_html())
    out=adapter(native_page,config(file));assert out['error']['code']=='invalid_audio_file',out
    assert out['calls'].get('cdp',0)==0 and native_page.evaluate('window.uploaded+window.submitted')==0
    assert not (file.parent/'.atm').exists()

@pytest.mark.browser
def test_native_mp3_unknown_input_result_retains_lock_and_does_not_repeat(native_page,tmp_path,tools):
    file=encode(tmp_path,tools);setup(native_page,audio_html());cfg=config(file);cfg['fail_native_file']=True
    out=adapter(native_page,cfg);assert out['error']['code']=='bridge_failed' and out['error']['outcome_uncertain'],out
    ledger=file.parent/'.atm/xyq-audio-uploads';assert (ledger/'active.lock').is_file()
    cfg['settings']['expected_form_sha256']=out['before']['form_sha256'] if 'before' in out else json.loads((ledger/'native-once.intent.json').read_text())['before_form_sha256']
    again=adapter(native_page,cfg);assert again['error']['code']=='upload_unknown' and again['calls'].get('cdp',0)==0
    assert native_page.evaluate('window.uploaded+window.submitted')==0
