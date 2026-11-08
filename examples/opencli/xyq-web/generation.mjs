// Strategy UI_SELECTOR / visible-ui: existing draft-bound home quote and native
// submit control. No internal API, credentials, reference uploads or paid retry.
import {createHash,randomUUID} from 'node:crypto';
import {existsSync,lstatSync,mkdirSync,openSync,closeSync,fstatSync,ftruncateSync,readFileSync,writeFileSync,fsyncSync,renameSync,constants} from 'node:fs';
import {resolve,dirname,join,isAbsolute} from 'node:path';
import {XyqError,pollDOM} from './core.mjs';
import {HOME_QUOTE_FILES,inspectHomeQuote} from './home-quote.mjs';
import {boundReadRouting} from './audio-bound.mjs';
export const GENERATION_FILES=[...HOME_QUOTE_FILES,'generation.mjs','generation.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
export function generationDigest(){const h=createHash('sha256');for(const n of GENERATION_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkGenerationPin(pin){if(typeof pin!=='string'||pin!==generationDigest())fail('definition_changed','Review the generation source closure.');}
export function parseGenerationSettings(raw){
  let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use exact draft/quote/budget confirmation JSON.');}
  const names=['expected_draft_sha256','quote_sha256','max_credits','human_confirmed','estimated_cost_confirmed','request_key'];
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).length!==names.length||names.some(k=>!Object.hasOwn(v,k))||
    !['expected_draft_sha256','quote_sha256'].every(k=>typeof v[k]==='string'&&/^[a-f0-9]{64}$/.test(v[k]))||
    typeof v.max_credits!=='number'||!Number.isFinite(v.max_credits)||v.max_credits<0||v.max_credits>10000||
    typeof v.request_key!=='string'||!/^[A-Za-z0-9_.:-]{1,160}$/.test(v.request_key))fail('invalid_argument','Bind one generation to its exact draft, quote, credit limit and request key.');
  if(v.human_confirmed!==true||v.estimated_cost_confirmed!==true)fail('confirmation_required','Confirm the exact draft and displayed estimate; final billing is separate.');
  return{...v};
}
function ledgerPath(workspace,key){
  if(typeof workspace!=='string'||!isAbsolute(workspace)||workspace==='/'||resolve(workspace)!==workspace||/[\x00-\x1f]/.test(workspace)||typeof key!=='string'||!/^[A-Za-z0-9_.:-]{1,160}$/.test(key))fail('unsafe_path','Use the exact approved project path and original request key.');
  const dir=join(workspace,'.atm','xyq-generation');
  for(let p=dir;;p=dirname(p)){if(existsSync(p)){const s=lstatSync(p);if(s.isSymbolicLink()||!s.isDirectory())fail('unsafe_path','Generation ledger paths must be regular project directories.');}if(dirname(p)===p)break;}
  return{dir,receipt:join(dir,sha(key)+'.json'),lock:join(dir,'active.lock')};
}
function readReceipt(path,key){
  if(!existsSync(path))return null;let fd,r;
  try{fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);const s=fstatSync(fd);if(!s.isFile()||s.nlink!==1||s.size<2||s.size>16000)fail('receipt_invalid','Expected a bounded private generation receipt.');r=JSON.parse(readFileSync(fd,'utf8'));}
  catch(e){if(e instanceof XyqError)throw e;fail('receipt_invalid','Retained generation receipt is inaccessible or malformed.');}finally{if(fd!==undefined)closeSync(fd);}
  if(!r||Array.isArray(r)||r.request_key!==key||!/^[a-f0-9]{64}$/.test(r.fingerprint||'')||!['dispatch_claimed','submitted','submission_unknown'].includes(r.status)||
    !['draft_sha256','quote_sha256'].every(k=>typeof r[k]==='string'&&/^[a-f0-9]{64}$/.test(r[k]))||
    typeof r.max_credits!=='number'||!Number.isFinite(r.max_credits)||r.max_credits<0||r.max_credits>10000||
    (r.mode!==undefined&&!['图片生成','视频生成','音频生成'].includes(r.mode))||
    (r.displayed_estimated_credits!==undefined&&(typeof r.displayed_estimated_credits!=='number'||!Number.isFinite(r.displayed_estimated_credits)||r.displayed_estimated_credits<0||r.displayed_estimated_credits>r.max_credits))||
    ['project_id','canvas_id'].some(k=>r[k]!==undefined&&(typeof r[k]!=='string'||!/^\d{1,20}$/.test(r[k])))||
    (r.status==='submitted'&&(!r.project_id||!r.canvas_id||!r.mode)))fail('receipt_invalid','Retained generation receipt has a different request contract.');
  return r;
}
function durable(path,record,exclusive=false){
  const fd=openSync(path,constants.O_WRONLY|constants.O_CREAT|constants.O_NOFOLLOW|constants.O_NONBLOCK|(exclusive?constants.O_EXCL:0),0o600);
  try{const s=fstatSync(fd);if(!s.isFile()||s.nlink!==1)fail('unsafe_path','Generation receipt must be a single-link regular file.');if(!exclusive)ftruncateSync(fd,0);writeFileSync(fd,JSON.stringify(record));fsyncSync(fd);}finally{closeSync(fd);}
  const parent=openSync(dirname(path),constants.O_RDONLY|constants.O_DIRECTORY|constants.O_NOFOLLOW);try{fsyncSync(parent);}finally{closeSync(parent);}
}
const publicReceipt=r=>({status:r.status,request_key:r.request_key,mode:r.mode||null,project_id:r.project_id||null,canvas_id:r.canvas_id||null,
  provider_task_id:null,task_completed:false,draft_sha256:r.draft_sha256||null,quote_sha256:r.quote_sha256||null,
  displayed_estimated_credits:r.displayed_estimated_credits??null,max_credits:r.max_credits??null,
  spend_ceiling_verified:false,final_billing_verified:false,download_started:false,secrets_returned:false});
