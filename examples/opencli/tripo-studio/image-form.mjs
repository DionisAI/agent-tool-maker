// Visible Generate Image form only. No upload, generation, history replay or API.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { StudioError, ORIGIN, unwrap, pollDOM } from './core.mjs';
import { PANEL, assetId } from './extended.mjs';
import { WORKSPACE_FILES, inspectWorkspace } from './workspace.mjs';

export const IMAGE_FORM_FILES=[...WORKSPACE_FILES,'image-form.mjs','image-form.js'];
export const IMAGE_MODELS=['GPT Image 2','GPT Image 2.5','Nano Banana Pro','Nano Banana 2','Nano Banana','Midjourney v8.2'];
export const IMAGE_RATIOS=['1:1','16:9','9:16','4:3','3:4'];
export const IMAGE_TEMPLATES=['Character Extraction','Head Extraction','T Pose','3D Enhance','Character Completion','Photo to Figure','Asset Extraction','Variants','3D Print-Ready'];
const sha=value=>createHash('sha256').update(value).digest('hex');
const fail=(code,message)=>{throw new StudioError(code,message);};
export function imageFormDigest(){const h=createHash('sha256');for(const n of IMAGE_FORM_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkImageFormPin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==imageFormDigest())fail('definition_changed','Review and rebuild the image form definitions.');}
export function parseImageFormSettings(raw='{}'){
  let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','settings must be JSON.');}
  const keys=['model','aspect_ratio','number_images','resolution_4k','template','prompt','expected_draft_sha256'];
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!keys.includes(k)))fail('invalid_argument','Use typed image settings, not selectors or URLs.');
  if(!/^[a-f0-9]{64}$/.test(v.expected_draft_sha256||''))fail('invalid_argument','Bind preparation to the exact inspected draft digest.');
  if('model'in v&&!IMAGE_MODELS.includes(v.model))fail('invalid_argument','Select an observed image model.');
  if('aspect_ratio'in v&&v.aspect_ratio!==null&&!IMAGE_RATIOS.includes(v.aspect_ratio))fail('invalid_argument','Use an observed ratio or null for no selected ratio.');
  if('number_images'in v&&(!Number.isInteger(v.number_images)||v.number_images<1||v.number_images>4))fail('invalid_argument','number_images must be an integer from 1 to 4.');
  if('resolution_4k'in v&&typeof v.resolution_4k!=='boolean')fail('invalid_argument','resolution_4k must be boolean.');
  if('template'in v&&v.template!==null&&!IMAGE_TEMPLATES.includes(v.template))fail('invalid_argument','Use an observed template or null to clear it.');
  if('prompt'in v&&(typeof v.prompt!=='string'||v.prompt.length>10000))fail('invalid_argument','prompt must contain 0-10000 characters.');
  if(v.model==='Midjourney v8.2'&&['aspect_ratio','number_images','resolution_4k'].some(k=>k in v))fail('setting_unavailable','Midjourney has no visible ratio, count or 4K controls.');
  return v;
}

