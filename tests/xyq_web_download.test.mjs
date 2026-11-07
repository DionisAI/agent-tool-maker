import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,readdirSync,statSync,existsSync,writeFileSync,linkSync,realpathSync,renameSync,symlinkSync,mkdirSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import fs from 'node:fs';
import {syncBuiltinESMExports} from 'node:module';
import {inspectConversationResults,RESULT_FILES} from '../examples/opencli/xyq-web/results.mjs';
import {DOWNLOAD_FILES,downloadDigest,checkDownloadPin,downloadSettings,verifiedDownloadEvent,downloadExistingResult,downloadBoundResult} from '../examples/opencli/xyq-web/download.mjs';
// Canonical temp root: macOS tmpdir() sits below the /var symlink, which path guards reject.
const TMP=realpathSync(tmpdir());
const scope={thread_id:'00000000-0000-0000-0000-000000000001',result_id:'b'.repeat(32)};
const src='https://p3-pippit-business-jianying-sign.byteimg.com/tos-cn-i-wipe09lpyt/'+scope.result_id+'~tplv-wipe09lpyt-resize-v1:1080:1080.image?FAKE_PRIVATE_SIGNATURE=secret';
const preview={result_id:scope.result_id,kind:'image',load_state:'loaded',width:81,height:108,resize_width:1080,resize_height:1080,surface:'artifact_preview',filename:'fixture.png',download_enabled:true,download_hit_verified:true};
async function fixture(){
  const workspace=mkdtempSync(join(TMP,'atm-xyq-download-')),root=mkdtempSync(join(TMP,'atm-xyq-root-')),state={kind:'ready',images:[],preview:structuredClone(preview)},calls=[];
  const page={evaluate:async(fn,arg)=>{calls.push(fn.name);if(fn.name==='readConversationResultsDOM')return structuredClone(state);if(fn.name==='readDownloadInputDOM')return {kind:'ready',x:7,y:8};assert.fail(fn.name);},
    nativeClick:async(x,y)=>{calls.push('nativeClick');assert.deepEqual([x,y],[7,8]);const d=join(workspace,'.atm','xyq-result-downloads');assert(existsSync(join(d,'active.lock')));const file=readdirSync(d).find(n=>n.endsWith('.json'));assert.equal(JSON.parse(readFileSync(join(d,file))).status,'download_dispatch_claimed');assert.equal(statSync(join(d,file)).mode&0o777,0o600);},
    waitForDownload:async(pattern,timeout)=>{calls.push('waitForDownload');assert.equal(pattern,'fixture.png');assert.equal(timeout,20000);return {downloaded:true,state:'complete',filename:'/private/tmp/fixture.png',url:src};},
    goto:()=>assert.fail('navigation'),getCookies:()=>assert.fail('auth')};
  const a=(await inspectConversationResults(page,scope,'result_inspect'))[0].result;
  const quote=(await inspectConversationResults(page,{...scope,expected_result_sha256:a.result_sha256},'result_download_quote'))[0].result;
  const settings={...scope,expected_result_sha256:a.result_sha256,quote_sha256:quote.quote_sha256,request_key:'one-download',human_confirmed:true};calls.length=0;
  return {workspace,root,state,page,calls,settings};
}
test('new download closure is independent of the three installed read pins',()=>{
  assert.deepEqual(DOWNLOAD_FILES,[...RESULT_FILES,'download.mjs','download.js']);checkDownloadPin(downloadDigest());
  for(const v of [null,[],[downloadDigest()],'0'.repeat(64)])assert.throws(()=>checkDownloadPin(v),e=>e.code==='definition_changed');
});
test('exact scope confirmation/schema rejects arbitrary input before browser creation',async()=>{
  const x=await fixture();for(const v of [null,[],{}, {...x.settings,url:'https://HOST'}, {...x.settings,request_key:'../key'}, {...x.settings,quote_sha256:'bad'}])assert.throws(()=>downloadSettings(v),e=>e.code==='invalid_argument');
  assert.throws(()=>downloadSettings({...x.settings,human_confirmed:false}),e=>e.code==='confirmation_required');
  assert.deepEqual(downloadSettings(Object.fromEntries(Object.entries(x.settings).reverse())),downloadSettings(x.settings));
  await assert.rejects(downloadBoundResult({},null,x.workspace,x.root,()=>assert.fail('factory')),e=>e.code==='invalid_argument');
});
test('one exact native download after durable intent, source URL stripped, no decoded-file claim',async()=>{
  const x=await fixture(),r=(await downloadExistingResult(x.page,x.settings,x.workspace,x.root))[0].result;
  assert.equal(r.status,'download_observed');assert.equal(r.file.source_result_id,scope.result_id);assert.equal(r.file.source_association_verified,true);assert.equal(r.file.download_freshness_verified,false);
  assert.equal(r.artifact_verified,false);assert.equal(r.complete_decode_verified,false);assert.equal(x.calls.filter(v=>v==='nativeClick').length,1);
  const dir=join(x.workspace,'.atm','xyq-result-downloads');assert(existsSync(join(dir,'active.lock')));
  for(const n of readdirSync(dir))assert(!readFileSync(join(dir,n),'utf8').includes('FAKE_PRIVATE'));
  const r2=(await downloadExistingResult({},Object.fromEntries(Object.entries(x.settings).reverse()),x.workspace,x.root))[0].result;
  assert.equal(r2.reused,true);assert.equal(x.calls.filter(v=>v==='nativeClick').length,1);
});
test('wrong quote, stale result, covered control and unknown protocol prevent first input',async()=>{
  for(const kind of ['quote','result','covered','protocol']){const x=await fixture();
    if(kind==='quote')x.settings.quote_sha256='0'.repeat(64);if(kind==='result')x.state.preview.width=80;
    if(kind==='covered')x.state.preview.download_hit_verified=false;
    if(kind==='protocol'){const old=x.page.evaluate;x.page.evaluate=(fn,arg)=>fn.name==='readDownloadInputDOM'?{kind:'FAKE_PRIVATE_TOKEN'}:old(fn,arg);}
    await assert.rejects(downloadExistingResult(x.page,x.settings,x.workspace,x.root));assert(!x.calls.includes('nativeClick'));assert(!existsSync(join(x.workspace,'.atm')));
  }
});
test('filename alone, blob URLs, wrong resource/origin and incomplete event never establish association',()=>{
  const good={downloaded:true,state:'complete',filename:'/private/tmp/fixture.png',url:src};
  for(const v of [{...good,url:undefined},{...good,url:'blob:https://xyq.jianying.com/ID'},{...good,url:src.replace(scope.result_id,'a'.repeat(32))},{...good,url:src.replace('p3-pippit','p9-pippit')}])assert.throws(()=>verifiedDownloadEvent(v,scope.result_id,'fixture.png'),e=>e.code==='download_source_unverified');
  for(const v of [{...good,filename:'/private/tmp/wrong.png'},{...good,state:'interrupted'},null,{...good,filename:'/private/tmp/../fixture.png'}])assert.throws(()=>verifiedDownloadEvent(v,scope.result_id,'fixture.png'),e=>e.code==='download_unknown');
  assert.equal(verifiedDownloadEvent({session:'fixture',data:good},scope.result_id,'fixture.png').source_result_id,scope.result_id);
});
test('public App download-event shape is accepted without exporting extra browser metadata',()=>{
  // Field shape observed through installed App 0.1.38 / CLI 1.8.6. The URL here
  // is the synthetic CDN fixture, not the real loopback probe or a provider call.
  const event={downloaded:true,id:150,filename:'/private/tmp/fixture.png',url:src,finalUrl:src,
    mime:'image/png',totalBytes:246,state:'complete',danger:'safe',elapsedMs:3948};
  assert.deepEqual(verifiedDownloadEvent(event,scope.result_id,'fixture.png'),{
    filename:'/private/tmp/fixture.png',state:'complete',source_result_id:scope.result_id,
    source_association_verified:true,download_freshness_verified:false});
  assert.throws(()=>verifiedDownloadEvent({...event,url:'http://127.0.0.1:58883/fixture.png'},scope.result_id,'fixture.png'),e=>e.code==='download_source_unverified');
});
test('lost click/observer/source acknowledgement holds original lock, same/new keys never replay',async()=>{
  for(const kind of ['click','observer','source']){
    const x=await fixture();if(kind==='click'){x.page.nativeClick=async()=>{x.calls.push('nativeClick');throw Error('FAKE_PRIVATE_TOKEN');};x.page.waitForDownload=async()=>({downloaded:false,state:'interrupted'});}
    if(kind==='observer')x.page.waitForDownload=async()=>{throw Error('FAKE_PRIVATE_TOKEN');};
    if(kind==='source')x.page.waitForDownload=async()=>({downloaded:true,state:'complete',filename:'/private/tmp/fixture.png',url:'blob:https://xyq.jianying.com/ID'});
    await assert.rejects(downloadExistingResult(x.page,x.settings,x.workspace,x.root),e=>e.code==='download_unknown'&&!e.message.includes('FAKE_PRIVATE'));
    const dir=join(x.workspace,'.atm','xyq-result-downloads'),lock=readFileSync(join(dir,'active.lock')),count=x.calls.filter(v=>v==='nativeClick').length;
    await assert.rejects(downloadExistingResult({},x.settings,x.workspace,x.root),e=>e.code==='download_unknown');
    await assert.rejects(downloadExistingResult({}, {...x.settings,request_key:'another'},x.workspace,x.root),e=>e.code==='workspace_busy');
    assert.equal(x.calls.filter(v=>v==='nativeClick').length,count);assert.deepEqual(readFileSync(join(dir,'active.lock')),lock);
    const r=JSON.parse(readFileSync(join(dir,readdirSync(dir).find(n=>n.endsWith('.json')))));assert.equal(r.status,'download_unknown');assert(!JSON.stringify(r).includes('FAKE_PRIVATE'));
  }
});
test('completed selected source event can reconcile lost native ack without a second click',async()=>{
  const x=await fixture();x.page.nativeClick=async()=>{x.calls.push('nativeClick');throw Error('FAKE_PRIVATE_TOKEN');};
  const r=(await downloadExistingResult(x.page,x.settings,x.workspace,x.root))[0].result;assert.equal(r.status,'download_observed');assert.equal(x.calls.filter(v=>v==='nativeClick').length,1);
  const dir=join(x.workspace,'.atm','xyq-result-downloads'),receipt=JSON.parse(readFileSync(join(dir,readdirSync(dir).find(n=>n.endsWith('.json')))));assert.equal(receipt.native_input_acknowledged,false);assert(!JSON.stringify(receipt).includes('FAKE_PRIVATE'));
});
test('post-intent control change is uncertain, zero native input, no automatic restart',async()=>{
  const x=await fixture(),old=x.page.evaluate;let n=0;x.page.evaluate=(fn,arg)=>fn.name==='readDownloadInputDOM'&&++n===2?{kind:'control_obscured'}:old(fn,arg);
  await assert.rejects(downloadExistingResult(x.page,x.settings,x.workspace,x.root),e=>e.code==='download_unknown');assert(!x.calls.includes('nativeClick'));assert(existsSync(join(x.workspace,'.atm','xyq-result-downloads','active.lock')));
});
test('changed key inputs and malformed/linked receipts never pass silently',async()=>{
  const x=await fixture();await downloadExistingResult(x.page,x.settings,x.workspace,x.root);
  await assert.rejects(downloadExistingResult({}, {...x.settings,quote_sha256:'0'.repeat(64)},x.workspace,x.root),e=>e.code==='request_conflict');
  const dir=join(x.workspace,'.atm','xyq-result-downloads'),file=join(dir,readdirSync(dir).find(n=>n.endsWith('.json')));
  const bytes=readFileSync(file);linkSync(file,join(dir,'linked-receipt'));
  await assert.rejects(downloadExistingResult({},x.settings,x.workspace,x.root),e=>e.code==='receipt_invalid');assert.deepEqual(readFileSync(file),bytes);
});
test('a same-name entry in the reviewed download directory is a definite refusal before intent or input',async()=>{
  // Chrome would save "fixture (1).png" (never this receipt's name) or replace the user's file.
  // Chrome's in-progress download reserving the name shows on disk as "<name>.crdownload".
  for(const kind of ['file','directory','dangling_link','crdownload']){
    const x=await fixture(),existing=join(x.root,kind==='crdownload'?'fixture.png.crdownload':'fixture.png');
    if(kind==='file'||kind==='crdownload')writeFileSync(existing,'USER_OWNED_FILE');if(kind==='directory')mkdirSync(existing);if(kind==='dangling_link')symlinkSync(join(x.root,'missing.png'),existing);
    const r=(await downloadExistingResult(x.page,x.settings,x.workspace,x.root))[0].result;
    assert.deepEqual(r,{status:'download_target_exists',thread_id:scope.thread_id,result_id:scope.result_id,request_key:'one-download',filename:'fixture.png',browser_input:false,intent_recorded:false});
    assert(!x.calls.includes('nativeClick')&&!x.calls.includes('waitForDownload'));assert(!existsSync(join(x.workspace,'.atm')));
    if(kind==='file'||kind==='crdownload')assert.equal(readFileSync(existing,'utf8'),'USER_OWNED_FILE');
    renameSync(existing,join(x.root,'moved-by-user'));
    const ok=(await downloadExistingResult(x.page,x.settings,x.workspace,x.root))[0].result;
    assert.equal(ok.status,'download_observed');assert.equal(ok.reused,false);assert.equal(x.calls.filter(v=>v==='nativeClick').length,1);
  }
});
test('Chrome finishing its in-progress download between the two name checks is still seen as taken',async()=>{
  // Chrome atomically renames "<name>.crdownload" to "<name>": checking the reservation first
  // means a rename right after any first check still leaves one of the two names visible.
  const x=await fixture(),partial=join(x.root,'fixture.png.crdownload'),final=join(x.root,'fixture.png'),lstat=fs.lstatSync;let renamed=false;
  writeFileSync(partial,'USER_OWNED_FILE');
  fs.lstatSync=(p,...rest)=>{const r=lstat(p,...rest);if(!renamed&&(p===partial||p===final)){renamed=true;renameSync(partial,final);}return r;};syncBuiltinESMExports();
  try{
    const r=(await downloadExistingResult(x.page,x.settings,x.workspace,x.root))[0].result;
    assert(renamed);assert.equal(r.status,'download_target_exists');assert.equal(r.intent_recorded,false);
    assert(!x.calls.includes('nativeClick')&&!x.calls.includes('waitForDownload'));assert(!existsSync(join(x.workspace,'.atm')));
    assert.equal(readFileSync(final,'utf8'),'USER_OWNED_FILE');assert(!existsSync(partial));
  }finally{fs.lstatSync=lstat;syncBuiltinESMExports();}
});
test('a same-name entry appearing after durable intent is recorded as definitely not sent, then the same key can retry',async()=>{
  for(const name of ['fixture.png','fixture.png.crdownload']){
    const x=await fixture(),old=x.page.evaluate,existing=join(x.root,name);let n=0;
    x.page.evaluate=(fn,arg)=>{if(fn.name==='readDownloadInputDOM'&&++n===2)writeFileSync(existing,'USER_OWNED_FILE');return old(fn,arg);};
    const r=(await downloadExistingResult(x.page,x.settings,x.workspace,x.root))[0].result;
    assert.deepEqual(r,{status:'download_target_exists',thread_id:scope.thread_id,result_id:scope.result_id,request_key:'one-download',filename:'fixture.png',browser_input:false,intent_recorded:true});
    assert(!x.calls.includes('nativeClick')&&!x.calls.includes('waitForDownload'));assert.equal(readFileSync(existing,'utf8'),'USER_OWNED_FILE');
    // The receipt keeps the unsent attempt; only the lock this call created is gone.
    const dir=join(x.workspace,'.atm','xyq-result-downloads'),file=join(dir,readdirSync(dir).find(n=>n.endsWith('.json'))),receipt=readFileSync(file);
    assert.deepEqual(readdirSync(dir),[file.split('/').pop()]);const v=JSON.parse(receipt);
    assert.equal(v.status,'download_not_sent');assert.equal(v.failure_code,'download_target_exists');assert(!('download' in v)&&!('native_input_acknowledged' in v));
    n=99;const again=(await downloadExistingResult(x.page,x.settings,x.workspace,x.root))[0].result;
    assert.equal(again.status,'download_target_exists');assert.equal(again.intent_recorded,false);assert.deepEqual(readFileSync(file),receipt);assert(!existsSync(join(dir,'active.lock')));
    renameSync(existing,join(x.root,'moved-by-user'));
    const ok=(await downloadExistingResult(x.page,x.settings,x.workspace,x.root))[0].result;
    assert.equal(ok.status,'download_observed');assert.equal(x.calls.filter(v=>v==='nativeClick').length,1);assert.equal(JSON.parse(readFileSync(file)).status,'download_observed');
    assert(existsSync(join(dir,'active.lock')));assert.equal(readFileSync(join(x.root,'moved-by-user'),'utf8'),'USER_OWNED_FILE');
  }
});
test('only a clean unsent receipt with no lock is retried; unknown or locked attempts never click again',async()=>{
  for(const kind of ['lock','unknown','acknowledged','failure']){
    const x=await fixture(),old=x.page.evaluate,existing=join(x.root,'fixture.png');let n=0;
    x.page.evaluate=(fn,arg)=>{if(fn.name==='readDownloadInputDOM'&&++n===2)writeFileSync(existing,'USER_OWNED_FILE');return old(fn,arg);};
    await downloadExistingResult(x.page,x.settings,x.workspace,x.root);renameSync(existing,join(x.root,'moved-by-user'));
    const dir=join(x.workspace,'.atm','xyq-result-downloads'),file=join(dir,readdirSync(dir).find(n=>n.endsWith('.json'))),v=JSON.parse(readFileSync(file));
    if(kind==='lock')writeFileSync(join(dir,'active.lock'),JSON.stringify({version:1,request_key:v.request_key,fingerprint:v.fingerprint}));
    if(kind==='unknown')v.status='download_unknown';if(kind==='acknowledged')v.native_input_acknowledged=false;if(kind==='failure')v.failure_code='result_changed';
    if(kind!=='lock')writeFileSync(file,JSON.stringify(v));const before=readFileSync(file);n=99;
    await assert.rejects(downloadExistingResult(x.page,x.settings,x.workspace,x.root),e=>e.code===(kind==='lock'?'workspace_busy':'download_unknown'));
    assert(!x.calls.includes('nativeClick'));assert.deepEqual(readFileSync(file),before);
  }
});
test('an unsent attempt never removes a lock it did not write',async()=>{
  const x=await fixture(),old=x.page.evaluate,dir=join(x.workspace,'.atm','xyq-result-downloads');let n=0;
  x.page.evaluate=(fn,arg)=>{if(fn.name==='readDownloadInputDOM'&&++n===2){writeFileSync(join(x.root,'fixture.png'),'USER_OWNED_FILE');writeFileSync(join(dir,'active.lock'),'{"other":true}');}return old(fn,arg);};
  await assert.rejects(downloadExistingResult(x.page,x.settings,x.workspace,x.root),e=>e.code==='download_unknown');
  assert(!x.calls.includes('nativeClick'));assert.equal(readFileSync(join(dir,'active.lock'),'utf8'),'{"other":true}');
  const file=join(dir,readdirSync(dir).find(n=>n.endsWith('.json')));assert.equal(JSON.parse(readFileSync(file)).status,'download_not_sent');
  renameSync(join(x.root,'fixture.png'),join(x.root,'moved-by-user'));n=99;
  await assert.rejects(downloadExistingResult(x.page,x.settings,x.workspace,x.root),e=>e.code==='workspace_busy');assert(!x.calls.includes('nativeClick'));
});
test('download root must be the exact canonical reviewed directory before any browser read',async()=>{
  const x=await fixture();
  for(const root of [undefined,'',3,'relative/downloads','/',x.root+'/',x.root+'/../'+x.root.split('/').pop(),x.root+'\n'])
    await assert.rejects(downloadExistingResult(x.page,x.settings,x.workspace,root),e=>e.code==='unsafe_path');
  assert.deepEqual(x.calls,[]);
  await assert.rejects(downloadBoundResult({},x.settings,x.workspace,'relative/downloads',()=>assert.fail('factory')),e=>e.code==='unsafe_path');
});
test('public factory keeps routing and sanitizes backend failures',async()=>{
  const x=await fixture();await downloadBoundResult({contextId:'fixture'},x.settings,x.workspace,x.root,async routing=>{assert.deepEqual(routing,{contextId:'fixture'});return x.page;});
  await assert.rejects(downloadBoundResult({},x.settings,x.workspace,x.root,()=>{throw Error('FAKE_PRIVATE');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
});
test('native write registration has no navigation/auth/paid generation or DOM mutations',()=>{
  const source=readFileSync(new URL('../examples/opencli/xyq-web/download.mjs',import.meta.url),'utf8');
  assert.match(source,/new Page\('site:xyq-home'/);assert.doesNotMatch(source,/localStorage|sessionStorage|document\.cookie|fetch\(|XMLHttpRequest|\.goto\(|\.cdp\(|setAttribute|dispatchEvent/);
  const loader=readFileSync(new URL('../examples/opencli/xyq-web/download.js',import.meta.url),'utf8');assert.match(loader,/access:'write'/);assert.match(loader,/navigateBefore:false/);
});
