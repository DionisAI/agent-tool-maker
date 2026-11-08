import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {AUDIO_BOUND_FILES} from '../examples/opencli/xyq-web/audio-bound.mjs';
import {RESULT_FILES,resultDigest,checkResultPin,resultScope,inspectConversationResults,inspectBoundConversationResults} from '../examples/opencli/xyq-web/results.mjs';
const scope={thread_id:'00000000-0000-0000-0000-000000000001'},id='a'.repeat(32);
const card={result_id:id,kind:'image',load_state:'loaded',width:360,height:480,resize_width:480,resize_height:480,surface:'conversation_card'};
const preview={...card,width:810,height:1080,resize_width:1080,resize_height:1080,surface:'artifact_preview',filename:'fixture.png',download_enabled:true,download_hit_verified:true};
const state={kind:'ready',images:[card],preview};
function fixture(data=state){let reads=0;return{get reads(){return reads;},evaluate:async(fn,arg)=>{reads++;assert.equal(fn.name,'readConversationResultsDOM');assert.deepEqual(arg,scope);return structuredClone(data);},nativeClick:()=>assert.fail('input'),goto:()=>assert.fail('navigation'),getCookies:()=>assert.fail('auth')};}
test('independent transitive pin and strict exact observed scope',()=>{
  assert.deepEqual(RESULT_FILES,[...AUDIO_BOUND_FILES,'results.mjs','results.js']);checkResultPin(resultDigest());
  for(const v of [null,[resultDigest()],'0'.repeat(64)])assert.throws(()=>checkResultPin(v),e=>e.code==='definition_changed');
  for(const v of [null,[],{}, {...scope,selector:'body'}, {...scope,thread_id:1},Object.create(scope)])assert.throws(()=>resultScope(v),e=>e.code==='invalid_argument');
  assert.throws(()=>resultScope({...scope,result_id:32},'result_inspect'),e=>e.code==='invalid_argument');
  assert.throws(()=>resultScope({...scope,result_id:id,expected_result_sha256:'bad'},'result_download_quote'),e=>e.code==='invalid_argument');
});
test('loaded image is a visible media resource, not provider task/completion/delivery',async()=>{
  const p=fixture(),r=(await inspectConversationResults(p,scope))[0].result;
  assert.equal(p.reads,2);assert.equal(r.visible_result_count,1);assert.equal(r.visible_card_count,1);assert.equal(r.results[0].surface,'artifact_preview');assert.equal(r.results[0].width,810);
  assert.equal(r.results[0].result_id_kind,'visible_media_resource');assert.equal(r.provider_task_id,null);assert.equal(r.provider_task_status,null);
  for(const k of ['all_results','task_association_verified','provider_generation_verified','secrets_returned','generation_submitted','upload_started','paid_submitted','download_started','download_verified'])assert.equal(r[k],false);
});
test('exact preview download plan is digest-bound and never initiates a download',async()=>{
  const a=(await inspectConversationResults(fixture(),{...scope,result_id:id},'result_inspect'))[0].result;
  const r=(await inspectConversationResults(fixture(),{...scope,result_id:id,expected_result_sha256:a.result_sha256},'result_download_quote'))[0].result;
  assert.equal(r.status,'download_control_ready');assert.equal(r.filename,'fixture.png');assert.equal(r.download_started,false);assert.equal(r.decoder_verified,false);assert.equal(r.bytes_verified,false);
  assert.equal(r.quote_kind,'existing_result_download_plan_not_price');assert.match(r.quote_sha256,/^[a-f0-9]{64}$/);
});
test('metadata digests ignore public evaluator key serialization order',async()=>{
  let n=0;const reverse=v=>Object.fromEntries(Object.entries(v).reverse());
  const p={evaluate:async()=>++n===1?state:reverse({...state,images:[reverse(card)],preview:reverse(preview)})};
  const a=(await inspectConversationResults(p,scope))[0].result,b=(await inspectConversationResults(fixture(),scope))[0].result;
  assert.equal(a.results_sha256,b.results_sha256);assert.equal(a.results[0].result_sha256,b.results[0].result_sha256);
});
test('empty/current loading/broken image observations are not all-account task states',async()=>{
  const empty=(await inspectConversationResults(fixture({kind:'ready',images:[],preview:null}),scope))[0].result;
  assert.equal(empty.status,'no_rendered_image_results');assert.equal(empty.all_results,false);assert.equal(empty.provider_task_status,null);
  for(const [load_state,width,height,status] of [['loading',0,0,'result_pending'],['failed',0,0,'result_load_failed']]){
    const r=(await inspectConversationResults(fixture({kind:'ready',images:[{...card,load_state,width,height}],preview:null}),scope))[0].result;
    assert.equal(r.results[0].status,status);
  }
});
test('missing/changed/closed/loading/covered/disabled preview stops download planning',async()=>{
  const cases=[['missing',{...state,images:[],preview:null},id,'result_missing'],['closed',{kind:'ready',images:[card],preview:null},id,'preview_required'],
    ['loading',{...state,preview:{...preview,load_state:'loading',width:0,height:0}},id,'result_not_ready'],
    ['covered',{...state,preview:{...preview,download_hit_verified:false}},id,'control_obscured'],
    ['disabled',{...state,preview:{...preview,download_enabled:false}},id,'download_unavailable']];
  for(const [,data,result_id,code] of cases){
    const hash=code==='result_missing'?'0'.repeat(64):(await inspectConversationResults(fixture(data),{...scope,result_id},'result_inspect'))[0].result.result_sha256;
    await assert.rejects(inspectConversationResults(fixture(data),{...scope,result_id,expected_result_sha256:hash},'result_download_quote'),e=>e.code===code);
  }
  await assert.rejects(inspectConversationResults(fixture(),{...scope,result_id:id,expected_result_sha256:'0'.repeat(64)},'result_download_quote'),e=>e.code==='result_changed');
});
test('wrong surface, independent layers and unsupported source errors stay explicit',async()=>{
  for(const code of ['origin_mismatch','login_required','thread_changed','unsupported_surface','dialog_open','unsupported_media_source','preview_ambiguous','filename_changed','result_limit_exceeded']){
    const p=fixture({kind:code});await assert.rejects(inspectConversationResults(p,scope),e=>e.code===code);assert.equal(p.reads,1);
  }
});
test('protocol rejects extra private fields, malformed shapes and values',async()=>{
  for(const data of [null,{...state,prompt:'FAKE_PRIVATE'}, {...state,images:[{...card,url:'https://HOST/?TOKEN'}]},
    {...state,preview:{...preview,filename:'../../fixture.png'}},{...state,preview:{...preview,download_enabled:'true'}},
    {...state,images:[{...card,result_id:11111111111111111111111111111111}]},{...state,images:[{...card,width:20000}]},
    {...state,images:[{...card,load_state:'loaded',width:0}]},{...state,images:[{...card,load_state:'failed'}]},
    {...state,images:new Array(101).fill(card)}]){
    await assert.rejects(inspectConversationResults(fixture(data),scope),e=>e.code==='bridge_protocol'&&!e.message.includes('FAKE_PRIVATE'));
  }
});
test('result/preview changes during repeated read remain errors without input',async()=>{
  for(const changed of [{...state,preview:null},{...state,preview:{...preview,width:809}},{...state,images:[]}]){
    let n=0;await assert.rejects(inspectConversationResults({evaluate:async()=>structuredClone(++n===1?state:changed)},scope),e=>e.code==='results_changed');
  }
});
test('public bound routing and readonly facade preserve context; failures sanitized',async()=>{
  for(const context of [{},{contextId:'fixture'},{preferredContextId:'fixture'}]){
    const p=fixture(),r=(await inspectBoundConversationResults(context,scope,'results',async routing=>{assert.deepEqual(routing,context);return p;}))[0].result;
    assert.equal(r.browser_session,'site:xyq-home');assert.equal(r.browser_surface,'browser');assert.equal(r.binding_changed,false);assert.equal(p.reads,2);
  }
  await assert.rejects(inspectBoundConversationResults({},scope,'results',()=>{throw Error('FAKE_PRIVATE');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  await assert.rejects(inspectBoundConversationResults({},scope,'results',()=>({})),e=>e.code==='unsupported_backend');
  await assert.rejects(inspectBoundConversationResults({contextId:'a',preferredContextId:'b'},scope,'results',()=>assert.fail('factory')),e=>e.code==='unsupported_backend');
  await assert.rejects(inspectConversationResults({evaluate:()=>{throw Error('FAKE_PRIVATE');}},scope),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
});
test('source/registration remains DOM-only and never returns or reads full prompts/auth',()=>{
  const s=readFileSync(new URL('../examples/opencli/xyq-web/results.mjs',import.meta.url),'utf8');
  assert.match(s,/new Page\('site:xyq-home'/);assert.doesNotMatch(s,/localStorage|sessionStorage|document\.cookie|fetch\(|XMLHttpRequest|\.goto\(|\.cdp\(|\.click\(|writeFile|bindTab|setAttribute|dispatchEvent/);
  const loader=readFileSync(new URL('../examples/opencli/xyq-web/results.js',import.meta.url),'utf8');assert.match(loader,/access:'read'/);assert.match(loader,/navigateBefore:false/);
});
