// Strategy UI_SELECTOR / visible-ui: exact already-open conversation results.
// Resource IDs are media identifiers, not provider task IDs. No prompt/auth reads.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM} from './core.mjs';
import {AUDIO_BOUND_FILES,boundReadRouting} from './audio-bound.mjs';
export const RESULT_FILES=[...AUDIO_BOUND_FILES,'results.mjs','results.js'];
const fail=(code,message)=>{throw new XyqError(code,message);};
const sha=v=>createHash('sha256').update(v).digest('hex');
const uuid=/^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$/;
export function resultDigest(){const h=createHash('sha256');for(const n of RESULT_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkResultPin(pin){if(typeof pin!=='string'||pin!==resultDigest())fail('definition_changed','Review the conversation-result source closure.');}
export function resultScope(raw,operation='results'){
  if(!['results','result_inspect','result_download_quote'].includes(operation))fail('invalid_argument','Unknown conversation-result operation.');
  const keys=['thread_id',...(operation==='results'?[]:['result_id']),...(operation==='result_download_quote'?['expected_result_sha256']:[])];
  if(!raw||typeof raw!=='object'||Array.isArray(raw)||Object.keys(raw).length!==keys.length||keys.some(k=>!Object.hasOwn(raw,k))||
    typeof raw.thread_id!=='string'||!uuid.test(raw.thread_id)||
    (operation!=='results'&&(typeof raw.result_id!=='string'||!/^[a-f0-9]{32}$/.test(raw.result_id)))||
    (operation==='result_download_quote'&&(typeof raw.expected_result_sha256!=='string'||!/^[a-f0-9]{64}$/.test(raw.expected_result_sha256))))fail('invalid_argument','Use an exact observed thread and media resource ID; no URLs or selectors.');
  return Object.fromEntries(keys.map(k=>[k,raw[k]]));
}

export function readConversationResultsDOM(scope){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  const u=new URL(location.href);
  if(u.searchParams.getAll('thread_id').length!==1||u.searchParams.get('thread_id')!==scope.thread_id)return{kind:'thread_changed'};
  if(u.searchParams.getAll('tab_name').length!==1||u.searchParams.get('tab_name')!=='integrated-agent'||
    u.searchParams.getAll('agent_name').length!==1||u.searchParams.get('agent_name')!=='pippit_nest_agent')return{kind:'unsupported_surface'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"],[inert]')&&getComputedStyle(e).visibility!=='hidden';
  if(Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).some(visible))return{kind:'dialog_open'};
  const media=e=>{
    let url;try{url=new URL(e.currentSrc||e.getAttribute('src')||'');}catch{return null;}
    if(url.protocol!=='https:'||url.hostname!=='p3-pippit-business-jianying-sign.byteimg.com'||url.port||url.username||url.password)return null;
    const m=url.pathname.match(/^\/tos-cn-i-wipe09lpyt\/([a-f0-9]{32})~tplv-wipe09lpyt-resize-v1:([0-9]{1,5}):([0-9]{1,5})\.image$/);
    if(!m||+m[2]<1||+m[3]<1||+m[2]>16384||+m[3]>16384)return null;
    const width=e.naturalWidth,height=e.naturalHeight;
    if(!Number.isInteger(width)||!Number.isInteger(height)||width<0||height<0||width>16384||height>16384||width*height>40000000)return null;
    return{result_id:m[1],kind:'image',load_state:!e.complete?'loading':width&&height?'loaded':'failed',width,height,resize_width:+m[2],resize_height:+m[3]};
  };
  const cards=Array.from(document.querySelectorAll('.ag-ui-assistant-message .ag-ui-x-biz-image-part')).filter(visible);
  if(cards.length>100)return{kind:'result_limit_exceeded'};
  const images=[];
  for(const card of cards){
    const es=Array.from(card.querySelectorAll('img')).filter(visible);
    if(es.length!==1)return{kind:'result_layout_changed'};
    const data=media(es[0]);if(!data)return{kind:'unsupported_media_source'};
    images.push({...data,surface:'conversation_card'});
  }
  const panels=Array.from(document.querySelectorAll('aside[class*="artifactPanel-"]')).filter(visible);
  if(panels.length>1)return{kind:'preview_ambiguous'};
  let preview=null;
  if(panels.length){
    const p=panels[0],es=Array.from(p.querySelectorAll('[class*="artifactPreviewMediaContext-"] img')).filter(visible);
    if(es.length!==1)return{kind:'preview_layout_changed'};
    const data=media(es[0]);if(!data)return{kind:'unsupported_media_source'};
    const back=Array.from(p.querySelectorAll('button[aria-label="返回资源列表"]')).filter(visible);
    const buttons=Array.from(p.querySelectorAll('button[data-slot="button"]')).filter(e=>visible(e)&&e.textContent.trim()==='下载');
    if(back.length!==1||buttons.length!==1)return{kind:'download_control_changed'};
    // Read only the observed file-name heading, never surrounding conversation text.
    const titles=Array.from(p.querySelectorAll('div.text-heading-h3.truncate')).filter(visible);
    if(titles.length!==1||titles[0].children.length)return{kind:'filename_changed'};
    const filename=titles[0].textContent.trim();
    if(!/^[A-Za-z0-9][A-Za-z0-9_. -]{0,159}\.png$/.test(filename))return{kind:'unsupported_filename'};
    const b=buttons[0],r=b.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);
    preview={...data,surface:'artifact_preview',filename,download_enabled:!b.disabled&&b.getAttribute('aria-disabled')!=='true'&&b.getAttribute('aria-busy')!=='true',
      download_hit_verified:r.width>0&&r.height>0&&x>=0&&y>=0&&x<innerWidth&&y<innerHeight&&(hit===b||b.contains(hit))};
  }
  return{kind:'ready',images,preview};
}

// Validate the public evaluator response as well as the DOM. No raw transport data.
function validateRead(data){
  const exact=(v,keys)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
  const common=['result_id','kind','load_state','width','height','resize_width','resize_height','surface'];
  if(!exact(data,['kind','images','preview'])||data.kind!=='ready'||!Array.isArray(data.images)||data.images.length>100)fail('bridge_protocol','Unexpected result-reader response.');
  const check=(v,preview=false)=>{
    if(!exact(v,[...common,...(preview?['filename','download_enabled','download_hit_verified']:[])])||v.kind!=='image'||typeof v.result_id!=='string'||!/^[a-f0-9]{32}$/.test(v.result_id)||
      !['loading','loaded','failed'].includes(v.load_state)||v.surface!==(preview?'artifact_preview':'conversation_card')||
      ['width','height','resize_width','resize_height'].some(k=>!Number.isInteger(v[k])||v[k]<(['width','height'].includes(k)?0:1)||v[k]>16384)||v.width*v.height>40000000||
      (v.load_state==='loaded'&&(!v.width||!v.height))||(v.load_state==='failed'&&(v.width||v.height))||
      (preview&&(typeof v.filename!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_. -]{0,159}\.png$/.test(v.filename)||typeof v.download_enabled!=='boolean'||typeof v.download_hit_verified!=='boolean')))
      fail('bridge_protocol','Unexpected media-result metadata.');
  };
  data.images.forEach(v=>check(v));if(data.preview!==null)check(data.preview,true);
  // Canonical key order makes digests independent of bridge object serialization.
  const normalize=(v,preview=false)=>Object.fromEntries([...common,...(preview?['filename','download_enabled','download_hit_verified']:[])].map(k=>[k,v[k]]));
  return{kind:'ready',images:data.images.map(v=>normalize(v)),preview:data.preview===null?null:normalize(data.preview,true)};
}
const evidence={source:'visible_dom',query_scope:'current_rendered_conversation_image_results',all_results:false,provider_task_id:null,provider_task_status:null,
  task_association_verified:false,provider_generation_verified:false,secrets_returned:false,generation_submitted:false,upload_started:false,paid_submitted:false,download_started:false,download_verified:false};
