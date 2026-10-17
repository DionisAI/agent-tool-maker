// Native audio prompt text and one existing uploaded-audio mention. No submit.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM} from './core.mjs';
import {AUDIO_FILES,AUDIO_PANEL,audioScope,readAudioFormDOM,audioFormHash} from './audio.mjs';
export const AUDIO_PROMPT_FILES=[...AUDIO_FILES,'audio-prompt.mjs','audio-prompt.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
const EDITOR=AUDIO_PANEL+' [data-testid="canvas-generation-prompt-editor"][contenteditable="true"]';
const MENTIONS=AUDIO_PANEL+' button[data-action="mention-audio-reference"]';
export function audioPromptDigest(){const h=createHash('sha256');for(const n of AUDIO_PROMPT_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkAudioPromptPin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==audioPromptDigest())fail('definition_changed','Review the audio prompt/mention adapter bundle.');}
export function parseAudioPromptSettings(raw){let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use typed prompt preparation JSON.');}
  if(!v||Array.isArray(v)||typeof v!=='object'||Object.keys(v).some(k=>!['expected_form_sha256','prompt','reference_sha256'].includes(k))||!/^[a-f0-9]{64}$/.test(v.expected_form_sha256||'')||!('prompt'in v||'reference_sha256'in v)||'prompt'in v&&(typeof v.prompt!=='string'||v.prompt.length>20000||v.prompt.includes('\r'))||'reference_sha256'in v&&!/^[a-f0-9]{64}$/.test(v.reference_sha256||''))fail('invalid_argument','Bind an exact audio-form digest and plain prompt or existing audio-reference digest.');return v;}

export function readAudioPromptDOM(scope){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/project')return{kind:'origin_mismatch'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==scope.project_id||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const roots=Array.from(document.querySelectorAll('[data-xyq-selected-audio-footer-panel="true"]')).filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]'));
  if(roots.length!==1)return{kind:'audio_form_closed'};
  const es=roots[0].querySelectorAll('[data-testid="canvas-generation-prompt-editor"][contenteditable="true"]');if(es.length!==1)return{kind:'layout_changed'};
  const editor=es[0],segments=[],tokens=[];let supported=true;
  const text=s=>{if(!s)return;const last=segments.at(-1);if(last?.kind==='text')last.text+=s;else segments.push({kind:'text',text:s});};
  const walk=e=>{
    if(e.nodeType===3){text(e.textContent);return;}
    if(e.nodeType!==1){supported=false;return;}
    if(e.tagName==='BR'){if(!e.classList.contains('ProseMirror-trailingBreak'))text('\n');return;}
    if(e.tagName==='SPAN'&&e.getAttribute('data-type')==='canvasPippitAssetMention'){
      const id=e.getAttribute('data-id'),label=e.getAttribute('data-label');
      const valid=e.getAttribute('contenteditable')==='false'&&/^\d{1,20}$/.test(id||'')&&id===e.getAttribute('data-pippit-asset-id')&&id===e.getAttribute('data-material-pippit-asset-id')&&e.getAttribute('data-mention-suggestion-char')==='@'&&typeof label==='string'&&label.length>0&&label.length<=512&&e.querySelectorAll('.xyq-canvas-rich-prompt-asset-audio-preview').length===1;
      if(!valid){supported=false;return;}const token={kind:'audio_reference',asset_id:id,label};tokens.push(token);segments.push(token);return;
    }
    supported=false;
  };
  Array.from(editor.childNodes).forEach((e,i)=>{if(e.nodeType!==1||e.tagName!=='P'){supported=false;return;}if(i)text('\n');Array.from(e.childNodes).forEach(walk);});
  if(segments.length>100||tokens.length>3||JSON.stringify(segments).length>40000)supported=false;
  return{kind:'ready',supported,segments,tokens,literal_text:segments.filter(x=>x.kind==='text').map(x=>x.text).join('')};
}
export function readAudioPromptTargetDOM(t){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/project')return{kind:'origin_mismatch'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==t.project_id||u.searchParams.get('canvasId')!==t.canvas_id)return{kind:'canvas_changed'};
  if(!['editor','mention'].includes(t.kind))return{kind:'invalid_argument'};
  const selector=t.kind==='editor'?'[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"] [data-testid="canvas-generation-prompt-editor"][contenteditable="true"]':'[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"] button[data-action="mention-audio-reference"]';
  const all=Array.from(document.querySelectorAll(selector)),matches=all.filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]')).filter(e=>t.kind==='editor'||e.getAttribute('data-action-object-id')===t.object_id);
  if(matches.length!==1)return{kind:'control_changed'};
  const e=matches[0],r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return{kind:'ready',nth:all.indexOf(e),pointer_ready:r.width>0&&r.height>0&&!e.disabled&&e.getAttribute('aria-disabled')!=='true'&&(hit===e||e.contains(hit))};
}
export function readAudioPromptCaretDOM(scope){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/project')return{kind:'origin_mismatch'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==scope.project_id||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const es=document.querySelectorAll('[data-xyq-selected-audio-footer-panel="true"] [data-testid="canvas-generation-prompt-editor"][contenteditable="true"]');if(es.length!==1)return{kind:'layout_changed'};
  const editor=es[0];if(typeof document.getSelection!=='function')return{kind:'ready',known:false};
  const s=document.getSelection(),r=s?.rangeCount===1?s.getRangeAt(0):null,active=document.activeElement===editor||editor.contains(document.activeElement);
  const within=!!r&&editor.contains(r.startContainer)&&editor.contains(r.endContainer);let end=within&&r.collapsed;
  const placeholder=n=>n.nodeType===3?n.textContent.length===0:n.nodeType===1&&n.tagName==='BR'&&n.classList.contains('ProseMirror-trailingBreak');
  if(end){let n=r.startContainer;const offset=r.startOffset;if(n.nodeType===3)end=offset===n.textContent.length;else end=Array.from(n.childNodes).slice(offset).every(placeholder);
    while(end&&n!==editor){for(let next=n.nextSibling;next;next=next.nextSibling)if(!placeholder(next)){end=false;break;}n=n.parentNode;if(!n)end=false;}}
  return{kind:'ready',known:true,active,at_end:!!end};
}
async function state(page,scope){const d=await pollDOM({evaluate:()=>page.evaluate(readAudioFormDOM,scope)},readAudioFormDOM),doc=await pollDOM({evaluate:()=>page.evaluate(readAudioPromptDOM,scope)},readAudioPromptDOM),after=await pollDOM({evaluate:()=>page.evaluate(readAudioFormDOM,scope)},readAudioFormDOM);
  if(audioFormHash(d)!==audioFormHash(after))fail('draft_changed','Audio form changed during prompt snapshot.');return{form:after,doc};}
