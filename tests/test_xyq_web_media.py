"""Mode selection and WAV references: actual source through isolated native CDP."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import wave
import pytest
from test_xyq_web_cli import native_page, load
from test_xyq_web_form import form_html

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('xyq_media_builder',ROOT/'scripts/build_xyq_web.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
SCOPE={'project_id':'1','canvas_id':'2','node_id':'3'}

@pytest.mark.parametrize('operation',b.MODE_OPERATIONS+b.AUDIO_OPERATIONS+b.AUDIO_PROMPT_OPERATIONS)
def test_media_manifests(operation):
    from agent_tool_maker.maker import validate_manifest
    tool=b.mode_manifest(operation) if operation in b.MODE_OPERATIONS else b.audio_prompt_manifest() if operation in b.AUDIO_PROMPT_OPERATIONS else b.audio_manifest(operation)
    assert validate_manifest(tool)==tool and not tool['paid']
    assert tool['schema']['additionalProperties'] is False
    assert set(tool['permissions'])==({'execute_code'} if operation=='audio_form_state' else {'execute_code','external_write'})
    assert 'credential' not in tool and 'credential_env' not in tool['command']
    if operation=='audio_reference_upload':
        fields=tool['schema']['properties']['settings']
        assert set(fields['required'])==set(fields['properties'])-{'mode'}
        assert fields['properties']['mode']['enum']==['empty','append']
        assert fields['properties']['confirm']['enum']==[True]
        assert tool['command']['argv'][-2:]==['--workspace',{'workspace':''}]

@pytest.mark.parametrize('name,files',[('mode',b.MODE_FILES),('audio',b.AUDIO_FILES),('audioPrompt',b.AUDIO_PROMPT_FILES)])
def test_media_pins_match_node(name,files):
    module='audio-prompt' if name=='audioPrompt' else name
    out=subprocess.run(['node','--input-type=module','-e',f"import {{{name}Digest}} from './examples/opencli/xyq-web/{module}.mjs'; console.log({name}Digest())"],cwd=ROOT,check=True,capture_output=True,text=True)
    assert out.stdout.strip()==b.bundle_digest(files)

@pytest.mark.parametrize('operation',b.MODE_OPERATIONS+b.AUDIO_OPERATIONS+b.AUDIO_PROMPT_OPERATIONS)
def test_media_actual_fake_subprocess_once(router,workspace,tmp_path,operation):
    import sys
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.mode_manifest(operation) if operation in b.MODE_OPERATIONS else b.audio_prompt_manifest() if operation in b.AUDIO_PROMPT_OPERATIONS else b.audio_manifest(operation)
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool));install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-reviewed-xyq-media';program.write_text(f'''#!{sys.executable}
import sys,json,os
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','{operation.replace('_','-')}']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('media-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fake_fixture','paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *a:pytest.fail('No credential read')
    inputs={} if operation in b.MODE_OPERATIONS else dict(SCOPE)
    if operation=='mode_prepare':inputs['settings']={'expected_draft_sha256':'a'*64,'mode':'音频生成'}
    if operation=='audio_reference_upload':inputs['settings']={'expected_form_sha256':'a'*64,'file':str(workspace/'test.wav'),'file_sha256':'b'*64,'request_key':'media-once','purpose':'audio_reference','confirm':True}
    if operation=='audio_prompt_prepare':inputs['settings']={'expected_form_sha256':'a'*64,'prompt':'fake prompt','reference_sha256':'b'*64}
    grants=['execute_code',*(['external_write'] if operation!='audio_form_state' else [])]
    one=router.run(tool['id'],inputs,workspace,request_key='media-once',grants=grants)
    two=router.run(tool['id'],inputs,workspace,request_key='media-once',grants=grants)
    assert one['status']=='completed' and one['id']==two['id']
    assert (workspace/'media-count').read_text()=='1'

def media_adapter(page,config):
    process=subprocess.Popen(['node','tests/fixtures/xyq_media_rpc.mjs',json.dumps(config,ensure_ascii=False)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    cdp=page.context.new_cdp_session(page)
    try:
        for line in process.stdout:
            req=json.loads(line)
            if req['type']=='done':
                process.wait(timeout=5);assert process.returncode==0,process.stderr.read();return req
            assert req['type']=='call';response={'id':req['id']}
            try:
                if req['method']=='evaluate':
                    assert any(req['source'].startswith('function '+n+'(') for n in ['readHomeDOM','readDraftDOM','readModeMenuDOM','readModeTargetDOM','readAudioFormDOM','readAudioQuoteDOM','readAudioPromptDOM','readAudioPromptCaretDOM','readAudioPromptTargetDOM','readAudioSettingsMenuDOM','readAudioSettingsTargetDOM'])
                    response['value']=page.evaluate(req['source'],req.get('arg'))
                elif req['method']=='key':
                    assert req['key']=='Escape';page.keyboard.press('Escape');response['value']=None
                elif req['method'] in ['click','fill','focus']:
                    assert '开始生成' not in req['selector'] and '上传' not in req['selector']
                    loc=page.locator(req['selector']).nth(req['options']['nth'])
                    if req['method']=='click':loc.click(timeout=2000)
                    elif req['method']=='fill':loc.fill(req['value'],timeout=2000)
                    else:loc.focus(timeout=2000)
                    response['value']=None
                elif req['method']=='cdp':
                    assert req['command'] in ['DOM.getDocument','DOM.querySelector','DOM.setFileInputFiles','Input.dispatchKeyEvent','Input.dispatchMouseEvent']
                    if req['command']=='Input.dispatchKeyEvent':
                        assert req['args']['key']=='End' and req['args'].get('commands',[]) in [[],['moveToEndOfDocument']]
                    if req['command']=='Input.dispatchMouseEvent':
                        assert config['operation'] in ['audio_choices','audio_prepare']
                        assert req['args']['type'] in ['mouseMoved','mousePressed','mouseReleased']
                        assert req['args'].get('button','left')=='left' and req['args'].get('clickCount',1)==1
                    if req['command']=='DOM.setFileInputFiles':assert req['args']['files']==[config['settings']['file']]
                    response['value']=cdp.send(req['command'],req['args'])
                else:pytest.fail('Unexpected native method')
            except Exception as e:
                response['error']='native_fixture_error'
            process.stdin.write(json.dumps(response,ensure_ascii=False)+'\n');process.stdin.flush()
        pytest.fail('No media result: '+process.stderr.read())
    finally:
        cdp.detach()
        if process.poll() is None:process.terminate();process.wait(timeout=5)

def mode_html(*,attached=False,prompt=False,modal=False):
    html=form_html().replace('FAKE_PRIVATE_PROMPT','FAKE_PRIVATE_PROMPT' if prompt else '')
    html=html.replace('<button aria-label="选择创作模式">视频生成</button>','<button id="mode" aria-label="选择创作模式" data-state="closed" aria-controls="modes" aria-expanded="false">视频生成</button>')
    rail='<div data-slot="home-input-composer-attachments"><div><input type="file" hidden></div>'+('<div title="FAKE_PRIVATE.wav" data-reference-type="audio"><button data-action-object-id="FAKE_PRIVATE-1">@</button></div>' if attached else '')+'</div>'
    html=html.replace('<div id="editor"',rail+'<div id="editor"')
    items=''.join(f'<div role="menuitemradio" tabindex="0" aria-checked="{str(m=="视频生成").lower()}"><span data-slot="dropdown-menu-item-title">{m}<span data-slot="badge">BADGE</span></span></div>' for m in ['Agent模式','图片生成','视频生成','音频生成'])
    js='''<div id="modes" role="menu" aria-labelledby="mode" data-slot="dropdown-menu-content" hidden>'''+items+'''</div><script>
    const mode=document.querySelector('#mode'),menu=document.querySelector('#modes');
    function setModeOpen(open){menu.hidden=!open;mode.dataset.state=open?'open':'closed';mode.setAttribute('aria-expanded',String(open));if(MODAL){const bg=document.querySelector('#mode-background');if(open)bg.setAttribute('aria-hidden','true');else bg.removeAttribute('aria-hidden');}}
    mode.onclick=()=>setModeOpen(menu.hidden);
    document.addEventListener('keydown',e=>{if(e.key==='Escape')setModeOpen(false);});
    document.querySelectorAll('#modes [role=menuitemradio]').forEach(e=>e.onclick=()=>{mode.textContent=e.querySelector('[data-slot=dropdown-menu-item-title]').firstChild.textContent;document.querySelectorAll('#modes [role=menuitemradio]').forEach(x=>x.setAttribute('aria-checked',String(x===e)));document.querySelector('#pref').setAttribute('aria-label','模型选择和偏好设置：'+mode.textContent+'默认模型');setModeOpen(false);});
    </script>'''.replace('MODAL',str(modal).lower())
    return html.replace('<body>','<body><div id="mode-background">').replace('</body>','</div>'+js+'</body>')

@pytest.mark.browser
@pytest.mark.parametrize('modal',[False,True])
@pytest.mark.parametrize('mode',['图片生成','视频生成','音频生成'])
def test_native_exact_mode_selection(native_page,mode,modal):
    load(native_page,mode_html(modal=modal));out=media_adapter(native_page,{'operation':'mode_prepare','settings':{'mode':mode}})
    assert 'error' not in out,out
    assert out['result'][0]['result']['mode']==mode
    assert native_page.locator('#modes').is_hidden()
    assert native_page.locator('#mode-background').get_attribute('aria-hidden') is None
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('modal',[False,True])
def test_native_mode_choices_badge_and_exact_draft(native_page,modal):
    load(native_page,mode_html(prompt=True,modal=modal));body=native_page.locator('body').inner_html()
    out=media_adapter(native_page,{'operation':'mode_choices'})
    assert 'error' not in out,out
    assert [x['label'] for x in out['result'][0]['result']['items']]==['Agent模式','图片生成','视频生成','音频生成']
    assert native_page.locator('body').inner_html()==body
    assert 'FAKE_PRIVATE' not in json.dumps(out)

def mode_source(name):
    module='core' if name=='readHomeDOM' else 'form' if name=='readDraftDOM' else 'mode'
    out=subprocess.run(['node','--input-type=module','-e',f"import {{{name}}} from './examples/opencli/xyq-web/{module}.mjs'; console.log({name}.toString());"],cwd=ROOT,text=True,capture_output=True,check=True)
    return out.stdout.strip()

@pytest.mark.browser
def test_native_owned_mode_mask_read_is_narrow_and_nonmutating(native_page):
    load(native_page,mode_html(prompt=True,modal=True));native_page.locator('#mode').click()
    body=native_page.locator('body').inner_html()
    for name in ['readHomeDOM','readDraftDOM']:
        src=mode_source(name)
        assert native_page.evaluate(src)['kind']=='pending'
        assert native_page.evaluate(src,{'owned_mode_menu':True})['kind']=='ready'
        assert native_page.evaluate(src,{'owned_mode_menu':'true'})['kind']=='pending'
    assert native_page.evaluate(mode_source('readModeMenuDOM'))['kind']=='ready'
    assert native_page.locator('body').inner_html()==body
    # Independent inner masks remain excluded even inside the owned background.
    native_page.locator('#editor').evaluate("e=>e.setAttribute('aria-hidden','true')")
    assert native_page.evaluate(mode_source('readHomeDOM'),{'owned_mode_menu':True})['form'] is None
    assert native_page.evaluate(mode_source('readDraftDOM'),{'owned_mode_menu':True})['kind']=='unsupported_surface'
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('mutation',[
    "document.querySelector('#modes').setAttribute('aria-labelledby','OTHER')",
    "document.querySelector('#mode').setAttribute('aria-controls','OTHER')",
    "document.querySelector('#mode').setAttribute('aria-expanded','false')",
    "document.querySelector('#modes').insertAdjacentHTML('afterend','<div role=dialog>OTHER</div>')",
])
def test_native_mode_wrong_owner_or_extra_layer_rejected(native_page,mutation):
    load(native_page,mode_html(modal=True));native_page.locator('#mode').click()
    native_page.evaluate('()=>{'+mutation+';}');body=native_page.locator('body').inner_html()
    for name in ['readHomeDOM','readDraftDOM']:
        assert native_page.evaluate(mode_source(name),{'owned_mode_menu':True})['kind']=='mode_context_changed'
    if 'role=dialog' not in mutation:
        assert native_page.evaluate(mode_source('readModeMenuDOM'))['kind']=='mode_context_changed'
        assert native_page.evaluate(mode_source('readModeTargetDOM'),{'kind':'item','label':'音频生成'})['kind']=='control_changed'
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_mode_preserves_audio_chip_with_cleared_filelist(native_page):
    load(native_page,mode_html(attached=True));body=native_page.locator('body').inner_html()
    out=media_adapter(native_page,{'operation':'mode_prepare','settings':{'mode':'音频生成'}})
    assert out['error']['code']=='draft_not_empty',out
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.submitted')==0

def audio_html(*,multiple_nodes=False):
    extra='<div class="react-flow__node react-flow__node-biz/audio" data-id="4"></div>' if multiple_nodes else ''
    return '''<!doctype html><html><head><meta charset="utf-8"></head><body>
    <div role="application" data-testid="rf__wrapper"><div class="react-flow__node react-flow__node-biz/audio" data-id="3"></div>'''+extra+'''
    <div role="dialog" aria-label="音频节点音频生成面板" data-xyq-selected-audio-footer-panel="true">
    <div id="references"></div><div data-testid="canvas-generation-prompt-editor" contenteditable="true"><p><br></p></div>
    <input data-audio-reference-upload="true" type="file" multiple hidden><input data-image-reference-upload="true" type="file" multiple hidden accept=".png">
    <button data-action="select-audio-model">Seed Audio 1.0<span data-slot="badge">vip</span></button>
    <button data-action="open-audio-parameter" data-action-object-id="sample_rate">44.1kHz</button>
    <button data-action="audio-generate-submit" aria-busy="false" disabled onclick="window.submitted++">Generate trap</button></div></div>
    <script>window.submitted=0;window.uploaded=0;
    document.querySelector('[data-audio-reference-upload]').onchange=e=>{window.uploaded++;const f=e.target.files[0],c=document.createElement('div');c.dataset.referenceType='audio';c.title=f.name;['mention','remove'].forEach(a=>{const b=document.createElement('button');b.dataset.action=a+'-audio-reference';b.dataset.actionObjectId=f.name+'-1-0';b.textContent=a==='mention'?'@':'X';c.appendChild(b);});document.querySelector('#references').appendChild(c);e.target.value='';};
    </script></body></html>'''

def audio_config(tmp_path,**settings):
    root=tmp_path.resolve();file=root/'FAKE_PRIVATE.wav'
    with wave.open(str(file),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\0\0'*44100)
    return {'operation':'audio_upload','scope':SCOPE,'workspace':str(root),'settings':{'file':str(file),'file_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'request_key':'native-once','confirm':True,'purpose':'audio_reference',**settings}}

@pytest.mark.browser
def test_native_exact_wav_upload_and_cleared_filelist(native_page,tmp_path):
    load(native_page,audio_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    config=audio_config(tmp_path);out=media_adapter(native_page,config)
    assert 'error' not in out,out
    r=out['result'][0]['result'];assert r['status']=='attached' and not r['voice_effect_verified'] and not r['paid_submitted']
    assert len(r['references'])==1 and r['files_known']
    assert native_page.evaluate('window.uploaded')==1 and native_page.evaluate('window.submitted')==0
    assert native_page.locator('[data-reference-type="audio"]').get_attribute('title')=='FAKE_PRIVATE.wav'
    assert native_page.locator('[data-audio-reference-upload]').evaluate('(e)=>e.files.length')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
@pytest.mark.parametrize('code,mutate',[('draft_changed',None),('dialog_open','layer'),('draft_not_empty','prompt'),('audio_node_ambiguous','nodes')])
def test_native_audio_preflight_preserves_draft(native_page,tmp_path,code,mutate):
    load(native_page,audio_html(multiple_nodes=mutate=='nodes'),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    if mutate=='layer':native_page.evaluate("()=>{const d=document.createElement('div');d.setAttribute('role','menu');d.textContent='FAKE_MENU';document.body.appendChild(d);}")
    if mutate=='prompt':native_page.locator('[contenteditable="true"]').fill('FAKE_PRIVATE')
    config=audio_config(tmp_path,**({'expected_form_sha256':'0'*64} if mutate is None else {}));body=native_page.locator('body').inner_html()
    out=media_adapter(native_page,config);assert out['error']['code']==code,out
    assert native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.uploaded')==0 and native_page.evaluate('window.submitted')==0

def prompt_html(*,ignore=False,invalid_token=False,duplicates=False,covered=False):
    # Mirror the observed TipTap mention data attributes, not literal @name.
    # The actual TipTap editor and its paragraphs use break-spaces. With normal
    # white-space Chrome's native fill substitutes NBSP at the edges; mirroring
    # the observed CSS preserves the literal request rather than normalizing it.
    html=audio_html().replace('<p><br></p>','<p><br class="ProseMirror-trailingBreak"></p>')
    html=html.replace('</head>','<style>[data-testid="canvas-generation-prompt-editor"]{white-space:break-spaces}</style></head>')
    def chip(key):
        return f'''<div data-reference-type="audio" title="FAKE_PRIVATE.wav"><button data-action="mention-audio-reference" data-action-object-id="{key}">@</button><button data-action="remove-audio-reference" data-action-object-id="{key}">X</button></div>'''
    html=html.replace('<div id="references"></div>','<div id="references">'+chip('FAKE_REF_ID')+(chip('OTHER_ID') if duplicates else '')+'</div>')
    script='''<script>window.mentioned=0;const editor=document.querySelector('[data-testid="canvas-generation-prompt-editor"]');
    editor.oninput=()=>{if([...editor.childNodes].some(n=>n.nodeName!=='P')){const p=document.createElement('p');while(editor.firstChild)p.appendChild(editor.firstChild);editor.appendChild(p);}};
    document.querySelectorAll('[data-action="mention-audio-reference"]').forEach(b=>{b.onmousedown=e=>e.preventDefault();b.onclick=()=>{window.mentioned++;if(IGNORE)return;const m=document.createElement('span');m.contentEditable='false';m.dataset.type='canvasPippitAssetMention';m.dataset.id='456';m.dataset.label='FAKE_PRIVATE.wav';m.dataset.pippitAssetId=INVALID?'999':'456';m.dataset.materialPippitAssetId='456';m.dataset.mentionSuggestionChar='@';const preview=document.createElement('span');preview.className='xyq-canvas-rich-prompt-asset-audio-preview';m.appendChild(preview);m.appendChild(document.createTextNode('FAKE_PRIVATE.wav'));const s=document.getSelection(),r=s.getRangeAt(0);r.insertNode(m);const text=document.createTextNode(' ');m.after(text);r.setStart(text,1);r.collapse(true);s.removeAllRanges();s.addRange(r);};});
    </script>'''.replace('IGNORE',str(ignore).lower()).replace('INVALID',str(invalid_token).lower())
    if covered:script+='<div style="position:fixed;inset:0;z-index:999">FAKE_COVER</div>'
    return html.replace('</body>',script+'</body>')

def prompt_config(**settings):
    return {'operation':'audio_prompt','scope':SCOPE,'settings':{'reference_sha256':hashlib.sha256(b'FAKE_REF_ID').hexdigest(),**settings}}

@pytest.mark.browser
@pytest.mark.parametrize('prompt',['ATM 音频引用测试：','  literal  ','line 1\nline 2'])
def test_native_plain_prompt_and_structured_audio_mention(native_page,prompt):
    load(native_page,prompt_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=media_adapter(native_page,prompt_config(prompt=prompt));assert 'error' not in out,out
    r=out['result'][0]['result'];assert r['completed_steps']==['prompt_input','reference_input']
    assert r['mentions'][0]['asset_id']=='456' and r['mentions'][0]['reference_sha256']==prompt_config()['settings']['reference_sha256']
    assert r['literal_text_sha256']==hashlib.sha256((prompt+' ').encode()).hexdigest()
    assert native_page.evaluate('window.mentioned')==1 and native_page.evaluate('window.submitted')==0
    assert native_page.evaluate('window.uploaded')==0 and 'FAKE_PRIVATE' not in json.dumps(out)

@pytest.mark.browser
def test_native_changed_whitespace_contract_stops_before_mention(native_page):
    html=prompt_html().replace('white-space:break-spaces','white-space:normal')
    load(native_page,html,url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=media_adapter(native_page,prompt_config(prompt='  literal  '))
    assert out['error']=={'code':'settings_changed','phase':'prompt_input',
                         'completed_steps':['prompt_input'],'outcome_uncertain':True,'cleanup_code':None}
    # Do not silently replace native NBSP with the requested ASCII spaces.
    assert native_page.locator('[contenteditable="true"]').text_content()=='\u00a0 literal\u00a0\u00a0'
    assert native_page.evaluate('window.mentioned')==0
    assert native_page.evaluate('window.submitted')==0 and native_page.evaluate('window.uploaded')==0

@pytest.mark.browser
def test_native_existing_mention_no_duplicate_input_or_plain_replacement(native_page):
    load(native_page,prompt_html(),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    first=media_adapter(native_page,prompt_config(prompt='prefix'));assert 'error' not in first,first
    body=native_page.locator('body').inner_html();second=media_adapter(native_page,prompt_config());assert 'error' not in second,second
    assert second['result'][0]['result']['completed_steps']==[] and native_page.evaluate('window.mentioned')==1
    assert native_page.locator('body').inner_html()==body
    out=media_adapter(native_page,prompt_config(prompt='REPLACE'));assert out['error']['code']=='rich_prompt_present'
    assert native_page.locator('body').inner_html()==body

@pytest.mark.browser
@pytest.mark.parametrize('flags,code',[({'ignore':True},'settings_changed'),({'invalid_token':True},'unsupported_prompt_structure'),({'duplicates':True},'reference_ambiguous'),({'covered':True},'control_obscured')])
def test_native_reference_failures_are_not_string_success(native_page,flags,code):
    load(native_page,prompt_html(**flags),url='https://xyq.jianying.com/project?projectId=1&canvasId=2')
    out=media_adapter(native_page,prompt_config());assert out['error']['code']==code,out
    assert native_page.evaluate('window.submitted')==0 and native_page.evaluate('window.uploaded')==0
    assert native_page.evaluate('window.mentioned')==(1 if flags.get('ignore') or flags.get('invalid_token') else 0)
