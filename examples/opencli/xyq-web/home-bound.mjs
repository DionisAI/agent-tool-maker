// Strategy UI_SELECTOR / visible-ui: existing form DOM and public native input.
// Explicit existing-home session; no auth access, upload or media submission.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError} from './core.mjs';
import {inspectFormState,inspectFormChoices,parseSettings,prepareForm} from './form.mjs';
import {MODE_FILES,parseModeSettings,inspectModeChoices,prepareMode} from './mode.mjs';
import {AUDIO_BOUND_FILES,boundReadRouting} from './audio-bound.mjs';

export const HOME_BOUND_FILES=[...new Set([...MODE_FILES,...AUDIO_BOUND_FILES]),'home-bound.mjs','home-bound.js'];
export const HOME_BOUND_OPERATIONS=['form_state','form_choices','form_prepare','mode_choices','mode_prepare'];
const fail=(code,message)=>{throw new XyqError(code,message);};
export function homeBoundDigest(){const h=createHash('sha256');for(const n of HOME_BOUND_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkHomeBoundPin(pin){if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==homeBoundDigest())fail('definition_changed','Review the explicit home-binding source bundle.');}
export function homeBoundSettings(operation,raw){
  if(!HOME_BOUND_OPERATIONS.includes(operation))fail('invalid_argument','Use a documented home-binding operation.');
  if(!['mode_prepare','form_prepare'].includes(operation)){
    if(raw!==undefined)fail('invalid_argument','This home query takes no settings.');
    return undefined;
  }
  const settings=operation==='form_prepare'?parseSettings(raw):parseModeSettings(raw);
  if(typeof settings.expected_draft_sha256!=='string')fail('invalid_argument','Use a string draft digest.');
  return settings;
}

export function readHomeBoundSurfaceDOM(context){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  const root=document.querySelector('#title-section-prompt-container');
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]'));
  if(layers.length&&(root?.closest('[aria-hidden="true"]')||context?.read_only!==true))return{kind:'dialog_open'};
  return{kind:'ready'};
}

// Evaluations inspect DOM only. Coordinates never come from CLI input.
export function readHomeBoundInputDOM(request){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const selectors=['#title-section-prompt-container button[aria-label^="模型选择和偏好设置"]','#title-section-prompt-container button[aria-label="选择创作模式"]','[role="menu"][data-slot="dropdown-menu-content"] [role="menuitemradio"]'];
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible);
  const pref=document.querySelector(selectors[0]);
  const ownedPreferences=layer=>visible(pref)&&!!layer?.id&&pref.getAttribute('aria-controls')===layer.id&&pref.getAttribute('aria-expanded')==='true'&&layer.getAttribute('data-slot')==='generation-preferences-panel-positioner'&&layer.getAttribute('data-state')==='open'&&layer.querySelectorAll('section[aria-label="模型选择"]').length===1&&layer.querySelectorAll('section[aria-label="偏好设置"]').length===1;
  const prepareSelectors=['section[aria-label="模型选择"] button[aria-pressed]:has([data-slot="model-picker-item-title"]),section[aria-label="模型选择"] [role="checkbox"]','section[aria-label="偏好设置"] [role="radio"]','#title-section-prompt-container [role="switch"][aria-label="画布"]'];
  if(request.kind==='click'){
    if(!(selectors.includes(request.selector)||request.prepare===true&&prepareSelectors.includes(request.selector))||!Number.isInteger(request.nth)||request.nth<0||request.nth>(selectors.includes(request.selector)?19:99))return{kind:'invalid_argument'};
    const element=document.querySelectorAll(request.selector)[request.nth];
    if(!visible(element))return{kind:'control_changed'};
    if(prepareSelectors.includes(request.selector)){
      if(request.selector===prepareSelectors[2]){if(layers.length)return{kind:'dialog_open'};}
      else if(layers.length!==1||!ownedPreferences(layers[0])||!layers[0].contains(element))return{kind:'dialog_open'};
    }
    const box=element.getBoundingClientRect(),x=box.x+box.width/2,y=box.y+box.height/2,hit=document.elementFromPoint(x,y);
    if(box.width<=0||box.height<=0||element.disabled||element.getAttribute('aria-disabled')==='true'||element.hasAttribute('data-disabled')||!(hit===element||element.contains(hit)))return{kind:'control_obscured'};
    return{kind:'ready',x,y};
  }
  if(request.kind==='escape'){
    if(layers.length!==1)return{kind:'dialog_open'};
    const layer=layers[0],mode=document.querySelector(selectors[1]);
    const associated=trigger=>!!trigger?.id&&!!layer.id&&trigger.getAttribute('aria-controls')===layer.id&&layer.getAttribute('aria-labelledby')===trigger.id&&trigger.getAttribute('aria-expanded')==='true';
    const modeOwned=associated(mode)&&layer.getAttribute('data-slot')==='dropdown-menu-content'&&!!layer.querySelector('[role="menuitemradio"] [data-slot="dropdown-menu-item-title"]');
    const prefOwned=ownedPreferences(layer);
    return{kind:modeOwned!==prefOwned?'ready':'dialog_open'};
  }
  return{kind:'invalid_argument'};
}

