// Exact homepage native file input, durable once-only guard and UI-only readback.
import {createHash,randomUUID} from 'node:crypto';
import {readFileSync,existsSync,mkdirSync,openSync,closeSync,fstatSync,ftruncateSync,writeFileSync,fsyncSync,renameSync,constants} from 'node:fs';
import {join,dirname} from 'node:path';
import {XyqError,pollDOM,readHomeDOM} from './core.mjs';
import {readDraftDOM,draftHash} from './form.mjs';
import {boundReadRouting} from './audio-bound.mjs';
import {HOME_MATERIAL_FILES,inspectHomeMaterials} from './material-home.mjs';
import {homeUploadSafePath,inspectHomeMediaFile} from './home-media-file.mjs';
export const HOME_UPLOAD_FILES=[...HOME_MATERIAL_FILES,'home-media-file.mjs','home-upload.mjs','home-upload.js'];
export const HOME_UPLOAD_SELECTOR='#title-section-prompt-container [data-slot="prompt-composer"] [class*="uploadInputArea-"] input[type="file"][multiple][accept]';
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new XyqError(code,message);};
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function homeUploadDigest(){const h=createHash('sha256');for(const n of HOME_UPLOAD_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkHomeUploadPin(pin){if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==homeUploadDigest())fail('definition_changed','Review the complete homepage upload closure.');}
export function parseHomeUpload(raw){
  let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use typed homepage upload JSON.');}
  const required=['expected_draft_sha256','expected_material_sha256','file','file_sha256','request_key','human_confirmed','purpose'];
  if(!v||typeof v!=='object'||Array.isArray(v)||required.some(k=>!Object.hasOwn(v,k))||Object.keys(v).some(k=>![...required,'mode'].includes(k))||
    !['expected_draft_sha256','expected_material_sha256','file_sha256'].every(k=>typeof v[k]==='string'&&/^[a-f0-9]{64}$/.test(v[k]))||
    typeof v.file!=='string'||typeof v.request_key!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(v.request_key)||
    !['image_reference','video_reference','audio_reference'].includes(v.purpose)||Object.hasOwn(v,'mode')&&!['empty','append'].includes(v.mode))fail('invalid_argument','Bind one approved file to its draft, material state, purpose and stable key.');
  if(v.human_confirmed!==true)fail('confirmation_required','Confirm this exact file, homepage draft and upload purpose.');
  return{...v,mode:v.mode||'empty'};
}
function paths(workspace,key,create=false){
  homeUploadSafePath(workspace,true);if(typeof key!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(key))fail('invalid_argument','Use the original upload key.');
  const base=join(workspace,'.atm'),dir=join(base,'xyq-home-uploads');
  for(const p of [base,dir]){if(existsSync(p))homeUploadSafePath(p,true);else if(create)mkdirSync(p,{mode:0o700});}
  return{dir,receipt:join(dir,key+'.json'),lock:join(dir,'active.lock')};
}
function durable(path,value,exclusive=false){
  const fd=openSync(path,constants.O_WRONLY|constants.O_CREAT|constants.O_NOFOLLOW|constants.O_NONBLOCK|(exclusive?constants.O_EXCL:0),0o600);
  try{const st=fstatSync(fd);if(!st.isFile()||st.nlink!==1)fail('unsafe_path','Upload records must be regular single-link files.');if(!exclusive)ftruncateSync(fd,0);writeFileSync(fd,JSON.stringify(value));fsyncSync(fd);}finally{closeSync(fd);}
  const parent=openSync(dirname(path),constants.O_RDONLY|constants.O_DIRECTORY|constants.O_NOFOLLOW);try{fsyncSync(parent);}finally{closeSync(parent);}
}
function saved(path,key){
  if(!existsSync(path))return null;let fd,r;
  try{fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);const st=fstatSync(fd);if(!st.isFile()||st.nlink!==1||st.size<2||st.size>16000)fail('receipt_invalid','Expected a bounded single-link upload receipt.');r=JSON.parse(readFileSync(fd,'utf8'));}
  catch(e){if(e instanceof XyqError)throw e;fail('receipt_invalid','The retained upload receipt is malformed or inaccessible.');}finally{if(fd!==undefined)closeSync(fd);}
  if(!r||r.version!==1||r.request_key!==key||!['dispatch_claimed','submission_unknown','attachment_observed'].includes(r.status)||
    !['fingerprint','file_sha256','before_draft_sha256','before_material_sha256'].every(k=>typeof r[k]==='string'&&/^[a-f0-9]{64}$/.test(r[k]))||
    !['image_reference','video_reference','audio_reference'].includes(r.purpose)||!['empty','append'].includes(r.mode)||!Number.isSafeInteger(r.file_size)||r.file_size<12||r.file_size>200*1024*1024||
    ![true,false,null].includes(r.native_input_attempted)||typeof r.native_acknowledged!=='boolean'||
    r.status==='attachment_observed'&&(!r.native_input_attempted||!r.native_acknowledged||!/^[a-f0-9]{64}$/.test(r.after_draft_sha256||'')))fail('receipt_invalid','The retained upload has a different contract.');
  return r;
}
const publicReceipt=r=>({status:r.status==='dispatch_claimed'?'submission_unknown':r.status,request_key:r.request_key,purpose:r.purpose,upload_mode:r.mode,
  file_sha256:r.file_sha256,file_size:r.file_size,before_draft_sha256:r.before_draft_sha256,after_draft_sha256:r.after_draft_sha256||null,
  native_input_attempted:r.native_input_attempted,native_acknowledged:r.native_acknowledged,
  ui_attachment_observed:r.status==='attachment_observed',provider_upload_completed_verified:false,voice_effect_verified:false,persistence_verified:false,
  decoder_verified:false,provider_limits_verified:false,generation_submitted:false,paid_submitted:false,download_started:false,secrets_returned:false});
