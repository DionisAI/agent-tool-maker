// Current creative composer only; native input, no uploads or generation.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,FILES,pollDOM,readHomeDOM,readOptionsDOM} from './core.mjs';

export const FORM_FILES=[...FILES,'form.mjs','form.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
export function formDigest(){const h=createHash('sha256');for(const n of FORM_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkFormPin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==formDigest())fail('definition_changed','Review the XYQ form adapter before execution.');}
export function parseSettings(raw){
  let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','settings must be JSON.');}
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!['expected_draft_sha256','model','radios','duration_seconds','canvas','prompt'].includes(k)))fail('invalid_argument','Use typed form settings, not selectors, URLs or scripts.');
  if(!/^[a-f0-9]{64}$/.test(v.expected_draft_sha256||''))fail('invalid_argument','Bind preparation to the inspected draft.');
  if('model'in v&&(typeof v.model!=='string'||!v.model.trim()||v.model.length>128))fail('invalid_argument','model must be an exact observed model title.');
  if('radios'in v&&(!v.radios||typeof v.radios!=='object'||Array.isArray(v.radios)||Object.keys(v.radios).length>10||Object.entries(v.radios).some(([k,x])=>!k.trim()||k.length>128||typeof x!=='string'||!x.trim()||x.length>128)))fail('invalid_argument','radios must map exact observed group labels to option labels.');
  if('duration_seconds'in v&&(!Number.isInteger(v.duration_seconds)||v.duration_seconds<1||v.duration_seconds>600))fail('invalid_argument','duration_seconds must be a bounded integer.');
  if('canvas'in v&&typeof v.canvas!=='boolean')fail('invalid_argument','canvas must be boolean.');
  if('prompt'in v&&(typeof v.prompt!=='string'||v.prompt.length>20000))fail('invalid_argument','prompt must contain 0-20000 characters.');
  return v;
}

// Internal raw prompt and file metadata are hashed on the Node side, never output.
export function readDraftDOM(context={}){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  let modeMask=null;
  if(context?.owned_mode_menu===true){
    const ts=document.querySelectorAll('#title-section-prompt-container button[aria-label="选择创作模式"]');
    if(ts.length===1&&ts[0].getAttribute('data-state')==='open'){
      const trigger=ts[0],layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]'));
      if(!layers.length)return{kind:'pending'};
      const m=layers[0];if(layers.length!==1||m.getAttribute('role')!=='menu'||m.getAttribute('data-slot')!=='dropdown-menu-content'||!m.querySelector('[role="menuitemradio"] [data-slot="dropdown-menu-item-title"]')||!trigger.id||!m.id||trigger.getAttribute('aria-controls')!==m.id||m.getAttribute('aria-labelledby')!==trigger.id||trigger.getAttribute('aria-expanded')!=='true')return{kind:'mode_context_changed'};
      modeMask=trigger.closest('[aria-hidden="true"]');
    }
  }
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden]')&&(!e.closest('[aria-hidden="true"]')||e.closest('[aria-hidden="true"]')===modeMask);
  const root=document.querySelector('#title-section-prompt-container');if(!visible(root))return{kind:'pending'};
  const editors=Array.from(root.querySelectorAll('[role="textbox"][contenteditable="true"]')).filter(visible);
  if(editors.length!==1)return{kind:'unsupported_surface'};
  const editor=editors[0],composer=editor.closest('[data-slot="prompt-composer"]');
  if(!composer||composer.querySelectorAll('[role="textbox"][contenteditable="true"]').length!==1)return{kind:'layout_changed'};
  const cleanURL=s=>{if(!s)return null;try{const u=new URL(s,location.origin);return u.origin+u.pathname;}catch{return null;}};
  const tree=e=>e.nodeType===3?e.textContent:e.nodeType===1?[e.tagName,
    ['contenteditable','data-type','data-id','data-reference-id','data-reference-type','data-action-object-id','title','aria-label','src','href'].map(k=>[k,['src','href'].includes(k)?cleanURL(e.getAttribute(k)):e.getAttribute(k)]).filter(x=>x[1]!==null),Array.from(e.childNodes).map(tree)]:null;
  const raw=(editor.innerText||'').replace(/\r\n/g,'\n');
  const prompt=raw.trim()?raw:'';
  if(prompt.length>20000)return{kind:'layout_changed'};
  const rich=Array.from(editor.querySelectorAll('[contenteditable="false"],img,video,audio'));
  const media=Array.from(composer.querySelectorAll('img,video,audio')).map(e=>({tag:e.tagName,src:cleanURL(e.getAttribute('src')),alt:e.getAttribute('alt')}));
  const files=Array.from(composer.querySelectorAll('input[type="file"]')).map(e=>({accept:e.getAttribute('accept'),multiple:e.hasAttribute('multiple'),
    files:typeof e.files?.length==='number'?Array.from(e.files).map(f=>({name:f.name,size:f.size,type:f.type,last_modified:f.lastModified})):null}));
  // Audio/file chips may have no media element and the browser resets FileList
  // after upload. Bind the observed attachment rail, not FileList alone.
  const rails=Array.from(composer.querySelectorAll('[data-slot="home-input-composer-attachments"]'));
  if(rails.length>1)return{kind:'layout_changed'};
  const attachments=rails.length?tree(rails[0]):null;
  const attachment_present=rails.length?!!rails[0].querySelector(':not(div):not(input)')||!!rails[0].innerText.trim():false;
  if(media.length>100||files.length>10||files.some(e=>e.files?.length>100))return{kind:'layout_changed'};
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible);
  return{kind:'ready',prompt,prompt_tree:prompt||rich.length?tree(editor):null,rich_references:rich.length,media,files,attachments,attachment_present,
    layers:layers.length,preferences_layers:layers.filter(e=>e.querySelector('section[aria-label="模型选择"]')&&e.querySelector('section[aria-label="偏好设置"]')).length};
}