// Internal text never enters result JSON. Only two fixed plain-text targets.
export function readHomeBoundTextDOM(request){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  const selectors=['#title-section-prompt-container [role="textbox"][contenteditable="true"]','section[aria-label="偏好设置"] input[aria-label="视频时长秒数"]'];
  if(!selectors.includes(request.selector)||request.nth!==0||!['target','focus','selected','caret','readback'].includes(request.kind))return{kind:'invalid_argument'};
  const elements=document.querySelectorAll(request.selector);
  if(elements.length!==1)return{kind:'control_changed'};
  const element=elements[0],prompt=request.selector===selectors[0];
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  if(!visible(element)||element.disabled||element.readOnly||element.getAttribute('aria-disabled')==='true'||element.hasAttribute('data-disabled'))return{kind:'control_obscured'};
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible);
  if(prompt){
    const root=document.querySelector('#title-section-prompt-container'),composer=element.closest('[data-slot="prompt-composer"]');
    if(!root?.contains(element)||!composer||composer.querySelectorAll('[role="textbox"][contenteditable="true"]').length!==1||!element.isContentEditable)return{kind:'control_changed'};
    if(layers.length)return{kind:'dialog_open'};
    if(element.querySelector('[contenteditable="false"],img,video,audio'))return{kind:'rich_prompt_present'};
  }else{
    if(element.tagName!=='INPUT'||!['text','number'].includes(element.type))return{kind:'control_changed'};
    const pref=document.querySelector('#title-section-prompt-container button[aria-label^="模型选择和偏好设置"]'),layer=layers[0];
    if(layers.length!==1||!visible(pref)||!layer.id||pref.getAttribute('aria-controls')!==layer.id||pref.getAttribute('aria-expanded')!=='true'||layer.getAttribute('data-slot')!=='generation-preferences-panel-positioner'||layer.getAttribute('data-state')!=='open'||layer.querySelectorAll('section[aria-label="模型选择"]').length!==1||layer.querySelectorAll('section[aria-label="偏好设置"]').length!==1||!layer.contains(element))return{kind:'dialog_open'};
  }
  const raw=prompt?(element.innerText||'').replace(/\r\n/g,'\n'):element.value;
  // Same explicit semantic-empty contract as readDraftDOM; nonempty text is literal.
  const text=prompt&&!raw.trim()?'':raw;
  if(request.kind==='target'){
    const box=element.getBoundingClientRect(),x=box.x+box.width/2,y=box.y+box.height/2,hit=document.elementFromPoint(x,y);
    if(box.width<=0||box.height<=0||!(hit===element||element.contains(hit)))return{kind:'control_obscured'};
    return{kind:'ready',x,y,text,modifier:/^Mac/.test(navigator.platform)?'Meta':'Control'};
  }
  if(document.activeElement!==element)return{kind:'selection_changed'};
  if(request.kind==='readback')return{kind:text===request.value?'ready':'settings_changed'};
  if(request.kind==='caret'){
    if(!prompt)return{kind:'invalid_argument'};
    const selection=window.getSelection();
    if(!selection?.isCollapsed||selection.rangeCount!==1)return{kind:'selection_changed'};
    const range=selection.getRangeAt(0);
    return{kind:range.collapsed&&element.contains(range.startContainer)&&element.contains(range.endContainer)?'ready':'selection_changed'};
  }
  if(text!==request.expected_text)return{kind:'draft_changed'};
  if(request.kind==='focus')return{kind:'ready'};
  if(!prompt){
    if(element.type==='number')return{kind:'selection_unverifiable'};
    return{kind:element.selectionStart===0&&element.selectionEnd===text.length?'ready':'selection_changed'};
  }
  const selection=window.getSelection();
  if(!selection||selection.rangeCount!==1)return{kind:'selection_changed'};
  const range=selection.getRangeAt(0);
  if(!element.contains(range.startContainer)||!element.contains(range.endContainer))return{kind:'selection_changed'};
  const prefix=document.createRange(),suffix=document.createRange();
  prefix.selectNodeContents(element);prefix.setEnd(range.startContainer,range.startOffset);
  suffix.selectNodeContents(element);suffix.setStart(range.endContainer,range.endOffset);
  return{kind:!prefix.toString()&&!suffix.toString()&&range.toString()===(element.textContent||'')?'ready':'selection_changed'};
}
export async function createHomeBoundBackend(routing){
  const {Page}=await import('@jackwener/opencli/browser/page');
  return new Page('site:xyq-home',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);
}
export function homeBoundPage(backend,operation){
  if(!backend||typeof backend.evaluate!=='function')fail('unsupported_backend','The home binding requires the documented Page evaluator.');
  const page={evaluate:(fn,arg)=>backend.evaluate(fn,arg)};
  if(operation!=='form_state'){
    page.click=async(selector,options)=>{
      if(typeof backend.nativeClick!=='function')fail('unsupported_backend','Menu input requires documented nativeClick.');
      const target=await backend.evaluate(readHomeBoundInputDOM,{kind:'click',selector,nth:options?.nth,...(operation==='form_prepare'?{prepare:true}:{})});
      if(target?.kind!=='ready')fail(target?.kind||'control_changed','Home menu target changed; no input sent.');
      if(!Number.isFinite(target.x)||!Number.isFinite(target.y)||target.x<0||target.y<0)fail('control_changed','Unexpected menu coordinates; no input sent.');
      try{await backend.nativeClick(target.x,target.y);}
      catch(error){if(error instanceof XyqError)throw error;const failure=new XyqError('bridge_failed','Native home menu input failed; its outcome is unknown. Inspect the current draft before continuing.');failure.outcome_uncertain=true;throw failure;}
    };
    page.pressKey=async key=>{
      if(key!=='Escape')fail('invalid_argument','Only owned-menu Escape is available.');
      if(typeof backend.nativeKeyPress!=='function')fail('unsupported_backend','Menu cleanup requires documented nativeKeyPress.');
      const target=await backend.evaluate(readHomeBoundInputDOM,{kind:'escape'});
      if(target?.kind!=='ready')fail(target?.kind||'dialog_open','Owned menu association changed; no key sent.');
      try{await backend.nativeKeyPress('Escape');}
      catch(error){if(error instanceof XyqError)throw error;const failure=new XyqError('bridge_failed','Native owned-menu cleanup failed; its outcome is unknown. Inspect the current layer.');failure.outcome_uncertain=true;throw failure;}
    };
  }
  if(operation==='form_prepare')page.fillText=async(selector,value,options)=>{
    const editor='#title-section-prompt-container [role="textbox"][contenteditable="true"]',duration='section[aria-label="偏好设置"] input[aria-label="视频时长秒数"]';
    if(![editor,duration].includes(selector)||options?.nth!==0||typeof value!=='string'||value.length>20000||selector===duration&&(!/^[1-9][0-9]{0,2}$/.test(value)||Number(value)>600))fail('invalid_argument','Use the fixed plain composer or bounded duration input.');
    if(['nativeClick','nativeType','cdp'].some(name=>typeof backend[name]!=='function'))fail('unsupported_backend','Plain text preparation requires the public native input and fixed edit-command APIs.');
    let phase='target',applied=false;
    try{
      const request={selector,nth:0},target=await backend.evaluate(readHomeBoundTextDOM,{...request,kind:'target'});
      if(target?.kind!=='ready')fail(target?.kind||'control_changed','Text target changed; no replacement sent.');
      if(!Number.isFinite(target.x)||!Number.isFinite(target.y)||target.x<0||target.y<0||typeof target.text!=='string'||!['Meta','Control'].includes(target.modifier))fail('control_changed','Unexpected text target metadata.');
      phase='focus';await backend.nativeClick(target.x,target.y);
      const check=async(kind,extra)=>{const state=await backend.evaluate(readHomeBoundTextDOM,{...request,kind,...extra});if(state?.kind!=='ready')fail(state?.kind||'selection_changed','Text focus, selection or literal readback changed; inspect the current field.');};
      // Public CDP native edit commands: the installed nativeKeyPress omits
      // key codes/commands, so its shortcut alone did not select text in Chrome.
      // These fixed commands are internal; no arbitrary CDP/keys reach the CLI.
      const edit=async(command)=>{
        const event=command==='deleteBackward'?{key:'Backspace',code:'Backspace',windowsVirtualKeyCode:8,modifiers:0}:command==='insertLineBreak'?{key:'Enter',code:'Enter',windowsVirtualKeyCode:13,modifiers:8}:{key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:target.modifier==='Meta'?4:2};
        await backend.cdp('Input.dispatchKeyEvent',{type:'keyDown',...event,commands:[command]});
        await backend.cdp('Input.dispatchKeyEvent',{type:'keyUp',...event});
      };
      await check('focus',{expected_text:target.text});
      phase='select_all';await edit('selectAll');
      phase='selected';await check('selected',{expected_text:target.text});
      phase='replace';applied=true;
      const lines=value.split('\n');
      if(lines[0])await backend.nativeType(lines[0]);else await edit('deleteBackward');
      // Native insertText turns LF into new paragraphs, whose innerText has
      // double breaks. Native Shift+Enter keeps the requested literal LF.
      for(const line of lines.slice(1)){
        phase='line_break';await check('caret');await edit('insertLineBreak');
        phase='replace';await check('caret');if(line)await backend.nativeType(line);
      }
      phase='readback';await check('readback',{value});
    }catch(error){
      const failure=error instanceof XyqError?error:new XyqError('bridge_failed','Native text preparation failed; inspect the current draft before continuing.');
      failure.input_phase=phase;if(applied||!(error instanceof XyqError))failure.outcome_uncertain=true;
      throw failure;
    }
  };
  return Object.freeze(page);
}
export async function runHomeBoundOperation(context,operation,rawSettings,createBackend=createHomeBoundBackend){
  const settings=homeBoundSettings(operation,rawSettings);
  let page;
  try{page=homeBoundPage(await createBackend(boundReadRouting(context)),operation);}
  catch(error){if(error instanceof XyqError)throw error;fail('bridge_failed','The explicit home Page could not be prepared.');}
  try{
    const surface=await page.evaluate(readHomeBoundSurfaceDOM,{read_only:operation==='form_state'});
    if(surface?.kind!=='ready'){
      const code=['origin_mismatch','unsupported_surface','login_required','dialog_open'].includes(surface?.kind)?surface.kind:'layout_changed';
      fail(code,code==='dialog_open'?'Existing browser layers are preserved. Close them locally before continuing.':'The explicit home binding is not ready for this operation.');
    }
    const output=await(operation==='form_state'?inspectFormState(page):operation==='form_choices'?inspectFormChoices(page):operation==='form_prepare'?prepareForm(page,settings):operation==='mode_choices'?inspectModeChoices(page):prepareMode(page,settings));
    return output.map(({result})=>({result:{...result,browser_session:'site:xyq-home',browser_surface:'browser',binding_changed:false}}));
  }catch(error){if(error instanceof XyqError){if(error.cleanup_code==='bridge_failed')error.outcome_uncertain=true;throw error;}fail('bridge_failed','Home binding operation failed; inspect the existing draft before continuing.');}
}
