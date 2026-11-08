// UI_SELECTOR / visible-ui: a single approved PCM WAV / MP3 on the existing binding.
import {createHash} from 'node:crypto';
import {readFileSync,lstatSync,existsSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {XyqError} from './core.mjs';
import {AUDIO_PANEL,audioScope,parseAudioUpload,inspectAudioFile,readAudioFormDOM,audioFormHash,uploadAudioReference} from './audio.mjs';
import {AUDIO_BOUND_FILES,boundReadRouting} from './audio-bound.mjs';
export const AUDIO_UPLOAD_BOUND_FILES=[...AUDIO_BOUND_FILES,'audio-upload-bound.mjs','audio-upload-bound.js'];
const fail=(code,message)=>{throw new XyqError(code,message);};
const unwrap=v=>v&&typeof v==='object'&&'session'in v&&'data'in v?v.data:v;
const keys=(v,names)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===names.length&&names.every(k=>Object.hasOwn(v,k));
export function audioUploadBoundDigest(){const h=createHash('sha256');for(const n of AUDIO_UPLOAD_BOUND_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkAudioUploadBoundPin(pin){if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==audioUploadBoundDigest())fail('definition_changed','Review the explicit audio upload bundle.');}

// Hidden file inputs are the observed native attachment route, not unmasked UI.
export function readAudioUploadTargetDOM(scope){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/project')return{kind:'unsupported_surface'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==scope.project_id||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const roots=Array.from(document.querySelectorAll('[data-testid="rf__wrapper"][role="application"]')).filter(visible);
  if(roots.length!==1)return{kind:'layout_changed'};
  const nodes=roots[0].querySelectorAll('.react-flow__node-biz\\/audio');
  if(nodes.length!==1)return{kind:'audio_node_ambiguous'};
  if(nodes[0].getAttribute('data-id')!==scope.node_id)return{kind:'node_changed'};
  const panels=Array.from(roots[0].querySelectorAll('[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"]')).filter(visible);
  if(panels.length!==1)return{kind:'audio_form_closed'};
  const p=panels[0],all=p.querySelectorAll('input[type="file"]'),inputs=p.querySelectorAll('input[type="file"][data-audio-reference-upload="true"]');
  if(all.length!==2||inputs.length!==1)return{kind:'layout_changed'};
  const input=inputs[0];
  if(input.disabled||input.getAttribute('aria-disabled')==='true'||input.hasAttribute('data-disabled'))return{kind:'control_obscured'};
  if(typeof input.files?.length!=='number')return{kind:'reference_state_unknown'};
  if(input.files.length)return{kind:'draft_not_empty'};
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible).filter(e=>e!==p);
  if(layers.length)return{kind:'dialog_open'};
  return{kind:'ready'};
}

export async function createAudioUploadBackend(routing){const {Page}=await import('@jackwener/opencli/browser/page');return new Page('site:xyq-web',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);}
export function audioUploadPage(backend,rawScope,args,workspace){
  const scope=audioScope(rawScope);
  if(!backend||typeof backend.evaluate!=='function')fail('unsupported_backend','Audio upload requires the public Page evaluator.');
  if(typeof backend.setFileInput!=='function')fail('upload_backend_missing','Audio attachment requires the public file-chooser upload API.');
  const selector=AUDIO_PANEL+' input[type="file"][data-audio-reference-upload="true"]';let rootId=null,inputId=null,sent=false;
  const call=async(method,params)=>{if(typeof backend.cdp!=='function')fail('upload_backend_missing','Audio attachment requires the reviewed public native DOM API.');try{return await backend.cdp(method,params);}catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','Native audio DOM request failed; retain intent and inspect the draft.');}};
  const target=async()=>{const value=await backend.evaluate(readAudioUploadTargetDOM,scope);if(value?.kind!=='ready')fail(value?.kind||'layout_changed','The exact native audio input association changed.');};
  const documentRoot=async()=>{const v=unwrap(await call('DOM.getDocument',{depth:0}));if(!Number.isSafeInteger(v?.root?.nodeId)||v.root.nodeId<1)fail('bridge_protocol','Native DOM root is missing.');return v;};
  const query=async nodeId=>{const v=unwrap(await call('DOM.querySelector',{nodeId,selector}));if(!Number.isSafeInteger(v?.nodeId)||v.nodeId<1)fail('layout_changed','The exact native audio file input is missing.');return v;};
  return Object.freeze({evaluate:(fn,arg)=>backend.evaluate(fn,arg),cdp:async(method,params)=>{
    if(method==='DOM.getDocument'){
      if(!keys(params,['depth'])||params.depth!==0)fail('invalid_argument','Only the native depth-zero document root is available.');
      await target();const doc=await documentRoot();rootId=doc.root.nodeId;return doc;
    }
    if(method==='DOM.querySelector'){
      if(!keys(params,['nodeId','selector'])||rootId===null||params.nodeId!==rootId||params.selector!==selector)fail('invalid_argument','Only the exact audio-reference input can be resolved.');
      await target();const input=await query(rootId);inputId=input.nodeId;return input;
    }
    if(method!=='DOM.setFileInputFiles'||!keys(params,['nodeId','files'])||inputId===null||params.nodeId!==inputId||!Array.isArray(params.files)||params.files.length!==1||params.files[0]!==args.file)fail('invalid_argument','Only one exact reviewed audio file input is available.');
    if(sent)fail('upload_unknown','A native file-input attempt already occurred; inspect its retained receipt.');
    inspectAudioFile(args.file,workspace,args.file_sha256);await target();
    // DOM.getDocument can repopulate frontend node IDs. Requery on the same
    // captured root so ID comparison detects replacement, not ID reallocation.
    const input=await query(rootId);
    if(input.nodeId!==inputId)fail('control_changed','The resolved audio input was replaced before native attachment.');
    const form=await backend.evaluate(readAudioFormDOM,scope);
    if(form?.kind!=='ready')fail(form?.kind||'layout_changed','The audio form is not ready for native attachment.');
    if(form.layers||form.submit_busy||audioFormHash(form)!==args.expected_form_sha256)fail('draft_changed','The audio form changed before native attachment.');
    await target();inspectAudioFile(args.file,workspace,args.file_sha256);sent=true;
    // chrome.debugger rejects a bare DOM.setFileInputFiles call. The installed
    // public API owns chooser interception and receives only this exact file
    // and the reviewed selector. No raw-CDP or in-page byte-injection fallback.
    try{return await backend.setFileInput([args.file],selector);}catch(error){
      const e=new XyqError('bridge_failed','Public audio file-input acknowledgement failed; retain intent and inspect the draft.');
      e.native_input_attempted=true;
      e.native_error_class=/Not allowed/.test(String(error?.message||''))?'native_permission_denied':'native_reply_unacknowledged';
      throw e;
    }
  }});
}

// Retain only bounded operation metadata after intent. Never serialize bridge
// messages, file contents, page text, authentication or arbitrary error objects.
function retainFailure(workspace,args,error){
  if(!(error instanceof XyqError)||error.outcome_uncertain!==true)return;
  const ledger=join(workspace,'.atm','xyq-audio-uploads'),intent=join(ledger,args.request_key+'.intent.json');
  try{
    for(const p of [join(workspace,'.atm'),ledger]){const s=lstatSync(p);if(!s.isDirectory()||s.isSymbolicLink())throw Error('unsafe_diagnostic_path');}
    const st=lstatSync(intent);if(!st.isFile()||st.isSymbolicLink()||st.size>50000)throw Error('unsafe_diagnostic_intent');
    const known=['upload_unknown','draft_changed','draft_not_empty','reference_state_unknown','reference_limit','reference_name_conflict','dialog_open','control_changed','control_obscured','layout_changed','bridge_failed','bridge_protocol','upload_readback_changed','page_not_ready','input_changed'];
    const record={version:1,request_key:args.request_key,file_sha256:args.file_sha256,
      code:known.includes(error.code)?error.code:'upload_operation_failed',
      phase:['intent','input_preflight','upload','readback','receipt'].includes(error.phase)?error.phase:'unknown',
      completed_steps:(error.completed_steps||[]).filter(s=>['upload_intent','file_input_sent'].includes(s)),
      outcome_uncertain:true,native_input_attempted:error.native_input_attempted===true||(error.completed_steps||[]).includes('file_input_sent'),
      native_error_class:['native_permission_denied','native_reply_unacknowledged'].includes(error.native_error_class)?error.native_error_class:null,
      receipt_is_success:false,automatic_retry_permitted:false};
    const path=join(ledger,args.request_key+'.failure.json');
    if(existsSync(path)){const s=lstatSync(path);if(!s.isFile()||s.isSymbolicLink()||s.size>50000)throw Error('unsafe_existing_diagnostic');error.diagnostic_status='preserved_existing';return;}
    writeFileSync(path,JSON.stringify(record),{mode:0o600,flag:'wx'});error.diagnostic_status='recorded';
  }catch{error.diagnostic_status='diagnostic_write_failed';}
}

// Declared conditional stops only. Bridge/IO/protocol or intent failures stay errors.
export function audioUploadRejection(error,scope){
  const codes=['draft_changed','draft_not_empty','reference_state_unknown','reference_limit','reference_name_conflict','dialog_open'];
  if(!(error instanceof XyqError)||!codes.includes(error.code)||error.phase!=='preflight'||error.outcome_uncertain!==false||!Array.isArray(error.completed_steps)||error.completed_steps.length)return null;
  return[{result:{status:'upload_rejected',reason:error.code,...scope,phase:'preflight',completed_steps:[],outcome_uncertain:false,upload_accepted:false,
    upload_started:false,native_file_input_sent:false,generation_submitted:false,paid_submitted:false,secrets_returned:false,
    browser_session:'site:xyq-web',browser_surface:'browser',binding_changed:false}}];
}
export async function runBoundAudioUpload(context,rawScope,rawSettings,workspace,createBackend=createAudioUploadBackend){
  const scope=audioScope(rawScope),args=parseAudioUpload(rawSettings);inspectAudioFile(args.file,workspace,args.file_sha256);let page;
  try{page=audioUploadPage(await createBackend(boundReadRouting(context)),scope,args,workspace);}catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','The explicit audio upload Page preparation failed.');}
  try{
    const output=await uploadAudioReference(page,scope,args,workspace);
    return output.map(({result})=>({result:{...result,browser_session:'site:xyq-web',browser_surface:'browser',binding_changed:false}}));
  }catch(e){const stopped=audioUploadRejection(e,scope);if(stopped)return stopped;if(e instanceof XyqError){retainFailure(workspace,args,e);throw e;}fail('bridge_failed','Explicit audio attachment failed; inspect its retained intent.');}
}
