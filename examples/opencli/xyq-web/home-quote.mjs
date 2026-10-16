// Strategy UI_SELECTOR / visible-ui: draft-bound displayed home credit estimate.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM,readHomeDOM} from './core.mjs';
import {FORM_FILES,readDraftDOM,draftHash} from './form.mjs';
import {AUDIO_BOUND_FILES,boundReadRouting} from './audio-bound.mjs';
export const HOME_QUOTE_FILES=[...new Set([...FORM_FILES,...AUDIO_BOUND_FILES]),'home-quote.mjs','home-quote.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
export function homeQuoteDigest(){const h=createHash('sha256');for(const n of HOME_QUOTE_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkHomeQuotePin(pin){if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==homeQuoteDigest())fail('definition_changed','Review the home quote source closure.');}
export function parseHomeQuoteSettings(raw){let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use typed draft-bound quote JSON.');}
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).length!==1||typeof v.expected_draft_sha256!=='string'||!/^[a-f0-9]{64}$/.test(v.expected_draft_sha256))fail('invalid_argument','Quote requires only the exact inspected draft SHA.');return v;}

// Self-contained DOM-only reader. Discounted amount and originalAmount are distinct.
export function readHomeQuoteDOM(){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible);
  if(layers.length)return{kind:'dialog_open'};
  const roots=document.querySelectorAll('#title-section-prompt-container');
  if(roots.length!==1||!visible(roots[0]))return{kind:'unsupported_surface'};
  const root=roots[0],submit=Array.from(root.querySelectorAll('button[aria-label="开始生成"],button[aria-label="生成"]')).filter(visible);
  if(submit.length!==1||submit[0].getAttribute('data-slot')!=='home-input-composer-submit-button')return{kind:'quote_layout_changed'};
  const busy=submit[0].getAttribute('aria-busy');if(busy!==null&&!['true','false'].includes(busy))return{kind:'quote_layout_changed'};
  const state={submit_enabled:!submit[0].disabled&&submit[0].getAttribute('aria-disabled')!=='true',submit_busy:busy==='true'};
  const prices=Array.from(root.querySelectorAll('[data-testid="home-direct-generation-credit-estimate"]')).filter(visible);
  const labelled=Array.from(root.querySelectorAll('[aria-label^="积分消耗"]')).filter(visible);
  if(!prices.length&&!labelled.length)return{kind:'ready',price:null,...state};
  if(prices.length!==1||labelled.length!==1||prices[0]!==labelled[0])return{kind:'quote_layout_changed'};
  const price=prices[0],amounts=Array.from(price.querySelectorAll('[data-slot="amount"]')).filter(visible),originals=Array.from(price.querySelectorAll('[data-slot="originalAmount"]')).filter(visible);
  const priceBusy=price.getAttribute('aria-busy');
  if(price.getAttribute('data-slot')!=='credit-amount'||amounts.length!==1||originals.length>1||priceBusy!==null&&!['true','false'].includes(priceBusy))return{kind:'quote_layout_changed'};
  if(originals.length&&(!originals[0].classList.contains('line-through')||!getComputedStyle(originals[0]).textDecorationLine.includes('line-through')))return{kind:'quote_layout_changed'};
  const text=e=>(e.innerText||'').replace(/\s+/g,' ').trim();
  const value={label:price.getAttribute('aria-label'),amount:text(amounts[0]),original_amount:originals.length?text(originals[0]):null,busy:priceBusy==='true'};
  if([value.label,value.amount,value.original_amount].some(s=>s!==null&&s.length>128))return{kind:'quote_layout_changed'};
  return{kind:'ready',price:value,...state};
}
export function parseHomeCreditEstimate(price){
  if(!price)return null;
  const pattern=/^(\d{1,7}(?:\.\d{1,6})?)(?:\s*\/\s*(秒))?$/;
  const amount=price.amount?.match(pattern),label=price.label?.match(/^积分消耗 (\d{1,7}(?:\.\d{1,6})?)$/);
  if(!amount||!label||amount[1]!==label[1])return null;
  const credit=Number(amount[1]);if(!Number.isFinite(credit)||credit<0||credit>1000000)return null;
  let original=null;
  if(price.original_amount!==null){
    const m=price.original_amount?.match(/^(\d{1,7}(?:\.\d{1,6})?)$/);
    if(!m||amount[2])return null;original=Number(m[1]);
    if(!Number.isFinite(original)||original<credit||original>1000000)return null;
  }
  return{credit_amount:credit,per_seconds:amount[2]?1:null,basis:amount[2]?'displayed_unit_rate':'displayed_amount',original_credit_amount:original,estimated:true};
}
export async function inspectHomeQuote(page,raw){
  const settings=parseHomeQuoteSettings(raw);
  const price=()=>pollDOM(page,readHomeQuoteDOM);
  const snapshot=async()=>{
    const home=await pollDOM(page,readHomeDOM),draft=await pollDOM(page,readDraftDOM),after=await pollDOM(page,readHomeDOM);
    if(home.agent!=='创作'||!home.form||!['图片生成','视频生成','音频生成'].includes(home.form.mode))fail('unsupported_surface','Quote covers the creative media composer only.');
    if(after.agent!==home.agent||!after.form||after.form.mode!==home.form.mode||after.form.preferences!==home.form.preferences||JSON.stringify(after.form.canvas)!==JSON.stringify(home.form.canvas))fail('draft_changed','Composer changed during quote snapshot.');
    if(draft.layers||home.form.preferences_open||after.form.preferences_open)fail('dialog_open','Existing menus stay intact.');
    if(draft.files.some(f=>f.files===null))fail('reference_state_unknown','Unknown file state is not a quote-ready draft.');
    if(draftHash({home,draft})!==settings.expected_draft_sha256)fail('draft_changed','Quote belongs to a different draft.');
    return{home,draft};
  };
  const a=await price();await snapshot();const b=await price();await snapshot();const c=await price();const last=await snapshot();
  if(JSON.stringify(a)!==JSON.stringify(b)||JSON.stringify(b)!==JSON.stringify(c))fail('quote_changed','Displayed price or submit state changed during quote reads.');
  const pending=!!c.price?.busy||c.submit_busy,estimate=pending?null:parseHomeCreditEstimate(c.price);
  const rate=estimate!==null&&estimate.per_seconds!==null;
  return[{result:{status:pending?'quote_pending':estimate?rate?'quoted_rate':'quoted_estimate':'quote_unavailable',
    mode:last.home.form.mode,preferences:last.home.form.preferences,draft_sha256:settings.expected_draft_sha256,
    quote_sha256:sha(JSON.stringify(['xyq-home-displayed-credit-v1',settings.expected_draft_sha256,c])),
    quote_status:pending?'pending':estimate?rate?'unit_rate_only':'displayed_estimate_only':'unknown',
    reason:pending?'price_or_submission_busy':estimate?null:c.price===null?'price_missing':'unsupported_price_format',
    reported_estimate:estimate,total_credits:null,output_duration_seconds:null,
    spend_ceiling_verified:false,charge_scope_verified:false,final_billing_verified:false,
    submit_enabled:c.submit_enabled,price_sha256:c.price===null?null:sha(JSON.stringify(c.price)),
    source:'visible_dom',observed_at:new Date().toISOString(),secrets_returned:false,paid_submitted:false,
    generation_submitted:false,upload_started:false}}];
}
export async function createHomeQuotePage(routing){const {Page}=await import('@jackwener/opencli/browser/page');const page=new Page('site:xyq-home',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);return Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)});}
export async function inspectBoundHomeQuote(context,raw,createPage=createHomeQuotePage){
  const settings=parseHomeQuoteSettings(raw);let page;
  try{page=await createPage(boundReadRouting(context));if(!page||typeof page.evaluate!=='function')fail('unsupported_backend','Home quote requires the public evaluator.');}
  catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','Home quote Page preparation failed.');}
  const output=await inspectHomeQuote(Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)}),settings);
  return output.map(({result})=>({result:{...result,browser_session:'site:xyq-home',browser_surface:'browser',binding_changed:false}}));
}
