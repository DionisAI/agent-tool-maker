import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,existsSync,statSync,readdirSync,writeFileSync,symlinkSync,linkSync,realpathSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {draftHash} from '../examples/opencli/xyq-web/form.mjs';
import {inspectHomeQuote} from '../examples/opencli/xyq-web/home-quote.mjs';
import {generationDigest,checkGenerationPin,parseGenerationSettings,generateHome,generateBoundHome,generationStatus} from '../examples/opencli/xyq-web/generation.mjs';
// Canonical temp root: macOS tmpdir() sits below the /var symlink, which path guards reject.
const TMP=realpathSync(tmpdir());
async function fixture(){
  const workspace=mkdtempSync(join(TMP,'atm-xyq-generation-')),home={kind:'ready',agent:'创作',form:{mode:'图片生成',preferences:'TEST_MODEL',preferences_open:false,canvas:{checked:true,disabled:false}}};
  const draft={kind:'ready',prompt:'TEST_PRIVATE_PROMPT',prompt_tree:null,media:[],files:[],attachments:null,layers:0};
  const price={kind:'ready',price:{label:'积分消耗 6',amount:'6',original_amount:null,busy:false},submit_enabled:true,submit_busy:false},calls=[];
  const page={evaluate:async fn=>{calls.push(fn.name);if(fn.name==='readHomeDOM')return structuredClone(home);if(fn.name==='readDraftDOM')return structuredClone(draft);if(fn.name==='readHomeQuoteDOM')return structuredClone(price);
    if(fn.name==='readGenerationInputDOM')return{kind:'ready',x:7,y:9};if(fn.name==='readGenerationAcceptedDOM')return{kind:'ready',project_id:'123',canvas_id:'456',acceptance:'project_route_and_canvas_observed_not_task_completion'};assert.fail(fn.name);},
    nativeClick:async(x,y)=>{calls.push('nativeClick');assert.deepEqual([x,y],[7,9]);const dir=join(workspace,'.atm','xyq-generation');assert(existsSync(join(dir,'active.lock')));const file=readdirSync(dir).find(n=>n.endsWith('.json'));assert.equal(JSON.parse(readFileSync(join(dir,file))).status,'dispatch_claimed');assert.equal(statSync(join(dir,file)).mode&0o777,0o600);},
    goto:()=>assert.fail('navigation'),fillText:()=>assert.fail('draft write'),cdp:()=>assert.fail('CDP')};
  const settings={expected_draft_sha256:draftHash({home,draft}),quote_sha256:(await inspectHomeQuote(page,{expected_draft_sha256:draftHash({home,draft})}))[0].result.quote_sha256,max_credits:6,human_confirmed:true,estimated_cost_confirmed:true,request_key:'once'};calls.length=0;
  return{workspace,home,draft,price,page,calls,settings};
}
test('generation pin and exact confirmation schema',async()=>{checkGenerationPin(generationDigest());assert.throws(()=>checkGenerationPin('0'.repeat(64)),e=>e.code==='definition_changed');const x=await fixture();
  for(const bad of [{...x.settings,selector:'body'},{...x.settings,max_credits:NaN},{...x.settings,request_key:'../x'},null,[]])assert.throws(()=>parseGenerationSettings(bad),e=>e.code==='invalid_argument');
  for(const key of ['human_confirmed','estimated_cost_confirmed'])assert.throws(()=>parseGenerationSettings({...x.settings,[key]:false}),e=>e.code==='confirmation_required');});
