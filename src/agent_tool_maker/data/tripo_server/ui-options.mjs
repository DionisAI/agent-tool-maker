// Reviewed transient animation/export controls. No generation, download or save.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { StudioError, ORIGIN, unwrap, pollDOM } from './core.mjs';
import { assetId, PANEL, EXPORT_DIALOG, readAssetDOM } from './extended.mjs';
import { WORKSPACE_FILES, inspectWorkspace } from './workspace.mjs';

export const UI_OPTIONS_FILES = [...WORKSPACE_FILES, 'ui-options.mjs', 'ui-options.js'];
export const EXPORT_FORMATS = ['USD','FBX','OBJ','STL','GLB','3MF'];
const sha = value => createHash('sha256').update(value).digest('hex');
const fail = (code,message) => { throw new StudioError(code,message); };
export function uiOptionsDigest() {
  const hash=createHash('sha256');
  for(const name of UI_OPTIONS_FILES)hash.update(name+'\0').update(readFileSync(new URL(name,import.meta.url))).update('\0');
  return hash.digest('hex');
}
export function checkUIOptionsPin(pin) {
  if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==uiOptionsDigest())fail('definition_changed','Review and rebuild UI option definitions.');
}
export function readUIContextDOM() {
  const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;};
  return{origin:location.origin,path:location.pathname,dialogs:[...document.querySelectorAll('[role="dialog"]')].filter(visible).length};
}
async function context(page,id) {
  const value=unwrap(await page.evaluate(readUIContextDOM));
  if(value.dialogs)fail('dialog_open','An existing visible dialog is preserved. Close it locally before preparing new options.');
  if(id&&(value.origin!==ORIGIN||!value.path.endsWith(id)))fail('asset_changed','Source asset changed during the UI operation.');
  return value;
}
export function parseUISettings(operation,raw='{}') {
  let value;try{value=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','settings must be JSON.');}
  const allowed=operation==='animation'?['prompt','duration','expected_prompt_sha256']:operation==='export'?['format','texture_resolution','export_skeleton','fbx_variant','vertex_colors']:[];
  if(!['animation','export'].includes(operation)||!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!allowed.includes(k)))fail('invalid_argument','Use reviewed semantic settings, not selectors or URLs.');
  if('prompt'in value&&(typeof value.prompt!=='string'||value.prompt.length>1000))fail('invalid_argument','prompt must contain 0-1000 characters.');
  if('duration'in value&&(!Number.isInteger(value.duration)||value.duration<1||value.duration>10))fail('invalid_argument','duration must be an integer from 1 to 10 seconds.');
  if('expected_prompt_sha256'in value&&(!/^[a-f0-9]{64}$/.test(value.expected_prompt_sha256)||!('prompt'in value)))fail('invalid_argument','Bind prompt replacement to the exact observed draft digest.');
  if('format'in value&&!EXPORT_FORMATS.includes(value.format))fail('invalid_argument','Select an observed export format.');
  if('texture_resolution'in value&&!['512','1k','2k','4k','8k'].includes(value.texture_resolution))fail('invalid_argument','Select an observed texture resolution.');
  for(const key of ['export_skeleton','vertex_colors'])if(key in value&&typeof value[key]!=='boolean')fail('invalid_argument',key+' must be boolean.');
  if('fbx_variant'in value&&!['Blender','Mixamo','3dsmax'].includes(value.fbx_variant))fail('invalid_argument','Select an observed FBX variant.');
  if(value.fbx_variant&&value.format&&value.format!=='FBX'||'vertex_colors'in value&&value.format&&value.format!=='OBJ')fail('invalid_argument','FBX variant and OBJ vertex colors are format-specific.');
  return value;
}

