// Strategy UI_SELECTOR / visible-ui: current project history view, never global tasks.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM} from './core.mjs';
import {AUDIO_BOUND_FILES,boundReadRouting} from './audio-bound.mjs';
export const HISTORY_FILES=[...AUDIO_BOUND_FILES,'history.mjs','history.js'];
const fail=(code,message)=>{throw new XyqError(code,message);};
const sha=v=>createHash('sha256').update(v).digest('hex');
export function historyDigest(){const h=createHash('sha256');for(const n of HISTORY_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkHistoryPin(pin){if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==historyDigest())fail('definition_changed','Review the project history view source closure.');}
export function historyScope(raw){const names=['project_id','canvas_id'];if(!raw||typeof raw!=='object'||Array.isArray(raw)||Object.keys(raw).length!==2||names.some(k=>!Object.hasOwn(raw,k)||typeof raw[k]!=='string'||!/^\d{1,20}$/.test(raw[k])))fail('invalid_argument','Use exact observed project/canvas IDs only.');return Object.fromEntries(names.map(k=>[k,raw[k]]));}

// No task-row inspection before its actual scoped layout has been verified.
export function readProjectHistoryDOM(scope){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/project')return{kind:'unsupported_surface'};
  const u=new URL(location.href);
  if(u.searchParams.getAll('projectId').length!==1||u.searchParams.get('projectId')!==scope.project_id)return{kind:'project_changed'};
  if(u.searchParams.getAll('canvasId').length!==1||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const roots=Array.from(document.querySelectorAll('[role="application"][data-testid="rf__wrapper"]')).filter(visible);
  if(roots.length!==1)return{kind:'layout_changed'};
  const triggers=Array.from(document.querySelectorAll('button[aria-label="生成历史"]')).filter(visible);
  if(triggers.length!==1)return{kind:'history_layout_changed'};
  const trigger=triggers[0],expanded=trigger.getAttribute('aria-expanded'),open=trigger.getAttribute('data-state');
  if(trigger.getAttribute('data-slot')!=='popover-trigger'||trigger.getAttribute('aria-haspopup')!=='dialog'||!['true','false'].includes(expanded)||open!==(expanded==='true'?'open':'closed'))return{kind:'history_context_changed'};
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible);
  const panels=layers.filter(e=>e.getAttribute('role')==='dialog'&&e.getAttribute('aria-label')==='生成历史');
  const audio=layers.filter(e=>e.getAttribute('role')==='dialog'&&e.getAttribute('aria-label')==='音频节点音频生成面板'&&e.getAttribute('data-xyq-selected-audio-footer-panel')==='true'&&roots[0].contains(e));
  if(audio.length>1||layers.some(e=>!panels.includes(e)&&!audio.includes(e)))return{kind:'dialog_open'};
  if(expanded==='false'){
    if(panels.length)return{kind:'history_context_changed'};
    return{kind:'ready',view_state:'closed',selected_media:null,selected_status:null,media_filters:[],visible_record_count:null};
  }
  if(panels.length!==1)return{kind:'history_context_changed'};
  const panel=panels[0];
  if(!panel.id||trigger.getAttribute('aria-controls')!==panel.id||panel.getAttribute('data-slot')!=='popover-content'||panel.getAttribute('data-state')!=='open')return{kind:'history_context_changed'};
  const titles=Array.from(panel.querySelectorAll('h2[data-slot="popover-title"]')).filter(visible);
  if(titles.length!==1||titles[0].innerText.trim()!=='生成历史')return{kind:'history_layout_changed'};
  const lists=Array.from(panel.querySelectorAll('[role="tablist"][aria-label="筛选生成历史"]')).filter(visible);
  if(lists.length!==1)return{kind:'history_layout_changed'};
  const tabs=Array.from(lists[0].querySelectorAll('[role="tab"]')).filter(visible),labels=['全部','图片','视频','音频'];
  if(tabs.length!==4||tabs.some((e,i)=>e.innerText.trim()!==labels[i]||!['true','false'].includes(e.getAttribute('aria-selected'))))return{kind:'history_layout_changed'};
  const selected=tabs.filter(e=>e.getAttribute('aria-selected')==='true');
  if(selected.length!==1)return{kind:'history_context_changed'};
  const bodies=Array.from(panel.querySelectorAll('[role="tabpanel"]')).filter(visible);
  if(bodies.length!==1)return{kind:'history_context_changed'};
  const body=bodies[0],tab=selected[0];
  if(!tab.id||!body.id||tab.getAttribute('aria-controls')!==body.id||body.getAttribute('aria-labelledby')!==tab.id||body.getAttribute('data-state')!=='active'||body.getAttribute('data-slot')!=='tabs-content'||!body.classList.contains('xyq-generation-history-content'))return{kind:'history_context_changed'};
  const filters=Array.from(panel.querySelectorAll('button[data-slot="dropdown-menu-trigger"]')).filter(visible);
  if(filters.length!==1)return{kind:'history_layout_changed'};
  const filter=filters[0],text=filter.innerText.trim(),states=['成功','全部状态','生成中','失败'];
  if(!states.includes(text)||filter.getAttribute('aria-label')!==text+'，筛选生成状态'||filter.getAttribute('aria-haspopup')!=='menu'||filter.getAttribute('aria-expanded')!=='false'||filter.getAttribute('data-state')!=='closed')return{kind:'history_filter_changed'};
  const meta={selected_media:tab.innerText.trim(),selected_status:text,media_filters:tabs.map(e=>({label:e.innerText.trim(),selected:e===tab,disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'}))};
  const busy=body.getAttribute('aria-busy');if(busy!==null&&!['true','false'].includes(busy))return{kind:'history_layout_changed'};
  if(busy==='true')return{kind:'ready',view_state:'loading',visible_record_count:null,...meta};
  const viewports=Array.from(body.querySelectorAll('.xyq-generation-history-viewport')).filter(visible);
  if(viewports.length!==1)return{kind:'history_layout_changed'};
  const viewport=viewports[0],children=Array.from(viewport.children).filter(visible),empty=Array.from(viewport.querySelectorAll('[role="status"][data-slot="empty"]')).filter(visible);
  // Populated layouts are deliberately not parsed, even if they look task-like.
  if(!empty.length)return{kind:'unsupported_history_records'};
  if(empty.length!==1||children.length!==1||children[0]!==empty[0])return{kind:'history_layout_changed'};
  const descriptions=Array.from(empty[0].querySelectorAll('[data-slot="empty-description"]')).filter(visible);
  if(descriptions.length!==1||descriptions[0].innerText.trim()!=='暂无符合筛选条件的生成记录')return{kind:'history_empty_changed'};
  return{kind:'ready',view_state:'empty',visible_record_count:0,...meta};
}
export async function inspectProjectHistory(page,raw){
  const scope=historyScope(raw),read=()=>pollDOM({evaluate:()=>page.evaluate(readProjectHistoryDOM,scope)},readProjectHistoryDOM);
  const before=await read(),after=await read();if(JSON.stringify(before)!==JSON.stringify(after))fail('history_changed','Current history view changed during the read.');
  return[{result:{status:after.view_state==='closed'?'history_closed':after.view_state==='loading'?'history_pending':'history_empty',...scope,
    view_state:after.view_state,selected_media:after.selected_media,selected_status:after.selected_status,media_filters:after.media_filters,
    visible_record_count:after.visible_record_count,task_count:null,all_records:false,coverage:'current_filtered_visible_view',
    scope_evidence:'exact_project_canvas_url_and_owned_history_trigger',row_scope_verified:false,task_rows_parsed:false,
    history_sha256:sha(JSON.stringify(['xyq-project-history-view-v1',scope,after])),source:'visible_dom',observed_at:new Date().toISOString(),
    secrets_returned:false,upload_started:false,paid_submitted:false,generation_submitted:false,download_started:false}}];
}
export async function createHistoryPage(routing){const {Page}=await import('@jackwener/opencli/browser/page');const page=new Page('site:xyq-web',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);return Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)});}
export async function inspectBoundProjectHistory(context,raw,createPage=createHistoryPage){
  const scope=historyScope(raw);let page;
  try{page=await createPage(boundReadRouting(context));if(!page||typeof page.evaluate!=='function')fail('unsupported_backend','History view requires the public evaluator.');}
  catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','History Page preparation failed.');}
  return(await inspectProjectHistory(Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)}),scope)).map(({result})=>({result:{...result,browser_session:'site:xyq-web',browser_surface:'browser',binding_changed:false}}));
}
