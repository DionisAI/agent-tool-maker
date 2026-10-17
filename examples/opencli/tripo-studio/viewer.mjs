// Reviewed visible viewer controls; no provider API, auth state or engine state.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { StudioError, ORIGIN, unwrap, pollDOM } from './core.mjs';
import { assetId, inspectAsset } from './extended.mjs';
import { WORKSPACE_FILES, inspectWorkspace } from './workspace.mjs';

export const VIEWER_FILES=[...WORKSPACE_FILES,'viewer.mjs','viewer.js'];
export const RENDER_MODES=['solid','pbr','normal','unlit','toon','sketch','hologram'];
export const PBR_EFFECTS=['unlit','toon','sketch','hologram'];
export const ENVIRONMENTS=['Beach','Desert','Forest','Interior','Night','Studio'];
export const CAMERA_ACTIONS=['reset','orbit_left','orbit_right','orbit_up','orbit_down','pan_left','pan_right','pan_up','pan_down','zoom_in','zoom_out'];
export const ENV_DIALOG='[role="dialog"]:has([role="slider"])';
const sha=value=>createHash('sha256').update(value).digest('hex');
const fail=(code,message)=>{throw new StudioError(code,message);};
export function viewerDigest(){const h=createHash('sha256');for(const name of VIEWER_FILES)h.update(name+'\0').update(readFileSync(new URL(name,import.meta.url))).update('\0');return h.digest('hex');}
export function checkViewerPin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==viewerDigest())fail('definition_changed','Review and rebuild viewer definitions before execution.');}
export function readViewerContextDOM(){return{origin:location.origin,path:location.pathname,
  dialogs:[...document.querySelectorAll('[role="dialog"],[role="listbox"]')].filter(e=>e.getClientRects().length).length};}
async function context(page,id){const d=unwrap(await page.evaluate(readViewerContextDOM));
  if(d.dialogs)fail('dialog_open','Existing visible dialogs and lists are preserved.');
  if(id&&(d.origin!==ORIGIN||!d.path.endsWith(id)))fail('asset_changed','Viewer source changed.');return d;}