// Serialized readers depend only on visible DOM, not captured module constants.
export function readAnimationDOM() {
  if(location.origin!=='https://studio.tripo3d.ai')return{kind:'origin_mismatch'};
  if(!/^\/workspace\/animate\//.test(location.pathname))return{kind:'pending'};
  const panels=[...document.querySelectorAll('div.rounded-r-5:has(h2)')].filter(e=>e.getClientRects().length);
  if(!panels.length)return{kind:'pending'};
  if(panels.length!==1)return{kind:'animation_fields_changed'};
  const p=panels[0];if(p.querySelector('h2')?.innerText.trim()!=='Animation')return{kind:'pending'};
  const prompts=[...p.querySelectorAll('textarea[aria-label="Create Your Own Animation"]')];
  const durations=[...p.querySelectorAll('input[type="number"][aria-label="Duration"]')];
  const ranges=[...p.querySelectorAll('input[type="range"][aria-label="Duration"]')];
  const buttons=[...p.querySelectorAll('button.animate-button')];
  if(prompts.length!==1||durations.length!==1||ranges.length!==1||buttons.length!==1)return{kind:'animation_fields_changed'};
  const number=durations[0],range=ranges[0],action=buttons[0],prompt=prompts[0].value;
  if(typeof prompt!=='string'||prompt.length>1000||number.getAttribute('min')!=='1'||number.getAttribute('max')!=='10'||![null,'1'].includes(number.getAttribute('step'))||range.getAttribute('min')!=='1'||range.getAttribute('max')!=='10'||!/^(?:[1-9]|10)$/.test(number.value)||range.value!==number.value)return{kind:'animation_fields_changed'};
  const label=action.innerText.replace(/\s+/g,' ').trim(),price=label.match(/^Generate (\d+)$/);
  if(!price)return{kind:'animation_price_changed'};
  const asset=location.pathname.match(/([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/)?.[1];
  if(!asset)return{kind:'asset_changed'};
  const warnings=[...new Set(p.innerText.split(/\n+/).map(s=>s.trim()).filter(s=>/Rig the Model First|Use a T-|failed|Unknown server error/i.test(s)))];
  const presets=[...p.querySelectorAll('[role="tabpanel"] button:has(img)')].filter(e=>e.getClientRects().length).map(e=>e.innerText.trim());
  if(presets.length>500||presets.some(s=>!s||s.length>100))return{kind:'animation_presets_changed'};
  return{kind:'ready',asset_id:asset,settings:{prompt,duration:Number(number.value)},duration_bounds:{min:1,max:10},
    quoted_credits:Number(price[1]),button_enabled:!action.disabled&&action.getAttribute('aria-disabled')!=='true',
    input_enabled:!prompts[0].disabled&&!number.disabled,warnings,rig_prerequisite_missing:warnings.some(s=>/Rig the Model First/i.test(s)),
    presets,preset_coverage:'currently_rendered_not_authoritative_all',action_label:label};
}
export function animationQuoteHash(data) {
  return sha(JSON.stringify(['tripo-animation-options-v1',data.asset_id,data.settings,data.quoted_credits,data.warnings,data.action_label]));
}
function animationResult(data) {
  return{...data,kind:undefined,status:data.rig_prerequisite_missing?'rig_prerequisite_missing':data.button_enabled?'ready':!data.settings.prompt.trim()?'draft_empty':'action_disabled',
    prompt_sha256:sha(data.settings.prompt),quote_sha256:animationQuoteHash(data),paid_submitted:false,
    acceptance:'visible_animation_options_not_generation_or_preset_application',secrets_returned:false};
}
export async function inspectAnimation(page,args) {
  assetId(args.asset);await context(page);await inspectWorkspace(page,{module:'animate',asset:args.asset});await context(page,args.asset);
  const data=await pollDOM(page,readAnimationDOM);
  if(data.asset_id!==args.asset)fail('asset_changed','Animation source differs from the requested source.');
  return[animationResult(data)];
}
export async function prepareAnimation(page,args) {
  const settings=parseUISettings('animation',args.settings);
  const initial=(await inspectAnimation(page,args))[0];
  if(initial.rig_prerequisite_missing||!initial.input_enabled)fail('prerequisite_missing','Use a rigged source with enabled animation input controls.');
  if('prompt'in settings&&initial.settings.prompt.trim()&&settings.prompt!==initial.settings.prompt&&settings.expected_prompt_sha256!==initial.prompt_sha256)fail('draft_present','The existing animation draft is preserved; bind replacement or clearing to its observed digest.');
  if('duration'in settings&&settings.duration!==initial.settings.duration){
    // OpenCLI 1.8.6 fillText deliberately accepts text inputs, not number.
    // Use the actual spinbutton's bounded native arrow keys, not DOM writes.
    if(typeof page.cdp!=='function'||typeof page.focus!=='function')fail('unsupported_backend','Numeric duration requires documented native focus and CDP keyboard support.');
    await page.focus(PANEL+' input[type="number"][aria-label="Duration"]');
    const up=settings.duration>initial.settings.duration,key=up?'ArrowUp':'ArrowDown',code=up?38:40;
    for(let step=0;step<Math.abs(settings.duration-initial.settings.duration);step++){
      await page.cdp('Input.dispatchKeyEvent',{type:'rawKeyDown',key,code:key,windowsVirtualKeyCode:code});
      await page.cdp('Input.dispatchKeyEvent',{type:'keyUp',key,code:key,windowsVirtualKeyCode:code});
    }
    await page.focus(PANEL+' textarea[aria-label="Create Your Own Animation"]');
  }
  if('prompt'in settings&&settings.prompt!==initial.settings.prompt)await page.fillText(PANEL+' textarea[aria-label="Create Your Own Animation"]',settings.prompt);
  await context(page,args.asset);const data=await pollDOM(page,readAnimationDOM);
  if(data.asset_id!==args.asset)fail('asset_changed','Animation source changed during preparation.');
  for(const[k,v]of Object.entries(settings))if(k!=='expected_prompt_sha256'&&data.settings[k]!==v)fail('settings_changed','The requested animation setting did not match the visible form.');
  return[animationResult(data)];
}

export function readExportOptionsDOM() {
  if(location.origin!=='https://studio.tripo3d.ai')return{kind:'origin_mismatch'};
  const dialogs=[...document.querySelectorAll('[role="dialog"]:has(input[maxlength="255"])')].filter(e=>e.getClientRects().length&&e.getAttribute('data-state')!=='closed');
  if(!dialogs.length)return{kind:'pending'};
  if(dialogs.length!==1)return{kind:'export_fields_changed'};
  const d=dialogs[0],combos=[...d.querySelectorAll('[role="combobox"]')],actions=[...d.querySelectorAll('button.animate-button')];
  if(combos.length!==2||actions.length!==1||actions[0].innerText.trim()!=='Export')return{kind:'export_fields_changed'};
  const format=combos[0].innerText.trim(),resolution=combos[1].innerText.replace(/\s+/g,' ').trim().replace(/ Current$/,'');
  if(!['USD','FBX','OBJ','STL','GLB','3MF'].includes(format)||!['512','1k','2k','4k','8k'].includes(resolution))return{kind:'export_fields_changed'};
  const switches=[...d.querySelectorAll('[role="switch"]')].map((e,nth)=>({nth,label:e.parentElement.innerText.trim(),checked:e.getAttribute('aria-checked'),disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'}));
  if(switches.some(s=>!['Export Skeleton','Export Vertex Colors'].includes(s.label)||!['true','false'].includes(s.checked))||new Set(switches.map(s=>s.label)).size!==switches.length)return{kind:'export_fields_changed'};
  const variants=[...d.querySelectorAll('button[aria-pressed]')].map((e,nth)=>({nth,label:e.innerText.trim(),selected:e.getAttribute('aria-pressed')}));
  if(format==='FBX'?(variants.map(v=>v.label).join(',')!=='Blender,Mixamo,3dsmax'||variants.filter(v=>v.selected==='true').length!==1):variants.length!==0)return{kind:'export_fields_changed'};
  const animationButtons=[...d.querySelectorAll('button')].map((e,nth)=>({nth,text:e.innerText.trim(),role:e.getAttribute('role')})).filter(b=>b.role!=='combobox'&&/^\d+$/.test(b.text));
  if(animationButtons.length>1)return{kind:'export_fields_changed'};
  const asset=location.pathname.match(/([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/)?.[1];
  if(!asset)return{kind:'asset_changed'};
  return{kind:'ready',asset_id:asset,settings:{format,texture_resolution:resolution,
    export_skeleton:switches.some(s=>s.label==='Export Skeleton')?switches.find(s=>s.label==='Export Skeleton').checked==='true':null,
    vertex_colors:switches.some(s=>s.label==='Export Vertex Colors')?switches.find(s=>s.label==='Export Vertex Colors').checked==='true':null,
    fbx_variant:variants.find(v=>v.selected==='true')?.label||null,animation_count:animationButtons.length?Number(animationButtons[0].text):null},
    switches,variants,filename:d.querySelector('input[maxlength="255"]').value,
    button_enabled:!actions[0].disabled&&actions[0].getAttribute('aria-disabled')!=='true'};
}
export function readExportListDOM(index) {
  const lists=[...document.querySelectorAll('[role="listbox"]')].filter(e=>e.getClientRects().length&&e.getAttribute('data-state')!=='closed');
  if(!lists.length)return{kind:'pending'};
  if(lists.length!==1)return{kind:'export_list_changed'};
  const options=[...lists[0].querySelectorAll('[role="option"]')].map(e=>({label:e.innerText.replace(/\s+/g,' ').trim(),disabled:e.getAttribute('aria-disabled')==='true',selected:e.getAttribute('aria-selected')==='true'}));
  if(!options.length||options.length>20||new Set(options.map(o=>o.label)).size!==options.length)return{kind:'export_list_changed'};
  const format=options.every(o=>['USD','FBX','OBJ','STL','GLB','3MF'].includes(o.label));
  const texture=options.every(o=>['512','1k','2k','4k','8k'].includes(o.label.replace(/ Current$/,'')));
  if(!format&&!texture)return{kind:'export_list_changed'};
  if(index===0&&!format||index===1&&!texture)return{kind:'pending'};
  return{kind:'ready',options,list_kind:format?'format':'texture'};
}
export function readExportListClosedDOM() {
  // data-state=closed starts the animation; its layer still intercepts input.
  // Wait until layout is gone before clicking the next combobox underneath.
  const open=[...document.querySelectorAll('[role="listbox"]')].some(e=>e.getClientRects().length);
  return{kind:open?'pending':'ready'};
}
export function readExportTargetDOM(spec) {
  const elements=[...document.querySelectorAll(spec.kind==='option'?'[role="listbox"] [role="option"]':spec.kind==='variant'?'[role="dialog"]:has(input[maxlength="255"]) button[aria-pressed]':'main button')];
  const matches=elements.map((e,nth)=>({e,nth})).filter(({e})=>e.getClientRects().length&&e.innerText.replace(/\s+/g,' ').trim()===spec.label&&(spec.kind!=='open'||!e.closest('[role="dialog"]')));
  if(!matches.length)return{kind:'pending'};
  if(matches.length!==1||matches[0].e.disabled||matches[0].e.getAttribute('aria-disabled')==='true')return{kind:'export_control_changed'};
  const {e,nth}=matches[0],r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return{kind:'ready',nth,pointer_ready:hit===e||!!hit&&e.contains(hit)};
}
async function exportClick(page,kind,label) {
  const target=await pollDOM({evaluate:()=>page.evaluate(readExportTargetDOM,{kind,label})},readExportTargetDOM);
  if(!target.pointer_ready)fail('control_obscured','The observed export control is covered; no click was dispatched.');
  await page.click(kind==='option'?'[role="listbox"] [role="option"]':kind==='variant'?EXPORT_DIALOG+' button[aria-pressed]':'main button',{nth:target.nth});
}
async function exportList(page,index,requested) {
  await page.click(EXPORT_DIALOG+' [role="combobox"]',{nth:index});
  let list;
  try{list=await pollDOM({evaluate:()=>page.evaluate(readExportListDOM,index)},readExportListDOM);}
  catch(error){if(!(error instanceof StudioError)||error.code!=='page_not_ready')throw error;
    const observed=unwrap(await page.evaluate(readExportListDOM));
    const labels=(observed.options||[]).map(o=>o.label).filter(s=>[...EXPORT_FORMATS,'512','1k','2k','4k','8k','8k Current','4k Current','2k Current','1k Current'].includes(s));
    fail('export_list_timeout','Expected '+(index===0?'format':'texture')+' list; observed kind='+observed.kind+', known labels='+labels.join(',')+'. No option was clicked.');}
  if(requested!==undefined){const item=list.options.filter(o=>o.label.replace(/ Current$/,'')===requested);if(item.length!==1||item[0].disabled)fail('setting_unavailable','The requested export option is not enabled in the observed list.');await exportClick(page,'option',item[0].label);}
  else {const current=list.options.filter(o=>o.selected&&!o.disabled);if(current.length!==1)fail('export_list_changed','Expected exactly one currently selected enabled option.');await exportClick(page,'option',current[0].label);}
  try{await pollDOM(page,readExportListClosedDOM);}catch(error){if(error instanceof StudioError&&error.code==='page_not_ready')fail('export_list_stuck','The '+(index===0?'format':'texture')+' list did not close after selecting its exact observed option.');throw error;}
  await pollDOM(page,readExportOptionsDOM);
  return list.options;
}
export function readOwnExportClosedDOM(id) {
  if(location.origin!=='https://studio.tripo3d.ai'||!location.pathname.endsWith(id))return{kind:'asset_changed'};
  const open=[...document.querySelectorAll('[role="dialog"]:has(input[maxlength="255"])')].some(e=>e.getClientRects().length);
  return{kind:open?'pending':'ready'};
}
export function readOwnExportCloseDOM() {
  const buttons=[...document.querySelectorAll('[role="dialog"]:has(input[maxlength="255"]) button:has([class~="i-tripo:close"])')].filter(e=>e.getClientRects().length);
  if(!buttons.length)return{kind:'pending'};
  if(buttons.length!==1)return{kind:'dialog_changed'};
  const e=buttons[0],r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return{kind:'ready',pointer_ready:hit===e||!!hit&&e.contains(hit)};
}
async function closeOwnExport(page,id) {
  const data=unwrap(await page.evaluate(readExportOptionsDOM));
  if(data.kind==='pending')return;
  if(data.kind!=='ready'||data.asset_id!==id)fail('dialog_changed','Changed export dialog is preserved for local inspection.');
  // Dropdown is a separate layer: close it first, then only our own export.
  const list=unwrap(await page.evaluate(readExportListDOM));
  if(list.kind==='ready'){const current=list.options.filter(o=>o.selected&&!o.disabled);if(current.length!==1)fail('dialog_changed','Unexpected export list is preserved.');await exportClick(page,'option',current[0].label);await pollDOM(page,readExportListClosedDOM);}
  else if(list.kind!=='pending')fail('dialog_changed','Unexpected export list is preserved.');
  const close=await pollDOM(page,readOwnExportCloseDOM);
  if(!close.pointer_ready)fail('control_obscured','The owned dialog close button is covered; no click was dispatched.');
  await page.click(EXPORT_DIALOG+' button:has([class~="i-tripo:close"])');
  await pollDOM({evaluate:()=>page.evaluate(readOwnExportClosedDOM,id)},readOwnExportClosedDOM);
}
async function exportOptions(page,args,prepare) {
  assetId(args.asset);const settings=prepare?parseUISettings('export',args.settings):{};
  await context(page);await inspectWorkspace(page,{module:'model',asset:args.asset});await context(page,args.asset);
  const model=await pollDOM(page,readAssetDOM);
  if(model.asset_id!==args.asset||model.status!=='ready'||!model.export_enabled)fail('model_not_ready','Use a completed model with an enabled Export control.');
  let owned=false,result,error;
  try {
    await exportClick(page,'open','Export');owned=true;
    let data=await pollDOM(page,readExportOptionsDOM);
    const formats=await exportList(page,0,settings.format),resolutions=await exportList(page,1,settings.texture_resolution);
    if(formats.some(o=>!EXPORT_FORMATS.includes(o.label)))fail('export_format_changed','The visible format list changed; review it before preparation.');
    data=await pollDOM(page,readExportOptionsDOM);
    if('fbx_variant'in settings){if(data.settings.format!=='FBX')fail('setting_unavailable','FBX variant requires the visible FBX form.');await exportClick(page,'variant',settings.fbx_variant);}
    for(const[key,label]of [['export_skeleton','Export Skeleton'],['vertex_colors','Export Vertex Colors']])if(key in settings){
      const control=data.switches.find(s=>s.label===label);if(!control||control.disabled)fail('setting_unavailable','The requested switch is not enabled for this model/format.');
      await page.setChecked(EXPORT_DIALOG+' [role="switch"]',settings[key],{nth:control.nth});
    }
    data=await pollDOM(page,readExportOptionsDOM);
    if(data.asset_id!==args.asset)fail('asset_changed','Export source changed during preparation.');
    for(const[k,v]of Object.entries(settings))if(data.settings[k]!==v)fail('settings_changed','Requested export settings differ from the visible dialog.');
    result={status:prepare?'prepared':'observed',asset_id:args.asset,settings:data.settings,available_formats:formats,available_texture_resolutions:resolutions,
      switches:data.switches,variants:data.variants,button_enabled:data.button_enabled,
      options_sha256:sha(JSON.stringify(['tripo-export-options-v1',data.asset_id,data.settings])),
      quoted_credits:null,paid_submitted:false,download_started:false,secrets_returned:false,
      acceptance:'visible_export_options_not_quote_or_download',dialog_closed:true,
      options_lifetime:'ui_may_remember_options_recheck_before_any_export'};
  } catch(caught){error=caught;}
  if(owned)try{await closeOwnExport(page,args.asset);}catch(cleanup){fail('cleanup_failed','Own export dialog needs local inspection; original error code: '+(error instanceof StudioError?error.code:'bridge_failure')+'.');}
  if(error)throw error;
  return[result];
}
export async function inspectExportOptions(page,args){return exportOptions(page,args,false);}
export async function prepareExportOptions(page,args){return exportOptions(page,args,true);}