export function homeUploadStatus(workspace,key){
  const r=saved(paths(workspace,key).receipt,key);if(!r)fail('request_missing','No original homepage upload receipt exists.');
  return[{result:{...publicReceipt(r),query_scope:'original_local_upload_receipt',provider_checked:false,current_form_verified:false,
    upload_repeated:false,lock_changed:false,browser_session:null}}];
}
// Self-contained exact target check; hidden input is the native attachment route.
export function readHomeUploadTargetDOM(){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/home')return{kind:'unsupported_surface'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"],[inert]')&&getComputedStyle(e).visibility!=='hidden';
  if([...document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')].some(visible))return{kind:'dialog_open'};
  const roots=document.querySelectorAll('#title-section-prompt-container');if(roots.length!==1||!visible(roots[0]))return{kind:'layout_changed'};
  const composers=roots[0].querySelectorAll('[data-slot="prompt-composer"]');if(composers.length!==1||!visible(composers[0]))return{kind:'layout_changed'};
  const areas=composers[0].querySelectorAll('[class*="uploadInputArea-"]');if(areas.length!==1)return{kind:'material_input_changed'};
  const inputs=areas[0].querySelectorAll('input[type="file"]'),locals=areas[0].querySelectorAll('input[type="file"][multiple][accept]'),replacements=areas[0].querySelectorAll('input[type="file"][aria-label="替换素材文件"]');
  if(inputs.length!==2||locals.length!==1||replacements.length!==1||locals[0]===replacements[0]||replacements[0].multiple)return{kind:'material_input_changed'};
  if(locals[0].disabled||locals[0].getAttribute('aria-disabled')==='true'||locals[0].hasAttribute('data-disabled'))return{kind:'control_obscured'};
  if(typeof locals[0].files?.length!=='number')return{kind:'reference_state_unknown'};
  if(locals[0].files.length)return{kind:'draft_not_empty'};
  const submits=roots[0].querySelectorAll('button[data-slot="home-input-composer-submit-button"]');if(submits.length!==1||!visible(submits[0]))return{kind:'layout_changed'};
  if(submits[0].getAttribute('aria-busy')==='true')return{kind:'draft_busy'};
  return{kind:'ready'};
}
async function snapshot(page){
  const meta=(await inspectHomeMaterials(page))[0].result,home=await pollDOM(page,readHomeDOM),draft=await pollDOM(page,readDraftDOM);
  if(draft.layers||home.form?.preferences_open)fail('dialog_open','Existing layers remain intact.');
  if(draftHash({home,draft})!==meta.draft_sha256)fail('draft_changed','The complete homepage snapshot changed.');
  return{meta,home,draft};
}
const labelCount=(tree,name)=>typeof tree==='string'?(tree.trim()===name?1:0):Array.isArray(tree)&&tree.length===3&&Array.isArray(tree[1])&&Array.isArray(tree[2])?
  tree[1].filter(([k,v])=>['title','aria-label'].includes(k)&&v===name).length+tree[2].reduce((n,t)=>n+labelCount(t,name),0):0;
// Exactly one structural insertion; every existing subtree stays byte-identical.
export function homeAttachmentInsertion(before,after){
  if(equal(before,after))return[];
  if(before===null&&Array.isArray(after))return[after];
  if(!Array.isArray(before)||!Array.isArray(after)||before.length!==3||after.length!==3||before[0]!==after[0]||!equal(before[1],after[1])||!Array.isArray(before[2])||!Array.isArray(after[2]))return null;
  const a=before[2],b=after[2];
  if(b.length===a.length+1){const candidates=b.filter((_,i)=>equal(a,[...b.slice(0,i),...b.slice(i+1)]));return candidates.length===1?[candidates[0]]:null;}
  if(a.length!==b.length)return null;let insertions=[];
  for(let i=0;i<a.length;i++){const added=homeAttachmentInsertion(a[i],b[i]);if(added===null)return null;insertions.push(...added);}
  return insertions.length===1?insertions:null;
}
function preflight(s,args,info){
  if(s.meta.draft_sha256!==args.expected_draft_sha256||s.meta.material_sha256!==args.expected_material_sha256)fail('draft_changed','The draft or declared input changed from its approved snapshot.');
  if(!s.meta.input_enabled||!s.meta.declared_accept.includes(info.extension))fail('format_unavailable','This exact local-upload input does not declare the approved extension.');
  if(!s.meta.file_state_known||s.draft.files.some(x=>x.files===null))fail('reference_state_unknown','The existing file state is unknown.');
  if(s.meta.selected_file_count||s.draft.files.some(x=>x.files.length))fail('draft_not_empty','Existing file input contents stay intact.');
  if(args.mode==='empty'&&(s.draft.prompt||s.draft.rich_references||s.draft.media.length||s.draft.attachment_present))fail('draft_not_empty','Empty mode preserves an existing prompt or reference.');
  if(labelCount(s.draft.attachments??null,info.name))fail('reference_name_conflict','An existing reference already uses this filename.');
}
function accepted(before,after,info){
  const stable=s=>[s.home.agent,s.home.form.mode,s.home.form.preferences,s.home.form.canvas,s.draft.prompt,s.draft.prompt_tree,s.draft.rich_references];
  if(!equal(stable(before),stable(after)))fail('upload_readback_changed','Unrequested prompt, mode or settings changed during upload.');
  const shapes=s=>s.draft.files.map(({files,...rest})=>rest);
  if(!equal(shapes(before),shapes(after))||after.draft.files.some(x=>x.files===null))fail('upload_readback_changed','File input association changed during upload.');
  for(let i=0;i<after.draft.files.length;i++)for(const f of after.draft.files[i].files){
    if(!before.draft.files[i].multiple||!before.draft.files[i].accept?.split(',').map(x=>x.trim()).includes(info.extension)||f.name!==info.name||f.size!==info.size)fail('upload_readback_changed','Unexpected file selection appeared during upload.');
  }
  if(after.draft.files.reduce((n,x)=>n+x.files.length,0)>1)fail('upload_readback_changed','More than one selected file appeared.');
  if(after.draft.media.length<before.draft.media.length||!equal(before.draft.media,after.draft.media.slice(0,before.draft.media.length))||after.draft.media.length-before.draft.media.length>1)fail('upload_readback_changed','Existing media order changed or several media appeared.');
  const added=homeAttachmentInsertion(before.draft.attachments??null,after.draft.attachments??null);
  if(added===null)fail('upload_readback_changed','Existing attachment subtrees changed or an ambiguous insertion appeared.');
  if(!added.length)return false;
  if(!after.draft.attachment_present||labelCount(added[0],info.name)<1)fail('upload_readback_changed','The inserted attachment has no exact approved filename label.');
  return true;
}
export async function createHomeUploadBackend(routing){const {Page}=await import('@jackwener/opencli/browser/page');return new Page('site:xyq-home',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);}
export function homeUploadBridge(backend,args,workspace){
  if(!backend||typeof backend.evaluate!=='function'||typeof backend.cdp!=='function'||typeof backend.setFileInput!=='function')fail('unsupported_backend','Use the public native DOM and file-chooser bridge.');
  let sent=false;
  return Object.freeze({evaluate:(fn,arg)=>backend.evaluate(fn,arg),uploadFile:async()=>{
    try{
    if(sent)fail('upload_unknown','The native upload attempt is already consumed.');
    const target=async()=>pollDOM(backend,readHomeUploadTargetDOM);
    const check=async()=>{const info=inspectHomeMediaFile(args.file,workspace,args.file_sha256,args.purpose);preflight(await snapshot(backend),args,info);await target();};
    await check();
    const unwrap=v=>v&&typeof v==='object'&&'session'in v&&'data'in v?v.data:v;
    const doc=unwrap(await backend.cdp('DOM.getDocument',{depth:0}));if(!Number.isSafeInteger(doc?.root?.nodeId)||doc.root.nodeId<1)fail('bridge_protocol','The depth-zero DOM root is missing.');
    const query=async()=>{const d=unwrap(await backend.cdp('DOM.querySelector',{nodeId:doc.root.nodeId,selector:HOME_UPLOAD_SELECTOR}));if(!Number.isSafeInteger(d?.nodeId)||d.nodeId<1)fail('control_changed','The exact native file input is missing.');return d.nodeId;};
    const id=await query();await check();if(await query()!==id)fail('control_changed','The native file input was replaced before attachment.');
    inspectHomeMediaFile(args.file,workspace,args.file_sha256,args.purpose);sent=true;
    try{return await backend.setFileInput([args.file],HOME_UPLOAD_SELECTOR);}catch{
      const e=new XyqError('bridge_failed','Native file input acknowledgement is unverified; retain the original intent.');e.native_input_attempted=true;throw e;}
    }catch(error){const e=error instanceof XyqError?error:new XyqError('bridge_failed','The reviewed native upload preparation failed.');e.native_input_attempted=sent;throw e;}
  }});
}
export async function uploadHomeReference(page,raw,workspace){
  const args=parseHomeUpload(raw),info=inspectHomeMediaFile(args.file,workspace,args.file_sha256,args.purpose),p=paths(workspace,args.request_key),fingerprint=sha(JSON.stringify(['xyq-home-upload-v1',args]));
  const prior=saved(p.receipt,args.request_key);
  if(prior){if(prior.fingerprint!==fingerprint)fail('request_key_conflict','This key belongs to different upload inputs.');if(prior.status!=='attachment_observed')fail('upload_unknown','The original homepage upload retains an unresolved intent.');
    return[{result:{...publicReceipt(prior),reused:true,current_form_verified:false,upload_repeated:false,lock_changed:false}}];}
  if(!page||typeof page.evaluate!=='function'||typeof page.uploadFile!=='function')fail('unsupported_backend','Homepage upload requires the reviewed native file-input facade.');
  let phase='preflight',claimed=false,attempted=false,record=null;
  try{
    const before=await snapshot(page);preflight(before,args,info);await pollDOM(page,readHomeUploadTargetDOM);
    paths(workspace,args.request_key,true);
    phase='intent';try{durable(p.lock,{request_key:args.request_key,fingerprint},true);}catch(e){if(e.code==='EEXIST')fail('workspace_busy','The original unresolved upload lock stays in place.');throw e;}
    claimed=true;record={version:1,status:'dispatch_claimed',request_key:args.request_key,fingerprint,purpose:args.purpose,mode:args.mode,file_sha256:info.sha256,file_size:info.size,
      before_draft_sha256:args.expected_draft_sha256,before_material_sha256:args.expected_material_sha256,native_input_attempted:false,native_acknowledged:false};durable(p.receipt,record,true);
    phase='input_preflight';preflight(await snapshot(page),args,info);inspectHomeMediaFile(args.file,workspace,args.file_sha256,args.purpose);
    phase='upload';record.native_input_attempted=null;durable(p.receipt,record);attempted=null;
    await page.uploadFile();attempted=true;record.native_input_attempted=true;record.native_acknowledged=true;durable(p.receipt,record);
    inspectHomeMediaFile(args.file,workspace,args.file_sha256,args.purpose);
    phase='readback';let last=null;
    await pollDOM({evaluate:async()=>{const after=await snapshot(page);if(!accepted(before,after,info))return{kind:'pending'};last=after;return{kind:'ready'};}},readDraftDOM,{timeout:15000});
    const final=await snapshot(page);if(!accepted(before,final,info)||final.meta.draft_sha256!==last.meta.draft_sha256)fail('upload_readback_changed','The observed attachment did not remain stable.');
    phase='receipt';record.status='attachment_observed';record.after_draft_sha256=final.meta.draft_sha256;durable(p.receipt,record);
    const lock=savedLock(p.lock);if(lock.request_key!==args.request_key||lock.fingerprint!==fingerprint)fail('receipt_invalid','The upload lock ownership changed.');
    renameSync(p.lock,join(p.dir,'observed-'+randomUUID()+'.lock'));
    return[{result:{...publicReceipt(record),acceptance:'visible_home_attachment_label_only',references_preserved:true,reused:false,current_form_verified:true,
      upload_repeated:false,lock_changed:true,duration_seconds:info.duration_seconds,duration_basis:info.duration_basis,browser_session:'site:xyq-home',binding_changed:false}}];
  }catch(error){
    const e=error instanceof XyqError?error:new XyqError('bridge_failed','Homepage upload failed; inspect the retained request.');
    if(typeof e.native_input_attempted==='boolean')attempted=e.native_input_attempted;
    if(claimed&&record){record.status='submission_unknown';record.native_input_attempted=attempted;record.failure_code=e.code;record.failure_phase=phase;
      try{durable(p.receipt,record);}catch(retention){e.retention_failure_code=retention instanceof XyqError?retention.code:'receipt_write_failed';}}
    e.phase=phase;e.outcome_uncertain=claimed;e.native_input_attempted=attempted;e.automatic_retry_permitted=false;throw e;
  }
}
function savedLock(path){let fd;try{fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);const s=fstatSync(fd);if(!s.isFile()||s.nlink!==1||s.size>1000)fail('receipt_invalid','Expected the original private upload lock.');return JSON.parse(readFileSync(fd,'utf8'));}catch(e){if(e instanceof XyqError)throw e;fail('receipt_invalid','Upload lock read failed.');}finally{if(fd!==undefined)closeSync(fd);}}
export async function runBoundHomeUpload(context,raw,workspace,createBackend=createHomeUploadBackend){
  const args=parseHomeUpload(raw),routing=boundReadRouting(context);let facade;
  const prepare=async()=>{if(!facade){let backend;try{backend=await createBackend(routing);}catch(e){if(e instanceof XyqError)throw e;fail('bridge_failed','The bound homepage upload Page was not prepared.');}facade=homeUploadBridge(backend,args,workspace);}return facade;};
  const page=Object.freeze({evaluate:async(fn,arg)=>(await prepare()).evaluate(fn,arg),uploadFile:async()=>(await prepare()).uploadFile()});
  return uploadHomeReference(page,args,workspace);
}