const SELECTORS={preferences:'#title-section-prompt-container button[aria-label^="模型选择和偏好设置"]',
  model:'section[aria-label="模型选择"] button[aria-pressed]:has([data-slot="model-picker-item-title"]),section[aria-label="模型选择"] [role="checkbox"]',
  radio:'section[aria-label="偏好设置"] [role="radio"]',duration:'section[aria-label="偏好设置"] input[aria-label="视频时长秒数"]',
  canvas:'#title-section-prompt-container [role="switch"][aria-label="画布"]',prompt:'#title-section-prompt-container [role="textbox"][contenteditable="true"]'};
export function readTargetDOM(t){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/home')return{kind:'origin_mismatch'};
  const selectors={preferences:'#title-section-prompt-container button[aria-label^="模型选择和偏好设置"]',
    model:'section[aria-label="模型选择"] button[aria-pressed]:has([data-slot="model-picker-item-title"]),section[aria-label="模型选择"] [role="checkbox"]',
    radio:'section[aria-label="偏好设置"] [role="radio"]',duration:'section[aria-label="偏好设置"] input[aria-label="视频时长秒数"]',
    canvas:'#title-section-prompt-container [role="switch"][aria-label="画布"]',prompt:'#title-section-prompt-container [role="textbox"][contenteditable="true"]'};
  if(!Object.hasOwn(selectors,t.kind))return{kind:'invalid_argument'};
  const all=Array.from(document.querySelectorAll(selectors[t.kind]));
  const text=e=>(e?.innerText||'').replace(/\s+/g,' ').trim();
  const candidates=all.filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]')).filter(e=>{
    if(t.kind==='model')return(text(e.querySelector('[data-slot="model-picker-item-title"]'))||e.getAttribute('aria-label')||text(e))===t.label;
    if(t.kind==='radio')return(e.getAttribute('aria-label')||text(e))===t.label&&(e.closest('[role="radiogroup"]')?.getAttribute('aria-label')||text(e.closest('[data-slot="home-direct-generic-parameter-field"]')?.querySelector('[data-slot="home-direct-parameter-label"]'))||null)===t.group;
    return true;
  });
  if(candidates.length!==1)return{kind:'control_changed'};
  const e=candidates[0],r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return{kind:'ready',nth:all.indexOf(e),pointer_ready:r.width>0&&r.height>0&&!e.disabled&&e.getAttribute('aria-disabled')!=='true'&&!e.hasAttribute('data-disabled')&&(hit===e||e.contains(hit))};
}
async function target(page,t){const d=await pollDOM({evaluate:()=>page.evaluate(readTargetDOM,t)},readTargetDOM);if(!d.pointer_ready)fail('control_obscured','Requested form control is disabled or covered; no input sent.');return d;}
async function click(page,t){const d=await target(page,t);await page.click(SELECTORS[t.kind],{nth:d.nth});}
async function fill(page,t,value){const d=await target(page,t);await page.fillText(SELECTORS[t.kind],value,{nth:d.nth});}
async function state(page){
  const home=await pollDOM(page,readHomeDOM);
  if(home.agent!=='创作'||!home.form||!['图片生成','视频生成','音频生成'].includes(home.form.mode))fail('unsupported_surface','This adapter covers the current creative image/video/audio composer.');
  const draft=await pollDOM(page,readDraftDOM);
  const after=await pollDOM(page,readHomeDOM);
  if(after.agent!==home.agent||!after.form||after.form.mode!==home.form.mode||after.form.preferences!==home.form.preferences||JSON.stringify(after.form.canvas)!==JSON.stringify(home.form.canvas))fail('draft_changed','Form changed during snapshot.');
  return{home,draft};
}
export function draftHash(s){return sha(JSON.stringify(['xyq-home-draft-v2',s.home.agent,s.home.form.mode,s.home.form.preferences,s.home.form.canvas,s.draft.prompt,s.draft.prompt_tree,s.draft.media,s.draft.files,s.draft.attachments??null]));}
const refs=s=>JSON.stringify([s.draft.media,s.draft.files,s.draft.rich_references,s.draft.attachments??null]);
function result(s,extra={}){return{status:'ready',agent:s.home.agent,mode:s.home.form.mode,form:s.home.form,draft_sha256:draftHash(s),prompt_sha256:sha(s.draft.prompt),
  references:{media_count:s.draft.media.length,rich_reference_count:s.draft.rich_references,attachment_present:s.draft.attachment_present??false,file_counts:s.draft.files.map(e=>e.files?.length??null),state_known:s.draft.files.every(e=>e.files!==null)},
  source:'visible_dom',secrets_returned:false,paid_submitted:false,upload_started:false,...extra};}
