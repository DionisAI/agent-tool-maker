import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {XyqError} from '../examples/opencli/xyq-web/core.mjs';
import {audioFormHash} from '../examples/opencli/xyq-web/audio.mjs';
import {inspectAudioQuote,AUDIO_QUOTE_FILES} from '../examples/opencli/xyq-web/audio-quote.mjs';
import {AUDIO_BOUND_FILES} from '../examples/opencli/xyq-web/audio-bound.mjs';
import {AUDIO_QUOTE_BOUND_FILES,audioQuoteBoundDigest,checkAudioQuoteBoundPin,inspectBoundAudioQuote} from '../examples/opencli/xyq-web/audio-quote-bound.mjs';

const scope={project_id:'1',canvas_id:'2',node_id:'3'};
function fixture(){
  const form={kind:'ready',...scope,model:'Seed Audio 1.0',sample_rate:'44.1kHz',prompt:'FAKE_PRIVATE_PROMPT',prompt_tree:null,references:[],files:[],layers:0,submit_busy:false,submit_enabled:true,association:'unique_audio_node_only'};
  const cost={kind:'ready',price_text:'1积分/3s',price_busy:false},calls=[];
  const page={evaluate:async(fn,arg)=>{calls.push(fn.name);assert.deepEqual(arg,scope);return structuredClone(fn.name==='readAudioFormDOM'?form:cost);},
    goto:()=>assert.fail('navigation'),click:()=>assert.fail('input'),bind:()=>assert.fail('binding'),cdp:()=>assert.fail('CDP'),getCookies:()=>assert.fail('auth')};
  return{form,cost,page,calls,settings:{expected_form_sha256:audioFormHash(form)}};
}
test('bound quote pins complete dependency union without changing the old closures',()=>{
  assert.deepEqual(AUDIO_QUOTE_BOUND_FILES,[...new Set([...AUDIO_QUOTE_FILES,...AUDIO_BOUND_FILES]),'audio-quote-bound.mjs','audio-quote-bound.js']);
  assert.equal(AUDIO_QUOTE_BOUND_FILES.length,10);
  checkAudioQuoteBoundPin(audioQuoteBoundDigest());
  for(const pin of [null,[],[audioQuoteBoundDigest()],'0'.repeat(64)])assert.throws(()=>checkAudioQuoteBoundPin(pin),e=>e.code==='definition_changed');
});
test('invalid exact scope or typed settings stop before the factory',async()=>{
  const x=fixture();
  await assert.rejects(inspectBoundAudioQuote({}, {...scope,node_id:'wrong'},x.settings,()=>assert.fail('factory')),e=>e.code==='invalid_argument');
  for(const raw of [null,{},[],{expected_form_sha256:'a'.repeat(64),selector:'body'}])
    await assert.rejects(inspectBoundAudioQuote({},scope,raw,()=>assert.fail('factory')),e=>e.code==='invalid_argument');
});
test('strict and preferred public routing stay distinct; only evaluators are exposed',async()=>{
  for(const context of [{},{contextId:'fixture-id'},{preferredContextId:'fixture-id'}]){
    const x=fixture(),result=(await inspectBoundAudioQuote(context,scope,x.settings,async routing=>{assert.deepEqual(routing,context);return x.page;}))[0].result;
    assert.equal(result.browser_session,'site:xyq-web');assert.equal(result.browser_surface,'browser');assert.equal(result.binding_changed,false);
    assert.equal(result.status,'quoted_rate');assert.equal(result.total_credits,null);assert.equal(result.spend_ceiling_verified,false);
    assert.equal(result.paid_submitted,false);assert.equal(result.upload_started,false);assert.equal(result.generation_submitted,false);
    assert.deepEqual(x.calls,['readAudioFormDOM','readAudioQuoteDOM','readAudioFormDOM','readAudioQuoteDOM','readAudioFormDOM']);
    const normal=(await inspectAudioQuote(x.page,scope,x.settings))[0].result;
    assert.equal(result.quote_sha256,normal.quote_sha256);assert(!JSON.stringify(result).includes('FAKE_PRIVATE'));
  }
});
test('invalid profile context stops without creating or rebinding a page',async()=>{
  const x=fixture();
  for(const context of [null,[],{contextId:''},{contextId:'../TOKEN'},{contextId:1},{contextId:'a',preferredContextId:'b'}])
    await assert.rejects(inspectBoundAudioQuote(context,scope,x.settings,()=>assert.fail('factory')),e=>e.code==='unsupported_backend');
});
test('wrong bound page, login loss and bridge failures remain failures without fallback',async()=>{
  const x=fixture();
  for(const kind of ['origin_mismatch','canvas_changed','node_changed','login_required']){
    let factories=0,reads=0;
    await assert.rejects(inspectBoundAudioQuote({},scope,x.settings,async()=>{factories++;return{evaluate:async()=>{reads++;return{kind};}};}),e=>e.code===kind);
    assert.equal(factories,1);assert.equal(reads,1);
  }
  await assert.rejects(inspectBoundAudioQuote({},scope,x.settings,()=>{throw Error('FAKE_PRIVATE_TOKEN');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  await assert.rejects(inspectBoundAudioQuote({get contextId(){throw Error('FAKE_PRIVATE_TOKEN');}},scope,x.settings,()=>assert.fail('factory')),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  await assert.rejects(inspectBoundAudioQuote({},scope,x.settings,async()=>({})),e=>e.code==='unsupported_backend');
  await assert.rejects(inspectBoundAudioQuote({},scope,x.settings,()=>{throw new XyqError('unsupported_backend','Fixture');}),e=>e.code==='unsupported_backend');
});
test('draft and price races keep original quote errors',async()=>{
  for(const code of ['draft_changed','quote_changed','dialog_open','reference_state_unknown']){
    const x=fixture();let n=0;
    if(code==='dialog_open')x.form.layers=1;
    if(code==='reference_state_unknown')x.form.files=[{kind:'audio',files:null}];
    const settings={expected_form_sha256:audioFormHash(x.form)};
    x.page.evaluate=async fn=>{n++;if(code==='draft_changed'&&n===3)x.form.prompt+=' changed';if(code==='quote_changed'&&n===4)x.cost.price_text='2积分/3s';return structuredClone(fn.name==='readAudioFormDOM'?x.form:x.cost);};
    await assert.rejects(inspectBoundAudioQuote({},scope,settings,async()=>x.page),e=>e.code===code);
  }
});
test('read-only rate pending/unknown never masquerades as free generation',async()=>{
  for(const [cost,status] of [[{price_busy:true},'quote_pending'],[{price_text:null},'quote_unavailable'],[{price_text:'FAKE_PRIVATE_COST'},'quote_unavailable']]){
    const x=fixture();Object.assign(x.cost,cost);
    const result=(await inspectBoundAudioQuote({},scope,x.settings,async()=>x.page))[0].result;
    assert.equal(result.status,status);assert.equal(result.reported_rate,null);assert.equal(result.total_credits,null);
    assert(!JSON.stringify(result).includes('FAKE_PRIVATE'));
  }
});
test('explicit registration is read only with a required pin and no actions',()=>{
  const source=readFileSync(new URL('../examples/opencli/xyq-web/audio-quote-bound.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(source,/document\.cookie|localStorage|sessionStorage|fetch\(|XMLHttpRequest|page\.(goto|click|cdp)|writeFile|bindTab|\._page/);
  const cli=readFileSync(new URL('../examples/opencli/xyq-web/audio-quote-bound.js',import.meta.url),'utf8');
  assert.match(cli,/name:'audio-quote-bound'/);assert.match(cli,/access:'read'/);assert.match(cli,/navigateBefore:false/);assert.match(cli,/name:'pin',type:'string',required:true/);
});
