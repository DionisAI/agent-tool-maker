import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {draftHash,FORM_FILES} from '../examples/opencli/xyq-web/form.mjs';
import {AUDIO_BOUND_FILES} from '../examples/opencli/xyq-web/audio-bound.mjs';
import {HOME_QUOTE_FILES,homeQuoteDigest,checkHomeQuotePin,parseHomeQuoteSettings,parseHomeCreditEstimate,inspectHomeQuote,inspectBoundHomeQuote} from '../examples/opencli/xyq-web/home-quote.mjs';
function fixture(){
  const home={kind:'ready',agent:'创作',form:{mode:'视频生成',preferences:'OBSERVED_VIDEO/30s',preferences_open:false,canvas:{checked:false,disabled:false}}};
  const draft={kind:'ready',prompt:'FAKE_PRIVATE_PROMPT',prompt_tree:null,media:[],files:[],attachments:null,layers:0};
  const price={kind:'ready',price:{label:'积分消耗 600',amount:'600',original_amount:'780',busy:false},submit_enabled:true,submit_busy:false};
  const calls=[],page={evaluate:async fn=>{calls.push(fn.name);return structuredClone(fn.name==='readHomeDOM'?home:fn.name==='readDraftDOM'?draft:price);},click:()=>assert.fail('input'),cdp:()=>assert.fail('CDP'),goto:()=>assert.fail('navigation')};
  return{home,draft,price,page,calls,settings:{expected_draft_sha256:draftHash({home,draft})}};
}
test('home quote has its own complete pin and old source closures stay distinct',()=>{
  assert.deepEqual(HOME_QUOTE_FILES,[...new Set([...FORM_FILES,...AUDIO_BOUND_FILES]),'home-quote.mjs','home-quote.js']);
  assert.equal(HOME_QUOTE_FILES.length,10);checkHomeQuotePin(homeQuoteDigest());
  for(const v of [null,[],[homeQuoteDigest()],'0'.repeat(64)])assert.throws(()=>checkHomeQuotePin(v),e=>e.code==='definition_changed');
});
test('typed exact draft settings stop before backend construction',async()=>{
  for(const raw of [null,{},[],{expected_draft_sha256:['a'.repeat(64)]},{expected_draft_sha256:'a'.repeat(64),selector:'body'}])
    await assert.rejects(inspectBoundHomeQuote({},raw,()=>assert.fail('factory')),e=>e.code==='invalid_argument');
  assert.deepEqual(parseHomeQuoteSettings(JSON.stringify(fixture().settings)),fixture().settings);
});
test('observed amount, discounted original and per-second rate stay distinct',()=>{
  const p={label:'积分消耗 600',amount:'600',original_amount:'780',busy:false};
  assert.deepEqual(parseHomeCreditEstimate(p),{credit_amount:600,per_seconds:null,basis:'displayed_amount',original_credit_amount:780,estimated:true});
  assert.equal(parseHomeCreditEstimate({...p,label:'积分消耗 0.33',amount:'0.33/秒',original_amount:null}).per_seconds,1);
  assert.equal(parseHomeCreditEstimate({...p,label:'积分消耗 0',amount:'0',original_amount:null}).credit_amount,0);
  for(const p of [null,{label:'积分消耗 6',amount:'7',original_amount:null},{label:'积分消耗 6',amount:'6',original_amount:'3'},
    {label:'积分消耗 0.33',amount:'0.33/秒',original_amount:'1'},{label:'积分消耗 1000001',amount:'1000001',original_amount:null},
    {label:'FAKE_PRIVATE_PRICE',amount:'secret',original_amount:null}])assert.equal(parseHomeCreditEstimate(p),null);
});
test('stable interleaved reads bind full draft and never prove spending ceiling',async()=>{
  const x=fixture(),r=(await inspectHomeQuote(x.page,x.settings))[0].result;
  assert.equal(r.status,'quoted_estimate');assert.equal(r.reported_estimate.credit_amount,600);assert.equal(r.reported_estimate.original_credit_amount,780);
  assert.equal(x.calls.filter(x=>x==='readHomeQuoteDOM').length,3);assert.equal(x.calls.filter(x=>x==='readDraftDOM').length,3);
  for(const k of ['total_credits','output_duration_seconds'])assert.equal(r[k],null);
  for(const k of ['spend_ceiling_verified','final_billing_verified','charge_scope_verified','paid_submitted','generation_submitted','upload_started'])assert.equal(r[k],false);
  assert(!JSON.stringify(r).includes('FAKE_PRIVATE'));
});
test('strict or preferred routing is inherited without exposing writable backend methods',async()=>{
  for(const context of [{},{contextId:'test'},{preferredContextId:'test'}]){
    const x=fixture(),r=(await inspectBoundHomeQuote(context,x.settings,async routing=>{assert.deepEqual(routing,context);return x.page;}))[0].result;
    assert.equal(r.browser_session,'site:xyq-home');assert.equal(r.browser_surface,'browser');assert.equal(r.binding_changed,false);
  }
});
test('invalid routing and bridge exceptions remain sanitized errors',async()=>{
  const x=fixture();
  for(const c of [null,[],{contextId:'../TOKEN'},{contextId:1},{contextId:'a',preferredContextId:'b'}])
    await assert.rejects(inspectBoundHomeQuote(c,x.settings,()=>assert.fail('factory')),e=>e.code==='unsupported_backend');
  await assert.rejects(inspectBoundHomeQuote({},x.settings,()=>{throw Error('FAKE_PRIVATE_TOKEN');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  await assert.rejects(inspectBoundHomeQuote({},x.settings,()=>({})),e=>e.code==='unsupported_backend');
  await assert.rejects(inspectBoundHomeQuote({},x.settings,()=>({evaluate:()=>{throw Error('FAKE_PRIVATE_TOKEN');}})),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
});
test('wrong page/login/menu failures do not trigger alternate routing or input',async()=>{
  for(const code of ['origin_mismatch','login_required','unsupported_surface','dialog_open','quote_layout_changed']){
    const x=fixture();let reads=0,factories=0;
    await assert.rejects(inspectBoundHomeQuote({},x.settings,()=>{factories++;return{evaluate:()=>{reads++;return{kind:code};}};}),e=>e.code===code);
    assert.equal(reads,1);assert.equal(factories,1);
  }
});
test('draft, price and submit-state races stop rather than return stale estimates',async()=>{
  for(const changed of ['draft','model','price','submit']){
    const x=fixture();let n=0;
    x.page.evaluate=async fn=>{if(fn.name==='readHomeQuoteDOM'&&++n===2){
      if(changed==='draft')x.draft.prompt+=' drift';if(changed==='model')x.home.form.preferences='other';
      if(changed==='price'){x.price.price.amount='601';x.price.price.label='积分消耗 601';}
      if(changed==='submit')x.price.submit_enabled=false;
    }return structuredClone(fn.name==='readHomeDOM'?x.home:fn.name==='readDraftDOM'?x.draft:x.price);};
    await assert.rejects(inspectHomeQuote(x.page,x.settings),e=>e.code===(['draft','model'].includes(changed)?'draft_changed':'quote_changed'));
  }
});
test('known missing, busy and unsupported estimates stay distinct from free generation',async()=>{
  for(const [changes,status,reason] of [[{price:null},'quote_unavailable','price_missing'],[{submit_busy:true},'quote_pending','price_or_submission_busy'],
    [{price:{label:'积分消耗 1',amount:'FAKE_PRIVATE_PRICE',original_amount:null,busy:false}},'quote_unavailable','unsupported_price_format']]){
    const x=fixture();Object.assign(x.price,changes);const r=(await inspectHomeQuote(x.page,x.settings))[0].result;
    assert.equal(r.status,status);assert.equal(r.reason,reason);assert.equal(r.reported_estimate,null);assert.equal(r.total_credits,null);assert(!JSON.stringify(r).includes('FAKE_PRIVATE'));
  }
});
test('reference uncertainty and changed expected SHA stop, even when a numeric price exists',async()=>{
  const x=fixture();x.draft.files=[{files:null}];x.settings.expected_draft_sha256=draftHash(x);
  await assert.rejects(inspectHomeQuote(x.page,x.settings),e=>e.code==='reference_state_unknown');
  const y=fixture();y.settings.expected_draft_sha256='0'.repeat(64);await assert.rejects(inspectHomeQuote(y.page,y.settings),e=>e.code==='draft_changed');
});
test('rate quote retains decimal display precision without duration or total inference',async()=>{
  const x=fixture();x.price.price={label:'积分消耗 0.33',amount:'0.33/秒',original_amount:null,busy:false};
  const r=(await inspectHomeQuote(x.page,x.settings))[0].result;assert.equal(r.status,'quoted_rate');assert.equal(r.quote_status,'unit_rate_only');
  assert.equal(r.reported_estimate.credit_amount,0.33);assert.equal(r.total_credits,null);assert.equal(r.output_duration_seconds,null);
});
test('registration and transport expose no auth, navigation, input or private fields',()=>{
  const source=readFileSync(new URL('../examples/opencli/xyq-web/home-quote.mjs',import.meta.url),'utf8');
  assert.match(source,/new Page\('site:xyq-home'/);assert.doesNotMatch(source,/localStorage|sessionStorage|document\.cookie|fetch\(|XMLHttpRequest|\.goto\(|\.cdp\(|writeFile|bindTab|setAttribute|dispatchEvent|\._page/);
  const loader=readFileSync(new URL('../examples/opencli/xyq-web/home-quote.js',import.meta.url),'utf8');
  assert.match(loader,/access:'read'/);assert.match(loader,/navigateBefore:false/);assert.match(loader,/name:'pin',type:'string',required:true/);
});