export function generationStatus(workspace,key){
  const paths=ledgerPath(workspace,key),r=readReceipt(paths.receipt,key);if(!r)fail('request_missing','No retained generation receipt for this request key.');
  return[{result:{...publicReceipt(r),status:r.status==='submitted'?'submitted':'submission_unknown',provider_checked:false,
    query_scope:'original_local_submission_receipt',generation_submitted:r.status==='submitted'?true:null,submission_repeated:false,lock_changed:false}}];
}
export function readGenerationInputDOM(){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  if(Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).some(visible))return{kind:'dialog_open'};
  const roots=document.querySelectorAll('#title-section-prompt-container');if(roots.length!==1||!visible(roots[0]))return{kind:'layout_changed'};
  const buttons=Array.from(roots[0].querySelectorAll('button[aria-label="开始生成"],button[aria-label="生成"]')).filter(visible);
  if(buttons.length!==1||buttons[0].getAttribute('data-slot')!=='home-input-composer-submit-button')return{kind:'control_changed'};
  const e=buttons[0];if(e.disabled||e.getAttribute('aria-disabled')==='true'||e.getAttribute('aria-busy')==='true')return{kind:'submit_unavailable'};
  const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);
  return{kind:r.width>0&&r.height>0&&(hit===e||e.contains(hit))?'ready':'control_obscured',x,y};
}
export function readGenerationAcceptedDOM(){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname==='/home')return{kind:'pending'};
  if(location.pathname!=='/project')return{kind:'unsupported_surface'};
  const u=new URL(location.href),project=u.searchParams.getAll('projectId'),canvas=u.searchParams.getAll('canvasId');
  if(project.length!==1||canvas.length!==1||!/^\d{1,20}$/.test(project[0])||!/^\d{1,20}$/.test(canvas[0]))return{kind:'project_context_changed'};
  const roots=Array.from(document.querySelectorAll('[role="application"][data-testid="rf__wrapper"]')).filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]'));
  if(roots.length!==1)return{kind:'pending'};
  return{kind:'ready',project_id:project[0],canvas_id:canvas[0],acceptance:'project_route_and_canvas_observed_not_task_completion'};
}
export async function generateHome(page,raw,workspace){
  const settings=parseGenerationSettings(raw),paths=ledgerPath(workspace,settings.request_key),fingerprint=sha(JSON.stringify(['xyq-generation-v1',settings]));
  const prior=readReceipt(paths.receipt,settings.request_key);
  if(prior){if(prior.fingerprint!==fingerprint)fail('request_conflict','The original request key has different generation inputs.');
    if(prior.status!=='submitted')fail('submission_unknown','Inspect the retained request and provider before another generation.');
    return[{result:{...publicReceipt(prior),generation_submitted:true,reused:true}}];}
  if(!page||typeof page.evaluate!=='function'||typeof page.nativeClick!=='function')fail('unsupported_backend','Generation requires the public native-click bridge.');
  const quote=async()=>{const q=(await inspectHomeQuote(page,{expected_draft_sha256:settings.expected_draft_sha256}))[0].result;
    if(q.quote_sha256!==settings.quote_sha256)fail('quote_changed','The current draft/settings/estimate differ from the approved quote.');
    if(q.status!=='quoted_estimate'||!q.reported_estimate||q.reported_estimate.per_seconds!==null)fail('total_quote_required','A unit rate or missing estimate does not establish a per-generation amount.');
    if(q.reported_estimate.credit_amount>settings.max_credits)fail('budget_exceeded','Displayed generation estimate exceeds the approved limit.');
    if(!q.submit_enabled)fail('submit_unavailable','Current generation prerequisites are incomplete.');return q;};
  await quote();await pollDOM(page,readGenerationInputDOM);
  mkdirSync(paths.dir,{recursive:true,mode:0o700});ledgerPath(workspace,settings.request_key);
  try{durable(paths.lock,{request_key:settings.request_key,fingerprint},true);}catch(e){if(e.code==='EEXIST')fail('workspace_busy','An unfinished generation retains its project operation lock.');throw e;}
  let claimed=false;const record={status:'dispatch_claimed',request_key:settings.request_key,fingerprint,created_at:new Date().toISOString(),
    draft_sha256:settings.expected_draft_sha256,quote_sha256:settings.quote_sha256,max_credits:settings.max_credits};
  try{
    const q=await quote();record.mode=q.mode;record.displayed_estimated_credits=q.reported_estimate.credit_amount;
    durable(paths.receipt,record,true);claimed=true;
    await quote();const target=await pollDOM(page,readGenerationInputDOM);
    await page.nativeClick(target.x,target.y);
    const accepted=await pollDOM(page,readGenerationAcceptedDOM,{timeout:15000});
    Object.assign(record,{status:'submitted',project_id:accepted.project_id,canvas_id:accepted.canvas_id,acceptance:accepted.acceptance});durable(paths.receipt,record);
    renameSync(paths.lock,join(paths.dir,'released-'+randomUUID()+'.lock'));
    return[{result:{...publicReceipt(record),acceptance:accepted.acceptance,generation_submitted:true,reused:false}}];
  }catch(e){if(claimed){record.status='submission_unknown';record.failure_code=e instanceof XyqError?e.code:'bridge_failed';
    try{durable(paths.receipt,record);}catch(retention){
      const error=new XyqError('submission_unknown','Generation acknowledgement or receipt retention is unverified; preserve the original bytes and operation lock.');
      error.phase='receipt_retention';error.retention_failure_code=retention instanceof XyqError?retention.code:'receipt_write_failed';error.outcome_uncertain=true;throw error;
    }
    fail('submission_unknown','Generation may have reached the provider; retain this request and operation lock.');}
    renameSync(paths.lock,join(paths.dir,'not-submitted-'+randomUUID()+'.lock'));throw e;}
}
export async function createGenerationPage(routing){const {Page}=await import('@jackwener/opencli/browser/page');const page=new Page('site:xyq-home',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);return Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg),nativeClick:(x,y)=>page.nativeClick(x,y)});}
export async function generateBoundHome(context,raw,workspace,createPage=createGenerationPage){
  const settings=parseGenerationSettings(raw);let page;try{page=await createPage(boundReadRouting(context));}catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','Generation Page preparation failed.');}
  return generateHome(page,settings,workspace);
}
