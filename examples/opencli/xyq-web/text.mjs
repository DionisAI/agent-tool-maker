// Whole text-node content/format editing through observed native UI only.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,pollDOM} from './core.mjs';
import {CANVAS_FILES,canvasScope,readCanvasDOM} from './canvas.mjs';
export const TEXT_FILES=[...CANVAS_FILES,'text.mjs','text.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
export function textDigest(){const h=createHash('sha256');for(const n of TEXT_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkTextPin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==textDigest())fail('definition_changed','Review the text-node adapter bundle.');}
export function textScope(args){const scope=canvasScope(args);if(typeof args.node_id!=='string'||!/^\d{1,20}$/.test(args.node_id))fail('invalid_argument','Use the exact inspected text node_id.');return{...scope,node_id:args.node_id};}
export function parseTextSettings(raw){
  let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','settings must be JSON.');}
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!['expected_content_sha256','text','heading','quote','bold','italic','underline','strike'].includes(k)))fail('invalid_argument','Use typed text/format settings; no HTML, selectors or arbitrary buttons.');
  if(!/^[a-f0-9]{64}$/.test(v.expected_content_sha256||''))fail('invalid_argument','Bind the entire inspected content, including its formatting.');
  if('text'in v&&(typeof v.text!=='string'||v.text.length>50000||v.text.includes('\0')))fail('invalid_argument','text must contain 0-50000 characters without NUL.');
  if('heading'in v&&![null,1,2,3].includes(v.heading))fail('invalid_argument','heading must be null, 1, 2 or 3.');
  for(const key of ['quote','bold','italic','underline','strike'])if(key in v&&typeof v[key]!=='boolean')fail('invalid_argument','Text marks must be boolean.');
  return v;
}

