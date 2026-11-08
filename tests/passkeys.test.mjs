import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../src/agent_tool_maker/data/web/passkeys.js',import.meta.url),'utf8');
const b64=bytes=>Buffer.from(bytes).toString('base64url');
const challenge=b64(Buffer.alloc(32,1)),id=b64(Buffer.alloc(32,2)),salt=b64(Buffer.alloc(32,3));
function runtime({prf=true,cancel=false,prfOutput=Buffer.alloc(32,4)}={}){
  const seen=[];
  const credential={id,rawId:Buffer.alloc(32,2),type:'public-key',response:{clientDataJSON:Buffer.from('{}'),attestationObject:Buffer.from('att'),authenticatorData:Buffer.from('auth'),signature:Buffer.from('sig'),userHandle:null},
    getClientExtensionResults:()=>({prf:prf?{enabled:true,results:{first:prfOutput}}:{enabled:false}})};
  const credentials={create:async options=>{seen.push(options);return credential;},get:async options=>{seen.push(options);if(cancel){const e=new Error('provider private diagnostic');e.name='NotAllowedError';throw e;}return credential;}};
  const context={window:{isSecureContext:true,PublicKeyCredential:function(){}},navigator:{credentials},location:{hostname:'localhost'},Uint8Array,structuredClone,btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary'),Error};
  vm.runInNewContext(source,context);
  const calls=[];const step={ceremony_id:'once',publicKey:{challenge,rpId:'localhost',allowCredentials:[{id,type:'public-key'}],extensions:{prf:{eval:{first:salt}}}}};
  const api=async(path,body)=>{calls.push({path,body});if(path.endsWith('/begin')&&path.includes('register'))return {ceremony_id:'create',publicKey:{challenge,user:{id},excludeCredentials:[{id,type:'public-key'}],extensions:{prf:{}}}};
    if(path.endsWith('/verify')||path.endsWith('/begin'))return step;
    return {status:'registered'};};
  return {helper:context.window.ATM_PASSKEY,api,calls,seen};
}
test('registration decodes buffers; sends recovery only at begin, PRF only at finish',async()=>{
  const r=runtime();assert.equal(r.helper.supported(),true);
  await r.helper.register(r.api,'fake-password','fixture');
  assert.deepEqual(r.calls.map(c=>c.path),['/api/passkeys/register/begin','/api/passkeys/register/verify','/api/passkeys/register/finish']);
  assert.equal(r.calls[0].body.passphrase,'fake-password');
  assert.ok(r.seen[0].publicKey.user.id instanceof Uint8Array);
  assert.ok(r.seen[1].publicKey.extensions.prf.eval.first instanceof Uint8Array);
  assert.equal(JSON.stringify(r.calls[1]).includes('prf_first'),false);
  assert.equal(r.calls[2].body.prf_first,b64(Buffer.alloc(32,4)));
  assert.equal(JSON.stringify(r.calls[2].body.credential.clientExtensionResults),'{}');
  assert.equal(JSON.stringify(r.calls.slice(1)).includes('fake-password'),false);
});
test('missing PRF prevents persistent finish; explicit server cancellation',async()=>{
  const r=runtime({prf:false});await assert.rejects(r.helper.register(r.api,'fake','fixture'),/passkey_prf_missing/);
  assert.deepEqual(r.calls.map(c=>c.path),['/api/passkeys/register/begin','/api/passkeys/cancel']);
});
test('authentication is proof only, never approval or lease extension',async()=>{
  const r=runtime();const proof=await r.helper.authenticate(r.api,'/api/desktop/passkey/begin',{consent:true},'/api/desktop/passkey/cancel');
  assert.equal(proof.ceremony_id,'once');assert.equal(r.calls.length,1);
});
test('cancel does not expose native provider diagnostics',async()=>{
  const r=runtime({cancel:true});await assert.rejects(r.helper.authenticate(r.api,'/api/passkeys/auth/begin',{},'/api/passkeys/cancel'),e=>/passkey_cancelled/.test(e.message)&&!e.message.includes('provider private'));
  assert.equal(r.calls.at(-1).path,'/api/passkeys/cancel');
});
test('missing PRF in assertion sends no finish',async()=>{
  const r=runtime({prf:false});await assert.rejects(r.helper.authenticate(r.api,'/api/passkeys/auth/begin',{},'/api/passkeys/cancel'),/passkey_prf_missing/);
  assert.equal(r.calls.at(-1).path,'/api/passkeys/cancel');
});
test('failed cleanup is visible rather than swallowed',async()=>{
  const r=runtime({cancel:true});const api=(path,body)=>path.endsWith('cancel')?Promise.reject(new Error('private')):r.api(path,body);
  await assert.rejects(r.helper.authenticate(api,'/api/passkeys/auth/begin',{},'/api/passkeys/cancel'),/passkey_cancel_cleanup_failed/);
});

const expectedPrf=Uint8Array.from({length:32},(_,i)=>i);
const backing=new Uint8Array(40);backing.fill(255);backing.set(expectedPrf,4);
for(const [name,prfOutput] of [
  ['ArrayBuffer',expectedPrf.buffer],
  ['Uint8Array with byte offset',new Uint8Array(backing.buffer,4,32)],
  ['DataView with byte offset',new DataView(backing.buffer,4,32)],
  ['Uint16Array bytes, not element coercion',new Uint16Array(backing.buffer,4,16)],
  ['1Password plain byte Array',Array.from(expectedPrf)],
  ['cross-realm byte Array',vm.runInNewContext('Array.from({length:32},(_,i)=>i)')],
]) test('registration and authentication preserve PRF bytes: '+name,async()=>{
  const r=runtime({prfOutput});await r.helper.register(r.api,'fake','fixture');
  assert.equal(r.calls.at(-1).path,'/api/passkeys/register/finish');
  assert.equal(r.calls.at(-1).body.prf_first,b64(expectedPrf));
  const proof=await r.helper.authenticate(r.api,'/api/passkeys/auth/begin',{},'/api/passkeys/cancel');
  assert.equal(proof.prf_first,b64(expectedPrf));
  assert.equal(JSON.stringify(r.calls).includes('results'),false);
});

for(const [name,prfOutput] of [
  ['short Array',Array(31).fill(4)],['long Array',Array(33).fill(4)],
  ['negative byte',[...Array(31).fill(4),-1]],['overflow byte',[...Array(31).fill(4),256]],
  ['fractional byte',[...Array(31).fill(4),1.5]],['string byte',[...Array(31).fill(4),'4']],
  ['NaN byte',[...Array(31).fill(4),NaN]],['sparse Array',Array(32)],
  ['object with claimed byteLength',{byteLength:32,length:32}],
  ['short ArrayBuffer',new ArrayBuffer(31)],['long view',new Uint8Array(33)],
]) test('malformed PRF fails before submission: '+name,async()=>{
  const r=runtime({prfOutput});
  await assert.rejects(r.helper.authenticate(r.api,'/api/passkeys/auth/begin',{},'/api/passkeys/cancel'),/passkey_prf_invalid/);
  assert.deepEqual(r.calls.map(c=>c.path),['/api/passkeys/auth/begin','/api/passkeys/cancel']);
});
