// Strategy UI_SELECTOR / visible-ui: exactly one already-open result download.
// The public observer's URL is checked internally, stripped before any receipt.
import {createHash} from 'node:crypto';
import {existsSync,lstatSync,mkdirSync,openSync,closeSync,fstatSync,ftruncateSync,readFileSync,writeFileSync,fsyncSync,constants} from 'node:fs';
import {join,resolve,dirname,isAbsolute,basename} from 'node:path';
import {XyqError} from './core.mjs';
import {RESULT_FILES,resultScope,inspectConversationResults} from './results.mjs';
import {boundReadRouting} from './audio-bound.mjs';
export const DOWNLOAD_FILES=[...RESULT_FILES,'download.mjs','download.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
const unwrap=v=>v&&typeof v==='object'&&'session'in v&&'data'in v?v.data:v;
export function downloadDigest(){const h=createHash('sha256');for(const n of DOWNLOAD_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkDownloadPin(pin){if(typeof pin!=='string'||pin!==downloadDigest())fail('definition_changed','Review the one-download source closure.');}
export function downloadSettings(raw){
  let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use exact existing-result download confirmation JSON.');}
  const names=['thread_id','result_id','expected_result_sha256','quote_sha256','request_key','human_confirmed'];
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).length!==names.length||names.some(k=>!Object.hasOwn(v,k))||
    typeof v.quote_sha256!=='string'||!/^[a-f0-9]{64}$/.test(v.quote_sha256)||
    typeof v.request_key!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(v.request_key))fail('invalid_argument','Bind one download to its exact result, control plan and stable request key.');
  resultScope({thread_id:v.thread_id,result_id:v.result_id,expected_result_sha256:v.expected_result_sha256},'result_download_quote');
  if(v.human_confirmed!==true)fail('confirmation_required','Confirm one download of the selected existing result.');
  return Object.fromEntries(names.map(k=>[k,v[k]]));
}
function paths(workspace,key){
  if(typeof workspace!=='string'||!isAbsolute(workspace)||workspace==='/'||resolve(workspace)!==workspace||/[\x00-\x1f]/.test(workspace))fail('unsafe_path','Use an exact regular project directory.');
  const dir=join(workspace,'.atm','xyq-result-downloads');
  for(let p=dir;;p=dirname(p)){if(existsSync(p)){const s=lstatSync(p);if(s.isSymbolicLink()||!s.isDirectory())fail('unsafe_path','Download ledger directories must not be linked.');}if(dirname(p)===p)break;}
  return{dir,receipt:join(dir,sha(key)+'.json'),lock:join(dir,'active.lock')};
}
function readReceipt(path){
  if(!existsSync(path))return null;let fd,r;
  try{fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);const s=fstatSync(fd);if(!s.isFile()||s.nlink!==1||s.size<2||s.size>32000)fail('receipt_invalid','Expected one bounded regular download receipt.');r=JSON.parse(readFileSync(fd,'utf8'));}
  catch(e){if(e instanceof XyqError)throw e;fail('receipt_invalid','Download receipt is malformed or inaccessible.');}finally{if(fd!==undefined)closeSync(fd);}
  if(!r||Array.isArray(r)||r.version!==1||typeof r.request_key!=='string'||typeof r.fingerprint!=='string'||!/^[a-f0-9]{64}$/.test(r.fingerprint)||
    !['download_dispatch_claimed','download_unknown','download_observed','delivered'].includes(r.status))fail('receipt_invalid','Download receipt has an unknown contract.');
  return r;
}
function durable(path,record,exclusive=false){
  // The receipt inode is never replaced or unlinked; readers validate private size/type.
  const fd=openSync(path,constants.O_WRONLY|constants.O_CREAT|constants.O_NOFOLLOW|constants.O_NONBLOCK|(exclusive?constants.O_EXCL:0),0o600);
  try{const s=fstatSync(fd);if(!s.isFile()||s.nlink!==1)fail('unsafe_path','Download receipt must be a single-link regular file.');if(!exclusive)ftruncateSync(fd,0);writeFileSync(fd,JSON.stringify(record));fsyncSync(fd);}finally{closeSync(fd);}
  const parent=openSync(dirname(path),constants.O_RDONLY|constants.O_DIRECTORY|constants.O_NOFOLLOW);try{fsyncSync(parent);}finally{closeSync(parent);}
}
const boundedCodes=new Set(['result_changed','results_changed','result_missing','preview_required','result_not_ready','download_unavailable','control_obscured','thread_changed','origin_mismatch','unsupported_surface','dialog_open','control_changed','bridge_protocol','download_source_unverified','download_unknown']);
export function verifiedDownloadEvent(raw,result_id,filename){
  const v=unwrap(raw);
  if(!v||typeof v!=='object'||Array.isArray(v)||v.downloaded!==true||v.state!=='complete'||
    typeof v.filename!=='string'||!isAbsolute(v.filename)||resolve(v.filename)!==v.filename||/[\x00-\x1f]/.test(v.filename)||basename(v.filename)!==filename)
    fail('download_unknown','A matching completed file download was not observed.');
  // Filename alone (or a blob URL) never proves the selected image's identity.
  let u;try{u=new URL(v.url);}catch{fail('download_source_unverified','The download event lacks the selected media source identity.');}
  if(u.protocol!=='https:'||u.hostname!=='p3-pippit-business-jianying-sign.byteimg.com'||u.port||u.username||u.password||
    !new RegExp('^/tos-cn-i-wipe09lpyt/'+result_id+'(?:~tplv-wipe09lpyt-resize-v1:[0-9]{1,5}:[0-9]{1,5}\\.image)?$').test(u.pathname))
    fail('download_source_unverified','The download event is not associated with the selected image resource.');
  return{filename:v.filename,state:'complete',source_result_id:result_id,source_association_verified:true,download_freshness_verified:false};
}
export function readDownloadInputDOM(scope){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  const u=new URL(location.href);
  if(u.pathname!=='/home'||u.searchParams.getAll('thread_id').length!==1||u.searchParams.get('thread_id')!==scope.thread_id||
    u.searchParams.getAll('tab_name').length!==1||u.searchParams.get('tab_name')!=='integrated-agent'||
    u.searchParams.getAll('agent_name').length!==1||u.searchParams.get('agent_name')!=='pippit_nest_agent')return{kind:'thread_changed'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"],[inert]')&&getComputedStyle(e).visibility!=='hidden';
  if(Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).some(visible))return{kind:'dialog_open'};
  const panels=Array.from(document.querySelectorAll('aside[class*="artifactPanel-"]')).filter(visible);if(panels.length!==1)return{kind:'control_changed'};
  const p=panels[0],images=Array.from(p.querySelectorAll('[class*="artifactPreviewMediaContext-"] img')).filter(visible),titles=Array.from(p.querySelectorAll('div.text-heading-h3.truncate')).filter(visible);
  if(images.length!==1||titles.length!==1||titles[0].children.length||titles[0].textContent.trim()!==scope.filename||!images[0].complete||!images[0].naturalWidth||!images[0].naturalHeight)return{kind:'result_changed'};
  let src;try{src=new URL(images[0].currentSrc||images[0].getAttribute('src')||'');}catch{return{kind:'result_changed'};}
  if(src.protocol!=='https:'||src.hostname!=='p3-pippit-business-jianying-sign.byteimg.com'||src.port||src.username||src.password||
    !new RegExp('^/tos-cn-i-wipe09lpyt/'+scope.result_id+'~tplv-wipe09lpyt-resize-v1:[0-9]{1,5}:[0-9]{1,5}\\.image$').test(src.pathname))return{kind:'result_changed'};
  const buttons=Array.from(p.querySelectorAll('button[data-slot="button"]')).filter(e=>visible(e)&&e.textContent.trim()==='下载');
  if(buttons.length!==1)return{kind:'control_changed'};const b=buttons[0];
  if(b.disabled||b.getAttribute('aria-disabled')==='true'||b.getAttribute('aria-busy')==='true')return{kind:'download_unavailable'};
  const r=b.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);
  if(r.width<=0||r.height<=0||x<0||y<0||x>=innerWidth||y>=innerHeight||!(hit===b||b.contains(hit)))return{kind:'control_obscured'};
  return{kind:'ready',x,y};
}
function publicObserved(r,reused=false){
  return[{result:{status:'download_observed',thread_id:r.thread_id,result_id:r.result_id,request_key:r.request_key,result_sha256:r.result_sha256,quote_sha256:r.quote_sha256,
    file:r.download,preview:{width:r.width,height:r.height},reused,submission_repeated:false,complete_decode_verified:false,artifact_verified:false,
    task_association_verified:false,provider_generation_verified:false,secrets_returned:false,generation_submitted:false,paid_submitted:false,upload_started:false}}];
}
export async function downloadExistingResult(page,raw,workspace){
  const args=downloadSettings(raw),p=paths(workspace,args.request_key),fingerprint=sha(JSON.stringify(['xyq-existing-image-download-v1',args])),old=readReceipt(p.receipt);
  if(old){
    if(old.request_key!==args.request_key||old.fingerprint!==fingerprint)fail('request_conflict','Original download has different parameters.');
    if(old.thread_id!==args.thread_id||old.result_id!==args.result_id||old.result_sha256!==args.expected_result_sha256||old.quote_sha256!==args.quote_sha256||
      !Number.isInteger(old.width)||!Number.isInteger(old.height)||old.width<1||old.height<1||old.width*old.height>40000000||
      typeof old.filename!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_. -]{0,159}\.png$/.test(old.filename))fail('receipt_invalid','Retained download scope or preview metadata changed.');
    if(old.status==='download_observed'||old.status==='delivered'){
      if(!old.download||old.download.source_association_verified!==true||old.download.source_result_id!==args.result_id||old.download.state!=='complete'||typeof old.download.filename!=='string'||
        !isAbsolute(old.download.filename)||resolve(old.download.filename)!==old.download.filename||/[\x00-\x1f]/.test(old.download.filename)||basename(old.download.filename)!==old.filename)fail('receipt_invalid','Retained download association is incomplete.');
      return publicObserved(old,true);
    }
    fail('download_unknown','Inspect the original download; this request never repeats native input.');
  }
  if(existsSync(p.lock))fail('workspace_busy','Another result download is unresolved; keep its original receipt.');
  const scope={thread_id:args.thread_id,result_id:args.result_id,expected_result_sha256:args.expected_result_sha256};
  const quote=(await inspectConversationResults(page,scope,'result_download_quote'))[0].result;
  if(quote.quote_sha256!==args.quote_sha256)fail('result_changed','Selected download control plan changed.');
  let input;try{input=unwrap(await page.evaluate(readDownloadInputDOM,{thread_id:args.thread_id,result_id:args.result_id,filename:quote.filename}));}
  catch{fail('bridge_failed','Download control read failed before dispatch.');}
  if(!input||typeof input!=='object'||!boundedCodes.has(input.kind)&&input.kind!=='ready'||input.kind==='ready'&&(!Number.isFinite(input.x)||!Number.isFinite(input.y)))fail('bridge_protocol','Unexpected download control response.');
  if(input.kind!=='ready')fail(input.kind,'Selected download control is not ready.');
  if(typeof page.nativeClick!=='function'||typeof page.waitForDownload!=='function')fail('unsupported_backend','One download requires the public native input and download observer.');
  mkdirSync(p.dir,{recursive:true,mode:0o700});
  try{durable(p.lock,{version:1,request_key:args.request_key,fingerprint},true);}catch(e){if(e.code==='EEXIST')fail('workspace_busy','Another result download claimed the project.');throw e;}
  const r={version:1,status:'download_dispatch_claimed',request_key:args.request_key,fingerprint,thread_id:args.thread_id,result_id:args.result_id,
    result_sha256:args.expected_result_sha256,quote_sha256:args.quote_sha256,filename:quote.filename,width:quote.width,height:quote.height};
  try{
    durable(p.receipt,r,true);
    const final=(await inspectConversationResults(page,scope,'result_download_quote'))[0].result;
    if(final.quote_sha256!==args.quote_sha256)fail('result_changed','Download plan changed after durable intent.');
    input=unwrap(await page.evaluate(readDownloadInputDOM,{thread_id:args.thread_id,result_id:args.result_id,filename:quote.filename}));
    if(!input||input.kind!=='ready'||!Number.isFinite(input.x)||!Number.isFinite(input.y))fail(boundedCodes.has(input?.kind)?input.kind:'bridge_protocol','Download control changed after durable intent.');
    const observed=Promise.resolve(page.waitForDownload(quote.filename,20000)).then(value=>({value}),()=>({error:true}));
    // A lost native-input acknowledgement is not a reason to click again. The
    // original observer may still prove the selected completed file independently.
    let acknowledged=true;try{await page.nativeClick(input.x,input.y);}catch{acknowledged=false;}
    const event=await observed;if(event.error)fail('download_unknown','Download observer did not confirm the completed selected file.');
    r.download=verifiedDownloadEvent(event.value,args.result_id,quote.filename);r.native_input_acknowledged=acknowledged;r.status='download_observed';durable(p.receipt,r);
    return publicObserved(r);
  }catch(e){r.status='download_unknown';r.failure_code=e instanceof XyqError&&boundedCodes.has(e.code)?e.code:'bridge_failed';durable(p.receipt,r);fail('download_unknown','One download remains unverified; retain intent/lock and inspect the original request.');}
}
export async function createDownloadPage(routing){const {Page}=await import('@jackwener/opencli/browser/page');const page=new Page('site:xyq-home',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);return Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg),nativeClick:(x,y)=>page.nativeClick(x,y),waitForDownload:(pattern,timeout)=>page.waitForDownload(pattern,timeout)});}
export async function downloadBoundResult(context,raw,workspace,createPage=createDownloadPage){
  const args=downloadSettings(raw);let page;
  try{page=await createPage(boundReadRouting(context));if(!page||typeof page.evaluate!=='function')fail('unsupported_backend','Download Page requires public browser APIs.');}
  catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','Download Page preparation failed.');}
  return downloadExistingResult(page,args,workspace);
}
