// Current single-audio-node model/sample-rate menus. No upload or generation.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM} from './core.mjs';
import {AUDIO_FILES,audioScope,readAudioFormDOM,audioFormHash} from './audio.mjs';

export const AUDIO_SETTINGS_FILES=[...AUDIO_FILES,'audio-settings.mjs','audio-settings.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
export function audioSettingsDigest(){const h=createHash('sha256');for(const n of AUDIO_SETTINGS_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkAudioSettingsPin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==audioSettingsDigest())fail('definition_changed','Review the audio parameter adapter bundle.');}
export function parseAudioSettings(raw){let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use typed audio parameter JSON.');}
  if(!v||Array.isArray(v)||typeof v!=='object'||Object.keys(v).some(k=>!['expected_form_sha256','model_id','sample_rate_hz'].includes(k))||typeof v.expected_form_sha256!=='string'||!/^[a-f0-9]{64}$/.test(v.expected_form_sha256)||!('model_id'in v||'sample_rate_hz'in v)||'model_id'in v&&(typeof v.model_id!=='string'||!/^[a-z0-9_]{1,64}$/.test(v.model_id))||'sample_rate_hz'in v&&(!Number.isSafeInteger(v.sample_rate_hz)||v.sample_rate_hz<8000||v.sample_rate_hz>192000))fail('invalid_argument','Bind exact form SHA and an observed model ID or integer sample rate.');return v;}

export function readAudioSettingsMenuDOM(t){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/project')return{kind:'origin_mismatch'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==t.project_id||u.searchParams.get('canvasId')!==t.canvas_id)return{kind:'canvas_changed'};
  if(!['model','sample_rate'].includes(t.menu))return{kind:'invalid_argument'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const panels=Array.from(document.querySelectorAll('[data-xyq-selected-audio-footer-panel="true"]')).filter(visible);if(panels.length!==1)return{kind:'audio_form_closed'};
  const selector=t.menu==='model'?'button[data-action="select-audio-model"]':'button[data-action="open-audio-parameter"][data-action-object-id="sample_rate"]';
  const triggers=panels[0].querySelectorAll(selector);if(triggers.length!==1)return{kind:'setting_unavailable'};
  if(triggers[0].getAttribute('data-state')!=='open')return{kind:'options_closed'};
  const roots=Array.from(document.querySelectorAll(t.menu==='model'?'[role="dialog"][data-slot="popover-content"][aria-label="模型选择"]':'[role="menu"][data-slot="dropdown-menu-content"][aria-label="采样率"]')).filter(visible);
  if(roots.length!==1)return{kind:'layout_changed'};const root=roots[0];
  if(t.menu==='sample_rate'&&(!triggers[0].id||root.getAttribute('aria-labelledby')!==triggers[0].id))return{kind:'control_changed'};
  const choices=Array.from(root.querySelectorAll(t.menu==='model'?'button[aria-pressed]':'[role="menuitemradio"]')).filter(visible).map(e=>{
    const disabled=!!e.disabled||e.getAttribute('aria-disabled')==='true'||e.hasAttribute('data-disabled');
    if(t.menu==='model'){const ts=e.querySelectorAll('[data-slot="model-picker-item-title"]'),action=e.getAttribute('data-action')||'',m=/^select-audio-model-([a-z0-9_]{1,64})$/.exec(action);
      return{id:m?.[1]||null,label:ts.length===1?ts[0].innerText.trim():null,checked:e.getAttribute('aria-pressed')==='true',disabled};}
    const value=e.getAttribute('data-action-value'),hz=/^[1-9]\d{3,5}$/.test(value||'')?Number(value):null,label=e.innerText.trim();
    const valid=e.getAttribute('data-action')==='select-audio-parameter'&&e.getAttribute('data-action-object-id')==='sample_rate'&&hz>=8000&&hz<=192000&&label===String(hz/1000)+'kHz';
    return{id:valid?value:null,label,checked:e.getAttribute('aria-checked')==='true',disabled};
  });
  if(!choices.length||choices.length>50||choices.some(e=>!e.id||!e.label||e.label.length>128)||new Set(choices.map(e=>e.id)).size!==choices.length||new Set(choices.map(e=>e.label)).size!==choices.length||choices.filter(e=>e.checked).length!==1)return{kind:'layout_changed'};
  return{kind:'ready',menu:t.menu,choices};
}

export function readAudioSettingsTargetDOM(t){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/project')return{kind:'origin_mismatch'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==t.project_id||u.searchParams.get('canvasId')!==t.canvas_id)return{kind:'canvas_changed'};
  const selectors={model_trigger:'[data-xyq-selected-audio-footer-panel="true"] button[data-action="select-audio-model"]',sample_rate_trigger:'[data-xyq-selected-audio-footer-panel="true"] button[data-action="open-audio-parameter"][data-action-object-id="sample_rate"]',
    model_item:'[role="dialog"][data-slot="popover-content"][aria-label="模型选择"] button[aria-pressed]',sample_rate_item:'[role="menu"][data-slot="dropdown-menu-content"][aria-label="采样率"] [role="menuitemradio"]'};
  if(!Object.hasOwn(selectors,t.kind))return{kind:'invalid_argument'};
  const all=Array.from(document.querySelectorAll(selectors[t.kind]));
  const matches=all.filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]')).filter(e=>!t.kind.endsWith('_item')||(t.kind==='model_item'?e.getAttribute('data-action')==='select-audio-model-'+t.id:e.getAttribute('data-action-value')===t.id));
  if(matches.length!==1)return{kind:'control_changed'};const e=matches[0],r=e.getBoundingClientRect();
  const enabled=!e.disabled&&e.getAttribute('aria-disabled')!=='true'&&!e.hasAttribute('data-disabled');
  // The real canvas rail covers the rate button's center. Probe only bounded
  // interior points and accept a point only when hit-testing the exact control.
  const points=[[.5,.5],[.25,.5],[.75,.5],[.1,.5],[.9,.5],[.5,.25],[.5,.75]];
  let point=null,center_ready=false;
  for(let i=0;i<points.length&&enabled&&r.width>0&&r.height>0;i++){const x=r.x+r.width*points[i][0],y=r.y+r.height*points[i][1],hit=document.elementFromPoint(x,y);if(hit===e||e.contains(hit)){point={x,y};center_ready=i===0;break;}}
  return{kind:'ready',selector:selectors[t.kind],nth:all.indexOf(e),pointer_ready:!!point,center_ready,point};
}

async function state(page,scope){const a=await pollDOM({evaluate:()=>page.evaluate(readAudioFormDOM,scope)},readAudioFormDOM),b=await pollDOM({evaluate:()=>page.evaluate(readAudioFormDOM,scope)},readAudioFormDOM);if(audioFormHash(a)!==audioFormHash(b))fail('draft_changed','Audio form changed during snapshot.');return b;}
function usable(d){if(d.submit_busy)fail('draft_busy','Audio draft is busy.');if(d.files.some(f=>f.files===null))fail('reference_state_unknown','File state is unknown.');}
function closed(d){usable(d);if(d.layers)fail('dialog_open','Existing layers are preserved.');}
const content=d=>sha(JSON.stringify([d.project_id,d.canvas_id,d.node_id,d.prompt,d.prompt_tree,d.prompt_references,d.references,d.files]));
function preserve(a,b){usable(b);if(content(a)!==content(b))fail('draft_changed','Prompt, references or file controls changed during audio parameter input.');}
async function menu(page,scope,kind,form){const m=await pollDOM({evaluate:()=>page.evaluate(readAudioSettingsMenuDOM,{...scope,menu:kind})},readAudioSettingsMenuDOM);if(form.layers!==1||m.choices.find(e=>e.checked).label!==(kind==='model'?form.model:form.sample_rate))fail('settings_changed','Menu selection differs from the current audio form.');return m;}
async function click(page,scope,kind,id){const t=await pollDOM({evaluate:()=>page.evaluate(readAudioSettingsTargetDOM,{...scope,kind,id})},readAudioSettingsTargetDOM);if(!t.pointer_ready)fail('control_obscured','No visible hit-tested area exists on the requested control.');
  if(t.center_ready){if(typeof page.click!=='function')fail('unsupported_backend','Native control clicking is required.');await page.click(t.selector,{nth:t.nth});return false;}
  if(typeof page.clickPoint==='function')await page.clickPoint(t.point);
  else if(typeof page.cdp==='function'){await page.cdp('Input.dispatchMouseEvent',{type:'mouseMoved',...t.point});await page.cdp('Input.dispatchMouseEvent',{type:'mousePressed',...t.point,button:'left',clickCount:1});await page.cdp('Input.dispatchMouseEvent',{type:'mouseReleased',...t.point,button:'left',clickCount:1});}
  else fail('unsupported_backend','A partly covered control needs native point input.');return true;
}
async function closeOwned(page,scope,kind){const d=await state(page,scope);if(!d.layers)return;if(d.layers!==1)fail('cleanup_failed','Another layer is present; no Escape sent.');await menu(page,scope,kind,d);
  if(typeof page.pressKey!=='function')fail('unsupported_backend','Owned menu cleanup needs native Escape.');await page.pressKey('Escape');closed(await state(page,scope));}
async function withMenu(page,scope,kind,fn){let opened=false,output,primary,cleanup;try{const before=await state(page,scope);closed(before);opened=true;
    const point_used=await click(page,scope,kind+'_trigger'),after=await state(page,scope);if(audioFormHash(before)!==audioFormHash(after))fail('draft_changed','Opening the parameter menu changed the draft.');output=await fn(await menu(page,scope,kind,after),after,point_used);
  }catch(e){primary=e;}if(opened)try{await closeOwned(page,scope,kind);}catch(e){cleanup=e;}
  if(primary){if(cleanup)primary.cleanup_code=cleanup.code||'bridge_failed';throw primary;}if(cleanup)throw cleanup;return output;}
function result(d,extra){return[{result:{status:'ready',project_id:d.project_id,canvas_id:d.canvas_id,node_id:d.node_id,form_sha256:audioFormHash(d),model:d.model,sample_rate:d.sample_rate,
  prompt_sha256:sha(d.prompt),references:d.references.map(r=>({type:r.type,reference_sha256:sha(r.id),name_sha256:sha(r.name)})),association:d.association,source:'visible_dom',secrets_returned:false,paid_submitted:false,upload_started:false,persistence_verified:false,...extra}}];}
export async function inspectAudioChoices(page,rawScope){const scope=audioScope(rawScope),before=await state(page,scope);closed(before);const models=await withMenu(page,scope,'model',(m,d,p)=>({choices:m.choices,point_used:p}));let rates=null;
  if(before.sample_rate!==null)rates=await withMenu(page,scope,'sample_rate',(m,d,p)=>({choices:m.choices.map(e=>({...e,hz:Number(e.id)})),point_used:p}));
  const after=await state(page,scope);closed(after);if(audioFormHash(before)!==audioFormHash(after))fail('draft_changed','Audio choices discovery changed the draft.');
  return result(after,{models:models.choices,sample_rates:rates?.choices||null,point_input_used:models.point_used||!!rates?.point_used,coverage:'current_model_options',all_options:false});}
export async function prepareAudioSettings(page,rawScope,raw){const scope=audioScope(rawScope),requested=parseAudioSettings(raw),steps=[];let phase='snapshot',attempted=false,point_used=false;
  try{const before=await state(page,scope);closed(before);if(audioFormHash(before)!==requested.expected_form_sha256)fail('draft_changed','Audio draft differs from the inspected digest; no input sent.');let current=before;
    for(const kind of ['model','sample_rate']){const id=kind==='model'?requested.model_id:requested.sample_rate_hz?.toString();if(id===undefined)continue;
      if(kind==='sample_rate'&&current.sample_rate===null)fail('setting_unavailable','The current model has no sample-rate control.');
      phase=kind+'_menu';await withMenu(page,scope,kind,async(m,form,p)=>{point_used||=p;preserve(before,form);if(audioFormHash(current)!==audioFormHash(form))fail('draft_changed','Draft changed before parameter input.');
        const item=m.choices.find(e=>e.id===id);if(!item||item.disabled)fail('setting_unavailable','Requested parameter is absent or disabled in the current menu.');if(item.checked)return;
        phase=kind+'_input';attempted=true;point_used=await click(page,scope,kind+'_item',id)||point_used;steps.push(kind+'_input');const after=await state(page,scope);preserve(before,after);
        if((kind==='model'?after.model:after.sample_rate)!==item.label)fail('settings_changed','Requested parameter differs from native readback.');if(kind==='sample_rate'&&after.model!==form.model)fail('draft_changed','Sample-rate input changed the model.');current=after;
      });current=await state(page,scope);closed(current);preserve(before,current);
    }
    phase='final_readback';const final=await state(page,scope);closed(final);preserve(before,final);if(audioFormHash(final)!==audioFormHash(current))fail('draft_changed','Audio parameters changed during final readback.');
    return result(final,{status:'prepared',completed_steps:steps,point_input_used:point_used,implicit_sample_rate_change:'model_id'in requested&&!('sample_rate_hz'in requested)&&before.sample_rate!==final.sample_rate?{before:before.sample_rate,after:final.sample_rate}:null});
  }catch(error){const e=error instanceof XyqError?error:new XyqError('bridge_failed','Audio parameter preparation failed; inspect the current draft.');e.phase=phase;e.completed_steps=steps;e.outcome_uncertain=attempted;throw e;}
}
