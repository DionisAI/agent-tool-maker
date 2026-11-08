// Current homepage reference intake discovery, not file input or asset selection.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM} from './core.mjs';
import {inspectFormState} from './form.mjs';
import {boundReadRouting} from './audio-bound.mjs';
import {HOME_QUOTE_FILES,createHomeQuotePage} from './home-quote.mjs';
export const HOME_MATERIAL_FILES=[...HOME_QUOTE_FILES,'material-home.mjs','material-home.js'];
const fail=(code,message)=>{throw new XyqError(code,message);};
const sha=v=>createHash('sha256').update(v).digest('hex');
export function homeMaterialDigest(){const h=createHash('sha256');for(const n of HOME_MATERIAL_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkHomeMaterialPin(pin){if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==homeMaterialDigest())fail('definition_changed','Review the homepage material discovery closure.');}
export function parseDeclaredAccept(value){
  if(typeof value!=='string'||!value||value.length>8000)fail('accept_changed','Expected a bounded declared file-accept list.');
  const entries=value.split(',').map(x=>x.trim());
  if(entries.length>128||entries.some(x=>!/^\.[a-z0-9]{1,16}$/.test(x)&&! /^[a-z][a-z0-9.+-]{0,80}\/([a-z0-9][a-z0-9.+-]{0,120}|\*)$/.test(x))||new Set(entries).size!==entries.length)
    fail('accept_changed','The declared file-accept list has an unreviewed syntax.');
  return entries;
}

export function readHomeMaterialsDOM(operation){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  if(!['home_material_state','home_material_choices'].includes(operation))return{kind:'invalid_argument'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"],[inert]')&&getComputedStyle(e).visibility!=='hidden';
  const roots=document.querySelectorAll('#title-section-prompt-container');if(roots.length!==1)return{kind:'layout_changed'};
  const root=roots[0],composers=root.querySelectorAll('[data-slot="prompt-composer"]');
  if(composers.length!==1)return{kind:'layout_changed'};
  const composer=composers[0],triggers=composer.querySelectorAll('button[aria-label="上传素材"][data-slot="home-input-composer-add-material-button"]');
  if(triggers.length!==1)return{kind:'material_control_changed'};
  const trigger=triggers[0],open=trigger.getAttribute('aria-expanded');
  if(trigger.getAttribute('aria-haspopup')!=='menu'||!['true','false'].includes(open)||trigger.getAttribute('data-state')!==(open==='true'?'open':'closed'))return{kind:'material_context_changed'};
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible);
  let menu=null,items=[];
  if(operation==='home_material_choices'){
    if(open!=='true')return{kind:'material_menu_closed'};
    if(layers.length!==1)return{kind:'dialog_open'};
    menu=layers[0];
    if(menu.getAttribute('role')!=='menu'||menu.getAttribute('data-slot')!=='dropdown-menu-content'||menu.getAttribute('data-state')!=='open'||
      !trigger.id||!menu.id||trigger.getAttribute('aria-controls')!==menu.id||menu.getAttribute('aria-labelledby')!==trigger.id)return{kind:'material_context_changed'};
    // Read the exact owned Radix background mask only. No DOM unmasking.
    const mask=trigger.closest('[aria-hidden="true"]');
    const associatedVisible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[inert]')&&(!e.closest('[aria-hidden="true"]')||e.closest('[aria-hidden="true"]')===mask)&&getComputedStyle(e).visibility!=='hidden';
    if(!associatedVisible(root)||!associatedVisible(composer)||!associatedVisible(trigger))return{kind:'material_context_changed'};
    const nodes=Array.from(menu.querySelectorAll('[role="menuitem"]')).filter(visible);
    if(!nodes.length||nodes.length>12||nodes.some(e=>e.closest('[role="menu"]')!==menu||e.getAttribute('data-size')!=='home-upload'||!['dropdown-menu-item','popover-anchor'].includes(e.getAttribute('data-slot'))))return{kind:'material_menu_changed'};
    for(const node of nodes){
      const titles=Array.from(node.querySelectorAll('[data-slot="dropdown-menu-item-title"]')).filter(visible);
      if(titles.length!==1||titles[0].children.length)return{kind:'material_menu_changed'};
      const label=titles[0].innerText.trim();if(!label||label.length>80||/[\x00-\x1f]/.test(label))return{kind:'material_menu_changed'};
      items.push({label,enabled:!node.hasAttribute('data-disabled')&&node.getAttribute('aria-disabled')!=='true',kind:({'本地上传':'local_file','资产库':'asset_library','预设提示词':'preset_prompt'})[label]||'unreviewed'});
    }
    if(new Set(items.map(x=>x.label)).size!==items.length)return{kind:'material_menu_changed'};
  }else{
    if(layers.length||open==='true')return{kind:'dialog_open'};
    if(!visible(root)||!visible(composer)||!visible(trigger))return{kind:'material_control_changed'};
  }
  const areas=composer.querySelectorAll('[class*="uploadInputArea-"]');
  if(areas.length!==1)return{kind:'material_input_changed'};
  const all=areas[0].querySelectorAll('input[type="file"]'),locals=areas[0].querySelectorAll('input[type="file"][multiple][accept]'),replacements=areas[0].querySelectorAll('input[type="file"][aria-label="替换素材文件"]');
  if(all.length!==2||locals.length!==1||replacements.length!==1||locals[0]===replacements[0]||replacements[0].multiple)return{kind:'material_input_changed'};
  const local=locals[0],count=typeof local.files?.length==='number'?local.files.length:null;
  if(count!==null&&(!Number.isInteger(count)||count<0||count>100))return{kind:'material_input_changed'};
  return{kind:'ready',accept:local.getAttribute('accept'),multiple:true,enabled:!local.disabled&&local.getAttribute('aria-disabled')!=='true'&&!local.hasAttribute('data-disabled'),selected_file_count:count,menu_open:open==='true',choices:items};
}
function validate(data,operation){
  const keys=['kind','accept','multiple','enabled','selected_file_count','menu_open','choices'];
  if(!data||typeof data!=='object'||Array.isArray(data)||Object.keys(data).length!==keys.length||keys.some(k=>!Object.hasOwn(data,k))||data.kind!=='ready'||data.multiple!==true||typeof data.enabled!=='boolean'||typeof data.menu_open!=='boolean'||data.menu_open!==(operation==='home_material_choices')||
    (data.selected_file_count!==null&&(!Number.isInteger(data.selected_file_count)||data.selected_file_count<0||data.selected_file_count>100))||!Array.isArray(data.choices)||data.choices.length>12||data.choices.some(x=>!x||typeof x!=='object'||Array.isArray(x)||Object.keys(x).length!==3||typeof x.label!=='string'||!x.label||x.label.length>80||/[\x00-\x1f]/.test(x.label)||typeof x.enabled!=='boolean'||!['local_file','asset_library','preset_prompt','unreviewed'].includes(x.kind)))fail('bridge_protocol','Unexpected homepage material metadata.');
  const expected={'本地上传':'local_file','资产库':'asset_library','预设提示词':'preset_prompt'};
  if(data.choices.some(x=>x.kind!==(expected[x.label]||'unreviewed'))||new Set(data.choices.map(x=>x.label)).size!==data.choices.length||(!data.menu_open&&data.choices.length)||data.menu_open&&!data.choices.length)fail('bridge_protocol','Unexpected homepage material choices.');
  const accept=parseDeclaredAccept(data.accept);
  return{kind:'ready',accept, multiple:true,enabled:data.enabled,selected_file_count:data.selected_file_count,menu_open:data.menu_open,choices:data.choices.map(x=>({label:x.label,enabled:x.enabled,kind:x.kind}))};
}
export async function inspectHomeMaterials(page,operation='home_material_state'){
  if(!['home_material_state','home_material_choices'].includes(operation)||!page||typeof page.evaluate!=='function')fail('invalid_argument','Select a reviewed material metadata operation.');
  const readonly=Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)});
  const read=async()=>validate(await pollDOM({evaluate:()=>readonly.evaluate(readHomeMaterialsDOM,operation)},readHomeMaterialsDOM),operation);
  const before=await read();
  const form=operation==='home_material_state'?(await inspectFormState(readonly))[0].result:null;
  const after=await read();if(JSON.stringify(before)!==JSON.stringify(after))fail('materials_changed','Homepage material metadata changed during discovery.');
  if(form){const final=(await inspectFormState(readonly))[0].result;if(final.draft_sha256!==form.draft_sha256)fail('draft_changed','The complete composer draft changed during material discovery.');}
  const mediaExtensions={image:['.jpg','.jpeg','.png','.webp','.bmp','.gif'],video:['.mp4','.mov'],audio:['.wav','.mp3']};
  return[{result:{status:'material_metadata_ready',mode:form?.mode||null,draft_sha256:form?.draft_sha256||null,draft_bound:form!==null,
    material_sha256:sha(JSON.stringify(['xyq-home-material-metadata-v1',operation,after,form?.draft_sha256||null])),
    declared_accept:after.accept,declared_media_extensions:Object.fromEntries(Object.entries(mediaExtensions).map(([k,v])=>[k,v.filter(x=>after.accept.includes(x))])),
    multiple:after.multiple,input_enabled:after.enabled,file_state_known:after.selected_file_count!==null,selected_file_count:after.selected_file_count,
    menu_open:after.menu_open,choices:after.choices,limits_verified:false,source:'visible_dom',secrets_returned:false,
    upload_started:false,file_input_sent:false,asset_selected:false,generation_submitted:false,paid_submitted:false,
    acceptance:'declared_home_intake_only_not_upload_acceptance'}}];
}
export async function inspectBoundHomeMaterials(context,operation='home_material_state',createPage=createHomeQuotePage){
  let page;try{page=await createPage(boundReadRouting(context));}catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','The bound material discovery Page was not prepared.');}
  return(await inspectHomeMaterials(page,operation)).map(({result})=>({result:{...result,browser_session:'site:xyq-home',browser_surface:'browser',binding_changed:false}}));
}
