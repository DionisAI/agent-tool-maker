// UI_SELECTOR / visible-ui: exact audio footer and public native input only.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError} from './core.mjs';
import {audioScope} from './audio.mjs';
import {AUDIO_BOUND_FILES,boundReadRouting} from './audio-bound.mjs';
import {AUDIO_SETTINGS_FILES,parseAudioSettings,inspectAudioChoices,prepareAudioSettings,readAudioSettingsTargetDOM} from './audio-settings.mjs';
import {AUDIO_PROMPT_FILES,parseAudioPromptSettings,prepareAudioPrompt} from './audio-prompt.mjs';

export const AUDIO_EDIT_BOUND_FILES=[...new Set([...AUDIO_SETTINGS_FILES,...AUDIO_PROMPT_FILES,...AUDIO_BOUND_FILES]),'audio-edit-bound.mjs','audio-edit-bound.js'];
export const AUDIO_EDIT_BOUND_OPERATIONS=['audio_choices','audio_prepare','audio_prompt_prepare'];
const fail=(code,message)=>{throw new XyqError(code,message);};
export function audioEditBoundDigest(){const h=createHash('sha256');for(const n of AUDIO_EDIT_BOUND_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkAudioEditBoundPin(pin){if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==audioEditBoundDigest())fail('definition_changed','Review the explicit audio-edit bundle.');}
export function audioEditBoundSettings(operation,raw){
  if(!AUDIO_EDIT_BOUND_OPERATIONS.includes(operation))fail('invalid_argument','Use a documented audio preparation operation.');
  if(operation==='audio_choices'){if(raw!==undefined)fail('invalid_argument','Audio choices takes no settings.');return undefined;}
  let value;try{value=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use typed audio settings JSON.');}
  if(!value||typeof value!=='object'||Array.isArray(value)||![Object.prototype,null].includes(Object.getPrototypeOf(value))||!Object.hasOwn(value,'expected_form_sha256')||typeof value.expected_form_sha256!=='string'||Object.hasOwn(value,'reference_sha256')&&typeof value.reference_sha256!=='string')fail('invalid_argument','Use owned string form/reference digests.');
  return operation==='audio_prepare'?parseAudioSettings(value):parseAudioPromptSettings(value);
}

// Serialization-ready DOM reader; fixed controls only, no DOM mutations.
export function readAudioEditInputDOM(request){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/project')return{kind:'unsupported_surface'};
  const u=new URL(location.href),scope=request.scope;
  if(u.searchParams.get('projectId')!==scope.project_id||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const roots=Array.from(document.querySelectorAll('[data-testid="rf__wrapper"][role="application"]')).filter(visible);
  if(roots.length!==1)return{kind:'layout_changed'};
  const nodes=roots[0].querySelectorAll('.react-flow__node-biz\\/audio');
  if(nodes.length!==1)return{kind:'audio_node_ambiguous'};
  if(nodes[0].getAttribute('data-id')!==scope.node_id)return{kind:'node_changed'};
  const panels=Array.from(roots[0].querySelectorAll('[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"]')).filter(visible);
  if(panels.length!==1)return{kind:'audio_form_closed'};
  const panel=panels[0],prefix='[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"]';
  const modelTrigger='[data-xyq-selected-audio-footer-panel="true"] button[data-action="select-audio-model"]';
  const rateTrigger='[data-xyq-selected-audio-footer-panel="true"] button[data-action="open-audio-parameter"][data-action-object-id="sample_rate"]';
  const modelItem='[role="dialog"][data-slot="popover-content"][aria-label="模型选择"] button[aria-pressed]';
  const rateItem='[role="menu"][data-slot="dropdown-menu-content"][aria-label="采样率"] [role="menuitemradio"]';
  const editorSelector=prefix+' [data-testid="canvas-generation-prompt-editor"][contenteditable="true"]';
  const mentionSelector=prefix+' button[data-action="mention-audio-reference"]';
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible).filter(e=>e!==panel);
  const menuOwned=kind=>{
    if(layers.length!==1)return false;
    const layer=layers[0],triggers=panel.querySelectorAll(kind==='model'?'button[data-action="select-audio-model"]':'button[data-action="open-audio-parameter"][data-action-object-id="sample_rate"]');
    if(triggers.length!==1||!visible(triggers[0])||triggers[0].getAttribute('data-state')!=='open')return false;
    return kind==='model'?layer.matches('[role="dialog"][data-slot="popover-content"][aria-label="模型选择"]'):layer.matches('[role="menu"][data-slot="dropdown-menu-content"][aria-label="采样率"]')&&!!triggers[0].id&&layer.getAttribute('aria-labelledby')===triggers[0].id;
  };
  if(request.kind==='escape')return{kind:['model','sample_rate'].includes(request.menu)&&menuOwned(request.menu)?'ready':'dialog_open'};
  if(![modelTrigger,rateTrigger,modelItem,rateItem,editorSelector,mentionSelector].includes(request.selector)||!Number.isInteger(request.nth)||request.nth<0||request.nth>49)return{kind:'invalid_argument'};
  const all=document.querySelectorAll(request.selector),e=all[request.nth];
  if(!visible(e)||e.disabled||e.readOnly||e.getAttribute('aria-disabled')==='true'||e.hasAttribute('data-disabled'))return{kind:'control_obscured'};
  const item=request.selector===modelItem||request.selector===rateItem;
  if(item){if(!menuOwned(request.selector===modelItem?'model':'sample_rate')||!layers[0].contains(e))return{kind:'dialog_open'};}
  else if(layers.length||!panel.contains(e))return{kind:'dialog_open'};
  const point=()=>{
    const b=e.getBoundingClientRect(),x=request.point?.x??b.x+b.width/2,y=request.point?.y??b.y+b.height/2;
    if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||y<0||b.width<=0||b.height<=0||x<=b.x||x>=b.right||y<=b.y||y>=b.bottom)return null;
    const hit=document.elementFromPoint(x,y);return hit===e||e.contains(hit)?{x,y}:null;
  };
  if(request.kind==='click'){const p=point();return p?{kind:'ready',...p}:{kind:'control_obscured'};}
  if(request.selector!==editorSelector||all.length!==1||!e.isContentEditable)return{kind:'invalid_argument'};
  if(request.kind==='end')return{kind:document.activeElement===e?'ready':'selection_changed'};
  // Plain replacement stays separate from structured-reference appending.
  if(e.querySelector('[contenteditable="false"],img,video,audio'))return{kind:'rich_prompt_present'};
  const parts=[];let supported=true;
  for(const p of e.childNodes){
    if(p.nodeType!==1||p.tagName!=='P'){supported=false;break;}
    let value='';for(const n of p.childNodes){if(n.nodeType===3)value+=n.textContent;else if(n.nodeType===1&&n.tagName==='BR'){if(!n.classList.contains('ProseMirror-trailingBreak'))value+='\n';}else supported=false;}
    parts.push(value);
  }
  if(!supported)return{kind:'unsupported_prompt_structure'};
  const text=parts.join('\n');
  if(request.kind==='target'){const p=point();return p?{kind:'ready',...p,text,modifier:/^Mac/.test(navigator.platform)?'Meta':'Control'}:{kind:'control_obscured'};}
  if(document.activeElement!==e)return{kind:'selection_changed'};
  if(request.kind==='readback')return{kind:text===request.value?'ready':'prompt_changed'};
  if(request.kind==='caret'){
    const s=window.getSelection(),r=s?.rangeCount===1?s.getRangeAt(0):null;
    return{kind:r?.collapsed&&e.contains(r.startContainer)&&e.contains(r.endContainer)?'ready':'selection_changed'};
  }
  if(text!==request.expected_text)return{kind:'draft_changed'};
  if(request.kind==='focus')return{kind:'ready'};
  if(request.kind==='selected'){
    const s=window.getSelection(),r=s?.rangeCount===1?s.getRangeAt(0):null;
    if(!r||!e.contains(r.startContainer)||!e.contains(r.endContainer))return{kind:'selection_changed'};
    const a=document.createRange(),b=document.createRange();a.selectNodeContents(e);a.setEnd(r.startContainer,r.startOffset);b.selectNodeContents(e);b.setStart(r.endContainer,r.endOffset);
    return{kind:!a.toString()&&!b.toString()&&r.toString()===(e.textContent||'')?'ready':'selection_changed'};
  }
  return{kind:'invalid_argument'};
}

export async function createAudioEditBackend(routing){const {Page}=await import('@jackwener/opencli/browser/page');return new Page('site:xyq-web',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);}
export function audioEditPage(backend,rawScope,operation){
  const scope=audioScope(rawScope);
  if(!AUDIO_EDIT_BOUND_OPERATIONS.includes(operation)||!backend||typeof backend.evaluate!=='function')fail('unsupported_backend','Use a documented audio operation and public Page evaluator.');
  let ownedMenu=null,lastPointTarget=null,uncertainInput=false;
  const prefix='[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"]',editor=prefix+' [data-testid="canvas-generation-prompt-editor"][contenteditable="true"]';
  const check=async request=>{const t=await backend.evaluate(readAudioEditInputDOM,{scope,...request});if(t?.kind!=='ready')fail(t?.kind||'control_changed','Audio input association, focus or readback changed; inspect the exact draft.');return t;};
  const nativeClick=async target=>{
    if(typeof backend.nativeClick!=='function')fail('unsupported_backend','Audio input requires public nativeClick.');
    if(!Number.isFinite(target.x)||!Number.isFinite(target.y)||target.x<0||target.y<0)fail('control_changed','Unexpected native target metadata.');
    try{await backend.nativeClick(target.x,target.y);}catch(e){uncertainInput=true;if(e instanceof XyqError)throw e;const f=new XyqError('bridge_failed','Native audio input failed; inspect before continuing.');f.outcome_uncertain=true;throw f;}
  };
  const click=async(selector,options,point)=>{
    const target=await check({kind:'click',selector,nth:options?.nth,point});
    if(selector.endsWith('button[data-action="select-audio-model"]'))ownedMenu='model';
    if(selector.endsWith('button[data-action="open-audio-parameter"][data-action-object-id="sample_rate"]'))ownedMenu='sample_rate';
    await nativeClick(target);
  };
  const page={get outcome_uncertain(){return uncertainInput;},evaluate:async(fn,arg)=>{const result=await backend.evaluate(fn,arg);lastPointTarget=fn===readAudioSettingsTargetDOM&&result?.kind==='ready'?{arg,result}:null;return result;},click:(selector,options)=>click(selector,options),
    clickPoint:async point=>{
      const prior=lastPointTarget;lastPointTarget=null;
      if(!prior||!point||point.x!==prior.result.point?.x||point.y!==prior.result.point?.y)fail('control_changed','Native point must match the exact inspected audio control.');
      const fresh=await backend.evaluate(readAudioSettingsTargetDOM,prior.arg);
      if(fresh?.kind!=='ready'||!fresh.pointer_ready||fresh.selector!==prior.result.selector||fresh.nth!==prior.result.nth||fresh.point?.x!==point.x||fresh.point?.y!==point.y)fail('control_changed','The inspected audio point changed; no input sent.');
      await click(fresh.selector,{nth:fresh.nth},point);
    },
    pressKey:async key=>{if(key!=='Escape'||!ownedMenu)fail('invalid_argument','Only owned audio-menu Escape is available.');if(typeof backend.nativeKeyPress!=='function')fail('unsupported_backend','Menu cleanup needs public nativeKeyPress.');await check({kind:'escape',menu:ownedMenu});try{await backend.nativeKeyPress('Escape');ownedMenu=null;}catch(e){uncertainInput=true;const f=e instanceof XyqError?e:new XyqError('bridge_failed','Native audio menu cleanup failed.');f.outcome_uncertain=true;throw f;}}
  };
  if(operation==='audio_prompt_prepare'){
    page.focus=async(selector,options)=>{if(selector!==editor)fail('invalid_argument','Only the exact audio editor can receive focus.');await click(selector,options);};
    page.nativeEnd=async()=>{
      if(typeof backend.cdp!=='function')fail('unsupported_backend','Reference append needs the fixed native End command.');
      await check({kind:'end',selector:editor,nth:0});
      try{await backend.cdp('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'End',code:'End',windowsVirtualKeyCode:35,modifiers:0,commands:['moveToEndOfDocument']});await backend.cdp('Input.dispatchKeyEvent',{type:'keyUp',key:'End',code:'End',windowsVirtualKeyCode:35,modifiers:0});}
      catch(e){uncertainInput=true;const f=e instanceof XyqError?e:new XyqError('bridge_failed','Native audio caret input failed.');f.outcome_uncertain=true;throw f;}
    };
    page.fillText=async(selector,value,options)=>{
      if(selector!==editor||options?.nth!==0||typeof value!=='string'||value.length>20000||value.includes('\r'))fail('invalid_argument','Use the fixed plain audio prompt and literal LF text.');
      if(['nativeClick','nativeType','cdp'].some(k=>typeof backend[k]!=='function'))fail('unsupported_backend','Plain audio input requires public native input and fixed editing commands.');
      let phase='target',applied=false;
      try{
        const request={selector:editor,nth:0},target=await check({...request,kind:'target'});
        if(typeof target.text!=='string'||!['Meta','Control'].includes(target.modifier))fail('control_changed','Unexpected native text metadata.');
        phase='focus';await nativeClick(target);await check({...request,kind:'focus',expected_text:target.text});
        const edit=async command=>{
          const event=command==='deleteBackward'?{key:'Backspace',code:'Backspace',windowsVirtualKeyCode:8,modifiers:0}:command==='insertLineBreak'?{key:'Enter',code:'Enter',windowsVirtualKeyCode:13,modifiers:8}:{key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:target.modifier==='Meta'?4:2};
          await backend.cdp('Input.dispatchKeyEvent',{type:'keyDown',...event,commands:[command]});await backend.cdp('Input.dispatchKeyEvent',{type:'keyUp',...event});
        };
        phase='select_all';await edit('selectAll');phase='selected';await check({...request,kind:'selected',expected_text:target.text});
        phase='replace';applied=true;const lines=value.split('\n');if(lines[0])await backend.nativeType(lines[0]);else await edit('deleteBackward');
        for(const line of lines.slice(1)){phase='line_break';await check({...request,kind:'caret'});await edit('insertLineBreak');phase='replace';await check({...request,kind:'caret'});if(line)await backend.nativeType(line);}
        phase='readback';await check({...request,kind:'readback',value});
      }catch(e){const f=e instanceof XyqError?e:new XyqError('bridge_failed','Native audio prompt input failed; inspect the current draft.');f.input_phase=phase;if(applied||!(e instanceof XyqError)){uncertainInput=true;f.outcome_uncertain=true;}throw f;}
    };
  }
  return Object.freeze(page);
}
export async function runBoundAudioEdit(context,operation,rawScope,rawSettings,createBackend=createAudioEditBackend){
  const scope=audioScope(rawScope),settings=audioEditBoundSettings(operation,rawSettings);let page;
  try{page=audioEditPage(await createBackend(boundReadRouting(context)),scope,operation);}catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','Explicit audio Page preparation failed.');}
  try{
    const output=await(operation==='audio_choices'?inspectAudioChoices(page,scope):operation==='audio_prepare'?prepareAudioSettings(page,scope,settings):prepareAudioPrompt(page,scope,settings));
    return output.map(({result})=>({result:{...result,browser_session:'site:xyq-web',browser_surface:'browser',binding_changed:false}}));
  }catch(e){if(e instanceof XyqError){if(page.outcome_uncertain)e.outcome_uncertain=true;throw e;}fail('bridge_failed','Explicit audio operation failed; inspect the current draft.');}
}