// Serialized readers use only their argument and visible DOM.
export function readImageContextDOM(){const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;};return{origin:location.origin,path:location.pathname,layers:[...document.querySelectorAll('[role="dialog"],[role="listbox"],[role="menu"]')].filter(visible).length};}
export function readImageFormDOM(){
  if(location.origin!=='https://studio.tripo3d.ai')return{kind:'origin_mismatch'};
  if(!/^\/workspace\/generate-image(?:\/|$)/.test(location.pathname))return{kind:'pending'};
  const ps=[...document.querySelectorAll('div.rounded-r-5:has(h2)')].filter(e=>e.getClientRects().length);if(!ps.length)return{kind:'pending'};
  if(ps.length!==1)return{kind:'image_form_changed'};const p=ps[0];if(p.querySelector('h2')?.innerText.trim()!=='Generate Image')return{kind:'pending'};
  const prompts=[...p.querySelectorAll('textarea')],models=[...p.querySelectorAll('[role="combobox"]')],actions=[...p.querySelectorAll('button.animate-button')];
  if(prompts.length!==1||models.length!==1||actions.length!==1||prompts[0].getAttribute('maxlength')!=='10000')return{kind:'image_form_changed'};
  const prompt=prompts[0].value,model=models[0].innerText.trim();
  if(typeof prompt!=='string'||prompt.length>10000||!['GPT Image 2','GPT Image 2.5','Nano Banana Pro','Nano Banana 2','Nano Banana','Midjourney v8.2'].includes(model))return{kind:'image_form_changed'};
  const toggle=[...p.querySelectorAll('button[value][aria-pressed]')];
  if(toggle.some(e=>!['1:1','16:9','9:16','4:3','3:4','1','2','3','4'].includes(e.getAttribute('value'))||!['on','off'].includes(e.getAttribute('data-state'))||e.getAttribute('aria-pressed')!==(e.getAttribute('data-state')==='on'?'true':'false')))return{kind:'image_form_changed'};
  const ratios=toggle.filter(e=>e.getAttribute('value').includes(':')),counts=toggle.filter(e=>/^[1-4]$/.test(e.getAttribute('value'))),switches=[...p.querySelectorAll('[role="switch"]')];
  const selected=es=>es.filter(e=>e.getAttribute('data-state')==='on');
  if(new Set(toggle.map(e=>e.getAttribute('value'))).size!==toggle.length||selected(ratios).length>1||counts.length&&selected(counts).length!==1||switches.length>1)return{kind:'image_form_changed'};
  if(model==='Midjourney v8.2'?(ratios.length||counts.length||switches.length):(!ratios.length||!counts.length||switches.length!==1))return{kind:'image_form_changed'};
  // The observed switch sits inside a relative wrapper; its semantic label is
  // the sibling paragraph in the grandparent row, not the empty direct parent.
  if(switches.some(e=>!['true','false'].includes(e.getAttribute('aria-checked'))||e.parentElement.parentElement.querySelector('p')?.innerText.trim()!=='4K Resolution'))return{kind:'image_form_changed'};
  const templateImages=[...p.querySelectorAll('img')].filter(e=>e.parentElement.querySelector('[class~="i-tripo:star-hollow"]'));
  if(templateImages.length>1||templateImages.some(e=>!['Character Extraction','Head Extraction','T Pose','3D Enhance','Character Completion','Photo to Figure','Asset Extraction','Variants','3D Print-Ready'].includes(e.getAttribute('alt'))))return{kind:'image_template_changed'};
  const rows=[...p.querySelectorAll('div.h-15.overflow-x-auto')];if(rows.length>1)return{kind:'image_references_changed'};
  const references=rows.flatMap(row=>[...row.querySelectorAll('img')].filter(e=>!e.parentElement.querySelector('[class~="i-tripo:star-hollow"]')).map(e=>{try{const u=new URL(e.getAttribute('src'),location.origin);return /^https?:$/.test(u.protocol)?{src:u.origin+u.pathname}:null;}catch{return null;}}));
  const fileCounts=[...p.querySelectorAll('input[type="file"]')].map(e=>typeof e.files?.length==='number'?e.files.length:null);
  if(references.some(e=>e===null)||fileCounts.some(n=>n===null)||references.length>10)return{kind:'image_references_changed'};
  const action=actions[0],label=action.innerText.replace(/\s+/g,' ').trim();if(label!=='Generate Image')return{kind:'image_price_changed'};
  const match=location.pathname.match(/([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/);
  return{kind:'ready',asset_id:match?.[1]||null,settings:{model,prompt,aspect_ratio:selected(ratios)[0]?.getAttribute('value')||null,number_images:counts.length?Number(selected(counts)[0].getAttribute('value')):null,resolution_4k:switches.length?switches[0].getAttribute('aria-checked')==='true':null,template:templateImages[0]?.getAttribute('alt')||null},
    controls:{aspect_ratios:ratios.map(e=>({value:e.getAttribute('value'),disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'})),number_images:counts.map(e=>({value:Number(e.getAttribute('value')),disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'})),resolution_4k:switches.length?{disabled:!!switches[0].disabled||switches[0].getAttribute('aria-disabled')==='true'}:null,prompt_enabled:!prompts[0].disabled},
    references,file_counts:fileCounts,button_enabled:!action.disabled&&action.getAttribute('aria-disabled')!=='true',action_label:label,
    billing_observation:{free_allowance:p.innerText.split(/\n+/).map(s=>s.trim()).find(s=>/^Free \d+\/\d+$/.test(s))||null,quoted_credits:null,quote_known:false}};
}
export function readImageChoicesDOM(kind){
  const visible=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;};
  const layers=[...document.querySelectorAll(kind==='model'?'[role="listbox"]':'[role="dialog"]')].filter(visible);
  if(layers.length!==1)return{kind:layers.length?'image_choices_changed':'pending'};
  const d=layers[0];if(kind==='template'&&d.innerText.split('\n')[0].trim()!=='Templates')return{kind:'image_choices_changed'};
  const items=[...d.querySelectorAll(kind==='model'?'[role="option"]':'button[aria-pressed]:has(img)')];
  const options=items.map(e=>({label:e.innerText.trim().split(/\n/)[0].trim(),selected:kind==='model'?e.getAttribute('aria-selected')==='true':e.getAttribute('data-state')==='on',disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'||e.hasAttribute('data-disabled')}));
  if(!options.length||options.some(o=>!o.label)||new Set(options.map(o=>o.label)).size!==options.length||options.filter(o=>o.selected).length>(kind==='model'?1:1)||kind==='model'&&options.filter(o=>o.selected).length!==1)return{kind:'image_choices_changed'};
  return{kind:'ready',options};
}
export function readImageLayerClosedDOM(kind){const selector=kind==='model'?'[role="listbox"]':'[role="dialog"]';return{kind:[...document.querySelectorAll(selector)].some(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0;})?'pending':'ready'};}
export function readImageTargetDOM(target){
  const p=document.querySelector('div.rounded-r-5:has(h2)');if(!p)return{kind:'pending'};let all=[],items=[];
  if(target.kind==='model'){all=[...p.querySelectorAll('[role="combobox"]')];items=all;}
  else if(target.kind==='model_option'){all=[...document.querySelectorAll('[role="listbox"] [role="option"]')];items=all.filter(e=>e.innerText.trim().split('\n')[0].trim()===target.label);}
  else if(target.kind==='template'){all=[...p.querySelectorAll('button')];items=all.filter(e=>e.innerText.trim()==='More Templates');}
  else if(target.kind==='template_option'){all=[...document.querySelectorAll('[role="dialog"] button[aria-pressed]:has(img)')];items=all.filter(e=>e.innerText.trim()===target.label);}
  else if(target.kind==='template_close'){all=[...document.querySelectorAll('[role="dialog"] button:has([class~="i-tripo:close"])')];items=all;}
  else if(target.kind==='toggle'){all=[...p.querySelectorAll('button[value][aria-pressed]')];items=all.filter(e=>e.getAttribute('value')===target.label);}
  else if(target.kind==='resolution'){all=[...p.querySelectorAll('[role="switch"]')];items=all;}
  else if(target.kind==='prompt'){all=[...p.querySelectorAll('textarea')];items=all;}
  else return{kind:'invalid_argument'};
  if(items.length!==1)return{kind:'image_control_changed'};const e=items[0],r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return{kind:'ready',nth:all.indexOf(e),pointer_ready:r.width>0&&r.height>0&&!e.disabled&&e.getAttribute('aria-disabled')!=='true'&&!e.hasAttribute('data-disabled')&&(hit===e||e.contains(hit))};
}
const selectors={model:PANEL+' [role="combobox"]',model_option:'[role="listbox"] [role="option"]',template:PANEL+' button',template_option:'[role="dialog"] button[aria-pressed]:has(img)',template_close:'[role="dialog"] button:has([class~="i-tripo:close"])',toggle:PANEL+' button[value][aria-pressed]',resolution:PANEL+' [role="switch"]',prompt:PANEL+' textarea'};
async function target(page,kind,label){const read=()=>pollDOM({evaluate:()=>page.evaluate(readImageTargetDOM,{kind,label})},readImageTargetDOM);let d=await read();
  if(!d.pointer_ready&&kind==='resolution'){
    // Observed 511px scroll viewport clips the 540px form: the fixed generation
    // footer covers 4K. Focus + End scrolls this exact control's nearest viewport.
    // Re-read the hit; never weaken it or send a click through the footer.
    if(typeof page.focus!=='function'||typeof page.cdp!=='function')fail('unsupported_backend','4K viewport repair requires focus and native keyboard support.');
    await page.focus(selectors.resolution,{nth:d.nth});
    // SDK 1.8.6's key-only shortcut omits the End virtual key code, as already
    // observed for Home in assets_query. Send the documented native key pair.
    for(const type of ['rawKeyDown','keyUp'])await page.cdp('Input.dispatchKeyEvent',{type,key:'End',code:'End',windowsVirtualKeyCode:35});
    try{d={...await pollDOM({evaluate:async()=>{const v=unwrap(await page.evaluate(readImageTargetDOM,{kind,label}));return v?.kind==='ready'&&!v.pointer_ready?{kind:'pending'}:v;}},readImageTargetDOM,{timeout:2000,pause:100}),viewport_repair:'focus_end'};}
    catch(e){if(!(e instanceof StudioError)||e.code!=='page_not_ready')throw e;fail('control_obscured','4K remains covered after bounded viewport repair; no click sent.');}
  }
  if(!d.pointer_ready)fail('control_obscured','The requested image control is disabled or covered; no click sent.');return d;}
async function click(page,kind,label){const d=await target(page,kind,label);await page.click(selectors[kind],{nth:d.nth});return d;}
async function context(page,id){const d=unwrap(await page.evaluate(readImageContextDOM));if(d.layers)fail('dialog_open','An existing layer is preserved; close it locally before new image preparation.');if(id&&(d.origin!==ORIGIN||!d.path.endsWith(id)))fail('asset_changed','Image workspace source changed.');}
export function imageDraftHash(d){return sha(JSON.stringify(['tripo-image-form-v1',d.asset_id,d.settings,d.references,d.file_counts]));}
async function state(page,id){const d=await pollDOM(page,readImageFormDOM);if((d.asset_id||'')!==(id||''))fail('asset_changed','Image form source differs from the requested source.');return d;}
async function choices(page,kind,label){
  await click(page,kind);let error,result;
  try{result=await pollDOM({evaluate:()=>page.evaluate(readImageChoicesDOM,kind)},readImageChoicesDOM);
    const known=kind==='model'?IMAGE_MODELS:IMAGE_TEMPLATES;if(result.options.some(o=>!known.includes(o.label)))fail('image_choices_changed','New image choices need source review.');
    if(label!==undefined){const option=result.options.find(o=>o.label===label);if(!option||option.disabled)fail('setting_unavailable','The requested image choice is not enabled.');await click(page,kind+'_option',label);}
  }catch(e){error=e;}
  try{const closed=unwrap(await page.evaluate(readImageLayerClosedDOM,kind));if(closed.kind!=='ready'){if(kind==='model')await page.pressKey('Escape');else await click(page,'template_close');await pollDOM({evaluate:()=>page.evaluate(readImageLayerClosedDOM,kind)},readImageLayerClosedDOM);}}
  catch(e){if(error)throw error;fail('cleanup_failed','The owned image layer did not close; inspect it locally.');}
  if(error)throw error;return result.options;
}
function result(d,extra={}){return{...d,kind:undefined,status:d.settings.prompt.trim()||d.references.length?'action_state_observed':'draft_empty',draft_sha256:imageDraftHash(d),prompt_sha256:sha(d.settings.prompt),paid_submitted:false,upload_started:false,download_started:false,secrets_returned:false,acceptance:'visible_image_form_not_generation_or_output',...extra};}
export async function inspectImageForm(page,args){if(args.asset)assetId(args.asset);await context(page);await inspectWorkspace(page,{module:'image',asset:args.asset||''});await context(page,args.asset);const before=await state(page,args.asset);
  const models=await choices(page,'model'),templates=await choices(page,'template');await context(page,args.asset);const after=await state(page,args.asset);
  if(imageDraftHash(before)!==imageDraftHash(after))fail('draft_changed','Image draft changed during inspection.');
  return[result(after,{available_models:models,available_templates:templates})];}
export async function prepareImageForm(page,args){
  const requested=parseImageFormSettings(args.settings),initial=(await inspectImageForm(page,args))[0];
  if(requested.expected_draft_sha256!==initial.draft_sha256)fail('draft_changed','The inspected image draft changed; no preparation submitted.');
  let d=await state(page,args.asset),resolution_preparation=null;if(imageDraftHash(d)!==initial.draft_sha256)fail('draft_changed','Image draft changed before preparation.');
  if(requested.model&&requested.model!==d.settings.model){await choices(page,'model',requested.model);d=await state(page,args.asset);if(d.settings.model!==requested.model)fail('settings_changed','Image model did not match readback.');}
  if('template'in requested&&requested.template!==d.settings.template){await choices(page,'template',requested.template||d.settings.template);d=await state(page,args.asset);if(d.settings.template!==requested.template)fail('settings_changed','Image template did not match readback.');}
  for(const key of ['aspect_ratio','number_images'])if(key in requested&&requested[key]!==d.settings[key]){
    const opts=d.controls[key==='aspect_ratio'?'aspect_ratios':'number_images'],value=requested[key]===null?d.settings[key]:requested[key];
    if(!opts.some(o=>o.value===value&&!o.disabled))fail('setting_unavailable','The requested image option has no enabled visible control.');await click(page,'toggle',String(value));d=await state(page,args.asset);if(d.settings[key]!==requested[key])fail('settings_changed','Image choice did not match readback.');}
  if('resolution_4k'in requested&&requested.resolution_4k!==d.settings.resolution_4k){if(!d.controls.resolution_4k||d.controls.resolution_4k.disabled)fail('setting_unavailable','4K control is absent or disabled.');
    // Dispatch once after viewport/hit verification, then read the actual UI.
    const prepared=await click(page,'resolution');d=await state(page,args.asset);
    resolution_preparation={viewport_repair:prepared.viewport_repair||null,requested:requested.resolution_4k,verified_value:d.settings.resolution_4k};}
  if('prompt'in requested&&requested.prompt!==d.settings.prompt){if(!d.controls.prompt_enabled)fail('setting_unavailable','Image prompt input is disabled.');const t=await target(page,'prompt');await page.fillText(selectors.prompt,requested.prompt,{nth:t.nth});}
  await context(page,args.asset);d=await state(page,args.asset);
  for(const[k,v]of Object.entries(requested))if(k!=='expected_draft_sha256'&&d.settings[k]!==v)fail('settings_changed','Requested image setting differs from final readback.');
  const beforeFiles=JSON.stringify(initial.file_counts),afterFiles=JSON.stringify(d.file_counts);
  // Native Midjourney removes the one empty file input; restoring a supported
  // model reinstates it. This is control availability, never uploaded-file loss.
  // Keep all other FileList shapes and every reference under the original guard.
  const emptyInputVisibilityChange=requested.model&&requested.model!==initial.settings.model&&
    (d.settings.model==='Midjourney v8.2'&&beforeFiles==='[0]'&&afterFiles==='[]'||
     initial.settings.model==='Midjourney v8.2'&&beforeFiles==='[]'&&afterFiles==='[0]');
  if(!('prompt'in requested)&&d.settings.prompt!==initial.settings.prompt||JSON.stringify(d.references)!==JSON.stringify(initial.references)||beforeFiles!==afterFiles&&!emptyInputVisibilityChange)fail('draft_changed','Unrequested prompt or reference change detected; inspect the current draft.');
  const implicit_changes=Object.fromEntries(Object.keys(d.settings).filter(k=>!(k in requested)&&d.settings[k]!==initial.settings[k]).map(k=>[k,{before:initial.settings[k],after:d.settings[k]}]));
  const implicit_control_changes=emptyInputVisibilityChange?{file_input_count:{before:initial.file_counts.length,after:d.file_counts.length}}:{};
  return[result(d,{status:'prepared',implicit_changes,implicit_control_changes,resolution_preparation})];
}
