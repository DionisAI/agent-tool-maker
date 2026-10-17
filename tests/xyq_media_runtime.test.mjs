import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtempSync,writeFileSync,readFileSync,existsSync,realpathSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {XyqError} from '../examples/opencli/xyq-web/core.mjs';
import {MEDIA_RUNTIME_FILES,MEDIA_RUNTIME_OPERATIONS,mediaRuntimeDigest,checkMediaRuntimePin,runMediaOperation} from '../examples/opencli/xyq-web/media-runtime.mjs';
// Canonical temp root: macOS tmpdir() sits below the /var symlink, which path guards reject.
const TMP=realpathSync(tmpdir());

const hash='a'.repeat(64),scope={project:'1',canvas:'2',node:'3'};
function uploadFixture(){
  const workspace=mkdtempSync(join(TMP,'atm-media-runtime-')),file=join(workspace,'fixture.wav'),wav=Buffer.alloc(60);
  wav.write('RIFF');wav.writeUInt32LE(52,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);
  wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(8000,24);wav.writeUInt32LE(16000,28);
  wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(16,40);writeFileSync(file,wav,{mode:0o600});
  return{workspace,settings:{expected_form_sha256:hash,file,file_sha256:createHash('sha256').update(wav).digest('hex'),
    request_key:'fixture-upload-once',purpose:'audio_reference',confirm:true}};
}
function argumentsFor(operation){
  if(operation==='audio_reference_upload')return{...scope,...uploadFixture()};
  if(operation==='generate')return{workspace:mkdtempSync(join(TMP,'atm-media-runtime-')),settings:{expected_draft_sha256:hash,quote_sha256:hash,
    max_credits:6,human_confirmed:true,estimated_cost_confirmed:true,request_key:'fixture-once'}};
  if(operation==='form_prepare')return{settings:{expected_draft_sha256:hash}};
  if(operation==='mode_prepare')return{settings:{expected_draft_sha256:hash,mode:'图片生成'}};
  if(operation==='home_quote')return{settings:{expected_draft_sha256:hash}};
  if(operation==='audio_prompt_prepare')return{...scope,settings:{expected_form_sha256:hash,prompt:'fixture-text'}};
  if(operation==='audio_prepare')return{...scope,settings:{expected_form_sha256:hash,sample_rate_hz:44100}};
  if(operation==='audio_quote')return{...scope,settings:{expected_form_sha256:hash}};
  return{...scope};
}
test('complete production closure pin includes the dispatcher and declaration, without parked canvas tools',()=>{
  assert.equal(MEDIA_RUNTIME_FILES.length,new Set(MEDIA_RUNTIME_FILES).size);
  assert(MEDIA_RUNTIME_FILES.includes('media-runtime.mjs')&&MEDIA_RUNTIME_FILES.includes('media-runtime.js'));
  assert(!MEDIA_RUNTIME_FILES.includes('canvas.mjs')&&!MEDIA_RUNTIME_FILES.includes('text.mjs'));
  assert.equal(MEDIA_RUNTIME_OPERATIONS.length,20);checkMediaRuntimePin(mediaRuntimeDigest());
  for(const pin of [null,[],[mediaRuntimeDigest()],'0'.repeat(64)])assert.throws(()=>checkMediaRuntimePin(pin),e=>e.code==='definition_changed');
});
test('all nineteen browser operations dispatch through exactly one original typed bound backend',async()=>{
  for(const operation of MEDIA_RUNTIME_OPERATIONS.filter(x=>x!=='generation_status')){
    let constructed=0;const factories=Object.fromEntries(['homeRead','home','audioRead','audioEdit','audioUpload','history','generation'].map(name=>[
      name,async routing=>{constructed++;assert.deepEqual(routing,{preferredContextId:'fixture-profile'});throw new XyqError('fixture_backend',name);} ]));
    await assert.rejects(runMediaOperation({preferredContextId:'fixture-profile'},operation,argumentsFor(operation),factories),e=>e.code==='fixture_backend',operation);
    assert.equal(constructed,1,operation);
  }
});
test('local original generation status works without Page construction or profile routing',async()=>{
  const workspace=mkdtempSync(join(TMP,'atm-media-runtime-local-')),context=new Proxy({},{get(){assert.fail('profile routing');}}),factories=new Proxy({},{get(){assert.fail('Page construction');}});
  await assert.rejects(runMediaOperation(context,'generation_status',{workspace,key:'missing'},factories),e=>e.code==='request_missing');
  assert(!existsSync(join(workspace,'.atm')));
});
test('foundation readers preserve explicit home profile routing and expose evaluations only',async()=>{
  for(const operation of ['account','surface','form_inspect','form_options']){
    let constructed=0;const calls=[],home={kind:'ready',logged_in:true,credits:40,agent:'创作',agents:[],navigation:[],shortcuts:[],
      form:{mode:'图片生成',preferences:'FIXTURE',preferences_open:operation==='form_options'}};
    const factories={homeRead:async routing=>{constructed++;assert.deepEqual(routing,{contextId:'profile-A'});
      return{evaluate:async fn=>{calls.push(fn.name);return fn.name==='readOptionsDOM'?{kind:'ready',groups:[]}:structuredClone(home);},
        goto:()=>assert.fail('navigation'),nativeClick:()=>assert.fail('input'),getCookies:()=>assert.fail('auth')};}};
    const result=(await runMediaOperation({contextId:'profile-A'},operation,{},factories))[0].result;
    assert.equal(constructed,1);assert.equal(result.status,'ready');assert.equal(result.source,'visible_dom');assert.equal(result.secrets_returned,false);
    assert(calls.every(n=>['readHomeDOM','readOptionsDOM'].includes(n)));
  }
});
test('both audio read IDs use the same bound scope and emit only hashed prompt metadata',async()=>{
  let constructed=0;const data={kind:'ready',project_id:'1',canvas_id:'2',node_id:'3',model:'Seed Audio 1.0',sample_rate:'44.1kHz',
    prompt:'FIXTURE_PRIVATE_PROMPT',prompt_tree:null,references:[],files:[],layers:0,submit_busy:false,submit_enabled:true,association:'unique_audio_node_only'};
  const factories={audioRead:async()=>{constructed++;return{evaluate:async()=>structuredClone(data)};}};
  const a=(await runMediaOperation({},'audio_form_state',scope,factories))[0].result;
  const b=(await runMediaOperation({},'audio_form_state_bound',scope,factories))[0].result;
  assert.equal(constructed,2);assert.equal(a.form_sha256,b.form_sha256);assert.equal(a.browser_session,'site:xyq-web');
  assert(!JSON.stringify(a).includes('FIXTURE_PRIVATE'));
});
test('wrong operation or malformed routing never selects a fallback or performs input',async()=>{
  await assert.rejects(runMediaOperation({},'canvas_inspect',{},{}),e=>e.code==='invalid_argument');
  for(const context of [null,[],{contextId:'a',preferredContextId:'b'},{contextId:'../x'}])
    await assert.rejects(runMediaOperation(context,'account',{}, {homeRead:()=>assert.fail('no factory')}),e=>e.code==='unsupported_backend');
  for(const kind of ['origin_mismatch','login_required','unsupported_surface']){
    let reads=0;await assert.rejects(runMediaOperation({},'account',{}, {homeRead:async()=>({evaluate:async()=>{reads++;return{kind};}})}),e=>e.code===kind);
    assert.equal(reads,1);
  }
});
test('production declarations are a new namespace and local status explicitly disables browser use',()=>{
  const source=readFileSync(new URL('../examples/opencli/xyq-web/media-runtime.js',import.meta.url),'utf8');
  assert.match(source,/site:'xyq-media'/);assert.match(source,/strategy:local\?Strategy.LOCAL:Strategy.UI,browser:!local/);
  assert.match(source,/retention_failure_code/);assert.doesNotMatch(source,/getCookies|document\.cookie|localStorage|sessionStorage|fetch\(|bindTab|\.goto\(/);
});
test('registered LOCAL status accepts the SDK arguments-first call without a Page',async()=>{
  const registryKey='__atmMediaRuntimeRegistrationFixture';globalThis[registryKey]=[];
  const asModule=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
  const registry=asModule(`export const Strategy={LOCAL:'local',UI:'ui'};export function cli(value){globalThis.${registryKey}.push(value);}`);
  const errors=asModule('export class ArgumentError extends Error{};export class AuthRequiredError extends Error{};export class CommandExecutionError extends Error{};');
  let source=readFileSync(new URL('../examples/opencli/xyq-web/media-runtime.js',import.meta.url),'utf8');
  source=source.replace("'@jackwener/opencli/registry'",JSON.stringify(registry))
    .replace("'@jackwener/opencli/errors'",JSON.stringify(errors))
    .replace("'./core.mjs'",JSON.stringify(new URL('../examples/opencli/xyq-web/core.mjs',import.meta.url).href))
    .replace("'./media-runtime.mjs'",JSON.stringify(new URL('../examples/opencli/xyq-web/media-runtime.mjs',import.meta.url).href));
  try{
    await import(asModule(source));const commands=globalThis[registryKey];assert.equal(commands.length,20);
    const command=commands.find(x=>x.name==='generation-status');assert.equal(command.browser,false);
    const workspace=mkdtempSync(join(TMP,'atm-media-runtime-registration-'));
    await assert.rejects(command.func({pin:mediaRuntimeDigest(),workspace,key:'missing'},false),e=>JSON.parse(e.message).code==='request_missing');
    assert(!existsSync(join(workspace,'.atm')));
    await assert.rejects(command.func({pin:'0'.repeat(64),workspace,key:'missing'},false),e=>JSON.parse(e.message).code==='definition_changed');
  }finally{delete globalThis[registryKey];}
});
