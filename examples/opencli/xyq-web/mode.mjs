// Current homepage media-mode selection; no draft clearing/upload/generation.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM,readHomeDOM} from './core.mjs';
import {FORM_FILES,readDraftDOM,draftHash} from './form.mjs';
export const MODE_FILES=[...FORM_FILES,'mode.mjs','mode.js'];
export const MEDIA_MODES=['图片生成','视频生成','音频生成'];
const fail=(code,message)=>{throw new XyqError(code,message);};
export function modeDigest(){const h=createHash('sha256');for(const n of MODE_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkModePin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==modeDigest())fail('definition_changed','Review the media-mode adapter bundle.');}
export function parseModeSettings(raw){let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','settings must be JSON.');}
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!['expected_draft_sha256','mode'].includes(k))||!/^[a-f0-9]{64}$/.test(v.expected_draft_sha256||'')||!MEDIA_MODES.includes(v.mode))fail('invalid_argument','Use an exact draft digest and image/video/audio mode.');return v;}

export function readModeMenuDOM(){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const trigger=document.querySelector('#title-section-prompt-container button[aria-label="选择创作模式"]');
  if(!trigger||!trigger.getClientRects().length||trigger.closest('[hidden]'))return{kind:'pending'};
  if(trigger.getAttribute('data-state')!=='open')return{kind:'mode_closed'};
  const menus=Array.from(document.querySelectorAll('[role="menu"][data-slot="dropdown-menu-content"]')).filter(visible).filter(e=>e.querySelector('[role="menuitemradio"] [data-slot="dropdown-menu-item-title"]'));
  if(menus.length!==1)return{kind:'layout_changed'};
  if(!trigger.id||!menus[0].id||trigger.getAttribute('aria-controls')!==menus[0].id||menus[0].getAttribute('aria-labelledby')!==trigger.id||trigger.getAttribute('aria-expanded')!=='true')return{kind:'mode_context_changed'};
  // Badges like 沉浸式短片 are part of the AX name, but not the mode title.
  const title=e=>{const walk=x=>x.nodeType===3?x.textContent:x.nodeType===1&&x.getAttribute('data-slot')==='badge'?'':Array.from(x.childNodes).map(walk).join('');return walk(e).replace(/\s+/g,' ').trim();};
  const items=Array.from(menus[0].querySelectorAll('[role="menuitemradio"]')).map(e=>{const ts=e.querySelectorAll('[data-slot="dropdown-menu-item-title"]');return{label:ts.length===1?title(ts[0]):null,checked:e.getAttribute('aria-checked')==='true',disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'||e.hasAttribute('data-disabled')};});
  if(!items.length||items.length>20||items.some(e=>!e.label||e.label.length>128)||new Set(items.map(e=>e.label)).size!==items.length||items.filter(e=>e.checked).length!==1||items.find(e=>e.checked).label!==trigger.innerText.trim())return{kind:'layout_changed'};
  return{kind:'ready',items:items.map(x=>({...x,eligible:['图片生成','视频生成','音频生成'].includes(x.label)}))};
}
const TRIGGER='#title-section-prompt-container button[aria-label="选择创作模式"]';
const ITEMS='[role="menu"][data-slot="dropdown-menu-content"] [role="menuitemradio"]';
export function readModeTargetDOM(t){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/home')return{kind:'origin_mismatch'};
  if(!['trigger','item'].includes(t.kind))return{kind:'invalid_argument'};
  const all=Array.from(document.querySelectorAll(t.kind==='trigger'?'#title-section-prompt-container button[aria-label="选择创作模式"]':'[role="menu"][data-slot="dropdown-menu-content"] [role="menuitemradio"]'));
  const title=e=>{const p=e.querySelector('[data-slot="dropdown-menu-item-title"]');if(!p)return null;const walk=x=>x.nodeType===3?x.textContent:x.nodeType===1&&x.getAttribute('data-slot')==='badge'?'':Array.from(x.childNodes).map(walk).join('');return walk(p).replace(/\s+/g,' ').trim();};
  const trigger=document.querySelector('#title-section-prompt-container button[aria-label="选择创作模式"]');
  const matches=all.filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]')).filter(e=>{
    if(t.kind==='trigger')return true;
    const m=e.closest('[role="menu"][data-slot="dropdown-menu-content"]');return title(e)===t.label&&!!trigger?.id&&!!m?.id&&m.getAttribute('aria-labelledby')===trigger.id&&trigger.getAttribute('aria-controls')===m.id&&trigger.getAttribute('aria-expanded')==='true'&&trigger.getAttribute('data-state')==='open';
  });
  if(matches.length!==1)return{kind:'control_changed'};
  const e=matches[0],r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return{kind:'ready',nth:all.indexOf(e),pointer_ready:r.width>0&&r.height>0&&!e.disabled&&e.getAttribute('aria-disabled')!=='true'&&!e.hasAttribute('data-disabled')&&(hit===e||e.contains(hit))};
}
async function snapshot(page,owned=false){const read=fn=>pollDOM({evaluate:()=>page.evaluate(fn,{owned_mode_menu:owned})},fn);const home=await read(readHomeDOM);if(home.agent!=='创作'||!home.form||!MEDIA_MODES.includes(home.form.mode))fail('unsupported_surface','Use the current creative image/video/audio composer.');
  const draft=await read(readDraftDOM),after=await read(readHomeDOM);
  if(home.form.mode!==after.form?.mode||home.form.preferences!==after.form.preferences||JSON.stringify(home.form.canvas)!==JSON.stringify(after.form.canvas))fail('draft_changed','Form changed during snapshot.');return{home,draft};}