export function readTextNodeDOM(scope){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname!=='/project')return{kind:'unsupported_surface'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==scope.project_id||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const ns=Array.from(document.querySelectorAll('.react-flow__node')).filter(e=>e.getAttribute('data-id')===scope.node_id);
  if(ns.length!==1)return{kind:'node_changed'};
  const n=ns[0];if(!n.classList.contains('react-flow__node-biz/text'))return{kind:'unsupported_node'};
  const es=Array.from(n.querySelectorAll('.xyq-text-node-editor[contenteditable]'));
  if(es.length!==1||!['true','false'].includes(es[0].getAttribute('contenteditable')))return{kind:'layout_changed'};
  const e=es[0],html=e.innerHTML,raw=(e.innerText||'').replace(/\r\n/g,'\n'),text=raw.trim()?raw:'';
  // innerText includes layout-generated separators. Tiptap adds an empty
  // paragraph after a heading/quote; that is not a change to literal characters.
  // Keep both observations; explicit hard breaks remain literal characters.
  const characters=x=>x.nodeType===3?x.textContent:x.nodeType===1&&x.tagName==='BR'?(x.classList.contains('ProseMirror-trailingBreak')?'':'\n'):Array.from(x.childNodes).map(characters).join('');
  const literal_text=characters(e).replace(/\r\n/g,'\n');
  if(html.length>500000||text.length>50000)return{kind:'layout_changed'};
  const supported=new Set(['P','BR','H1','H2','H3','BLOCKQUOTE','STRONG','B','EM','I','U','S','STRIKE','SPAN','HR']);
  const unsupported=Array.from(e.querySelectorAll('*')).some(x=>!supported.has(x.tagName)||x.getAttribute('contenteditable')==='false');
  const runs=[];
  const walk=x=>{if(x.nodeType===3&&x.textContent.length){let p=x.parentElement,h=null,marks={quote:false,bold:false,italic:false,underline:false,strike:false};
    while(p&&p!==e){if(/^H[1-3]$/.test(p.tagName))h=Number(p.tagName.slice(1));if(p.tagName==='BLOCKQUOTE')marks.quote=true;if(['STRONG','B'].includes(p.tagName))marks.bold=true;if(['EM','I'].includes(p.tagName))marks.italic=true;if(p.tagName==='U')marks.underline=true;if(['S','STRIKE'].includes(p.tagName))marks.strike=true;p=p.parentElement;}
    runs.push({heading:h,...marks});}else Array.from(x.childNodes).forEach(walk);};walk(e);
  const uniform=key=>!runs.length?(key==='heading'?null:false):runs.every(x=>x[key]===runs[0][key])?runs[0][key]:'mixed';
  const formats=Object.fromEntries(['heading','quote','bold','italic','underline','strike'].map(k=>[k,uniform(k)]));
  const editors=Array.from(document.querySelectorAll('.xyq-text-node-editor[contenteditable="true"]')).filter(visible);
  const toolbars=Array.from(document.querySelectorAll('[data-xyq-text-toolbar="true"]')).filter(visible);
  const controls=toolbars.length===1?Array.from(toolbars[0].querySelectorAll('button[aria-label][aria-pressed]')).map(x=>({label:x.getAttribute('aria-label'),pressed:x.getAttribute('aria-pressed')==='true',disabled:!!x.disabled||x.getAttribute('aria-disabled')==='true'})):[];
  const foreign=Array.from(document.querySelectorAll('[contenteditable="true"]')).filter(x=>!x.closest('.react-flow__node')).map(x=>({slot:x.getAttribute('data-slot'),html:x.innerHTML}));
  const others=Array.from(document.querySelectorAll('.react-flow__node')).filter(x=>x!==n).map(x=>({node_id:x.getAttribute('data-id'),html:x.innerHTML,transform:x.style.transform,width:x.style.width,height:x.style.height}));
  const visibleLayers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible);
  // The selected text node's own prompt footer is a non-modal dialog on the
  // observed site. Its contenteditable draft is in `foreign` above and stays
  // protected. Other layers (including menus inside this footer) still block.
  const ownFooters=visibleLayers.filter(x=>x.getAttribute('role')==='dialog'&&x.getAttribute('aria-label')==='节点浮动操作面板'&&x.getAttribute('data-xyq-selected-node-footer-panel')==='true'&&x.getAttribute('data-xyq-text-prompt-generation-footer')==='true');
  const ownFooter=ownFooters.length===1&&editors.length===1&&editors[0]===e?ownFooters[0]:null;
  const layers=visibleLayers.filter(x=>x!==ownFooter).length;
  return{kind:'ready',scope,html,text,literal_text,unsupported,formats,horizontal_lines:e.querySelectorAll('hr').length,editable:e.getAttribute('contenteditable')==='true',
    active_editor_count:editors.length,active_node_id:editors.length===1?editors[0].closest('.react-flow__node')?.getAttribute('data-id'):null,
    toolbar_count:toolbars.length,controls,foreign,others,layers};
}
export function readTextSelectionDOM(scope){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/project')return{kind:'origin_mismatch'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==scope.project_id||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const ns=Array.from(document.querySelectorAll('.react-flow__node')).filter(e=>e.getAttribute('data-id')===scope.node_id);
  const e=ns.length===1?ns[0].querySelector('.xyq-text-node-editor[contenteditable="true"]'):null;
  if(!e)return{kind:'node_not_editable'};
  const active=document.activeElement===e||e.contains(document.activeElement);
  if(typeof document.getSelection!=='function')return{kind:'ready',known:false,active,full:false};
  const s=document.getSelection();
  if(!s||s.rangeCount!==1)return{kind:'ready',known:true,active,full:false};
  const r=s.getRangeAt(0),within=(r.startContainer===e||e.contains(r.startContainer))&&(r.endContainer===e||e.contains(r.endContainer));
  const normalized=t=>t.replace(/\r?\n/g,'');
  const full=within&&!r.collapsed&&normalized(s.toString())===normalized(e.textContent||'');
  return{kind:'ready',known:true,active,full};
}
const EDITORS='.react-flow__node .xyq-text-node-editor[contenteditable]';
const BUTTONS='[data-xyq-text-toolbar="true"] button[aria-label][aria-pressed]';
export function readTextTargetDOM(t){
  if(location.origin!=='https://xyq.jianying.com'||location.pathname!=='/project')return{kind:'origin_mismatch'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==t.project_id||u.searchParams.get('canvasId')!==t.canvas_id)return{kind:'canvas_changed'};
  if(!['editor','format'].includes(t.kind))return{kind:'invalid_argument'};
  const selector=t.kind==='editor'?'.react-flow__node .xyq-text-node-editor[contenteditable]':'[data-xyq-text-toolbar="true"] button[aria-label][aria-pressed]';
  const all=Array.from(document.querySelectorAll(selector));
  const matches=all.filter(e=>e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]')).filter(e=>t.kind==='editor'?e.closest('.react-flow__node')?.getAttribute('data-id')===t.node_id:e.getAttribute('aria-label')===t.label);
  if(matches.length!==1)return{kind:'control_changed'};
  const e=matches[0],r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return{kind:'ready',nth:all.indexOf(e),pointer_ready:r.width>0&&r.height>0&&!e.disabled&&e.getAttribute('aria-disabled')!=='true'&&(hit===e||e.contains(hit))};
}
export function contentHash(d){return sha(JSON.stringify(['xyq-text-node-content-v1',d.scope,d.html]));}
const surroundings=d=>sha(JSON.stringify([d.foreign,d.others]));
async function state(page,scope){await pollDOM({evaluate:()=>page.evaluate(readCanvasDOM,scope)},readCanvasDOM);return pollDOM({evaluate:()=>page.evaluate(readTextNodeDOM,scope)},readTextNodeDOM);}
function context(d){if(d.layers)fail('dialog_open','Existing browser layers are preserved.');}
function preserve(initial,d){if(surroundings(initial)!==surroundings(d))fail('context_changed','Another node or unsubmitted editor changed; inspect the current canvas.');}
function publicState(d,extra={}){return{status:'ready',...d.scope,content_sha256:contentHash(d),text_sha256:sha(d.text),text_characters:d.text.length,formats:d.formats,
  literal_text_sha256:sha(d.literal_text),literal_text_characters:d.literal_text.length,
  horizontal_lines:d.horizontal_lines,unsupported_structure:d.unsupported,editable:d.editable,controls:d.controls,source:'visible_dom',
  secrets_returned:false,paid_submitted:false,upload_started:false,persistence_verified:false,...extra};}
