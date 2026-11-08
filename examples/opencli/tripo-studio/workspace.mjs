// Domain-specific visible workspace forms; no arbitrary JS, selectors or URLs.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { StudioError, ORIGIN, unwrap, pollDOM, readAccountDOM } from './core.mjs';
import { EXTENDED_FILES, PANEL, assetId, inspectAsset, claimedOperation, validateExecution, readLocation } from './extended.mjs';

export const WORKSPACE_FILES = [...EXTENDED_FILES, 'workspace.mjs', 'workspace.js'];
export const MODULES = {
  model: ['Model','generate','Generate Model'], image: ['Image','generate-image','Generate Image'],
  segment: ['Segment','segmentation','Segmentation'], fill_parts: ['Fill Parts','fill-parts','Fill Parts'],
  retopo: ['Retopo','retopology','Retopology'], smart_uv: ['Smart UV','smart-uv','Smart UV'],
  texture: ['Texture','texture','3D Model Texture Generator'], edit: ['Edit','texture-edit','Magic Brush'],
  upscale: ['Upscale','texture-upscale','Texture Upscale'], pbr: ['PBR','texture-pbr','PBR Generator'],
  rig: ['Rig','rigging','3D Rigging'], animate: ['Animate','animate','Animation'],
};
export const MODULE_PARENTS={fill_parts:'segment',edit:'texture',upscale:'texture',pbr:'texture',animate:'rig'};
export const SUBMIT_MODULES = ['segment','texture','edit','upscale','pbr'];
const sha = value => createHash('sha256').update(value).digest('hex');
export function workspaceDigest() {
  const hash = createHash('sha256');
  for (const name of WORKSPACE_FILES) hash.update(name+'\0').update(readFileSync(new URL(name,import.meta.url))).update('\0');
  return hash.digest('hex');
}
export function checkWorkspacePin(pin) {
  if (!/^[a-f0-9]{64}$/.test(pin||'') || pin !== workspaceDigest()) throw new StudioError('definition_changed','Review workspace source and rebuild definitions.');
}
export function moduleName(name) {
  if (!Object.hasOwn(MODULES,name)) throw new StudioError('invalid_argument','Select an observed Workspace module.');
  return name;
}
export function readWorkspaceLinkDOM(label) {
  if (location.origin !== 'https://studio.tripo3d.ai') return {kind:'origin_mismatch'};
  const allLinks = [...document.querySelectorAll('a[href]')];
  const links = allLinks.filter(e=>e.innerText.trim()===label && !e.closest('[role="tabpanel"]'));
  if (!links.length) return {kind:'pending'};
  if (links.length!==1) return {kind:'workspace_navigation_changed'};
  const e=links[0], r=e.getBoundingClientRect(), url=new URL(e.getAttribute('href'),location.origin);
  if (url.origin!==location.origin || !url.pathname.startsWith('/workspace/') || url.search || url.hash) return {kind:'workspace_navigation_changed'};
  const group=e.parentElement,collapsed=group?.getAttribute('data-state')==='closed'&&r.height===0;
  const parent=collapsed?[...group.querySelectorAll(':scope > a')].find(a=>a!==e&&a.getBoundingClientRect().height>0):null;
  // Rigged models expose a second same-href link inside the form. Bind the
  // single click to the semantic link actually inspected, not every same URL.
  const nth=allLinks.filter(a=>a.getAttribute('href')===e.getAttribute('href')).indexOf(e);
  return {kind:'ready',href:e.getAttribute('href'),nth,collapsed,parent_label:parent?.innerText.trim()||null,
    available:r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none'&&e.getAttribute('aria-disabled')!=='true'};
}
export function readWorkspaceDOM(module) {
  const contracts={model:['generate','Generate Model'],image:['generate-image','Generate Image'],segment:['segmentation','Segmentation'],
    fill_parts:['fill-parts','Fill Parts'],retopo:['retopology','Retopology'],smart_uv:['smart-uv','Smart UV'],texture:['texture','3D Model Texture Generator'],
    edit:['texture-edit','Magic Brush'],upscale:['texture-upscale','Texture Upscale'],pbr:['texture-pbr','PBR Generator'],rig:['rigging','3D Rigging'],animate:['animate','Animation']};
  const actions={model:'Generate',image:'Generate Image',segment:'Start Segmenting',retopo:'Retopology',texture:'Generate Texture',edit:'Generate Preview',upscale:'Enhance Now',pbr:'Generate PBR',rig:'Auto Rig',smart_uv:'Unwrap UV',animate:'Generate'};
  if (!Object.hasOwn(contracts,module)) return {kind:'invalid_argument'};
  if (location.origin!=='https://studio.tripo3d.ai') return {kind:'origin_mismatch'};
  const [route,heading]=contracts[module];
  if(heading===null)return{kind:'workspace_heading_unreviewed'};
  if (!new RegExp('^/workspace/'+route+'(?:/|$)').test(location.pathname)) return {kind:'pending'};
  const panels=[...document.querySelectorAll('div.rounded-r-5:has(h2)')].filter(e=>e.getClientRects().length);
  if (panels.length>1) return {kind:'workspace_panel_changed'};
  if (!panels.length) return /Something went wrong|Please try again later/.test(document.querySelector('main')?.innerText||'')?{kind:'site_error'}:{kind:'pending'};
  const panel=panels[0], title=panel.querySelector('h2')?.innerText.trim();
  if (title!==heading) return {kind:Object.values(contracts).some(c=>c[1]===title)?'pending':'workspace_heading_changed'};
  // Animation presets are a separate large list, not form-setting controls.
  const buttons=[...panel.querySelectorAll('button')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&!e.closest('[role="tabpanel"]');});
  const active=e=>e.getAttribute('aria-pressed')==='true'||e.getAttribute('data-state')==='on'||e.classList.contains('ring-purple-1')||e.classList.contains('border-purple-1');
  const firstLine=e=>e.innerText.trim().split(/\n/)[0].trim();
  const choices=buttons.filter(e=>e.innerText.trim()&&active(e)).map(firstLine);
  const fields=[...panel.querySelectorAll('input:not([type="file"]),textarea')].filter(e=>!e.closest('[role="tabpanel"]')).map(e=>({type:e.getAttribute('type')||e.tagName.toLowerCase(),placeholder:e.getAttribute('placeholder'),value:e.value,
    min:e.getAttribute('min'),max:e.getAttribute('max'),checked:['checkbox','radio'].includes(e.getAttribute('type'))?e.checked:null}));
  if (fields.some(f=>typeof f.value!=='string'||f.value.length>10000)||buttons.length>60) return {kind:'workspace_fields_changed'};
  const switches=[...panel.querySelectorAll('[role="switch"]')].map(e=>e.getAttribute('aria-checked'));
  if (switches.some(value=>!['true','false'].includes(value))) return {kind:'workspace_fields_changed'};
  const combos=[...panel.querySelectorAll('[role="combobox"]')].map(e=>e.innerText.trim());
  const files=[...panel.querySelectorAll('input[type="file"]')].map(e=>e.files?.length||0);
  const previews=[...panel.querySelectorAll('img')].map(e=>{try{const url=new URL(e.getAttribute('src'),location.origin);return url.origin+url.pathname;}catch{return null;}});
  const candidates=buttons.filter(e=>e.classList.contains('animate-button'));
  if (candidates.length>1) return {kind:'workspace_action_changed'};
  const action=candidates[0]||null, label=action?.innerText.trim().replace(/\s+/g,' ')||null;
  if (action&&(!actions[module]||!(label===actions[module]||label.startsWith(actions[module]+' ')))) return {kind:'workspace_action_changed'};
  const price=action?label.slice(actions[module].length).trim():'';
  if (price&&!/^\d+$/.test(price)) return {kind:'workspace_price_changed'};
  const credit=document.querySelector('header [class~="i-tripo:bolt:search"]')?.parentElement?.querySelector('p[title]')?.getAttribute('title');
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(credit||'')) return {kind:'pending'};
  const match=location.pathname.match(/([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/);
  const warnings=[...new Set(panel.innerText.split(/\n+/).map(s=>s.trim()).filter(s=>/Not Ready|Use a T-|Unknown server error|failed|segmented model|select.*model|Rig the Model First/i.test(s)))];
  const radios=[...panel.querySelectorAll('[role="radio"]')].map(e=>({label:e.innerText.trim(),checked:e.getAttribute('aria-checked')}));
  if(radios.some(r=>!['true','false'].includes(r.checked)))return{kind:'workspace_fields_changed'};
  const settings={choices,fields,switches,combos,radios,file_counts:files,previews};
  if (module==='segment') { const selected=choices.filter(s=>['Simple','Balanced','Detailed'].includes(s));if(selected.length!==1)return{kind:'workspace_selection_changed'};settings.detail_level=selected[0]; }
  if (module==='upscale') { const selected=choices.filter(s=>['4K','8K'].includes(s));if(selected.length!==1)return{kind:'workspace_selection_changed'};settings.resolution=selected[0]; }
  if (module==='texture') { const selected=choices.filter(s=>['2K','4K','8K'].includes(s));if(selected.length!==1||fields.length!==1||switches.length!==1)return{kind:'workspace_fields_changed'};settings.resolution=selected[0];settings.prompt=fields[0].value;settings.remove_lighting=switches[0]==='true'; }
  if (module==='edit') { const prompt=fields.find(f=>f.type==='textarea'),strength=fields.find(f=>f.type==='text');if(!prompt||!strength||!/^0(?:\.\d+)?$|^1(?:\.0+)?$/.test(strength.value))return{kind:'workspace_fields_changed'};settings.prompt=prompt.value;settings.creativity_strength=Number(strength.value); }
  const presets=module==='animate'?[...panel.querySelectorAll('[role="tabpanel"] button')].map(firstLine).filter(s=>s&&!['Rig','More'].includes(s)):[];
  if(presets.length>500)return{kind:'workspace_presets_changed'};
  return {kind:'ready',module,asset_id:match?.[1]||null,heading:title,credits:Number(credit.replaceAll(',','')),settings,warnings,presets,
    action_label:label,button_enabled:!!action&&!action.disabled&&action.getAttribute('aria-disabled')!=='true',quoted_credits:price===''?null:Number(price),
    controls:buttons.map(e=>({label:e.innerText.trim().replace(/\s+/g,' '),disabled:e.disabled,selected:active(e)}))};
}
export function workspaceQuoteHash(data) {
  return sha(JSON.stringify(['tripo-workspace-v1',data.module,data.asset_id,data.quoted_credits,data.action_label,data.settings,data.warnings]));
}
async function navigate(page,module,asset) {
  moduleName(module);if(asset)assetId(asset);
  let where=unwrap(await page.evaluate(readLocation));
  if (asset && (where.origin!==ORIGIN||!where.path.endsWith(asset))) {
    await inspectAsset(page,{asset,wait:20});where=unwrap(await page.evaluate(readLocation));
  } else if(where.origin!==ORIGIN) { await page.goto(ORIGIN+'/');await pollDOM(page,readAccountDOM); }
  const label=MODULES[module][0];
  let target=unwrap(await page.evaluate(readWorkspaceLinkDOM,label));
  if (target.kind==='pending') {
    const entry=await pollDOM({evaluate:()=>page.evaluate(readWorkspaceLinkDOM,'3D Workspace')},readWorkspaceLinkDOM);
    if(!entry.available)throw new StudioError('workspace_unavailable','Workspace entry is not interactable.');
    await page.click('a[href='+JSON.stringify(entry.href)+']',{nth:entry.nth});
    target=await pollDOM({evaluate:()=>page.evaluate(readWorkspaceLinkDOM,label)},readWorkspaceLinkDOM);
  }
  if(target.kind!=='ready')throw new StudioError(target.kind,'Workspace navigation contract changed.');
  const parentModule=MODULE_PARENTS[module];
  if(!target.available&&target.collapsed&&parentModule&&target.parent_label===MODULES[parentModule][0]) {
    const parent=await pollDOM({evaluate:()=>page.evaluate(readWorkspaceLinkDOM,MODULES[parentModule][0])},readWorkspaceLinkDOM);
    if(!parent.available)throw new StudioError('workspace_navigation_changed','Collapsed group has no interactable parent.');
    await page.click('a[href='+JSON.stringify(parent.href)+']',{nth:parent.nth});
    target=await pollDOM({evaluate:async()=>{const next=unwrap(await page.evaluate(readWorkspaceLinkDOM,label));return next.kind==='ready'&&!next.available?{kind:'pending'}:next;}},readWorkspaceLinkDOM);
  }
  if(!target.available)return{status:'unavailable',module,asset_id:asset||null,reason:'module_entry_not_interactable',paid_submitted:false,secrets_returned:false};
  if(where.path!==new URL(target.href,ORIGIN).pathname)await page.click('a[href='+JSON.stringify(target.href)+']',{nth:target.nth});
  const data=await pollDOM({evaluate:()=>page.evaluate(readWorkspaceDOM,module)},readWorkspaceDOM);
  if(asset&&data.asset_id!==asset)throw new StudioError('asset_changed','Workspace did not preserve the selected source asset.');
  return data;
}
function result(data) {
  if(data.status==='unavailable')return data;
  return{...data,kind:undefined,prompt_sha256:typeof data.settings.prompt==='string'?sha(data.settings.prompt):null,
    status:data.button_enabled?'ready':'prerequisite_missing',quote_sha256:data.quoted_credits===null?null:workspaceQuoteHash(data),
    quote_known:data.quoted_credits!==null,paid_submitted:false,secrets_returned:false,acceptance:'visible_workspace_form_not_submitted'};
}
export async function inspectWorkspace(page,args){return[result(await navigate(page,args.module,args.asset))];}
export function parseWorkspaceSettings(module,raw='{}') {
  moduleName(module);let value;
  try{value=typeof raw==='string'?JSON.parse(raw):raw;}catch{throw new StudioError('invalid_argument','settings must be JSON.');}
  const allowed={segment:['detail_level'],upscale:['resolution'],texture:['resolution','prompt','remove_lighting','expected_prompt_sha256'],edit:['prompt','creativity_strength','expected_prompt_sha256'],pbr:[]}[module];
  if(!allowed||!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!allowed.includes(k)))throw new StudioError('invalid_argument','Use reviewed settings for this module.');
  if('detail_level'in value&&!['Simple','Balanced','Detailed'].includes(value.detail_level))throw new StudioError('invalid_argument','Select Simple, Balanced or Detailed.');
  if('resolution'in value&&!(module==='texture'?['2K','4K','8K']:['4K','8K']).includes(value.resolution))throw new StudioError('invalid_argument','Select an observed resolution.');
  if('prompt'in value&&(typeof value.prompt!=='string'||value.prompt.length>1000))throw new StudioError('invalid_argument','prompt must be 0-1000 characters; empty clears only an explicitly bound draft.');
  if('remove_lighting'in value&&typeof value.remove_lighting!=='boolean')throw new StudioError('invalid_argument','remove_lighting must be boolean.');
  if('creativity_strength'in value&&(typeof value.creativity_strength!=='number'||!Number.isFinite(value.creativity_strength)||value.creativity_strength<0||value.creativity_strength>1))throw new StudioError('invalid_argument','creativity_strength must be 0-1.');
  if('expected_prompt_sha256'in value&&(!/^[a-f0-9]{64}$/.test(value.expected_prompt_sha256)||!('prompt'in value)))throw new StudioError('invalid_argument','Bind an intended prompt replacement to the exact previous prompt SHA256.');
  return value;
}
export function readChoiceDOM(label) {
  const matches=[...document.querySelectorAll('div.rounded-r-5:has(h2) button')].map((e,nth)=>({e,nth})).filter(({e})=>{
    const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&e.innerText.trim().split(/\n/)[0].trim()===label&&!e.disabled&&!e.classList.contains('animate-button');
  });return{kind:matches.length===1?'ready':matches.length===0?'pending':'workspace_choice_ambiguous',nth:matches[0]?.nth};
}
export async function prepareWorkspace(page,args) {
  const settings=parseWorkspaceSettings(args.module,args.settings);assetId(args.asset);
  let data=await navigate(page,args.module,args.asset);
  if(data.status==='unavailable')throw new StudioError('prerequisite_missing','The source has no interactable module entry.');
  // Preserve existing human prompts instead of overwriting a different draft.
  if('prompt'in settings&&data.settings.prompt?.trim()&&settings.prompt!==data.settings.prompt&&settings.expected_prompt_sha256!==sha(data.settings.prompt))throw new StudioError('draft_present','Existing prompt is preserved; explicitly bind replacement to the observed prompt digest.');
  for(const label of [settings.detail_level,settings.resolution].filter(Boolean)) {
    const target=await pollDOM({evaluate:()=>page.evaluate(readChoiceDOM,label)},readChoiceDOM);
    await page.click(PANEL+' button',{nth:target.nth});
  }
  if('prompt'in settings&&settings.prompt!==data.settings.prompt)await page.fillText(PANEL+' textarea',settings.prompt);
  if('creativity_strength'in settings){await page.fillText(PANEL+' input[type="text"]',String(settings.creativity_strength));await page.pressKey('Tab');}
  if('remove_lighting'in settings)await page.setChecked(PANEL+' [role="switch"]',settings.remove_lighting);
  data=await pollDOM({evaluate:()=>page.evaluate(readWorkspaceDOM,args.module)},readWorkspaceDOM);
  for(const[k,v]of Object.entries(settings))if(k!=='expected_prompt_sha256'&&data.settings[k]!==v)throw new StudioError('settings_changed','Requested setting did not match the actual visible form.');
  if(data.asset_id!==args.asset)throw new StudioError('asset_changed','Source asset changed during preparation.');
  return[result(data)];
}
export function readWorkspaceSubmissionDOM(module,priorId) {
  const routes={segment:'segmentation',texture:'texture',edit:'texture-edit',upscale:'texture-upscale',pbr:'texture-pbr'};
  if(location.origin!=='https://studio.tripo3d.ai')return{kind:'origin_mismatch'};
  if(!Object.hasOwn(routes,module))return{kind:'invalid_argument'};
  const match=location.pathname.match(new RegExp('^/workspace/'+routes[module]+'/.*?([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$'));
  const states=['Generating','Processing','Segmenting','Enhancing'];
  const processing=[...document.querySelectorAll('main p')].some(e=>e.getClientRects().length&&states.some(s=>new RegExp('^'+s+'\\.{0,3}$','i').test(e.innerText.trim())));
  if(match&&(match[1]!==priorId||processing))return{kind:'ready',asset_id:match[1],acceptance:processing?'processing_ui_not_completion':'new_asset_route_not_completion'};
  return{kind:'pending'};
}
export async function submitWorkspace(page,raw) {
  const args=validateExecution(raw);moduleName(args.module);assetId(args.asset);
  if(!SUBMIT_MODULES.includes(args.module))throw new StudioError('invalid_argument','This submit tool accepts observed quoted model operations only.');
  args.operation='workspace_'+args.module;
  const fingerprint=sha(JSON.stringify([args.operation,args.asset,args.quote,args.budget]));
  const accepted=await claimedOperation(args,fingerprint,async claim=>{
    const data=await navigate(page,args.module,args.asset);
    if(data.status==='unavailable'||!data.button_enabled)throw new StudioError('prerequisite_missing','Visible operation prerequisites are not met.');
    if(data.quoted_credits===null)throw new StudioError('quote_unknown','No unambiguous visible price; prepare and inspect first.');
    if(workspaceQuoteHash(data)!==args.quote||data.quoted_credits>args.budget)throw new StudioError('quote_changed','Source, settings or price differ from the approved quote.');
    if(data.credits<data.quoted_credits)throw new StudioError('insufficient_credits','Balance is below the current quote.');
    await claim('paid_click');await page.click(PANEL+' button.animate-button');
    const observed=await pollDOM({evaluate:()=>page.evaluate(readWorkspaceSubmissionDOM,args.module,args.asset)},readWorkspaceSubmissionDOM);
    return{status:'submitted',module:args.module,source_asset_id:args.asset,asset_id:observed.asset_id,settings:data.settings,quoted_credits:data.quoted_credits,
      quote_sha256:args.quote,max_credits:args.budget,paid_submitted:true,secrets_returned:false,acceptance:observed.acceptance,model_completed:false};
  });return[accepted];
}