function context(s,owned=false){if(s.draft.layers&&( !owned||s.draft.layers!==1||s.draft.preferences_layers!==1))fail('dialog_open','Existing browser layers are preserved. Close them locally before preparation.');}
function preserve(before,after,promptRequested=false){
  if(after.home.agent!==before.home.agent||after.home.form.mode!==before.home.form.mode||refs(before)!==refs(after)||!promptRequested&&(before.draft.prompt!==after.draft.prompt||JSON.stringify(before.draft.prompt_tree)!==JSON.stringify(after.draft.prompt_tree)))fail('draft_changed','Unrequested draft or reference change; inspect the current form.');
}
async function options(page){return pollDOM(page,readOptionsDOM);}
async function ownedMenu(page,fn){
  let owned=false,primary,output;
  try{
    const s=await state(page);context(s);
    if(s.home.form.preferences_open)fail('dialog_open','An existing preferences menu is preserved.');
    owned=true;await click(page,{kind:'preferences'});
    const opened=await state(page);context(opened,true);
    if(!opened.home.form.preferences_open)fail('menu_not_open','The preferences menu did not open.');
    output=await fn(await options(page));
  }catch(e){primary=e;}
  let cleanup;
  if(owned){try{
    const s=await state(page);context(s,true);
    // Live Chrome's owned preference popover closes reliably with native Escape;
    // button toggles can interact with focus/portal state. Never dismiss other layers.
    if(s.home.form.preferences_open){if(typeof page.pressKey!=='function')fail('unsupported_backend','Owned-menu cleanup needs native keyboard support.');await page.pressKey('Escape');}
    const closed=await state(page);
    if(closed.home.form.preferences_open||closed.draft.layers)fail('cleanup_failed','The owned preferences menu remains open.');
  }catch(e){cleanup=e;}}
  if(primary){if(cleanup)primary.cleanup_code=cleanup.code||'bridge_failed';throw primary;}
  if(cleanup)throw cleanup;
  return output;
}
export async function inspectFormState(page){const s=await state(page);return[{result:result(s)}];}
export async function inspectFormChoices(page){const before=await state(page);context(before);const o=await ownedMenu(page,async x=>x);const after=await state(page);if(draftHash(after)!==draftHash(before))fail('draft_changed','Draft changed during options discovery.');return[{result:result(after,{options:o,quote_status:'not_final'})}];}

