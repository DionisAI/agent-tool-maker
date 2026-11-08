// Read-only, draft-bound displayed audio credit rate. Never a total-cost ceiling.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM} from './core.mjs';
import {AUDIO_FILES,audioScope,readAudioFormDOM,audioFormHash} from './audio.mjs';
export const AUDIO_QUOTE_FILES=[...AUDIO_FILES,'audio-quote.mjs','audio-quote.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
export function audioQuoteDigest(){const h=createHash('sha256');for(const name of AUDIO_QUOTE_FILES)h.update(name+'\0').update(readFileSync(new URL(name,import.meta.url))).update('\0');return h.digest('hex');}
export function checkAudioQuotePin(pin){if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==audioQuoteDigest())fail('definition_changed','Review the audio quote adapter bundle.');}
export function parseAudioQuoteSettings(raw){let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use typed quote JSON.');}
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).length!==1||!Object.hasOwn(v,'expected_form_sha256')||typeof v.expected_form_sha256!=='string'||!/^[a-f0-9]{64}$/.test(v.expected_form_sha256))fail('invalid_argument','Quote must bind the exact observed audio form digest.');return v;}

// Self-contained for serialization; no navigation, input, storage or auth access.
export function readAudioQuoteDOM(scope){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/project')return{kind:'unsupported_surface'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==scope.project_id||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const roots=Array.from(document.querySelectorAll('[data-testid="rf__wrapper"][role="application"]')).filter(visible);
  if(!roots.length)return{kind:'pending'};if(roots.length!==1)return{kind:'layout_changed'};
  const nodes=Array.from(roots[0].querySelectorAll('.react-flow__node-biz\\/audio'));
  if(nodes.length!==1)return{kind:'audio_node_ambiguous'};
  if(nodes[0].getAttribute('data-id')!==scope.node_id)return{kind:'node_changed'};
  const panels=Array.from(roots[0].querySelectorAll('[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"]')).filter(visible);
  if(!panels.length)return{kind:'audio_form_closed'};if(panels.length!==1)return{kind:'layout_changed'};
  const prices=Array.from(panels[0].querySelectorAll('span[title="预计消耗积分"]')).filter(visible);
  if(prices.length>1)return{kind:'quote_layout_changed'};
  if(!prices.length)return{kind:'ready',price_text:null,price_busy:false};
  const text=(prices[0].innerText||'').replace(/\s+/g,' ').trim();
  const busy=prices[0].getAttribute('aria-busy');
  if(text.length>128||!['true','false'].includes(busy))return{kind:'quote_layout_changed'};
  return{kind:'ready',price_text:text,price_busy:busy==='true'};
}

export function parseAudioCreditRate(text){
  if(typeof text!=='string')return null;
  // Preserve the displayed denominator. No duration inference or rate rounding.
  const m=text.match(/^(\d{1,7}(?:\.\d{1,6})?)\s*积分\s*\/\s*(\d{1,4}(?:\.\d{1,3})?)?s$/);
  if(!m)return null;const credits=Number(m[1]),seconds=m[2]===undefined?1:Number(m[2]);
  if(!Number.isFinite(credits)||credits<0||credits>1000000||!Number.isFinite(seconds)||seconds<=0||seconds>600)return null;
  return{credit_amount:credits,per_seconds:seconds,display_text:text,estimated:true};
}
export async function inspectAudioQuote(page,rawScope,rawSettings){
  const scope=audioScope(rawScope),settings=parseAudioQuoteSettings(rawSettings);
  const form=async()=>{const d=await pollDOM({evaluate:()=>page.evaluate(readAudioFormDOM,scope)},readAudioFormDOM);
    if(audioFormHash(d)!==settings.expected_form_sha256)fail('draft_changed','Audio quote draft differs from the inspected form.');
    if(d.layers)fail('dialog_open','Existing layers stay intact.');
    if(d.files.some(f=>f.files===null))fail('reference_state_unknown','Quote binding needs known file state.');
    return d;};
  const cost=async()=>{const d=await pollDOM({evaluate:()=>page.evaluate(readAudioQuoteDOM,scope)},readAudioQuoteDOM);
    if(typeof d.price_busy!=='boolean'||!(d.price_text===null||typeof d.price_text==='string'&&d.price_text.length<=128))fail('bridge_protocol','Unexpected audio quote response shape.');return d;};
  const before=await form(),a=await cost(),middle=await form(),b=await cost(),after=await form();
  if(a.price_text!==b.price_text||a.price_busy!==b.price_busy||before.submit_enabled!==middle.submit_enabled||middle.submit_enabled!==after.submit_enabled||before.submit_busy!==middle.submit_busy||middle.submit_busy!==after.submit_busy)fail('quote_changed','Audio price or submission readiness changed during the quote.');
  const pending=b.price_busy||after.submit_busy,rate=pending?null:parseAudioCreditRate(b.price_text);
  const reason=pending?'price_or_submission_busy':rate?null:b.price_text===null?'price_missing':'unsupported_price_format';
  return[{result:{status:pending?'quote_pending':rate?'quoted_rate':'quote_unavailable',...scope,
    model:after.model,sample_rate:after.sample_rate,form_sha256:settings.expected_form_sha256,
    quote_sha256:sha(JSON.stringify(['xyq-audio-rate-v1',settings.expected_form_sha256,b.price_text,b.price_busy,after.submit_enabled,after.submit_busy])),
    quote_status:pending?'pending':rate?'unit_rate_only':'unknown',reason,reported_rate:rate,
    price_text_sha256:b.price_text===null?null:sha(b.price_text),total_credits:null,output_duration_seconds:null,
    spend_ceiling_verified:false,final_billing_verified:false,requires_duration_quote:true,
    submit_enabled:after.submit_enabled,association:after.association,source:'visible_dom',observed_at:new Date().toISOString(),
    secrets_returned:false,upload_started:false,paid_submitted:false,generation_submitted:false}}];
}