const fileState=s=>s.draft.files.every(f=>f.files!==null);
const empty=s=>!s.draft.prompt&&!s.draft.rich_references&&!s.draft.media.length&&!s.draft.attachment_present&&s.draft.files.every(f=>f.files?.length===0);
function closed(s){if(s.draft.layers||s.home.form.preferences_open)fail('dialog_open','Existing layers are preserved.');}
async function click(page,t){const d=await pollDOM({evaluate:()=>page.evaluate(readModeTargetDOM,t)},readModeTargetDOM);if(!d.pointer_ready)fail('control_obscured','Mode control is disabled or covered; no input sent.');await page.click(t.kind==='trigger'?TRIGGER:ITEMS,{nth:d.nth});}
function result(s,extra={}){return[{result:{status:'ready',mode:s.home.form.mode,draft_sha256:draftHash(s),preferences:s.home.form.preferences,
  references_known:fileState(s),source:'visible_dom',secrets_returned:false,paid_submitted:false,upload_started:false,...extra}}];}
async function closeOwned(page){const s=await snapshot(page,true);if(!s.draft.layers)return;
  if(s.draft.layers!==1)fail('cleanup_failed','Another layer is present; no Escape sent.');
  await pollDOM(page,readModeMenuDOM);if(typeof page.pressKey!=='function')fail('unsupported_backend','Owned mode-menu cleanup needs native Escape.');
  await page.pressKey('Escape');closed(await snapshot(page));}
async function owned(page,fn){let opened=false,primary,output;
  try{const before=await snapshot(page);closed(before);opened=true;await click(page,{kind:'trigger'});
    const s=await snapshot(page,true);if(s.draft.layers!==1||draftHash(s)!==draftHash(before))fail('draft_changed','Opening the mode menu changed the draft or other layers.');
    output=await fn(await pollDOM(page,readModeMenuDOM),before);
  }catch(e){primary=e;}
  let cleanup;if(opened)try{await closeOwned(page);}catch(e){cleanup=e;}
  if(primary){if(cleanup)primary.cleanup_code=cleanup.code||'bridge_failed';throw primary;}
  if(cleanup)throw cleanup;return output;}
export async function inspectModeChoices(page){const before=await snapshot(page);closed(before);const menu=await owned(page,async m=>m),after=await snapshot(page);closed(after);if(draftHash(before)!==draftHash(after))fail('draft_changed','Mode discovery changed the draft.');return result(after,{items:menu.items});}
export async function prepareMode(page,raw){const requested=parseModeSettings(raw),steps=[];let phase='snapshot';
  try{const before=await snapshot(page);closed(before);if(draftHash(before)!==requested.expected_draft_sha256)fail('draft_changed','Draft differs from the inspected digest; no input sent.');
    if(before.home.form.mode===requested.mode)return result(before,{status:'prepared',completed_steps:steps,implicit_changes:{}});
    if(!fileState(before))fail('reference_state_unknown','File state is unknown; mode selection stops before input.');
    if(!empty(before))fail('draft_not_empty','Mode switching requires an empty draft; existing content and references stay intact.');
    phase='mode_menu';await owned(page,async(menu,current)=>{
      if(draftHash(current)!==requested.expected_draft_sha256)fail('draft_changed','Draft changed before mode input.');
      const item=menu.items.find(x=>x.label===requested.mode&&x.eligible);
      if(!item||item.disabled)fail('setting_unavailable','Requested media mode is not enabled in this menu.');
      phase='mode_input';await click(page,{kind:'item',label:item.label});steps.push('mode_input');
    });
    phase='final_readback';const after=await snapshot(page);closed(after);
    if(!fileState(after))fail('reference_state_unknown','File state became unknown after mode selection; inspect the current draft.');
    if(!empty(after))fail('draft_changed','Mode input changed content or references; inspect the current draft.');
    if(after.home.form.mode!==requested.mode)fail('settings_changed','Media mode differs from final readback.');
    return result(after,{status:'prepared',completed_steps:steps,implicit_changes:{preferences:{before:before.home.form.preferences,after:after.home.form.preferences},canvas:{before:before.home.form.canvas,after:after.home.form.canvas}}});
  }catch(error){const e=error instanceof XyqError?error:new XyqError('bridge_failed','Native mode selection failed; inspect the current form.');e.phase=phase;e.completed_steps=steps;throw e;}
}