test('one native submit after durable claim; project receipt is not a provider task ID or completion',async()=>{
  const x=await fixture(),r=(await generateHome(x.page,x.settings,x.workspace))[0].result;
  assert.equal(r.status,'submitted');assert.equal(r.project_id,'123');assert.equal(r.provider_task_id,null);assert.equal(r.task_completed,false);assert.equal(r.spend_ceiling_verified,false);assert.equal(r.final_billing_verified,false);assert.equal(r.displayed_estimated_credits,6);assert.equal(x.calls.filter(c=>c==='nativeClick').length,1);assert(!JSON.stringify(r).includes('TEST_PRIVATE'));
  const count=x.calls.length,reused=(await generateHome({},x.settings,x.workspace))[0].result;assert.equal(reused.reused,true);assert.equal(x.calls.length,count);
  const status=generationStatus(x.workspace,'once')[0].result;assert.equal(status.provider_checked,false);assert.equal(status.task_completed,false);assert.equal(status.query_scope,'original_local_submission_receipt');
});
test('post-click hardlinked receipt is preserved before truncation; uncertain retention stays locked',async()=>{
  const x=await fixture(),dir=join(x.workspace,'.atm','xyq-generation');let before,linked;
  x.page.nativeClick=async()=>{
    x.calls.push('nativeClick');const p=join(dir,readdirSync(dir).find(n=>n.endsWith('.json')));
    before=readFileSync(p);linked=join(x.workspace,'protected-receipt');linkSync(p,linked);
  };
  let failure;try{await generateHome(x.page,x.settings,x.workspace);}catch(e){failure=e;}
  assert.deepEqual(readFileSync(linked),before);assert(existsSync(join(dir,'active.lock')));
  assert.equal(x.calls.filter(c=>c==='nativeClick').length,1);
  assert.equal(failure?.code,'submission_unknown');assert.equal(failure.phase,'receipt_retention');
  assert.equal(failure.retention_failure_code,'unsafe_path');assert.equal(failure.outcome_uncertain,true);
});
test('draft/quote/budget/missing/rate-only changes stop before any submit',async()=>{
  for(const kind of ['draft','quote','budget','missing','rate','disabled']){const x=await fixture();
    if(kind==='draft')x.draft.prompt+=' drift';if(kind==='quote')x.settings.quote_sha256='0'.repeat(64);if(kind==='budget')x.settings.max_credits=5;
    if(kind==='missing')x.price.price=null;if(kind==='rate')x.price.price={label:'积分消耗 0.33',amount:'0.33/秒',original_amount:null,busy:false};if(kind==='disabled')x.price.submit_enabled=false;
    await assert.rejects(generateHome(x.page,x.settings,x.workspace));assert(!x.calls.includes('nativeClick'));assert(!existsSync(join(x.workspace,'.atm')));}
});
test('unacknowledged native submit retains unknown receipt/lock and neither same nor new key replays',async()=>{
  const x=await fixture();x.page.nativeClick=async()=>{x.calls.push('nativeClick');throw Error('TEST_PRIVATE_TOKEN');};
  await assert.rejects(generateHome(x.page,x.settings,x.workspace),e=>e.code==='submission_unknown'&&!e.message.includes('TEST_PRIVATE'));
  const dir=join(x.workspace,'.atm','xyq-generation'),lock=readFileSync(join(dir,'active.lock')),count=x.calls.filter(c=>c==='nativeClick').length;
  await assert.rejects(generateHome(x.page,x.settings,x.workspace),e=>e.code==='submission_unknown');await assert.rejects(generateHome(x.page,{...x.settings,request_key:'other'},x.workspace),e=>e.code==='workspace_busy');
  assert.equal(x.calls.filter(c=>c==='nativeClick').length,count);assert.deepEqual(readFileSync(join(dir,'active.lock')),lock);assert.equal(generationStatus(x.workspace,'once')[0].result.status,'submission_unknown');
  const receipt=readFileSync(join(dir,readdirSync(dir).find(n=>n.endsWith('.json'))),'utf8');assert(!receipt.includes('TEST_PRIVATE'));assert.equal(JSON.parse(receipt).failure_code,'bridge_failed');
});
test('post-claim price change is unknown with zero input; old receipt is preserved',async()=>{
  const x=await fixture(),original=x.page.evaluate;let reads=0;x.page.evaluate=async fn=>{if(fn.name==='readHomeQuoteDOM'&&++reads===7){x.price.price.amount='7';x.price.price.label='积分消耗 7';}return original(fn);};
  await assert.rejects(generateHome(x.page,x.settings,x.workspace),e=>e.code==='submission_unknown');assert(!x.calls.includes('nativeClick'));assert(existsSync(join(x.workspace,'.atm','xyq-generation','active.lock')));
});
test('different inputs, corrupt/linked receipts and unknown paths fail explicitly',async()=>{
  const x=await fixture();await generateHome(x.page,x.settings,x.workspace);await assert.rejects(generateHome({}, {...x.settings,max_credits:7},x.workspace),e=>e.code==='request_conflict');
  const dir=join(x.workspace,'.atm','xyq-generation'),file=join(dir,readdirSync(dir).find(n=>n.endsWith('.json')));writeFileSync(file,'bad-json');assert.throws(()=>generationStatus(x.workspace,'once'),e=>e.code==='receipt_invalid');
  const y=await fixture();symlinkSync(dir,join(y.workspace,'.atm'));assert.throws(()=>generationStatus(y.workspace,'once'),e=>e.code==='unsafe_path');assert.throws(()=>generationStatus('/', 'once'),e=>e.code==='unsafe_path');
});
test('public bound generation preserves profile routing and exposes no raw errors',async()=>{
  const x=await fixture();const r=await generateBoundHome({contextId:'fixture'},x.settings,x.workspace,async routing=>{assert.deepEqual(routing,{contextId:'fixture'});return x.page;});assert.equal(r[0].result.status,'submitted');
  await assert.rejects(generateBoundHome({},x.settings,x.workspace,()=>{throw Error('TEST_PRIVATE_TOKEN');}),e=>e.code==='bridge_failed'&&!e.message.includes('TEST_PRIVATE'));
});