async function target(page,scope,kind,label){const t={...scope,kind,label},d=await pollDOM({evaluate:()=>page.evaluate(readTextTargetDOM,t)},readTextTargetDOM);if(!d.pointer_ready)fail('control_obscured','Target text control is disabled or covered; no input sent.');return d;}
async function click(page,scope,kind,label){const d=await target(page,scope,kind,label);await page.click(kind==='editor'?EDITORS:BUTTONS,{nth:d.nth});}
export async function inspectText(page,args){const scope=textScope(args),d=await state(page,scope);return[{result:publicState(d)}];}
async function selectAll(page,scope){
  if(typeof page.focus!=='function'||typeof page.nativeSelectAll!=='function'&&typeof page.cdp!=='function')fail('unsupported_backend','Whole-text formatting needs native focus and selection input.');
  const t=await target(page,scope,'editor');await page.focus(EDITORS,{nth:t.nth});
  const before=await pollDOM({evaluate:()=>page.evaluate(readTextSelectionDOM,scope)},readTextSelectionDOM);
  if(!before.known)fail('selection_unknown','The backend does not expose the DOM selection; no format input sent.');
  if(!before.active)fail('selection_changed','Target editor is not focused; no keyboard input sent.');
  // Chromium's documented native editing command, not page-side selection JS.
  // No raw auth, arbitrary CDP method or caller-provided command is accepted.
  // The editing command selects the focused editable, without an OS-dependent
  // shortcut modifier (which can also reach page-level shortcut handlers).
  if(typeof page.nativeSelectAll==='function')await page.nativeSelectAll();
  else{
    const modifiers=0;
    await page.cdp('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers,commands:['selectAll']});
    await page.cdp('Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers});
  }
  const selected=await pollDOM({evaluate:()=>page.evaluate(readTextSelectionDOM,scope)},readTextSelectionDOM);
  if(!selected.known||!selected.active||!selected.full)fail('selection_changed','Native selection does not cover this whole editor; no format click sent.');
}
export async function prepareText(page,args,raw){
  const scope=textScope(args),requested=parseTextSettings(raw),steps=[];let phase='snapshot';
  try{
    const initial=await state(page,scope);context(initial);
    if(contentHash(initial)!==requested.expected_content_sha256)fail('content_changed','Node content differs from the inspected digest; no input sent.');
    if(initial.unsupported)fail('unsupported_structure','Existing non-text content needs its own editing contract; it stays intact.');
    let d=initial;
    phase='activate';if(!d.editable){await click(page,scope,'editor');d=await state(page,scope);context(d);preserve(initial,d);if(contentHash(d)!==contentHash(initial))fail('content_changed','Activation changed node content.');}
    if(!d.editable||d.active_editor_count!==1||d.active_node_id!==scope.node_id)fail('node_not_editable','The exact node is not the unique active text editor.');
    if('text'in requested&&requested.text!==d.text){
      phase='replace_text';const expected=contentHash(d),t=await target(page,scope,'editor'),before=await state(page,scope);context(before);preserve(initial,before);
      if(contentHash(before)!==expected)fail('content_changed','Node changed before text input.');
      await page.fillText(EDITORS,requested.text,{nth:t.nth});d=await state(page,scope);context(d);preserve(initial,d);
      if(d.text!==requested.text)fail('settings_changed','Typed text differs from DOM readback.');steps.push('text');
    }
    const expectedLiteral=d.literal_text;
    const labels={quote:'Quote',bold:'粗体',italic:'斜体',underline:'下划线',strike:'删除线'};
    for(const key of ['heading','quote','bold','italic','underline','strike'])if(key in requested&&d.formats[key]!==requested[key]){
      if(!d.text.trim())fail('setting_unavailable','Whole-text formatting needs existing text, not a future typing mark.');
      for(let attempt=0;attempt<2&&d.formats[key]!==requested[key];attempt++){
        phase='format:'+key;
        const label=key==='heading'?(requested.heading===null?'H'+(typeof d.formats.heading==='number'?d.formats.heading:1):'H'+requested.heading):labels[key];
        const control=d.controls.filter(x=>x.label===label);
        if(d.toolbar_count!==1||control.length!==1||control[0].disabled)fail('setting_unavailable','Requested text format control is not uniquely enabled.');
        const expected=contentHash(d);await selectAll(page,scope);const selected=await state(page,scope);context(selected);preserve(initial,selected);
        if(contentHash(selected)!==expected)fail('content_changed','Node changed during text selection.');
        await click(page,scope,'format',label);const after=await state(page,scope);context(after);preserve(initial,after);
        if(after.literal_text!==d.literal_text)fail('content_changed','Format input changed literal text characters or hard breaks.');
        // A caret-only aria-pressed change is not body formatting success.
        if(after.formats[key]===d.formats[key])fail('settings_changed','Toolbar toggled but the node body format did not change.');
        d=after;steps.push('format:'+key);
      }
      if(d.formats[key]!==requested[key])fail('settings_changed','Requested whole-text format differs from the node body.');
    }
    phase='final_readback';const final=await state(page,scope);context(final);preserve(initial,final);
    if(contentHash(final)!==contentHash(d))fail('content_changed','Node changed during final verification.');
    if(final.literal_text!==expectedLiteral||Object.keys(labels).concat('heading').some(k=>k in requested&&final.formats[k]!==requested[k]))fail('settings_changed','Requested text settings differ from final readback.');
    const implicit=Object.fromEntries(Object.keys(final.formats).filter(k=>!(k in requested)&&final.formats[k]!==initial.formats[k]).map(k=>[k,{before:initial.formats[k],after:final.formats[k]}]));
    if(final.text!==initial.text)implicit.rendered_text={before_sha256:sha(initial.text),after_sha256:sha(final.text),literal_characters_changed:final.literal_text!==initial.literal_text};
    return[{result:publicState(final,{status:'prepared',completed_steps:steps,implicit_changes:implicit})}];
  }catch(error){const e=error instanceof XyqError?error:new XyqError('bridge_failed','Native text editing failed; inspect this node before further input.');e.phase=phase;e.completed_steps=steps;throw e;}
}
