import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {XyqError} from '../examples/opencli/xyq-web/core.mjs';
import {inspectAudioForm} from '../examples/opencli/xyq-web/audio.mjs';
import {audioBoundDigest,checkAudioBoundPin,boundReadRouting,inspectBoundAudioForm} from '../examples/opencli/xyq-web/audio-bound.mjs';

const scope={project_id:'1',canvas_id:'2',node_id:'3'};
const data={kind:'ready',...scope,model:'Seed Audio 1.0',sample_rate:'44.1kHz',prompt:'FAKE_PRIVATE_PROMPT',prompt_tree:null,references:[],files:[],layers:0,submit_busy:false,submit_enabled:true,association:'unique_audio_node_only'};
test('bound source pin is exact, typed and self-computed',()=>{
  checkAudioBoundPin(audioBoundDigest());
  for(const pin of ['0'.repeat(64),[audioBoundDigest()],null])assert.throws(()=>checkAudioBoundPin(pin),e=>e.code==='definition_changed');
});
test('public strict and preferred profile routing retain their original meanings',()=>{
  assert.deepEqual(boundReadRouting({contextId:'fixture-id'}),{contextId:'fixture-id'});
  assert.deepEqual(boundReadRouting({preferredContextId:'fixture-id'}),{preferredContextId:'fixture-id'});
  assert.deepEqual(boundReadRouting({}),{});
});
test('unexpected routing metadata fails before a Page is created',async()=>{
  for(const context of [null,[],{contextId:''},{contextId:'../FAKE_PRIVATE'},{contextId:1},{contextId:'a',preferredContextId:'b'}])
    await assert.rejects(inspectBoundAudioForm(context,scope,()=>assert.fail('no constructor')),e=>e.code==='unsupported_backend');
});
test('invalid scope fails before factory or browser evaluation',async()=>{
  await assert.rejects(inspectBoundAudioForm({}, {...scope,node_id:'wrong'},()=>assert.fail('no constructor')),e=>e.code==='invalid_argument');
});
test('explicit bound read returns the same DOM digest and exposes evaluations only',async()=>{
  const calls=[];
  const page={evaluate:async fn=>{calls.push(fn.name);return structuredClone(data);},goto:()=>assert.fail('navigation'),bind:()=>assert.fail('binding'),click:()=>assert.fail('input'),getCookies:()=>assert.fail('auth')};
  const output=(await inspectBoundAudioForm({contextId:'fixture'},scope,async routing=>{assert.deepEqual(routing,{contextId:'fixture'});return page;}))[0].result;
  const normal=(await inspectAudioForm({evaluate:async()=>structuredClone(data)},scope))[0].result;
  assert.equal(output.form_sha256,normal.form_sha256);
  assert.equal(output.browser_session,'site:xyq-web');assert.equal(output.browser_surface,'browser');assert.equal(output.binding_changed,false);
  assert.equal(output.paid_submitted,false);assert.equal(output.upload_started,false);
  assert(calls.length>0&&calls.every(x=>x==='readAudioFormDOM'));
  assert(!JSON.stringify(output).includes('FAKE_PRIVATE'));
});
test('wrong page and login loss are failures, with no fallback or rebinding',async()=>{
  for(const kind of ['origin_mismatch','canvas_changed','login_required']){
    let factories=0,reads=0;
    await assert.rejects(inspectBoundAudioForm({},scope,async()=>{factories++;return{evaluate:async()=>{reads++;return{kind};}};}),e=>e.code===kind);
    assert.equal(factories,1);assert.equal(reads,1);
  }
});
test('factory and routing getter diagnostics never expose secrets',async()=>{
  await assert.rejects(inspectBoundAudioForm({},scope,()=>{throw Error('FAKE_PRIVATE_TOKEN');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  const context={get contextId(){throw Error('FAKE_PRIVATE_TOKEN');}};
  await assert.rejects(inspectBoundAudioForm(context,scope,()=>assert.fail('no constructor')),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
});
test('missing documented evaluator is explicit, not a successful empty read',async()=>{
  await assert.rejects(inspectBoundAudioForm({},scope,async()=>({})),e=>e.code==='unsupported_backend');
});
test('bound reader preserves typed factory errors',async()=>{
  await assert.rejects(inspectBoundAudioForm({},scope,()=>{throw new XyqError('unsupported_backend','Fixture missing');}),e=>e.code==='unsupported_backend');
});
test('bound source uses public API without private-field mutation or actions',()=>{
  const src=readFileSync(new URL('../examples/opencli/xyq-web/audio-bound.mjs',import.meta.url),'utf8');
  assert.match(src,/new Page\('site:xyq-web'/);
  assert.doesNotMatch(src,/document\.cookie|localStorage|sessionStorage|indexedDB|getCookies|page\.goto|page\.click|fetch\(|XMLHttpRequest|\.surface\s*=|\._page|bindTab|unlink|rmSync/);
});