function publicResult(scope,v){
  return{thread_id:scope.thread_id,...v,provider_task_id:null,provider_task_status:null,result_id_kind:'visible_media_resource',
    status:v.load_state==='loaded'?'result_available':v.load_state==='loading'?'result_pending':'result_load_failed',
    result_sha256:sha(JSON.stringify(['xyq-visible-image-result-v1',scope.thread_id,v]))};
}
export async function inspectConversationResults(page,raw,operation='results'){
  const scope=resultScope(raw,operation),read=async()=>validateRead(await pollDOM({evaluate:()=>page.evaluate(readConversationResultsDOM,{thread_id:scope.thread_id})},readConversationResultsDOM));
  const before=await read(),after=await read();if(JSON.stringify(before)!==JSON.stringify(after))fail('results_changed','Rendered result metadata changed during the read.');
  const variants=[...after.images,...(after.preview?[after.preview]:[])];
  const ids=[...new Set(variants.map(v=>v.result_id))];
  const selected=id=>variants.find(v=>v.result_id===id&&v.surface==='artifact_preview')||variants.find(v=>v.result_id===id);
  const items=ids.map(id=>publicResult(scope,selected(id)));
  if(operation==='results')return[{result:{status:items.length?'results_available':'no_rendered_image_results',thread_id:scope.thread_id,
    results:items,visible_result_count:items.length,visible_card_count:after.images.length,preview_result_id:after.preview?.result_id||null,
    ...evidence,results_sha256:sha(JSON.stringify(['xyq-rendered-results-v1',scope.thread_id,after]))}}];
  const item=items.find(v=>v.result_id===scope.result_id);if(!item)fail('result_missing','Selected media resource is not rendered in the exact current conversation.');
  if(operation==='result_inspect')return[{result:{...item,...evidence}}];
  if(item.result_sha256!==scope.expected_result_sha256)fail('result_changed','Selected result metadata differs from the approved result digest.');
  if(item.surface!=='artifact_preview')fail('preview_required','Open the selected result preview before reading its download plan.');
  if(item.load_state!=='loaded')fail('result_not_ready','Selected image has not loaded successfully.');
  if(!item.download_enabled)fail('download_unavailable','Selected preview download control is disabled.');
  if(!item.download_hit_verified)fail('control_obscured','Selected preview download control is covered.');
  return[{result:{status:'download_control_ready',thread_id:scope.thread_id,result_id:scope.result_id,kind:'image',filename:item.filename,
    width:item.width,height:item.height,result_sha256:item.result_sha256,quote_sha256:sha(JSON.stringify(['xyq-result-download-plan-v1',item])),
    quote_kind:'existing_result_download_plan_not_price',download_control_verified:true,bytes_verified:false,decoder_verified:false,...evidence}}];
}
export async function createResultPage(routing){const {Page}=await import('@jackwener/opencli/browser/page');const page=new Page('site:xyq-home',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);return Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)});}
export async function inspectBoundConversationResults(context,raw,operation='results',createPage=createResultPage){
  const scope=resultScope(raw,operation);let page;
  try{page=await createPage(boundReadRouting(context));if(!page||typeof page.evaluate!=='function')fail('unsupported_backend','Result queries require the public evaluator.');}
  catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','Conversation-result Page preparation failed.');}
  return(await inspectConversationResults(Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)}),scope,operation)).map(({result})=>({result:{...result,
    browser_session:'site:xyq-home',browser_surface:'browser',binding_changed:false}}));
}
