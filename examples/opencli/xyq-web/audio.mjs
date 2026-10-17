// Current audio-generation footer. PCM WAV / MP3 reference upload, never generation.
import {createHash} from 'node:crypto';
import {readFileSync,lstatSync,openSync,closeSync,fstatSync,constants,mkdirSync,writeFileSync,fsyncSync,existsSync,renameSync} from 'node:fs';
import {isAbsolute,resolve,relative,dirname,basename,join} from 'node:path';
import {XyqError,FILES,pollDOM} from './core.mjs';
const sha=v=>createHash('sha256').update(v).digest('hex');
const unwrap=v=>v&&typeof v==='object'&&'session'in v&&'data'in v?v.data:v;
const fail=(code,message)=>{throw new XyqError(code,message);};
export const AUDIO_FILES=[...FILES,'audio.mjs','audio.js'];
export const AUDIO_PANEL='[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"]';
export function audioDigest(){const h=createHash('sha256');for(const n of AUDIO_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');return h.digest('hex');}
export function checkAudioPin(pin){if(!/^[a-f0-9]{64}$/.test(pin||'')||pin!==audioDigest())fail('definition_changed','Review the audio-reference adapter bundle.');}
export function audioScope(raw){if(!raw||['project_id','canvas_id','node_id'].some(k=>typeof raw[k]!=='string'||!/^\d{1,20}$/.test(raw[k])))fail('invalid_argument','Use exact project, canvas and audio-node IDs.');return Object.fromEntries(['project_id','canvas_id','node_id'].map(k=>[k,raw[k]]));}
export function readAudioFormDOM(scope){
  if(location.origin!=='https://xyq.jianying.com')return{kind:'origin_mismatch'};
  if(location.pathname==='/login')return{kind:'login_required'};
  if(location.pathname!=='/project')return{kind:'unsupported_surface'};
  const u=new URL(location.href);if(u.searchParams.get('projectId')!==scope.project_id||u.searchParams.get('canvasId')!==scope.canvas_id)return{kind:'canvas_changed'};
  const visible=e=>!!e&&!!e.getClientRects().length&&!e.closest('[hidden],[aria-hidden="true"]');
  const roots=Array.from(document.querySelectorAll('[data-testid="rf__wrapper"][role="application"]')).filter(visible);
  if(!roots.length)return{kind:'pending'};if(roots.length!==1)return{kind:'layout_changed'};
  // The footer is a viewport portal with no node-id marker. This first contract
  // accepts only a canvas with exactly one audio node; never guess selection.
  const nodes=Array.from(roots[0].querySelectorAll('.react-flow__node')).filter(e=>e.classList.contains('react-flow__node-biz/audio'));
  if(nodes.length!==1)return{kind:'audio_node_ambiguous'};
  if(nodes[0].getAttribute('data-id')!==scope.node_id)return{kind:'node_changed'};
  const panels=Array.from(roots[0].querySelectorAll('[role="dialog"][aria-label="音频节点音频生成面板"][data-xyq-selected-audio-footer-panel="true"]')).filter(visible);
  if(!panels.length)return{kind:'audio_form_closed'};if(panels.length!==1)return{kind:'layout_changed'};
  const p=panels[0],editors=p.querySelectorAll('[data-testid="canvas-generation-prompt-editor"][contenteditable="true"]');
  const models=p.querySelectorAll('button[data-action="select-audio-model"]'),rates=p.querySelectorAll('button[data-action="open-audio-parameter"][data-action-object-id="sample_rate"]');
  const submits=p.querySelectorAll('button[data-action="audio-generate-submit"]'),inputs=Array.from(p.querySelectorAll('input[type="file"]'));
  if(editors.length!==1||models.length!==1||rates.length>1||submits.length!==1||inputs.filter(e=>e.getAttribute('data-audio-reference-upload')==='true').length!==1||inputs.length!==2)return{kind:'layout_changed'};
  const clean=e=>{const walk=x=>x.nodeType===3?x.textContent:x.nodeType===1&&x.getAttribute('data-slot')==='badge'?'':Array.from(x.childNodes).map(walk).join('');return walk(e).replace(/\s+/g,' ').trim();};
  const prompt=(editors[0].innerText||'').replace(/\r\n/g,'\n').trim();if(prompt.length>20000)return{kind:'layout_changed'};
  const tree=e=>e.nodeType===3?e.textContent:e.nodeType===1?[e.tagName,['contenteditable','data-type','data-id','data-reference-id','data-reference-type','data-action-object-id'].map(k=>[k,e.getAttribute(k)]).filter(x=>x[1]!==null),Array.from(e.childNodes).map(tree)]:null;
  const refs=Array.from(p.querySelectorAll('[data-reference-type]')).map(e=>{
    const type=e.getAttribute('data-reference-type'),m=e.querySelectorAll('button[data-action="mention-'+type+'-reference"]'),r=e.querySelectorAll('button[data-action="remove-'+type+'-reference"]');
    return{type,name:e.getAttribute('title'),id:m.length===1?m[0].getAttribute('data-action-object-id'):null,valid:m.length===1&&r.length===1&&m[0].getAttribute('data-action-object-id')===r[0].getAttribute('data-action-object-id')};});
  if(refs.length>4||refs.some(e=>!e.valid||!['audio','image'].includes(e.type)||!e.name||e.name.length>512||!e.id||e.id.length>1024)||new Set(refs.map(e=>e.id)).size!==refs.length||refs.filter(e=>e.type==='audio').length>3||refs.filter(e=>e.type==='image').length>1)return{kind:'reference_layout_changed'};
  const files=inputs.map(e=>({kind:e.getAttribute('data-audio-reference-upload')==='true'?'audio':e.getAttribute('data-image-reference-upload')==='true'?'image':'unknown',multiple:e.multiple,accept:e.getAttribute('accept'),files:typeof e.files?.length==='number'?Array.from(e.files).map(f=>({name:f.name,size:f.size,type:f.type,last_modified:f.lastModified})):null}));
  if(files.some(e=>e.kind==='unknown'||e.files?.length>4))return{kind:'layout_changed'};
  const layers=Array.from(document.querySelectorAll('[role="dialog"],[role="menu"],[role="listbox"]')).filter(visible).filter(e=>e!==p);
  return{kind:'ready',...scope,model:clean(models[0]),sample_rate:rates.length?clean(rates[0]):null,prompt,prompt_tree:tree(editors[0]),prompt_references:editors[0].querySelectorAll('[contenteditable="false"],[data-reference-id],img,video,audio').length,references:refs,files,layers:layers.length,
    submit_enabled:!submits[0].disabled&&submits[0].getAttribute('aria-disabled')!=='true',submit_busy:submits[0].getAttribute('aria-busy')==='true',association:'unique_audio_node_only'};
}
export function audioFormHash(d){return sha(JSON.stringify(['xyq-audio-footer-v1',d.project_id,d.canvas_id,d.node_id,d.model,d.sample_rate,d.prompt,d.prompt_tree,d.references,d.files]));}
function publicState(d){return{status:'ready',project_id:d.project_id,canvas_id:d.canvas_id,node_id:d.node_id,model:d.model,sample_rate:d.sample_rate,form_sha256:audioFormHash(d),prompt_sha256:sha(d.prompt),
  references:d.references.map(({type,name,id})=>({type,name_sha256:sha(name),reference_sha256:sha(id)})),reference_limits:{audio:3,image:1},files_known:d.files.every(e=>e.files!==null),layers:d.layers,
  prompt_reference_count:d.prompt_references??0,submit_enabled:d.submit_enabled,association:d.association,source:'visible_dom',secrets_returned:false,paid_submitted:false,voice_effect_verified:false,persistence_verified:false};}
async function state(page,scope){return pollDOM({evaluate:()=>page.evaluate(readAudioFormDOM,scope)},readAudioFormDOM);}
export async function inspectAudioForm(page,raw){const scope=audioScope(raw),a=await state(page,scope),b=await state(page,scope);if(audioFormHash(a)!==audioFormHash(b))fail('draft_changed','Audio draft changed during snapshot.');return[{result:{...publicState(b),upload_started:false}}];}
function safePath(p,directory=false){if(typeof p!=='string'||!isAbsolute(p)||resolve(p)!==p||p==='/')fail('unsafe_path','Use a canonical absolute project path.');let current=p;
  while(current!=='/'){let st;try{st=lstatSync(current);}catch{fail('unsafe_path','Project path is missing.');}if(st.isSymbolicLink()||current!==p&&!st.isDirectory()||current===p&&(directory?!st.isDirectory():!st.isFile()))fail('unsafe_path','Paths must be regular and contain no symlinks.');current=dirname(current);}return p;}
export function inspectAudioFile(file,workspace,expected){safePath(workspace,true);safePath(file);const rel=relative(workspace,file);
  const mp3=file.toLowerCase().endsWith('.mp3');
  if(!rel||rel.startsWith('..')||isAbsolute(rel)||!mp3&&!file.toLowerCase().endsWith('.wav'))fail('invalid_audio_file','Select one project-owned PCM WAV or MP3 file.');
  let fd;try{fd=openSync(file,constants.O_RDONLY|constants.O_NOFOLLOW);const st=fstatSync(fd);if(!st.isFile()||st.size<44||st.size>20*1024*1024)fail('invalid_audio_file','Audio size must be 44 bytes to 20 MiB.');
    const bytes=readFileSync(fd);if(bytes.length!==st.size)fail('input_changed','Audio file changed while reading.');const digest=sha(bytes);if(expected&&digest!==expected)fail('input_changed','Audio bytes differ from the approved SHA256.');
    if(mp3)return{sha256:digest,size:bytes.length,name:basename(file),...inspectMp3Frames(bytes)};
    if(bytes.toString('ascii',0,4)!=='RIFF'||bytes.toString('ascii',8,12)!=='WAVE'||bytes.readUInt32LE(4)+8!==bytes.length)fail('invalid_audio_file','Expected a complete RIFF/WAVE file.');
    let fmt=null,data=null,offset=12;for(;offset+8<=bytes.length;){const tag=bytes.toString('ascii',offset,offset+4),size=bytes.readUInt32LE(offset+4),end=offset+8+size;if(end>bytes.length)fail('invalid_audio_file','WAV chunk exceeds the file.');
      if(tag==='fmt '){if(fmt||size<16)fail('invalid_audio_file','Expected one PCM format chunk.');fmt={format:bytes.readUInt16LE(offset+8),channels:bytes.readUInt16LE(offset+10),rate:bytes.readUInt32LE(offset+12),byte_rate:bytes.readUInt32LE(offset+16),align:bytes.readUInt16LE(offset+20),bits:bytes.readUInt16LE(offset+22)};}
      if(tag==='data'){if(data!==null)fail('invalid_audio_file','Expected one audio data chunk.');data=size;}offset=end+(size%2);if(offset>bytes.length)fail('invalid_audio_file','WAV padding is incomplete.');}
    if(offset!==bytes.length||!fmt||!data||fmt.format!==1||![1,2].includes(fmt.channels)||![8,16,24,32].includes(fmt.bits)||!Number.isInteger(fmt.rate)||fmt.rate<8000||fmt.rate>192000||fmt.align!==fmt.channels*fmt.bits/8||fmt.byte_rate!==fmt.rate*fmt.align||data%fmt.align||data/fmt.byte_rate>120)fail('invalid_audio_file','Use a bounded PCM WAV, mono/stereo, up to 120 seconds.');
    return{sha256:digest,size:bytes.length,name:basename(file),duration_seconds:data/fmt.byte_rate,channels:fmt.channels,sample_rate:fmt.rate};
  }catch(e){if(e instanceof XyqError)throw e;fail('file_read_failed','Approved audio file read failed.');}finally{if(fd!==undefined)closeSync(fd);}}

// Frame/header integrity only, not a decoder or provider-acceptance assertion.
// Frame sizing follows the MPEG Layer-III contract; tags are bounded and never output.
function inspectMp3Frames(bytes){
  let offset=0,end=bytes.length,frames=0,rate=null,channels=null,version=null,samples=0;
  if(end>=128&&bytes.toString('latin1',end-128,end-125)==='TAG')end-=128;
  if(bytes.toString('latin1',0,3)==='ID3'){
    const major=bytes[3];
    if(bytes.length<10||![2,3,4].includes(major)||bytes[4]===255||bytes[5]&(major===4?15:major===3?31:63)||Array.from(bytes.subarray(6,10)).some(v=>v&128))fail('invalid_audio_file','Expected a bounded ID3v2 header.');
    if(major===4&&(bytes[5]&16))fail('invalid_audio_file','ID3v2 footer variants require a separate intake contract.');
    offset=10+bytes.subarray(6,10).reduce((n,v)=>n*128+v,0);
    if(offset>=end)fail('invalid_audio_file','MP3 tag consumes the available audio frames.');
  }
  while(offset<end){
    if(offset+4>end)fail('invalid_audio_file','MP3 ends inside a frame header.');
    const h=bytes.readUInt32BE(offset),v=h>>>19&3,layer=h>>>17&3,b=h>>>12&15,s=h>>>10&3,c=(h>>>6&3)===3?1:2;
    if(h>>>21!==2047||v===1||layer!==1||s===3||(h&3)===2)fail('invalid_audio_file','Expected contiguous MPEG Layer-III frame boundaries.');
    if(b===0||b===15)fail('invalid_audio_file','Free or reserved MP3 bitrates require a separate intake contract.');
    const kbps=(v===3?[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320]:[0,8,16,24,32,40,48,56,64,80,96,112,128,144,160])[b];
    const r=[44100,48000,32000][s]/(v===3?1:v===2?2:4);
    if(rate!==null&&(rate!==r||channels!==c||version!==v))fail('invalid_audio_file','MP3 rate, version and channel count must remain stable.');
    rate=r;channels=c;version=v;
    const length=Math.floor((v===3?144000:72000)*kbps/r)+(h>>>9&1);
    const minimum=4+((h>>>16&1)?0:2)+(v===3?(c===1?17:32):(c===1?9:17));
    if(length<=minimum||offset+length>end)fail('invalid_audio_file','MP3 ends inside a complete audio frame.');
    offset+=length;frames++;samples+=v===3?1152:576;
    if(samples/r>120)fail('invalid_audio_file','Use a bounded MP3, mono/stereo, up to 120 encoded-frame seconds.');
  }
  if(!frames||offset!==end)fail('invalid_audio_file','Expected at least one complete MP3 audio frame.');
  return{format:'mp3',duration_seconds:samples/rate,channels,sample_rate:rate,duration_basis:'encoded_frame_samples',decoder_verified:false};
}
export function parseAudioUpload(raw){let v;try{v=typeof raw==='string'?JSON.parse(raw):raw;}catch{fail('invalid_argument','Use typed audio-upload JSON.');}
  const required=['expected_form_sha256','file','file_sha256','request_key','confirm','purpose'];
  if(!v||Array.isArray(v)||typeof v!=='object'||required.some(k=>!Object.hasOwn(v,k))||Object.keys(v).some(k=>![...required,'mode'].includes(k))||typeof v.expected_form_sha256!=='string'||!/^[a-f0-9]{64}$/.test(v.expected_form_sha256)||typeof v.file_sha256!=='string'||!/^[a-f0-9]{64}$/.test(v.file_sha256)||typeof v.file!=='string'||typeof v.request_key!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(v.request_key)||v.confirm!==true||v.purpose!=='audio_reference'||Object.hasOwn(v,'mode')&&!['empty','append'].includes(v.mode))fail('invalid_argument','Bind one approved audio-reference file, digest, draft and stable request key; mode is empty or append.');return v;}
function uploadDraft(d,mode,name){
  if(mode==='empty'&&(d.prompt||d.prompt_references||d.references.length))fail('draft_not_empty','Empty-mode upload preserves any existing draft.');
  if(d.files.some(e=>e.files===null))fail('reference_state_unknown','File state is unknown.');
  if(d.files.some(e=>e.files.length)||d.submit_busy)fail('draft_not_empty','Existing files or a busy draft are preserved.');
  if(d.references.filter(e=>e.type==='audio').length>=3)fail('reference_limit','The observed audio reference limit is already reached.');
  if(d.references.some(e=>e.name===name))fail('reference_name_conflict','A reference with this file name already exists; no replacement or input sent.');
}
function writeNew(path,value){const fd=openSync(path,'wx',0o600);try{writeFileSync(fd,JSON.stringify(value));fsyncSync(fd);}finally{closeSync(fd);}}
function ledgerPaths(workspace,key){safePath(workspace,true);const base=join(workspace,'.atm');if(existsSync(base))safePath(base,true);else mkdirSync(base,{mode:0o700});const dir=join(base,'xyq-audio-uploads');if(existsSync(dir))safePath(dir,true);else mkdirSync(dir,{mode:0o700});return{dir,intent:join(dir,key+'.intent.json'),result:join(dir,key+'.result.json'),lock:join(dir,'active.lock'),done:join(dir,key+'.completed.lock')};}
function saved(path){safePath(path);if(lstatSync(path).size>50000)fail('receipt_invalid','Retained receipt exceeds its size bound.');let v;try{v=JSON.parse(readFileSync(path,'utf8'));}catch{fail('receipt_invalid','Retained upload receipt is invalid.');}if(!v||v.version!==1||!/^[a-f0-9]{64}$/.test(v.fingerprint||''))fail('receipt_invalid','Retained receipt schema is invalid.');return v;}
export async function uploadAudioReference(page,rawScope,raw,workspace){const scope=audioScope(rawScope),args=parseAudioUpload(raw),info=inspectAudioFile(args.file,workspace,args.file_sha256),mode=Object.hasOwn(args,'mode')?args.mode:'empty';
  // Preserve the original empty-upload fingerprint so old receipts still reuse.
  const fingerprint=sha(JSON.stringify([scope,args.expected_form_sha256,args.file,args.file_sha256,args.purpose,...(mode==='append'?['append-v1']:[])])),paths=ledgerPaths(workspace,args.request_key);
  if(existsSync(paths.intent)){const intent=saved(paths.intent);if(intent.fingerprint!==fingerprint)fail('request_key_conflict','Stable request key belongs to another upload.');if(!existsSync(paths.result))fail('upload_unknown','An upload intent is retained; inspect the provider draft before another action.');const old=saved(paths.result);if(old.fingerprint!==fingerprint||old.result?.status!=='attached'||old.result.file_sha256!==info.sha256||old.result.request_key!==args.request_key||(old.result.upload_mode||'empty')!==mode)fail('receipt_invalid','Upload receipt differs from its intent.');return[{result:{...old.result,upload_mode:mode,reused:true,current_form_verified:false}}];}
  let phase='preflight',claimed=false,steps=[];
  try{const before=await state(page,scope);if(before.layers)fail('dialog_open','Existing layers stay intact.');if(audioFormHash(before)!==args.expected_form_sha256)fail('draft_changed','Audio draft differs from the inspected digest.');
    uploadDraft(before,mode,info.name);
    if(typeof page.cdp!=='function')fail('upload_backend_missing','Reviewed DOM file-input support is required.');
    const doc=unwrap(await page.cdp('DOM.getDocument',{depth:0}));if(!Number.isSafeInteger(doc?.root?.nodeId)||doc.root.nodeId<1)fail('bridge_protocol','DOM root is missing.');
    const input=unwrap(await page.cdp('DOM.querySelector',{nodeId:doc.root.nodeId,selector:AUDIO_PANEL+' input[type="file"][data-audio-reference-upload="true"]'}));if(!Number.isSafeInteger(input?.nodeId)||input.nodeId<1)fail('layout_changed','Observed audio-reference input is missing.');
    inspectAudioFile(args.file,workspace,args.file_sha256);const last=await state(page,scope);if(last.layers||audioFormHash(last)!==args.expected_form_sha256)fail('draft_changed','Draft changed before the upload intent.');
    phase='intent';try{writeNew(paths.lock,{request_key:args.request_key,fingerprint});}catch(e){if(e.code==='EEXIST')fail('workspace_busy','Retained upload lock requires reconciliation.');throw e;}
    claimed=true;writeNew(paths.intent,{version:1,scope,request_key:args.request_key,fingerprint,file_sha256:info.sha256,file_size:info.size,upload_mode:mode,before_form_sha256:args.expected_form_sha256,before_reference_count:before.references.length,phase:'upload_intent'});
    phase='input_preflight';steps.push('upload_intent');const immediate=await state(page,scope);
    if(immediate.layers||audioFormHash(immediate)!==args.expected_form_sha256)fail('draft_changed','Draft changed after upload intent; no file input sent.');uploadDraft(immediate,mode,info.name);
    phase='upload';inspectAudioFile(args.file,workspace,args.file_sha256);await page.cdp('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[args.file]});steps.push('file_input_sent');inspectAudioFile(args.file,workspace,args.file_sha256);
    phase='readback';const previousIds=new Set(before.references.map(e=>e.id));
    const after=await pollDOM({evaluate:async()=>{const d=await state(page,scope);
      if(d.model!==before.model||d.sample_rate!==before.sample_rate||d.prompt!==before.prompt||d.prompt_references!==before.prompt_references||JSON.stringify(d.prompt_tree)!==JSON.stringify(before.prompt_tree)||JSON.stringify(d.references.filter(e=>previousIds.has(e.id)))!==JSON.stringify(before.references))return{kind:'upload_readback_changed'};
      return d.references.some(e=>!previousIds.has(e.id))?d:{kind:'pending'};}},readAudioFormDOM);
    const added=after.references.filter(e=>!previousIds.has(e.id)),preserved=after.references.filter(e=>previousIds.has(e.id));
    const shapes=d=>JSON.stringify(d.files.map(({files,...rest})=>rest));
    if(after.layers||after.submit_busy||after.model!==before.model||after.sample_rate!==before.sample_rate||after.prompt!==before.prompt||after.prompt_references!==before.prompt_references||JSON.stringify(after.prompt_tree)!==JSON.stringify(before.prompt_tree)||shapes(after)!==shapes(before)||after.references.length!==before.references.length+1||JSON.stringify(preserved)!==JSON.stringify(before.references)||added.length!==1||added[0].type!=='audio'||added[0].name!==info.name||after.references.filter(e=>e.type==='audio').length>3||after.files.some(e=>e.files===null||e.files.length>1||e.files.some(f=>e.kind!=='audio'||f.name!==info.name||f.size!==info.size)))fail('upload_readback_changed','Reference or unrequested form state differs; inspect the retained draft.');
    const result={...publicState(after),status:'attached',request_key:args.request_key,file_sha256:info.sha256,file_size:info.size,duration_seconds:info.duration_seconds,...(info.format==='mp3'?{file_format:'mp3',duration_basis:info.duration_basis,decoder_verified:false}:{}),upload_mode:mode,previous_reference_count:before.references.length,added_reference_sha256:sha(added[0].id),references_preserved:true,upload_started:true,reused:false,acceptance:'visible_audio_reference_chip_only',generation_submitted:false};
    phase='receipt';writeNew(paths.result,{version:1,fingerprint,result});if(existsSync(paths.done))fail('receipt_invalid','Completed-lock destination already exists; the active lock is retained.');renameSync(paths.lock,paths.done);return[{result}];
  }catch(error){const e=error instanceof XyqError?error:new XyqError('bridge_failed','Audio upload step failed; inspect the retained draft.');e.phase=phase;e.completed_steps=steps;e.outcome_uncertain=claimed;throw e;}
}