export function readViewerDOM(){
  if(location.origin!=='https://studio.tripo3d.ai')return{kind:'origin_mismatch'};
  const id=location.pathname.match(/^\/workspace\/generate\/.*?([a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/)?.[1];
  if(!id)return{kind:'pending'};
  const canvases=[...document.querySelectorAll('main canvas')].filter(e=>e.getClientRects().length);
  if(!canvases.length)return{kind:'pending'};if(canvases.length!==1)return{kind:'viewer_layout_changed'};
  const modes=[...document.querySelectorAll('main button[aria-pressed]:has(img)')].filter(e=>e.getClientRects().length&&!e.closest('[role="tabpanel"]')&&!e.closest('div.rounded-r-5:has(h2)')).map(e=>{
    let path;try{path=new URL(e.querySelector('img').getAttribute('src'),location.origin).pathname;}catch{return null;}
    const mode=path.match(/^\/studio-prod\/viewer\/images\/(wireframe|solid|pbr|normal|unlit|toon|sketch|hologram)\.png$/)?.[1];
    return{mode,pressed:e.getAttribute('aria-pressed'),disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true'};});
  if(modes.length!==8||modes.some(m=>!m?.mode||!['true','false'].includes(m.pressed))||new Set(modes.map(m=>m.mode)).size!==8)return{kind:'viewer_modes_changed'};
  // The visible UI keeps PBR pressed while one PBR effect is active. Solid and
  // Normal are base modes; Wireframe is independent of both groups.
  const selected=modes.filter(m=>['solid','pbr','normal'].includes(m.mode)&&m.pressed==='true');
  const effects=modes.filter(m=>['unlit','toon','sketch','hologram'].includes(m.mode)&&m.pressed==='true');
  if(selected.length!==1||effects.length>1||effects.length&&selected[0].mode!=='pbr')return{kind:'viewer_selection_changed'};
  const grid=[...document.querySelectorAll('main button[aria-pressed]:has([class~="i-tripo:line-visible"]),main button[aria-pressed]:has([class~="i-tripo:line-invisible"])')].filter(e=>e.getClientRects().length);
  if(grid.length!==1||!['true','false'].includes(grid[0].getAttribute('aria-pressed')))return{kind:'viewer_grid_changed'};
  const tabs=[...document.querySelectorAll('main [role="tab"]')].filter(e=>['Assets','Property'].includes(e.innerText.trim()));
  if(tabs.length!==2||tabs.filter(e=>e.getAttribute('aria-selected')==='true').length!==1)return{kind:'viewer_sidebar_changed'};
  const sidebar=tabs.find(e=>e.getAttribute('aria-selected')==='true').innerText.trim(),r=canvases[0].getBoundingClientRect();
  return{kind:'ready',asset_id:id,settings:{render_mode:effects[0]?.mode||selected[0].mode,wireframe:modes.find(m=>m.mode==='wireframe').pressed==='true',grid:grid[0].getAttribute('aria-pressed')==='true'},
    modes,sidebar,canvas:{x:r.x,y:r.y,width:r.width,height:r.height}};
}
export function readHierarchyDOM(){
  if(location.origin!=='https://studio.tripo3d.ai')return{kind:'origin_mismatch'};
  const panes=[...document.querySelectorAll('main [role="tabpanel"]')].filter(e=>e.getClientRects().length&&e.querySelector('p')?.innerText.trim()==='Hierarchy');
  if(!panes.length)return{kind:'pending'};if(panes.length!==1)return{kind:'hierarchy_layout_changed'};
  const p=panes[0],rows=[...p.querySelectorAll('li')].filter(e=>e.getClientRects().length).map(e=>{
    const name=e.querySelector(':scope > .text-start')?.innerText.trim();
    const icons=[...e.querySelectorAll(':scope > button [class]')],vis=icons.filter(n=>n.classList.contains('i-tripo:visible')||n.classList.contains('i-tripo:invisible'));
    return{name,selected:e.classList.contains('bg-purple-20'),visible:vis.length===1?vis[0].classList.contains('i-tripo:visible'):null};});
  if(rows.length>1000||rows.some(n=>!n.name||n.name.length>256||n.visible===null)||new Set(rows.map(n=>n.name)).size!==rows.length||rows.filter(n=>n.selected).length>1)return{kind:'hierarchy_nodes_changed'};
  const selected=rows.find(n=>n.selected)?.name||null,transform={};
  for(const key of ['position','rotation','scale']){
    const icons=[...p.querySelectorAll('[class]')].filter(n=>n.classList.contains('i-tripo:'+key));
    if(!selected){if(icons.length)return{kind:'hierarchy_selection_changed'};continue;}
    if(icons.length!==1)return{kind:'transform_fields_changed'};
    const inputs=[...icons[0].parentElement.querySelectorAll('input')];
    if(inputs.length!==3||inputs.map(e=>e.parentElement.innerText.trim()).join(',')!=='X,Y,Z'||inputs.some(e=>e.getAttribute('type')!=='text'||!/^[-+]?\d+(?:\.\d+)?$/.test(e.value)||!Number.isFinite(Number(e.value))))return{kind:'transform_fields_changed'};
    transform[key]=inputs.map(e=>Number(e.value));
  }
  return{kind:'ready',nodes:rows,selected_node:selected,transform:selected?transform:null,coverage:'currently_rendered_hierarchy_not_authoritative_all'};
}
export function readEnvironmentDOM(){
  const ds=[...document.querySelectorAll('[role="dialog"]:has([role="slider"])')].filter(e=>e.getClientRects().length&&e.getAttribute('data-state')!=='closed');
  if(!ds.length)return{kind:'pending'};if(ds.length!==1)return{kind:'environment_layout_changed'};
  const d=ds[0],combos=[...d.querySelectorAll('[role="combobox"]')],inputs=[...d.querySelectorAll('input[type="text"]')],sliders=[...d.querySelectorAll('[role="slider"]')],sw=[...d.querySelectorAll('[role="switch"]')];
  if(!d.innerText.trim().startsWith('Environment Settings')||combos.length!==1||inputs.length!==2||sliders.length!==2||sw.length!==1)return{kind:'environment_fields_changed'};
  const surrounding=combos[0].innerText.trim(),bounds=sliders.map(e=>({min:Number(e.getAttribute('aria-valuemin')),max:Number(e.getAttribute('aria-valuemax')),now:Number(e.getAttribute('aria-valuenow'))}));
  if(!['Beach','Desert','Forest','Interior','Night','Studio'].includes(surrounding)||bounds[0].min!==0||bounds[0].max!==2||bounds[1].min!==0||bounds[1].max!==360||inputs.some((e,i)=>!/^\d+(?:\.\d+)?$/.test(e.value)||Number(e.value)!==bounds[i].now||Number(e.value)<bounds[i].min||Number(e.value)>bounds[i].max)||!['true','false'].includes(sw[0].getAttribute('aria-checked'))||sw[0].parentElement.innerText.trim()!=='Auto Rotate')return{kind:'environment_fields_changed'};
  return{kind:'ready',settings:{surrounding,strength:Number(inputs[0].value),rotation:Number(inputs[1].value),auto_rotate:sw[0].getAttribute('aria-checked')==='true'},bounds};
}
export function readEnvironmentListDOM(){
  const lists=[...document.querySelectorAll('[role="listbox"]')].filter(e=>e.getClientRects().length&&e.getAttribute('data-state')!=='closed');
  if(!lists.length)return{kind:'pending'};if(lists.length!==1)return{kind:'environment_list_changed'};
  const options=[...lists[0].querySelectorAll('[role="option"]')].map(e=>({label:e.innerText.trim(),selected:e.getAttribute('aria-selected')==='true',disabled:e.getAttribute('aria-disabled')==='true'}));
  if(options.length!==6||options.some(o=>!['Beach','Desert','Forest','Interior','Night','Studio'].includes(o.label))||new Set(options.map(o=>o.label)).size!==6)return{kind:'environment_list_changed'};
  return{kind:'ready',options};
}
export function readViewerLayersClosedDOM(kind){const selector=kind==='list'?'[role="listbox"]':'[role="dialog"]:has([role="slider"])';return{kind:[...document.querySelectorAll(selector)].some(e=>e.getClientRects().length)?'pending':'ready'};}
export const TARGETS={mode:'main button[aria-pressed]',grid:'main button[aria-pressed]',sidebar:'main [role="tab"]',
  environment:'main button.p-2:has([class~="i-tripo:env"])',environment_close:ENV_DIALOG+' button:has([class~="i-tripo:close"])',
  environment_option:'[role="listbox"] [role="option"]',camera_reset:'main button:has([class~="i-tripo:camera-reset"])',
  node:'main [role="tabpanel"] li',visibility:'main [role="tabpanel"] li > button'};
export function readViewerTargetDOM(spec){
  const selectors={mode:'main button[aria-pressed]',grid:'main button[aria-pressed]',sidebar:'main [role="tab"]',environment:'main button.p-2:has([class~="i-tripo:env"])',
    environment_close:'[role="dialog"]:has([role="slider"]) button:has([class~="i-tripo:close"])',environment_option:'[role="listbox"] [role="option"]',camera_reset:'main button:has([class~="i-tripo:camera-reset"])',node:'main [role="tabpanel"] li',visibility:'main [role="tabpanel"] li > button'};
  if(!selectors[spec.kind])return{kind:'invalid_argument'};
  const all=[...document.querySelectorAll(selectors[spec.kind])],matches=all.map((e,nth)=>({e,nth})).filter(({e})=>{
    if(!e.getClientRects().length||e.disabled||e.getAttribute('aria-disabled')==='true')return false;
    if(spec.kind==='mode'){const img=e.querySelector('img');if(!img||e.closest('[role="tabpanel"]')||e.closest('div.rounded-r-5:has(h2)'))return false;try{return new URL(img.getAttribute('src'),location.origin).pathname==='/studio-prod/viewer/images/'+spec.label+'.png';}catch{return false;}}
    if(spec.kind==='grid')return!!e.querySelector('[class~="i-tripo:line-visible"],[class~="i-tripo:line-invisible"]');
    if(spec.kind==='sidebar'||spec.kind==='environment_option')return e.innerText.trim()===spec.label;
    if(spec.kind==='node'||spec.kind==='visibility'){const row=spec.kind==='node'?e:e.closest('li');return row.querySelector(':scope > .text-start')?.innerText.trim()===spec.label&&(spec.kind==='node'||!!e.querySelector('[class~="i-tripo:visible"],[class~="i-tripo:invisible"]'));}
    return true;});
  if(!matches.length)return{kind:'pending'};if(matches.length!==1)return{kind:'viewer_target_ambiguous'};
  const {e,nth}=matches[0],r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return{kind:'ready',nth,pointer_ready:hit===e||!!hit&&e.contains(hit)};
}
async function click(page,kind,label){const target=await pollDOM({evaluate:()=>page.evaluate(readViewerTargetDOM,{kind,label})},readViewerTargetDOM);
  if(!target.pointer_ready)fail('control_obscured','The observed viewer control is covered; no click was dispatched.');await page.click(TARGETS[kind],{nth:target.nth});}
async function base(page,args){assetId(args.asset);await context(page);await inspectWorkspace(page,{module:'model',asset:args.asset});const asset=(await inspectAsset(page,{asset:args.asset,wait:20}))[0];
  if(asset.status!=='ready')fail('model_not_ready','Viewer controls require the observed completed source mesh.');await context(page,args.asset);
  const d=await pollDOM(page,readViewerDOM);if(d.asset_id!==args.asset)fail('asset_changed','Viewer source differs.');return d;}
async function property(page){const d=await pollDOM(page,readViewerDOM);if(d.sidebar!=='Property')await click(page,'sidebar','Property');return pollDOM(page,readHierarchyDOM);}
async function closed(page,kind){await pollDOM({evaluate:()=>page.evaluate(readViewerLayersClosedDOM,kind)},readViewerLayersClosedDOM);}
async function tabKey(page){if(typeof page.cdp!=='function')fail('unsupported_backend','Native numeric-field blur requires documented keyboard support.');
  for(const type of ['rawKeyDown','keyUp'])await page.cdp('Input.dispatchKeyEvent',{type,key:'Tab',code:'Tab',windowsVirtualKeyCode:9});}
async function environment(page,requested={}){
  let owned=false,err,out;
  try{await click(page,'environment');owned=true;let data=await pollDOM(page,readEnvironmentDOM);
    await page.click(ENV_DIALOG+' [role="combobox"]');const list=await pollDOM(page,readEnvironmentListDOM);
    const item=list.options.filter(o=>requested.surrounding?o.label===requested.surrounding:o.selected);if(item.length!==1||item[0].disabled)fail('setting_unavailable','The environment preset is not enabled.');
    await click(page,'environment_option',item[0].label);await closed(page,'list');
    data=await pollDOM(page,readEnvironmentDOM);
    const finalRotate='auto_rotate'in requested?requested.auto_rotate:data.settings.auto_rotate;
    // Auto Rotate updates the visible angle continuously. Verify a requested
    // starting angle while stopped, then enable/restore rotation separately.
    if('rotation'in requested&&data.settings.auto_rotate)await page.setChecked(ENV_DIALOG+' [role="switch"]',false);
    for(const[key,nth]of [['strength',0],['rotation',1]])if(key in requested){await page.fillText(ENV_DIALOG+' input[type="text"]',String(requested[key]),{nth});await tabKey(page);}
    const numeric=await pollDOM(page,readEnvironmentDOM);
    for(const key of ['strength','rotation'])if(key in requested&&numeric.settings[key]!==requested[key])fail('settings_changed','Environment '+key+' readback differs before auto rotation.');
    if('auto_rotate'in requested||'rotation'in requested)await page.setChecked(ENV_DIALOG+' [role="switch"]',finalRotate);
    data=await pollDOM(page,readEnvironmentDOM);for(const[k,v]of Object.entries(requested))if(!(k==='rotation'&&data.settings.auto_rotate)&&data.settings[k]!==v)fail('settings_changed','Environment '+k+' readback differs from the requested settings.');
    out={...data,kind:undefined,available_presets:list.options,rotation_preparation:'rotation'in requested?{requested:requested.rotation,verified_value:numeric.settings.rotation,auto_rotate_after:data.settings.auto_rotate}:null};
  }catch(e){err=e;}
  if(owned)try{const list=unwrap(await page.evaluate(readEnvironmentListDOM));if(list.kind==='ready'){const chosen=list.options.filter(o=>o.selected&&!o.disabled);if(chosen.length!==1)fail('dialog_changed','Changed environment list is preserved.');await click(page,'environment_option',chosen[0].label);await closed(page,'list');}
    else if(list.kind!=='pending')fail('dialog_changed','Changed environment list is preserved.');await click(page,'environment_close');await closed(page,'dialog');
  }catch(e){fail('cleanup_failed','Owned environment layer needs local inspection; original error code: '+(err instanceof StudioError?err.code:'bridge_failure')+'.');}
  if(err)throw err;return out;
}
function result(data){return{...data,kind:undefined,paid_submitted:false,download_started:false,save_button_clicked:false,secrets_returned:false,acceptance:data.acceptance||'visible_editor_state_not_provider_result_or_export'};}
export function transformHash(asset,node,transform){return sha(JSON.stringify(['tripo-visible-transform-v1',asset,node,transform]));}
export async function inspectViewer(page,args){const initial=await base(page,args);let error,out;
  try{const hierarchy=await property(page),env=await environment(page);await context(page,args.asset);const d=await pollDOM(page,readViewerDOM);
    out=result({...d,status:'observed',environment:env,hierarchy:{...hierarchy,kind:undefined,transform_sha256:hierarchy.transform?transformHash(args.asset,hierarchy.selected_node,hierarchy.transform):null}});
  }catch(e){error=e;}
  const current=unwrap(await page.evaluate(readViewerDOM)),layers=unwrap(await page.evaluate(readViewerContextDOM));
  // A failed owned-layer cleanup must not be masked by a sidebar click behind
  // that layer. Preserve the original failure and the existing layer instead.
  if(current.kind==='ready'&&current.sidebar!==initial.sidebar&&!layers.dialogs)await click(page,'sidebar',initial.sidebar);
  if(error)throw error;return[out];}
export function parseViewerSettings(kind,raw='{}'){
  let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','settings must be JSON.');}
  const allowed={viewer:['render_mode','wireframe','grid','environment'],hierarchy:['select','visible'],transform:['position','rotation','scale','expected_transform_sha256']}[kind];
  if(!allowed||!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!allowed.includes(k)))fail('invalid_argument','Use reviewed semantic viewer settings.');
  if('render_mode'in v&&!RENDER_MODES.includes(v.render_mode))fail('invalid_argument','Select an observed render mode.');
  for(const k of ['wireframe','grid','select','visible'])if(k in v&&typeof v[k]!=='boolean')fail('invalid_argument',k+' must be boolean.');
  if(v.select===false||v.select&&v.visible===false)fail('invalid_argument','Selection accepts true for a visible node; visibility false clears the selected node in the UI.');
  if('environment'in v){const e=v.environment;if(!e||typeof e!=='object'||Array.isArray(e)||Object.keys(e).some(k=>!['surrounding','strength','rotation','auto_rotate'].includes(k)))fail('invalid_argument','Use typed environment fields.');
    if('surrounding'in e&&!ENVIRONMENTS.includes(e.surrounding))fail('invalid_argument','Select an observed environment preset.');
    for(const[k,max]of [['strength',2],['rotation',360]])if(k in e&&(typeof e[k]!=='number'||!Number.isFinite(e[k])||e[k]<0||e[k]>max))fail('invalid_argument','Environment numeric value is outside its observed bounds.');
    if('auto_rotate'in e&&typeof e.auto_rotate!=='boolean')fail('invalid_argument','auto_rotate must be boolean.');}
  if(kind==='transform'){if(!/^[a-f0-9]{64}$/.test(v.expected_transform_sha256||'')||!['position','rotation','scale'].some(k=>k in v))fail('invalid_argument','Bind transform changes to the exact observed transform digest.');
    for(const k of ['position','rotation','scale'])if(k in v&&(!Array.isArray(v[k])||v[k].length!==3||v[k].some(n=>typeof n!=='number'||!Number.isFinite(n)||Math.abs(n)>1000000||Math.abs(Math.round(n*100)-n*100)>1e-7)))fail('invalid_argument','Transform vectors require three finite values, two-decimal precision, within the reviewed one-million magnitude bound.');}
  return v;
}
export async function prepareViewer(page,args){const s=parseViewerSettings('viewer',args.settings),before=(await inspectViewer(page,args))[0];let envPrepared=null;
  // Clicking the already-pressed PBR base does not clear its effect. Toggle the
  // exact active effect off to restore plain PBR, as independently observed.
  if(s.render_mode&&s.render_mode!==before.settings.render_mode){
    if(s.render_mode==='pbr'&&PBR_EFFECTS.includes(before.settings.render_mode)){
      await click(page,'mode',before.settings.render_mode);
      const cleared=await pollDOM(page,readViewerDOM);
      if(PBR_EFFECTS.includes(cleared.settings.render_mode))fail('settings_changed','The active PBR effect was not cleared.');
      // Disabling an effect can restore its previous Solid/Normal base.
      if(cleared.settings.render_mode!=='pbr')await click(page,'mode','pbr');
    }else await click(page,'mode',s.render_mode);
  }
  for(const[key,kind,label]of [['wireframe','mode','wireframe'],['grid','grid',undefined]])if(key in s&&s[key]!==before.settings[key])await click(page,kind,label);
  if(s.environment)envPrepared=await environment(page,s.environment);await context(page,args.asset);const after=(await inspectViewer(page,args))[0];
  for(const[k,v]of Object.entries(s))if(k==='environment'){for(const[f,w]of Object.entries(v)){
    if(f==='rotation'&&after.environment.settings.auto_rotate){if(envPrepared?.rotation_preparation?.verified_value!==w)fail('settings_changed','Starting environment rotation was not verified.');}
    else if(after.environment.settings[f]!==w)fail('settings_changed','Viewer environment '+f+' changed during readback.');
  }}else if(after.settings[k]!==v)fail('settings_changed','Viewer setting changed during readback.');
  if(envPrepared?.rotation_preparation)after.environment.rotation_preparation=envPrepared.rotation_preparation;
  return[{...after,status:'prepared'}];}
function nodeName(n){if(typeof n!=='string'||!n.trim()||n.length>256||/[\r\n\0]/.test(n))fail('invalid_argument','Use the exact observed hierarchy node name.');return n;}
export async function prepareHierarchy(page,args){const s=parseViewerSettings('hierarchy',args.settings);nodeName(args.node);await base(page,args);let d=await property(page),n=d.nodes.find(n=>n.name===args.node);
  if(!n)fail('node_missing','Requested node is not in the currently rendered hierarchy.');
  if('visible'in s&&n.visible!==s.visible){await click(page,'visibility',args.node);d=await pollDOM(page,readHierarchyDOM);n=d.nodes.find(n=>n.name===args.node);if(!n||n.visible!==s.visible)fail('settings_changed','Node visibility readback differs.');}
  if(s.select&&!n.selected){if(!n.visible)fail('node_hidden','Show the node before selecting it.');await click(page,'node',args.node);d=await pollDOM(page,readHierarchyDOM);if(d.selected_node!==args.node)fail('selection_changed','Selected hierarchy node differs.');}
  await context(page,args.asset);return[result({...d,status:'prepared',asset_id:args.asset,transform_sha256:d.transform?transformHash(args.asset,d.selected_node,d.transform):null})];}
export function readTransformFieldsDOM(){const p=[...document.querySelectorAll('main [role="tabpanel"]')].find(e=>e.getClientRects().length&&e.querySelector('p')?.innerText.trim()==='Hierarchy');if(!p)return{kind:'pending'};
  const all=[...document.querySelectorAll('main [role="tabpanel"] input[type="text"]')],fields={};for(const key of ['position','rotation','scale']){const icon=[...p.querySelectorAll('[class]')].find(e=>e.classList.contains('i-tripo:'+key));if(!icon)return{kind:'transform_fields_changed'};const inputs=[...icon.parentElement.querySelectorAll('input[type="text"]')];if(inputs.length!==3)return{kind:'transform_fields_changed'};fields[key]=inputs.map(e=>all.indexOf(e));}return{kind:'ready',fields};}
export async function prepareTransform(page,args){const s=parseViewerSettings('transform',args.settings);nodeName(args.node);await base(page,args);let d=await property(page);
  if(d.selected_node!==args.node||!d.transform)fail('selection_changed','Select the exact observed node before changing its transform.');
  if(transformHash(args.asset,args.node,d.transform)!==s.expected_transform_sha256)fail('transform_changed','The prior transform differs from the approved snapshot.');
  const expected=structuredClone(d.transform),fields=await pollDOM(page,readTransformFieldsDOM);
  for(const key of ['position','rotation','scale'])if(key in s){expected[key]=s[key];for(let axis=0;axis<3;axis++)if(d.transform[key][axis]!==s[key][axis]){
    await context(page,args.asset);await page.fillText('main [role="tabpanel"] input[type="text"]',s[key][axis].toFixed(2),{nth:fields.fields[key][axis]});await tabKey(page);}}
  d=await pollDOM(page,readHierarchyDOM);if(d.selected_node!==args.node||JSON.stringify(d.transform)!==JSON.stringify(expected))fail('settings_changed','Transform or selected node differs after native input.');await context(page,args.asset);
  return[result({...d,status:'prepared',asset_id:args.asset,transform_sha256:transformHash(args.asset,args.node,d.transform)})];}
export function readCanvasTargetDOM(){const cs=[...document.querySelectorAll('main canvas')].filter(e=>e.getClientRects().length);if(cs.length!==1)return{kind:'viewer_layout_changed'};const c=cs[0],r=c.getBoundingClientRect(),points=[[.5,.5],[.3,.5],[.7,.5],[.5,.3],[.5,.7]],clear=points.every(([x,y])=>document.elementFromPoint(r.x+r.width*x,r.y+r.height*y)===c);return{kind:'ready',pointer_ready:clear,rect:{x:r.x,y:r.y,width:r.width,height:r.height}};}
export async function cameraViewer(page,args){if(!CAMERA_ACTIONS.includes(args.action))fail('invalid_argument','Use a reviewed bounded camera action.');await base(page,args);
  if(args.action==='reset')await click(page,'camera_reset');else{if(typeof page.cdp!=='function')fail('unsupported_backend','Camera gestures require documented native CDP input support.');const target=await pollDOM(page,readCanvasTargetDOM);if(!target.pointer_ready)fail('control_obscured','Camera gesture region is covered; no input was dispatched.');
    const r=target.rect,x=r.x+r.width*.5,y=r.y+r.height*.5;await page.cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x,y});
    if(args.action.startsWith('zoom_'))await page.cdp('Input.dispatchMouseEvent',{type:'mouseWheel',x,y,deltaX:0,deltaY:args.action==='zoom_in'?-120:120});
    else{const pan=args.action.startsWith('pan_'),button=pan?'right':'left',buttons=pan?2:1,dir=args.action.split('_')[1],dx=dir==='left'?-r.width*.18:dir==='right'?r.width*.18:0,dy=dir==='up'?-r.height*.18:dir==='down'?r.height*.18:0;
      await page.cdp('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button,buttons,clickCount:1});
      try{for(let step=1;step<=5;step++)await page.cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:x+dx*step/5,y:y+dy*step/5,button,buttons});}
      finally{await page.cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:x+dx,y:y+dy,button,buttons:0,clickCount:1});}}}
  await context(page,args.asset);return[result({status:'input_dispatched',asset_id:args.asset,action:args.action,camera_pose_exposed:false,acceptance:'bounded_native_camera_input_requires_rendered_visual_validation'})];}