export async function prepareForm(page,raw){
  const requested=parseSettings(raw),steps=[];let phase='snapshot';
  try{
    const initial=await state(page);context(initial);
    if(draftHash(initial)!==requested.expected_draft_sha256)fail('draft_changed','Draft differs from the inspected digest; no input sent.');
    if(initial.draft.files.some(e=>e.files===null))fail('reference_state_unknown','File state is unknown; preparation stops before input.');
    if('prompt'in requested&&requested.prompt!==initial.draft.prompt&&initial.draft.rich_references)fail('rich_prompt_present','Rich references require their own edit contract; no prompt replacement sent.');
    let finalOptions=null,originalOptions=null;
    if('model'in requested||'radios'in requested||'duration_seconds'in requested){
      phase='preferences';
      await ownedMenu(page,async o=>{
        originalOptions=o;
        let s=await state(page);preserve(initial,s);if(draftHash(s)!==requested.expected_draft_sha256)fail('draft_changed','Draft changed before parameter input.');
        if('model'in requested){
          const item=o.models.find(x=>x.label===requested.model);
          if(!item||item.disabled)fail('setting_unavailable','Requested model is not enabled in the visible menu.');
          if(!item.checked){phase='model';await click(page,{kind:'model',label:requested.model});o=await options(page);s=await state(page);context(s,true);preserve(initial,s);
            if(!o.models.some(x=>x.label===requested.model&&x.checked))fail('settings_changed','Model selection differs from readback.');steps.push('model');}
        }
        // Validate the entire parameter request against the post-model dynamic menu.
        for(const[group,label]of Object.entries(requested.radios||{})){
          const matches=o.radios.filter(x=>x.group===group&&x.label===label);
          if(matches.length!==1||matches[0].disabled)fail('setting_unavailable','Requested group/option is not uniquely enabled.');
        }
        let bounds;
        if('duration_seconds'in requested){const ns=o.numbers.filter(x=>x.label==='视频时长秒数'),ss=o.sliders.filter(x=>x.label==='视频秒数');
          if(ns.length!==1||ss.length!==1)fail('setting_unavailable','Video duration input and bounds are not present.');
          bounds=[Number(ss[0].min),Number(ss[0].max)];
          if(!ss[0].min||!ss[0].max||!bounds.every(Number.isFinite)||bounds[0]>bounds[1]||requested.duration_seconds<bounds[0]||requested.duration_seconds>bounds[1])fail('setting_unavailable','Duration exceeds the visible slider bounds.');
        }
        for(const[group,label]of Object.entries(requested.radios||{})){
          if(!o.radios.some(x=>x.group===group&&x.label===label&&x.checked)){
            phase='radio';s=await state(page);context(s,true);preserve(initial,s);await click(page,{kind:'radio',group,label});o=await options(page);
            if(!o.radios.some(x=>x.group===group&&x.label===label&&x.checked))fail('settings_changed','Parameter selection differs from readback.');steps.push('radio:'+group);
          }
        }
        if('duration_seconds'in requested&&Number(o.numbers.find(x=>x.label==='视频时长秒数').value)!==requested.duration_seconds){
          phase='duration';s=await state(page);context(s,true);preserve(initial,s);await fill(page,{kind:'duration'},String(requested.duration_seconds));o=await options(page);
          if(Number(o.numbers.find(x=>x.label==='视频时长秒数')?.value)!==requested.duration_seconds||Number(o.sliders.find(x=>x.label==='视频秒数')?.value)!==requested.duration_seconds)fail('settings_changed','Video duration differs from input/slider readback.');steps.push('duration_seconds');
        }
        finalOptions=o;
      });
    }
    let s=await state(page);context(s);preserve(initial,s);
    if(!finalOptions&&s.home.form.preferences!==initial.home.form.preferences)fail('draft_changed','Unrequested preferences changed before input.');
    if('canvas'in requested&&requested.canvas!==s.home.form.canvas.checked){phase='canvas';if(s.home.form.canvas.disabled)fail('setting_unavailable','Canvas toggle is disabled in this mode.');await click(page,{kind:'canvas'});s=await state(page);context(s);preserve(initial,s);if(s.home.form.canvas.checked!==requested.canvas)fail('settings_changed','Canvas differs from readback.');steps.push('canvas');}
    if('prompt'in requested&&requested.prompt!==s.draft.prompt){phase='prompt';await fill(page,{kind:'prompt'},requested.prompt);steps.push('prompt');}
    phase='final_readback';const final=await state(page);context(final);preserve(initial,final,'prompt'in requested);
    if(!finalOptions&&final.home.form.preferences!==initial.home.form.preferences)fail('draft_changed','Unrequested preferences changed during preparation.');
    if('prompt'in requested&&final.draft.prompt!==requested.prompt)fail('settings_changed','Prompt differs from readback.');
    if('canvas'in requested&&final.home.form.canvas.checked!==requested.canvas)fail('settings_changed','Canvas differs from final readback.');
    // Reopen/read/close our menu to verify every requested dynamic setting at exit.
    if(finalOptions){finalOptions=await ownedMenu(page,async x=>x);
      if('model'in requested&&!finalOptions.models.some(x=>x.label===requested.model&&x.checked)||Object.entries(requested.radios||{}).some(([g,l])=>!finalOptions.radios.some(x=>x.group===g&&x.label===l&&x.checked))||'duration_seconds'in requested&&Number(finalOptions.numbers.find(x=>x.label==='视频时长秒数')?.value)!==requested.duration_seconds)fail('settings_changed','Requested settings differ from final menu readback.');}
    const after=await state(page);context(after);if(draftHash(after)!==draftHash(final))fail('draft_changed','Draft changed during final verification.');
    const implicit={};
    if(originalOptions&&finalOptions){
      const selection=o=>({model:o.models.find(x=>x.checked)?.label,
        radios:Object.fromEntries(o.radios.filter(x=>x.checked&&x.group).map(x=>[x.group,x.label])),
        numbers:Object.fromEntries(o.numbers.filter(x=>x.label).map(x=>[x.label,x.value]))});
      const a=selection(originalOptions),b=selection(finalOptions);
      if(!('model'in requested)&&a.model!==b.model)implicit.model={before:a.model,after:b.model};
      for(const g of new Set([...Object.keys(a.radios),...Object.keys(b.radios)]))if(!(g in (requested.radios||{}))&&a.radios[g]!==b.radios[g])implicit['radio:'+g]={before:a.radios[g]??null,after:b.radios[g]??null};
      for(const label of new Set([...Object.keys(a.numbers),...Object.keys(b.numbers)]))if(!(label==='视频时长秒数'&&'duration_seconds'in requested)&&a.numbers[label]!==b.numbers[label])implicit['number:'+label]={before:a.numbers[label]??null,after:b.numbers[label]??null};
    }
    if(!('canvas'in requested)&&initial.home.form.canvas.checked!==after.home.form.canvas.checked)implicit.canvas={before:initial.home.form.canvas.checked,after:after.home.form.canvas.checked};
    return[{result:result(after,{prepared:true,completed_steps:steps,options:finalOptions,implicit_changes:implicit,quote_status:'not_final'})}];
  }catch(error){const e=error instanceof XyqError?error:new XyqError('bridge_failed','Native form operation failed; inspect the current draft before continuing.');if(error?.cleanup_code)e.cleanup_code=error.cleanup_code;e.phase=phase;e.completed_steps=steps;throw e;}
}
