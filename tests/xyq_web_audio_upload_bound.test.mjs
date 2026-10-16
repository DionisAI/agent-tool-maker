import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,existsSync,statSync,realpathSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {XyqError} from '../examples/opencli/xyq-web/core.mjs';
import {audioFormHash,AUDIO_PANEL} from '../examples/opencli/xyq-web/audio.mjs';
import {AUDIO_BOUND_FILES} from '../examples/opencli/xyq-web/audio-bound.mjs';
import {AUDIO_UPLOAD_BOUND_FILES,audioUploadBoundDigest,checkAudioUploadBoundPin,audioUploadPage,audioUploadRejection,runBoundAudioUpload} from '../examples/opencli/xyq-web/audio-upload-bound.mjs';
// Canonical temp root: macOS tmpdir() sits below the /var symlink, which path guards reject.
const TMP=realpathSync(tmpdir());
const scope={project_id:'1',canvas_id:'2',node_id:'3'};
function fixture(){
  const root=mkdtempSync(join(TMP,'atm-xyq-upload-bound-unit-')),file=join(root,'FAKE_PRIVATE.wav'),wav=Buffer.alloc(60);
  wav.write('RIFF');wav.writeUInt32LE(52,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(8000,24);wav.writeUInt32LE(16000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(16,40);writeFileSync(file,wav,{mode:0o600});
  const form={kind:'ready',...scope,model:'Seed Audio 1.0',sample_rate:'44.1kHz',prompt:'',prompt_tree:null,prompt_references:0,references:[],files:[{kind:'audio',multiple:true,accept:null,files:[]},{kind:'image',multiple:true,accept:'.png',files:[]}],layers:0,submit_busy:false,submit_enabled:false,association:'unique_audio_node_only'};
  const calls=[],s={queries:0,fail:false,replace:false,mutate:false,wrapped:false};
  const backend={evaluate:async(fn,arg)=>{assert.deepEqual(arg,scope);calls.push(fn.name);return fn.name==='readAudioFormDOM'?structuredClone(form):{kind:'ready'};},cdp:async(method,params)=>{
    calls.push(method);let value;
    if(method==='DOM.getDocument'){assert.deepEqual(params,{depth:0});value={root:{nodeId:1}};}
    else if(method==='DOM.querySelector'){assert.equal(params.selector,AUDIO_PANEL+' input[type="file"][data-audio-reference-upload="true"]');s.queries++;value={nodeId:s.replace&&s.queries>1?9:2};if(s.mutate&&s.queries>1)form.prompt='changed';}
    else assert.fail('Unexpected raw native method: '+method);
    return s.wrapped?{session:'fixture',data:value}:value;
  },setFileInput:async(files,selector)=>{
    calls.push('setFileInput');assert.deepEqual(files,[file]);assert.equal(selector,AUDIO_PANEL+' input[type="file"][data-audio-reference-upload="true"]');
    assert(existsSync(join(root,'.atm/xyq-audio-uploads','native-once.intent.json')));assert(existsSync(join(root,'.atm/xyq-audio-uploads','active.lock')));
    if(s.fail)throw Error(s.denied?'Not allowed: FAKE_PRIVATE_BRIDGE':'FAKE_PRIVATE_BRIDGE');
    form.references.push({type:'audio',name:'FAKE_PRIVATE.wav',id:'FAKE_REF_ID',valid:true});
  },goto:()=>assert.fail('navigation'),click:()=>assert.fail('input'),getCookies:()=>assert.fail('auth')};
  return{root,file,form,calls,s,backend,settings:more=>({expected_form_sha256:audioFormHash(form),file,file_sha256:createHash('sha256').update(wav).digest('hex'),request_key:'native-once',purpose:'audio_reference',confirm:true,...more})};
}
test('upload pin binds the entire explicit public-routing closure with strict type',()=>{
  assert.deepEqual(AUDIO_UPLOAD_BOUND_FILES,[...AUDIO_BOUND_FILES,'audio-upload-bound.mjs','audio-upload-bound.js']);assert.equal(AUDIO_UPLOAD_BOUND_FILES.length,8);checkAudioUploadBoundPin(audioUploadBoundDigest());for(const pin of [null,[],[audioUploadBoundDigest()],'0'.repeat(64)])assert.throws(()=>checkAudioUploadBoundPin(pin),e=>e.code==='definition_changed');
});
test('scope/settings/file validation happens before constructing a browser',async()=>{
  const x=fixture();
  for(const settings of [null,{},[],{...x.settings(),confirm:false},{...x.settings(),selector:'input'},{...x.settings(),file_sha256:'0'.repeat(64)}])await assert.rejects(runBoundAudioUpload({},scope,settings,x.root,()=>assert.fail('factory')));
  await assert.rejects(runBoundAudioUpload({}, {...scope,node_id:'wrong'},x.settings(),x.root,()=>assert.fail('factory')),e=>e.code==='invalid_argument');
});
test('native upload once follows durable intent and scoped DOM; replay is historical',async()=>{
  for(const wrapped of [false,true]){
    const x=fixture();x.s.wrapped=wrapped;const settings=x.settings();
    const result=(await runBoundAudioUpload({preferredContextId:'fixture'},scope,settings,x.root,async routing=>{assert.deepEqual(routing,{preferredContextId:'fixture'});return x.backend;}))[0].result;
    assert.equal(result.status,'attached');assert.equal(result.browser_session,'site:xyq-web');assert.equal(result.binding_changed,false);assert.equal(result.paid_submitted,false);assert.equal(result.voice_effect_verified,false);assert.equal(result.references.length,1);assert(!JSON.stringify(result).includes('FAKE_PRIVATE'));
    assert.equal(x.calls.filter(c=>c==='setFileInput').length,1);assert(!x.calls.includes('DOM.setFileInputFiles'));
    assert.equal(x.calls.filter(c=>c==='DOM.getDocument').length,1);
    assert.equal(x.calls.filter(c=>c==='DOM.querySelector').length,2);
    assert(!existsSync(join(x.root,'.atm/xyq-audio-uploads/native-once.failure.json')));
    x.calls.length=0;const reused=(await runBoundAudioUpload({},scope,settings,x.root,async()=>x.backend))[0].result;
    assert.equal(reused.reused,true);assert.equal(reused.current_form_verified,false);assert.equal(x.calls.length,0);
  }
});
test('known preflight conflicts return explicit non-upload outcomes and no native requests',async()=>{
  for(const [mutate,code] of [[x=>x.form.prompt='existing','draft_not_empty'],[x=>x.form.layers=1,'dialog_open'],[x=>x.form.files[0].files=null,'reference_state_unknown']]){
    const x=fixture();mutate(x);const result=(await runBoundAudioUpload({},scope,x.settings(),x.root,async()=>x.backend))[0].result;
    assert.equal(result.status,'upload_rejected');assert.equal(result.reason,code);assert.equal(result.upload_accepted,false);assert.equal(result.native_file_input_sent,false);assert.equal(result.outcome_uncertain,false);assert.equal(result.phase,'preflight');assert(!x.calls.some(c=>c.startsWith('DOM.')));assert(!existsSync(join(x.root,'.atm/xyq-audio-uploads','active.lock')));
  }
});
test('stale digest is an explicit stop; backend origin/login/node failures remain errors',async()=>{
  const x=fixture(),result=(await runBoundAudioUpload({},scope,x.settings({expected_form_sha256:'0'.repeat(64)}),x.root,async()=>x.backend))[0].result;assert.equal(result.reason,'draft_changed');assert.equal(result.status,'upload_rejected');
  for(const kind of ['origin_mismatch','login_required','node_changed']){const y=fixture();y.backend.evaluate=async()=>({kind});await assert.rejects(runBoundAudioUpload({},scope,y.settings(),y.root,async()=>y.backend),e=>e.code===kind);assert(!y.calls.includes('setFileInput'));}
});
test('intent or unknown diagnostics are never converted to a clean preflight outcome',()=>{
  for(const override of [{phase:'upload'},{outcome_uncertain:true},{completed_steps:['upload_intent']},{code:'bridge_failed'},{phase:undefined}]){
    const error=new XyqError('draft_changed','fixture');Object.assign(error,{phase:'preflight',outcome_uncertain:false,completed_steps:[]},override);assert.equal(audioUploadRejection(error,scope),null);
  }assert.equal(audioUploadRejection(Error('FAKE_PRIVATE_TOKEN'),scope),null);
});
test('changed native node or draft after intent keeps lock and sends no file input',async()=>{
  for(const mode of ['replace','mutate']){const x=fixture();x.s[mode]=true;await assert.rejects(runBoundAudioUpload({},scope,x.settings(),x.root,async()=>x.backend),e=>e.code===(mode==='replace'?'control_changed':'draft_changed')&&e.outcome_uncertain&&e.phase==='upload');assert(!x.calls.includes('setFileInput'));assert(existsSync(join(x.root,'.atm/xyq-audio-uploads','active.lock')));}
});
test('native file-input exception keeps unknown intent and never retries or rebinds',async()=>{
  const x=fixture(),settings=x.settings();x.s.fail=true;
  await assert.rejects(runBoundAudioUpload({},scope,settings,x.root,async()=>x.backend),e=>e.code==='bridge_failed'&&e.outcome_uncertain&&!e.message.includes('FAKE_PRIVATE'));
  assert.equal(x.calls.filter(c=>c==='setFileInput').length,1);assert(!x.calls.includes('DOM.setFileInputFiles'));x.calls.length=0;
  await assert.rejects(runBoundAudioUpload({},scope,settings,x.root,async()=>x.backend),e=>e.code==='upload_unknown');assert.equal(x.calls.length,0);
});
test('arbitrary CDP, selectors, files and foreign node ids stop before backend calls',async()=>{
  const x=fixture(),page=audioUploadPage(x.backend,scope,x.settings(),x.root);
  for(const [method,params] of [['Runtime.evaluate',{expression:'anything'}],['DOM.getDocument',{depth:-1}],['DOM.querySelector',{nodeId:1,selector:'input'}],['DOM.setFileInputFiles',{nodeId:2,files:[x.file]}]])await assert.rejects(page.cdp(method,params),e=>e.code==='invalid_argument');assert.equal(x.calls.length,0);
  await page.cdp('DOM.getDocument',{depth:0});await page.cdp('DOM.querySelector',{nodeId:1,selector:AUDIO_PANEL+' input[type="file"][data-audio-reference-upload="true"]'});
  for(const params of [{nodeId:3,files:[x.file]},{nodeId:2,files:[x.file,x.file]},{nodeId:2,files:['/private/tmp/FOREIGN.wav']}])await assert.rejects(page.cdp('DOM.setFileInputFiles',params),e=>e.code==='invalid_argument');assert(!x.calls.includes('setFileInput'));
});
test('missing public chooser API fails before native requests or intent, never uses raw CDP',async()=>{
  const x=fixture();delete x.backend.setFileInput;
  await assert.rejects(runBoundAudioUpload({},scope,x.settings(),x.root,async()=>x.backend),e=>e.code==='upload_backend_missing');
  assert.equal(x.calls.length,0);assert(!existsSync(join(x.root,'.atm/xyq-audio-uploads','active.lock')));
});
test('a second facade input call never invokes the chooser API twice',async()=>{
  const x=fixture(),page=audioUploadPage(x.backend,scope,x.settings(),x.root);
  x.backend.setFileInput=async(files,selector)=>{assert.deepEqual(files,[x.file]);assert.equal(selector,AUDIO_PANEL+' input[type="file"][data-audio-reference-upload="true"]');x.calls.push('setFileInput');};
  await page.cdp('DOM.getDocument',{depth:0});await page.cdp('DOM.querySelector',{nodeId:1,selector:AUDIO_PANEL+' input[type="file"][data-audio-reference-upload="true"]'});
  await page.cdp('DOM.setFileInputFiles',{nodeId:2,files:[x.file]});
  await assert.rejects(page.cdp('DOM.setFileInputFiles',{nodeId:2,files:[x.file]}),e=>e.code==='upload_unknown');
  assert.equal(x.calls.filter(c=>c==='setFileInput').length,1);
});
test('post-intent native errors retain private bounded diagnostics without bridge message leakage',async()=>{
  for(const denied of [false,true]){
    const x=fixture(),settings=x.settings();x.s.fail=true;x.s.denied=denied;
    await assert.rejects(runBoundAudioUpload({},scope,settings,x.root,async()=>x.backend),e=>e.code==='bridge_failed'&&e.diagnostic_status==='recorded');
    const path=join(x.root,'.atm/xyq-audio-uploads/native-once.failure.json'),bytes=readFileSync(path,'utf8'),d=JSON.parse(bytes);
    assert.equal(d.phase,'upload');assert.equal(d.outcome_uncertain,true);assert.equal(d.native_input_attempted,true);
    assert.equal(d.native_error_class,denied?'native_permission_denied':'native_reply_unacknowledged');
    assert.deepEqual(d.completed_steps,['upload_intent']);assert.equal(d.receipt_is_success,false);assert.equal(d.automatic_retry_permitted,false);
    assert(!bytes.includes('FAKE_PRIVATE'));assert(!Object.hasOwn(d,'message'));assert.equal(statSync(path).mode&0o777,0o600);
    await assert.rejects(runBoundAudioUpload({},scope,settings,x.root,async()=>x.backend),e=>e.code==='upload_unknown');
    assert.equal(readFileSync(path,'utf8'),bytes);assert.equal(x.calls.filter(c=>c==='setFileInput').length,1);
  }
});
test('post-intent revalidation failures record zero native attempts and keep the lock',async()=>{
  const x=fixture();x.s.replace=true;
  await assert.rejects(runBoundAudioUpload({},scope,x.settings(),x.root,async()=>x.backend),e=>e.code==='control_changed'&&e.diagnostic_status==='recorded');
  const d=JSON.parse(readFileSync(join(x.root,'.atm/xyq-audio-uploads/native-once.failure.json')));
  assert.equal(d.native_input_attempted,false);assert.deepEqual(d.completed_steps,['upload_intent']);assert.equal(d.phase,'upload');
  assert(!x.calls.includes('setFileInput'));assert(existsSync(join(x.root,'.atm/xyq-audio-uploads/active.lock')));
});
test('post-input readback failure records the acknowledged input, never a success receipt',async()=>{
  const x=fixture(),input=x.backend.setFileInput;x.backend.setFileInput=async(...args)=>{await input(...args);x.form.prompt='CHANGED';};
  await assert.rejects(runBoundAudioUpload({},scope,x.settings(),x.root,async()=>x.backend),e=>e.code==='upload_readback_changed'&&e.diagnostic_status==='recorded');
  const d=JSON.parse(readFileSync(join(x.root,'.atm/xyq-audio-uploads/native-once.failure.json')));
  assert.equal(d.native_input_attempted,true);assert.deepEqual(d.completed_steps,['upload_intent','file_input_sent']);assert.equal(d.phase,'readback');
  assert.equal(x.calls.filter(c=>c==='setFileInput').length,1);assert(!existsSync(join(x.root,'.atm/xyq-audio-uploads/native-once.result.json')));
});
test('diagnostic IO conflicts stay observable without replacing the original upload error',async()=>{
  const x=fixture();x.s.fail=true;mkdirSync(join(x.root,'.atm/xyq-audio-uploads/native-once.failure.json'),{recursive:true});
  await assert.rejects(runBoundAudioUpload({},scope,x.settings(),x.root,async()=>x.backend),e=>e.code==='bridge_failed'&&e.outcome_uncertain&&e.diagnostic_status==='diagnostic_write_failed');
  assert(existsSync(join(x.root,'.atm/xyq-audio-uploads/active.lock')));assert.equal(x.calls.filter(c=>c==='setFileInput').length,1);
});
test('factory and routing diagnostics are sanitized without private Page mutation',async()=>{
  const x=fixture();await assert.rejects(runBoundAudioUpload({},scope,x.settings(),x.root,()=>{throw Error('FAKE_PRIVATE_TOKEN');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  await assert.rejects(runBoundAudioUpload({contextId:'a',preferredContextId:'b'},scope,x.settings(),x.root,()=>assert.fail('factory')),e=>e.code==='unsupported_backend');
  const src=readFileSync(new URL('../examples/opencli/xyq-web/audio-upload-bound.mjs',import.meta.url),'utf8');assert.match(src,/new Page\('site:xyq-web'/);assert.doesNotMatch(src,/document\.cookie|localStorage|sessionStorage|indexedDB|fetch\(|XMLHttpRequest|\.innerHTML\s*=|page\.goto|bindTab|\._page|nativeClick/);
});
