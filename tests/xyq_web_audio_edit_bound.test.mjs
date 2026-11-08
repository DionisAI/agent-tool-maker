import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {audioFormHash} from '../examples/opencli/xyq-web/audio.mjs';
import {AUDIO_SETTINGS_FILES,readAudioSettingsTargetDOM} from '../examples/opencli/xyq-web/audio-settings.mjs';
import {AUDIO_PROMPT_FILES} from '../examples/opencli/xyq-web/audio-prompt.mjs';
import {AUDIO_BOUND_FILES} from '../examples/opencli/xyq-web/audio-bound.mjs';
import {AUDIO_EDIT_BOUND_FILES,audioEditBoundDigest,checkAudioEditBoundPin,audioEditBoundSettings,audioEditPage,runBoundAudioEdit} from '../examples/opencli/xyq-web/audio-edit-bound.mjs';
const scope={project_id:'1',canvas_id:'2',node_id:'3'},sha=s=>createHash('sha256').update(s).digest('hex');
const editor='[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"] [data-testid="canvas-generation-prompt-editor"][contenteditable="true"]';
function noop(){
  const ref={type:'audio',name:'FAKE_PRIVATE.wav',id:'FAKE_REF_ID'},token={kind:'audio_reference',asset_id:'456',label:ref.name};
  const doc={kind:'ready',supported:true,literal_text:'prefix ',segments:[{kind:'text',text:'prefix'},token,{kind:'text',text:' '}],tokens:[token]};
  const form={kind:'ready',...scope,model:'Seed Audio 1.0',sample_rate:'44.1kHz',prompt:'prefixFAKE_PRIVATE.wav ',prompt_tree:doc.segments,prompt_references:1,references:[ref],files:[],layers:0,submit_enabled:true,submit_busy:false,association:'unique_audio_node_only'};
  const calls=[];
  const backend={evaluate:async fn=>{calls.push(fn.name);if(fn.name==='readAudioFormDOM')return structuredClone(form);if(fn.name==='readAudioPromptDOM')return structuredClone(doc);assert.fail(fn.name);},nativeClick:()=>assert.fail('input'),nativeType:()=>assert.fail('text'),nativeKeyPress:()=>assert.fail('key'),cdp:()=>assert.fail('CDP')};
  return{form,doc,backend,calls,settings:{expected_form_sha256:audioFormHash(form),reference_sha256:sha(ref.id)}};
}
test('pin covers the full settings/prompt/public routing union and rejects coerced input',()=>{
  assert.deepEqual(AUDIO_EDIT_BOUND_FILES,[...new Set([...AUDIO_SETTINGS_FILES,...AUDIO_PROMPT_FILES,...AUDIO_BOUND_FILES]),'audio-edit-bound.mjs','audio-edit-bound.js']);assert.equal(AUDIO_EDIT_BOUND_FILES.length,12);
  checkAudioEditBoundPin(audioEditBoundDigest());for(const pin of [null,[],[audioEditBoundDigest()],'0'.repeat(64)])assert.throws(()=>checkAudioEditBoundPin(pin),e=>e.code==='definition_changed');
});
test('typed operation/scope/settings fail before factory or browser reads',async()=>{
  const x=noop();
  for(const [op,settings] of [['wrong',{}],['audio_choices',{}],['audio_prepare',{}],['audio_prompt_prepare',{...x.settings,reference_sha256:[x.settings.reference_sha256]}],['audio_prompt_prepare',Object.assign(Object.create({prompt:'inherited'}),x.settings)]])
    await assert.rejects(runBoundAudioEdit({},op,scope,settings,()=>assert.fail('factory')),e=>e.code==='invalid_argument');
  await assert.rejects(runBoundAudioEdit({},'audio_choices',{...scope,node_id:'wrong'},undefined,()=>assert.fail('factory')),e=>e.code==='invalid_argument');
  for(const input of [null,[],{},'{',{...x.settings,selector:'body'}])assert.throws(()=>audioEditBoundSettings('audio_prompt_prepare',input),e=>e.code==='invalid_argument');
});
test('already-present structured reference is a real zero-input bound operation',async()=>{
  for(const context of [{},{contextId:'fixture'},{preferredContextId:'fixture'}]){
    const x=noop(),result=(await runBoundAudioEdit(context,'audio_prompt_prepare',scope,x.settings,async routing=>{assert.deepEqual(routing,context);return x.backend;}))[0].result;
    assert.equal(result.status,'prepared');assert.deepEqual(result.completed_steps,[]);assert.equal(result.form_sha256,x.settings.expected_form_sha256);assert.equal(result.mentions[0].reference_sha256,x.settings.reference_sha256);
    assert.equal(result.browser_session,'site:xyq-web');assert.equal(result.binding_changed,false);assert.equal(result.paid_submitted,false);assert.equal(result.upload_started,false);assert.equal(result.voice_effect_verified,false);assert(!JSON.stringify(result).includes('FAKE_PRIVATE'));assert(x.calls.every(n=>['readAudioFormDOM','readAudioPromptDOM'].includes(n)));
  }
});
test('origin/node/login and stale drafts fail without fallback or native actions',async()=>{
  const x=noop();
  for(const kind of ['origin_mismatch','canvas_changed','node_changed','login_required']){let factories=0;await assert.rejects(runBoundAudioEdit({},'audio_choices',scope,undefined,async()=>{factories++;return{evaluate:async()=>({kind})};}),e=>e.code===kind);assert.equal(factories,1);}
  await assert.rejects(runBoundAudioEdit({},'audio_prompt_prepare',scope,{...x.settings,expected_form_sha256:'0'.repeat(64)},async()=>x.backend),e=>e.code==='draft_changed'&&!e.outcome_uncertain);
});
test('factory/routing failures sanitize diagnostics and malformed Page stays explicit',async()=>{
  const x=noop();
  for(const context of [null,[],{contextId:'../TOKEN'},{contextId:'a',preferredContextId:'b'}])await assert.rejects(runBoundAudioEdit(context,'audio_choices',scope,undefined,()=>assert.fail('factory')),e=>e.code==='unsupported_backend');
  await assert.rejects(runBoundAudioEdit({},'audio_choices',scope,undefined,()=>{throw Error('FAKE_PRIVATE_TOKEN');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  await assert.rejects(runBoundAudioEdit({},'audio_choices',scope,undefined,async()=>({})),e=>e.code==='unsupported_backend');
});
test('dangling or changed point targets send no native pointer input',async()=>{
  const backend={evaluate:async()=>({kind:'ready',selector:'fixed',nth:0,point:{x:20,y:20},pointer_ready:true}),nativeClick:()=>assert.fail('input')},page=audioEditPage(backend,scope,'audio_prepare');
  await assert.rejects(page.clickPoint({x:20,y:20}),e=>e.code==='control_changed');
  await page.evaluate(readAudioSettingsTargetDOM,{...scope,kind:'sample_rate_trigger'});await assert.rejects(page.clickPoint({x:21,y:20}),e=>e.code==='control_changed');
  await page.evaluate(readAudioSettingsTargetDOM,{...scope,kind:'sample_rate_trigger'});backend.evaluate=async()=>({kind:'ready',selector:'fixed',nth:0,point:{x:22,y:20},pointer_ready:true});await assert.rejects(page.clickPoint({x:20,y:20}),e=>e.code==='control_changed');
});
test('Escape is restricted to a native-opened menu and rechecked ownership',async()=>{
  const backend={evaluate:async(fn,arg)=>({kind:arg.kind==='escape'?'dialog_open':'ready',x:20,y:20}),nativeClick:async()=>{},nativeKeyPress:()=>assert.fail('key')},page=audioEditPage(backend,scope,'audio_choices');
  await assert.rejects(page.pressKey('Escape'),e=>e.code==='invalid_argument');await assert.rejects(page.pressKey('Enter'),e=>e.code==='invalid_argument');
  await page.click('[data-xyq-selected-audio-footer-panel="true"] button[data-action="select-audio-model"]',{nth:0});await assert.rejects(page.pressKey('Escape'),e=>e.code==='dialog_open');
});
test('plain native text requires full selection before replacement and retains input phase',async()=>{
  let typed=0;const backend={evaluate:async(fn,arg)=>arg.kind==='selected'?{kind:'selection_changed'}:{kind:'ready',x:20,y:20,text:'old',modifier:'Control'},nativeClick:async()=>{},nativeType:async()=>{typed++;},cdp:async()=>{}};
  const page=audioEditPage(backend,scope,'audio_prompt_prepare');await assert.rejects(page.fillText(editor,'new',{nth:0}),e=>e.code==='selection_changed'&&e.input_phase==='selected');assert.equal(typed,0);
  await assert.rejects(page.fillText('button[data-action="audio-generate-submit"]','new',{nth:0}),e=>e.code==='invalid_argument');assert.equal(typed,0);
});
test('native failure is sanitized and retained with zero automatic retries',async()=>{
  let typed=0;const backend={evaluate:async()=>({kind:'ready',x:20,y:20,text:'old',modifier:'Control'}),nativeClick:async()=>{},nativeType:async()=>{typed++;throw Error('FAKE_PRIVATE_TOKEN');},cdp:async()=>{}};
  const page=audioEditPage(backend,scope,'audio_prompt_prepare');await assert.rejects(page.fillText(editor,'new',{nth:0}),e=>e.code==='bridge_failed'&&e.input_phase==='replace'&&e.outcome_uncertain&&!e.message.includes('FAKE_PRIVATE'));assert.equal(typed,1);assert.equal(page.outcome_uncertain,true);
});
test('wrapper has no arbitrary CDP/navigation/auth/upload surface or source mutation',()=>{
  const page=audioEditPage({evaluate:async()=>({})},scope,'audio_prompt_prepare');for(const key of ['goto','bind','cdp','getCookies','upload','nativeKeyPress'])assert.equal(page[key],undefined);
  const src=readFileSync(new URL('../examples/opencli/xyq-web/audio-edit-bound.mjs',import.meta.url),'utf8');assert.match(src,/new Page\('site:xyq-web'/);assert.doesNotMatch(src,/document\.cookie|localStorage|sessionStorage|indexedDB|fetch\(|XMLHttpRequest|\.innerHTML\s*=|writeFile|bindTab|\._page|DOM\.setFileInputFiles/);
});
