"""Explicit one-WAV native bridge, independent of real supplier upload approval."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_xyq_web_cli import native_page,load
from test_xyq_web_media import b,SCOPE,audio_html,audio_config,media_adapter,prompt_config
from test_xyq_web_audio_append import append_html

ROOT=Path(__file__).resolve().parents[1]

def test_bound_upload_manifest_preserves_schema_permissions_and_default():
    normal=b.audio_manifest('audio_reference_upload');tool=b.audio_upload_bound_manifest()
    assert tool['id']==normal['id'] and tool['permissions']==['execute_code','external_write'] and not tool['paid']
    assert tool['command']['argv'][2]=='audio-reference-upload-bound'
    assert b.bundle_digest(b.AUDIO_UPLOAD_BOUND_FILES) in tool['command']['argv']
    tool['command']['argv']=normal['command']['argv'];tool['notes']=normal['notes'];tool['completion']=normal['completion'];assert tool==normal

def test_upload_bound_pin_matches_node_and_reviewed_transitive_sources():
    out=subprocess.run(['node','--input-type=module','-e',"import{audioUploadBoundDigest}from'./examples/opencli/xyq-web/audio-upload-bound.mjs';console.log(audioUploadBoundDigest())"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.AUDIO_UPLOAD_BOUND_FILES) and len(b.AUDIO_UPLOAD_BOUND_FILES)==8
    # MP3 intake changes the shared audio closure; installed WAV snapshots stay separate.
    assert b.bundle_digest(b.HOME_BOUND_FILES)=='8f5f2abbb2610665312d4380ccdeeb995f8336cd6aef1cbbd5f647e785ac8d55'
    assert b.bundle_digest(b.AUDIO_EDIT_BOUND_FILES)=='141ec0fbad543511aaefd0816d82b39a89566c595d78be6c24caf99ca0ea12a1'
    assert b.bundle_digest(b.AUDIO_QUOTE_BOUND_FILES)=='08d259ea0a951cb9af61de506d2ed8927c418a00911b1b2dd7a1c653a83c13dc'

@pytest.mark.parametrize('combo',[False,True])
def test_bound_upload_explicit_compiler_only_changes_selected_routes(tmp_path,combo):
    base=[sys.executable,str(ROOT/'scripts/build_xyq_web.py')]
    subprocess.run(base+['--out',str(tmp_path/'default')],text=True,capture_output=True,check=True)
    metadata=json.loads(subprocess.run(base+['--out',str(tmp_path/'bound'),'--bound-audio-upload',*(['--bound-home','--bound-audio-quote','--bound-audio-edit'] if combo else [])],text=True,capture_output=True,check=True).stdout)
    assert len(metadata['operations'])==18 and metadata['audio_upload_binding']=='explicit-browser'
    for operation in metadata['operations']:
        actual=json.loads((tmp_path/'bound'/operation/'manifest.json').read_text())
        expected=b.audio_upload_bound_manifest() if operation=='audio_reference_upload' else b.home_bound_manifest(operation) if combo and operation in b.HOME_BOUND_OPERATIONS else b.audio_quote_bound_manifest() if combo and operation=='audio_quote' else b.audio_edit_bound_manifest(operation) if combo and operation in b.AUDIO_EDIT_BOUND_OPERATIONS else json.loads((tmp_path/'default'/operation/'manifest.json').read_text())
        assert actual==expected

def test_bound_upload_actual_fake_subprocess_reuses_once_without_credentials(router,workspace,tmp_path):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.audio_upload_bound_manifest();manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(tool))
    install(router.state,router.catalog,manifest,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-bound-upload'
    program.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','audio-reference-upload-bound']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('upload-bound-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fake_bound_upload_fixture','paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program));router.vault.get=lambda *args:pytest.fail('No credentials')
    inputs={**SCOPE,'settings':{'expected_form_sha256':'a'*64,'file':str(workspace/'test.wav'),'file_sha256':'b'*64,'request_key':'upload-bound-once','purpose':'audio_reference','confirm':True,'mode':'append'}}
    one=router.run(tool['id'],inputs,workspace,request_key='upload-bound-once',grants=['execute_code','external_write'])
    reused=router.run(tool['id'],inputs,workspace,request_key='upload-bound-once',grants=['execute_code','external_write'])
    assert one['status']=='completed' and reused['id']==one['id']
    assert (workspace/'upload-bound-count').read_text()=='1'

def adapter(page,config):
    process=subprocess.Popen(['node','tests/fixtures/xyq_audio_upload_bound_rpc.mjs',json.dumps(config)],cwd=ROOT,text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    cdp=page.context.new_cdp_session(page);queries=0
    try:
        for line in process.stdout:
            req=json.loads(line)
            if req['type']=='done':process.wait(timeout=5);assert process.returncode==0,process.stderr.read();return req
            assert req['type']=='call';response={'id':req['id']}
            try:
                if req['method']=='evaluate':
                    assert any(req['source'].startswith('function '+n+'(') for n in ['readAudioFormDOM','readAudioUploadTargetDOM'])
                    response['value']=page.evaluate(req['source'],req.get('arg'))
                elif req['method']=='cdp':
                    method=req['command'];assert method in ['DOM.getDocument','DOM.querySelector']
                    if method=='DOM.getDocument':assert req['args']=={'depth':0}
                    if method=='DOM.querySelector':
                        queries+=1;assert req['args']['selector'].endswith('input[type="file"][data-audio-reference-upload="true"]')
                    value=cdp.send(method,req['args'])
                    if method=='DOM.querySelector' and queries==1 and config.get('replace_dom_input'):
                        page.locator('[data-audio-reference-upload]').evaluate('(e)=>e.replaceWith(e.cloneNode())')
                    if method=='DOM.querySelector' and queries>1 and config.get('replace_native_id'):value={'nodeId':value['nodeId']+100000}
                    response['value']=value
                elif req['method']=='set_file_input':
                    # Simulate the reviewed public chooser API in an isolated
                    # Chrome fixture. This is not extension/provider acceptance.
                    assert queries==2
                    assert req['selector']=='[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"] input[type="file"][data-audio-reference-upload="true"]'
                    assert req['files']==[config['settings']['file']]
                    ledger=Path(config['workspace'])/'.atm/xyq-audio-uploads'
                    assert (ledger/'active.lock').is_file()
                    assert (ledger/(config['settings']['request_key']+'.intent.json')).is_file()
                    if config.get('fail_native_file'):raise RuntimeError('FAKE_FILE_FAILURE')
                    page.locator(req['selector']).set_input_files(req['files'])
                    response['value']=None
                else:pytest.fail('Unexpected native upload method')
            except Exception:response['error']='native_fixture_error'
            process.stdin.write(json.dumps(response)+'\n');process.stdin.flush()
        pytest.fail('Missing native result: '+process.stderr.read())
    finally:
        cdp.detach()
        if process.poll() is None:process.terminate();process.wait(timeout=5)

def setup(page,html):load(page,html,url='https://xyq.jianying.com/project?projectId=1&canvasId=2')

@pytest.mark.browser
def test_native_bound_one_wav_intent_readback_and_historical_reuse(native_page,tmp_path):
    setup(native_page,audio_html());config=audio_config(tmp_path);out=adapter(native_page,config)
    assert 'error' not in out,out
    r=out['result'][0]['result'];assert r['status']=='attached' and r['browser_session']=='site:xyq-web'
    assert r['upload_started'] and not r['paid_submitted'] and not r['voice_effect_verified']
    assert out['calls']['set_file_input']==1 and out['calls']['cdp']==3
    assert native_page.evaluate('window.uploaded')==1 and native_page.evaluate('window.submitted')==0
    assert native_page.locator('[data-audio-reference-upload]').evaluate('(e)=>e.files.length')==0
    assert 'FAKE_PRIVATE' not in json.dumps(out)
    config['settings']['expected_form_sha256']=out['before']['form_sha256']
    body=native_page.locator('body').inner_html();again=adapter(native_page,config)
    assert 'error' not in again,again
    assert again['result'][0]['result']['reused'] and not again['result'][0]['result']['current_form_verified']
    assert set(again['calls'])=={'evaluate'} and native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.uploaded')==1

@pytest.mark.browser
@pytest.mark.parametrize('audio_count',[1,2])
@pytest.mark.parametrize('image',[False,True])
def test_native_bound_append_preserves_original_tokens_and_reference_order(native_page,tmp_path,audio_count,image):
    setup(native_page,append_html(audio_count=audio_count,image=image))
    mention=media_adapter(native_page,prompt_config(prompt='FAKE_PRIVATE_PROMPT'));assert 'error' not in mention,mention
    editor=native_page.locator('[data-testid="canvas-generation-prompt-editor"]');body=editor.inner_html();cards=native_page.locator('#references').inner_html()
    out=adapter(native_page,audio_config(tmp_path,mode='append'));assert 'error' not in out,out
    r=out['result'][0]['result'];assert r['status']=='attached' and r['references_preserved'] and r['upload_mode']=='append'
    assert r['previous_reference_count']==audio_count+int(image)
    assert editor.inner_html()==body and native_page.locator('#references').inner_html().startswith(cards)
    assert native_page.evaluate('window.uploaded')==1 and native_page.evaluate('window.mentioned')==1
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
@pytest.mark.parametrize('case,code',[('stale','draft_changed'),('prompt','draft_not_empty'),('layer','dialog_open'),('full','reference_limit'),('name','reference_name_conflict')])
def test_native_bound_expected_preflight_stop_is_explicit_not_uploaded(native_page,tmp_path,case,code):
    setup(native_page,append_html(audio_count=3 if case=='full' else 1,same_name=case=='name') if case in ['full','name'] else audio_html())
    if case=='prompt':native_page.locator('[contenteditable="true"]').fill('FAKE_PRIVATE_PROMPT')
    if case=='layer':native_page.evaluate("document.body.insertAdjacentHTML('beforeend','<div role=menu>FAKE_MENU</div>')")
    config=audio_config(tmp_path,**({'expected_form_sha256':'0'*64} if case=='stale' else {'mode':'append'} if case in ['full','name'] else {}))
    body=native_page.locator('body').inner_html();out=adapter(native_page,config);assert 'error' not in out,out
    r=out['result'][0]['result'];assert r['status']=='upload_rejected' and r['reason']==code
    assert r['upload_accepted'] is False and not r['native_file_input_sent'] and not r['upload_started'] and not r['outcome_uncertain']
    assert out['calls'].get('cdp',0)==0 and native_page.locator('body').inner_html()==body
    assert native_page.evaluate('window.uploaded+window.submitted')==0
    assert not (tmp_path/'.atm/xyq-audio-uploads/active.lock').exists()

@pytest.mark.browser
@pytest.mark.parametrize('case,code',[('replace','control_changed'),('replace-dom','control_changed'),('failure','bridge_failed')])
def test_native_bound_intent_failure_retains_unknown_and_never_repeats(native_page,tmp_path,case,code):
    setup(native_page,audio_html());config=audio_config(tmp_path);config[{'replace':'replace_native_id','replace-dom':'replace_dom_input','failure':'fail_native_file'}[case]]=True
    out=adapter(native_page,config);assert out['error']['code']==code and out['error']['outcome_uncertain'],out
    assert out['error']['phase']=='upload'
    diagnostic=tmp_path/'.atm/xyq-audio-uploads/native-once.failure.json'
    saved=json.loads(diagnostic.read_text())
    assert saved['outcome_uncertain'] and saved['phase']=='upload' and not saved['receipt_is_success']
    assert diagnostic.stat().st_mode&0o777==0o600
    assert saved['native_input_attempted']==(case=='failure')
    assert 'FAKE_FILE_FAILURE' not in diagnostic.read_text()
    assert (tmp_path/'.atm/xyq-audio-uploads/active.lock').is_file()
    assert native_page.evaluate('window.uploaded+window.submitted')==0
    config['settings']['expected_form_sha256']=json.loads((tmp_path/'.atm/xyq-audio-uploads/native-once.intent.json').read_text())['before_form_sha256']
    again=adapter(native_page,config);assert again['error']['code']=='upload_unknown',again
    assert again['calls'].get('cdp',0)==0

@pytest.mark.browser
def test_native_document_root_ids_diagnosis_and_same_root_identity(native_page,tmp_path):
    setup(native_page,audio_html());cdp=native_page.context.new_cdp_session(native_page)
    selector='[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"] input[type="file"][data-audio-reference-upload="true"]'
    try:
        root=cdp.send('DOM.getDocument',{'depth':0})['root']['nodeId']
        first=cdp.send('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId']
        same=cdp.send('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId']
        backend=cdp.send('DOM.describeNode',{'nodeId':first})['node']['backendNodeId']
        newroot=cdp.send('DOM.getDocument',{'depth':0})['root']['nodeId']
        fresh=cdp.send('DOM.querySelector',{'nodeId':newroot,'selector':selector})['nodeId']
        same_backend=cdp.send('DOM.describeNode',{'nodeId':fresh})['node']['backendNodeId']
        assert first==same and backend==same_backend
        path=tmp_path/'cdp-node-identity.json';path.write_text(json.dumps({'old_root':root,'first':first,'same_root_requery':same,'new_root':newroot,'fresh_query':fresh,'backend_node_id':backend,'same_backend_node_id':same_backend}));path.chmod(0o600)
        assert native_page.evaluate('window.uploaded+window.submitted')==0
    finally:cdp.detach()
@pytest.mark.browser
@pytest.mark.parametrize('mutation',[
    "document.querySelector('[data-audio-reference-upload]').addEventListener('change',()=>{document.querySelector('[contenteditable=true]').textContent='CHANGED';})",
    "document.querySelector('[data-audio-reference-upload]').addEventListener('change',()=>{document.querySelector('[data-action=select-audio-model]').textContent='CHANGED';})",
])
def test_native_bound_after_input_mutation_is_unknown_not_clean_stop(native_page,tmp_path,mutation):
    setup(native_page,audio_html());native_page.evaluate(mutation)
    out=adapter(native_page,audio_config(tmp_path));assert out['error']['code']=='upload_readback_changed' and out['error']['outcome_uncertain'],out
    assert native_page.evaluate('window.uploaded')==1 and native_page.evaluate('window.submitted')==0
    assert (tmp_path/'.atm/xyq-audio-uploads/active.lock').is_file()

@pytest.mark.browser
@pytest.mark.parametrize('case,code',[('disabled','control_obscured'),('duplicate','layout_changed'),('node','node_changed'),('mask','audio_form_closed')])
def test_native_bound_file_target_guard_keeps_hidden_native_contract(native_page,case,code):
    setup(native_page,audio_html())
    source=subprocess.run(['node','--input-type=module','-e',"import{readAudioUploadTargetDOM}from'./examples/opencli/xyq-web/audio-upload-bound.mjs';console.log(readAudioUploadTargetDOM.toString())"],cwd=ROOT,text=True,capture_output=True,check=True).stdout
    scope=dict(SCOPE)
    assert native_page.evaluate(source,scope)['kind']=='ready'
    if case=='disabled':native_page.locator('[data-audio-reference-upload]').evaluate('(e)=>e.disabled=true')
    if case=='duplicate':native_page.locator('[data-audio-reference-upload]').evaluate('(e)=>e.after(e.cloneNode())')
    if case=='node':scope['node_id']='9'
    if case=='mask':native_page.locator('[data-xyq-selected-audio-footer-panel]').evaluate('(e)=>e.setAttribute("aria-hidden","true")')
    assert native_page.evaluate(source,scope)['kind']==code
    assert native_page.evaluate('window.uploaded+window.submitted')==0
