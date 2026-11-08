import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {bundleDigest,checkPin,pollDOM,inspect} from '../examples/opencli/xyq-web/core.mjs';

const form={mode:'视频生成',preferences:'模型选择和偏好设置：SD 2.5、720P',preferences_open:false,
  prompt_empty:true,canvas:{checked:false,disabled:false},quote_status:'not_final'};
const ready={kind:'ready',logged_in:true,credits:100,agent:'创作',agents:[],navigation:[],shortcuts:[],form};
test('source pin is mandatory and binds both adapter files',()=>{
  checkPin(bundleDigest());
  for(const value of ['',undefined,'0'.repeat(64),'x'.repeat(64)])assert.throws(()=>checkPin(value),e=>e.code==='definition_changed');
});
for(const kind of ['login_required','origin_mismatch','layout_changed','unsupported_surface'])test('typed DOM failure: '+kind,async()=>{
  await assert.rejects(pollDOM({evaluate:async()=>({kind})},()=>{}),e=>e.code===kind);
});
test('pending is a bounded failure, not empty success',async()=>{
  await assert.rejects(pollDOM({evaluate:async()=>({kind:'pending'})},()=>{},{timeout:0}),e=>e.code==='page_not_ready');
});
test('invalid bridge envelope and rejected evaluation remain distinct',async()=>{
  await assert.rejects(pollDOM({evaluate:async()=>({})},()=>{}),e=>e.code==='bridge_protocol');
  await assert.rejects(pollDOM({evaluate:async()=>{throw new Error('FAKE_CREDENTIAL_DO_NOT_LEAK');}},()=>{}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_CREDENTIAL'));
  assert.equal((await pollDOM({evaluate:async()=>({session:'fixture',data:ready})},()=>{})).credits,100);
});
for(const op of ['account','surface','form-inspect'])test('inspection '+op+' performs evaluations only',async()=>{
  const calls=[];
  const page={evaluate:async fn=>{calls.push(fn.name);return ready;},goto:()=>assert.fail('navigation'),click:()=>assert.fail('click')};
  const result=(await inspect(page,op))[0].result;
  assert.equal(result.paid_submitted,false);assert.equal(result.secrets_returned,false);assert.deepEqual(calls,['readHomeDOM']);
  if(op==='surface')assert.equal(result.full_web_coverage,false);
});
test('unknown operation has zero browser calls',async()=>{
  await assert.rejects(inspect({evaluate:()=>assert.fail('must not evaluate')},'generate'),e=>e.code==='invalid_argument');
});
test('closed options are explicit and never opened by the tool',async()=>{
  await assert.rejects(inspect({evaluate:async()=>ready},'form-options'),e=>e.code==='options_closed');
});
test('workspace without reviewed form is not success',async()=>{
  await assert.rejects(inspect({evaluate:async()=>({...ready,form:null})},'form-inspect'),e=>e.code==='unsupported_surface');
});
test('already-open options are read and left open',async()=>{
  const responses=[{...ready,form:{...form,preferences_open:true}},{kind:'ready',models:[{label:'fixture',checked:true}],all_options:false},{...ready,form:{...form,preferences_open:true}}];
  const page={evaluate:async()=>responses.shift(),click:()=>assert.fail('popup mutation')};
  assert.equal((await inspect(page,'form-options'))[0].result.options.all_options,false);assert.equal(responses.length,0);
});
test('form drift while reading options is explicit',async()=>{
  const responses=[{...ready,form:{...form,preferences_open:true}},{kind:'ready',models:[]},{...ready,agent:'营销',form:{...form,preferences_open:true}}];
  await assert.rejects(inspect({evaluate:async()=>responses.shift()},'form-options'),e=>e.code==='draft_changed');
});
test('source never uses browser authentication or unreviewed HTTP/JS hooks',()=>{
  const s=readFileSync(new URL('../examples/opencli/xyq-web/core.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(s,/document\.cookie|localStorage|sessionStorage|indexedDB|getCookies|page\.goto|page\.click|fetch\(|XMLHttpRequest|\.evaluate\(['"`]/);
});