function context(s){if(s.form.layers)fail('dialog_open','Existing layers are preserved.');if(s.form.submit_busy)fail('draft_busy','Audio draft is busy.');if(s.form.files.some(e=>e.files===null))fail('reference_state_unknown','File state is unknown.');if(!s.doc.supported)fail('unsupported_prompt_structure','Existing prompt structure stays intact.');}
const surroundings=s=>sha(JSON.stringify([s.form.project_id,s.form.canvas_id,s.form.node_id,s.form.model,s.form.sample_rate,s.form.references,s.form.files]));
function preserve(a,b){context(b);if(surroundings(a)!==surroundings(b))fail('draft_changed','Model, sample rate, files or uploaded references changed.');}
async function target(page,scope,kind,object_id){const d=await pollDOM({evaluate:()=>page.evaluate(readAudioPromptTargetDOM,{...scope,kind,object_id})},readAudioPromptTargetDOM);if(!d.pointer_ready)fail('control_obscured','Requested prompt control is disabled or covered.');return d;}
async function endCaret(page,scope){if(typeof page.focus!=='function'||typeof page.nativeEnd!=='function'&&typeof page.cdp!=='function')fail('unsupported_backend','Reference appending needs native focus and caret input.');
  const t=await target(page,scope,'editor');await page.focus(EDITOR,{nth:t.nth});const first=await pollDOM({evaluate:()=>page.evaluate(readAudioPromptCaretDOM,scope)},readAudioPromptCaretDOM);
  if(!first.known)fail('selection_unknown','DOM caret is unknown; no reference input sent.');if(!first.active)fail('selection_changed','Audio prompt is not the focused editor.');
  if(typeof page.nativeEnd==='function')await page.nativeEnd();else{await page.cdp('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'End',code:'End',windowsVirtualKeyCode:35,modifiers:0,commands:['moveToEndOfDocument']});await page.cdp('Input.dispatchKeyEvent',{type:'keyUp',key:'End',code:'End',windowsVirtualKeyCode:35,modifiers:0});}
  const caret=await pollDOM({evaluate:()=>page.evaluate(readAudioPromptCaretDOM,scope)},readAudioPromptCaretDOM);if(!caret.known||!caret.active||!caret.at_end)fail('selection_changed','Native caret is not at the end of the audio prompt.');}
function result(s,steps){return[{result:{status:'prepared',project_id:s.form.project_id,canvas_id:s.form.canvas_id,node_id:s.form.node_id,form_sha256:audioFormHash(s.form),literal_text_sha256:sha(s.doc.literal_text),literal_text_characters:s.doc.literal_text.length,
  mentions:s.doc.tokens.map(t=>({asset_id:t.asset_id,label_sha256:sha(t.label),reference_sha256:s.form.references.filter(r=>r.type==='audio'&&r.name===t.label).length===1?sha(s.form.references.find(r=>r.type==='audio'&&r.name===t.label).id):null})),model:s.form.model,sample_rate:s.form.sample_rate,
  completed_steps:steps,association:s.form.association,source:'visible_dom',secrets_returned:false,paid_submitted:false,upload_started:false,voice_effect_verified:false,persistence_verified:false,acceptance:'native_prompt_and_structured_uploaded_audio_mention_only'}}];}
export async function prepareAudioPrompt(page,rawScope,raw){const scope=audioScope(rawScope),requested=parseAudioPromptSettings(raw),steps=[];let phase='snapshot',attempted=false;
  try{const initial=await state(page,scope);context(initial);if(audioFormHash(initial.form)!==requested.expected_form_sha256)fail('draft_changed','Audio form differs from the inspected digest; no input sent.');
    let ref=null;
    if('reference_sha256'in requested){const matches=initial.form.references.filter(r=>r.type==='audio'&&sha(r.id)===requested.reference_sha256);if(matches.length!==1)fail('reference_missing','Requested uploaded audio reference is absent.');ref=matches[0];if(initial.form.references.filter(r=>r.name===ref.name).length!==1)fail('reference_ambiguous','Duplicate attachment names make mention attribution ambiguous.');}
    if('prompt'in requested&&initial.doc.tokens.length&&requested.prompt!==initial.doc.literal_text)fail('rich_prompt_present','Existing structured mentions are preserved; prepare plain text before adding references.');
    let current=initial;
    if('prompt'in requested&&requested.prompt!==current.doc.literal_text){phase='prompt_input';const t=await target(page,scope,'editor'),last=await state(page,scope);preserve(initial,last);if(audioFormHash(last.form)!==audioFormHash(current.form))fail('draft_changed','Prompt changed before text input.');
      if(typeof page.fillText!=='function')fail('unsupported_backend','Plain prompt input needs native fill support.');attempted=true;await page.fillText(EDITOR,requested.prompt,{nth:t.nth});steps.push('prompt_input');current=await state(page,scope);preserve(initial,current);
      if(current.doc.tokens.length||current.doc.literal_text!==requested.prompt)fail('settings_changed','Plain text differs from native readback.');}
    if(ref&&!current.doc.tokens.some(t=>t.label===ref.name)){phase='reference_caret';const expected=audioFormHash(current.form);await endCaret(page,scope);const last=await state(page,scope);preserve(initial,last);if(audioFormHash(last.form)!==expected)fail('draft_changed','Draft changed while positioning the caret.');
      const t=await target(page,scope,'mention',ref.id);phase='reference_input';attempted=true;await page.click(MENTIONS,{nth:t.nth});steps.push('reference_input');const after=await state(page,scope);preserve(initial,after);
      const added=after.doc.tokens.slice(current.doc.tokens.length);if(added.length!==1||added[0].label!==ref.name)fail('settings_changed','No single matching structured reference appeared.');
      const expectedSegments=structuredClone(current.doc.segments);expectedSegments.push(added[0],{kind:'text',text:' '});
      if(JSON.stringify(after.doc.segments)!==JSON.stringify(expectedSegments))fail('prompt_changed','Reference input changed unrequested text or mentions.');current=after;}
    phase='final_readback';const final=await state(page,scope);preserve(initial,final);if(audioFormHash(final.form)!==audioFormHash(current.form))fail('draft_changed','Audio prompt changed during final readback.');return result(final,steps);
  }catch(error){const e=error instanceof XyqError?error:new XyqError('bridge_failed','Audio prompt preparation failed; inspect the current draft.');e.phase=phase;e.completed_steps=steps;e.outcome_uncertain=attempted;throw e;}
}
