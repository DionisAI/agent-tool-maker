import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,symlinkSync} from 'node:fs';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {readAssetDOM,readLocation} from '../examples/opencli/tripo-studio/extended.mjs';
import {deliveryDigest,checkDeliveryPin,readOperationReceipt,operationStatus} from '../examples/opencli/tripo-studio/delivery.mjs';
const SOURCE='11111111-2222-3333-4444-555555555555',OUTPUT='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const hash=s=>createHash('sha256').update(s).digest('hex');
function fixture(extra={},text=false){const ledger=mkdtempSync('/private/tmp/atm-tripo-delivery-'),dir=join(ledger,'.atm','tripo-studio-paid');mkdirSync(dir,{recursive:true});
  const file=join(dir,(text?'':'extended-')+hash('once')+'.json');writeFileSync(file,JSON.stringify({request_key:'once',fingerprint:'a'.repeat(64),operation:text?undefined:'workspace_texture',status:'submitted',asset_id:OUTPUT,source_asset_id:text?undefined:SOURCE,...extra}),{mode:0o600});
  return{ledger,key:'once',wait:0,file};}
test('delivery pin includes all reviewed dependencies',()=>{checkDeliveryPin(deliveryDigest());assert.throws(()=>checkDeliveryPin('0'.repeat(64)),e=>e.code==='definition_changed');});
test('Tripo model reader covers each observed post-processing route and processing signal',()=>{
  const paragraphs=[{innerText:'Faces',nextElementSibling:{innerText:'12'},getClientRects:()=>[1]},{innerText:'Vertices',nextElementSibling:{innerText:'8'},getClientRects:()=>[1]}];
  const main={innerText:'',querySelectorAll:s=>s==='p'?paragraphs:[{innerText:'Export',disabled:false,closest:()=>null}]};globalThis.document={querySelector:()=>main};
  for(const route of ['generate','retopology','rigging','segmentation','fill-parts','smart-uv','texture','texture-edit','texture-upscale','texture-pbr','animate']){
    globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/'+route+'/'+OUTPUT};assert.equal(readAssetDOM().status,'ready');
    paragraphs.push({innerText:'Enhancing...',getClientRects:()=>[1]});assert.equal(readAssetDOM().status,'generating');paragraphs.pop();}
  location.pathname='/workspace/generate-image/'+OUTPUT;assert.equal(readAssetDOM().kind,'pending');
});
test('status reads texture result in place without returning to the generation route',async()=>{
  const args=fixture(),before=readFileSync(args.file),calls=[];
  const page={evaluate:async fn=>{calls.push(fn.name);if(fn===readLocation)return{origin:'https://studio.tripo3d.ai',path:'/workspace/texture/'+OUTPUT};
    assert.equal(fn,readAssetDOM);return{kind:'ready',status:'ready',asset_id:OUTPUT,faces:12,vertices:8,export_enabled:true};},click:()=>assert.fail('navigation'),goto:()=>assert.fail('navigation')};
  const r=(await operationStatus(page,args))[0];assert.equal(r.status,'completed');assert.equal(r.operation,'workspace_texture');assert.equal(r.model_completed,true);assert.equal(r.paid_submitted,false);assert.deepEqual(readFileSync(args.file),before);
});
test('observed Generating Texture label outranks old ready mesh while unrelated sidebar processing is excluded',()=>{
  const paragraphs=[{innerText:'Faces',nextElementSibling:{innerText:'8468'},getClientRects:()=>[1]},{innerText:'Vertices',nextElementSibling:{innerText:'8399'},getClientRects:()=>[1]}];
  const progress={innerText:'Generating Texture...',getClientRects:()=>[1],closest:()=>null};
  const main={innerText:'',querySelectorAll:s=>s==='p'?paragraphs:[{innerText:'Export',disabled:false,closest:()=>null}]};
  globalThis.document={querySelector:()=>main};globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/texture/'+SOURCE};
  paragraphs.push(progress);assert.equal(readAssetDOM().status,'generating');assert.equal(readAssetDOM().processing,true);
  progress.closest=()=>({});assert.equal(readAssetDOM().status,'ready');
});
test('unknown receipt and source-only acknowledgement never report completed or use the provider',async()=>{
  for(const extra of [{status:'submission_unknown'},{status:'dispatch_claimed'},{asset_id:SOURCE}]){
    const args=fixture(extra);const r=(await operationStatus({evaluate:()=>assert.fail('provider')},args))[0];assert.equal(r.model_completed,false);assert.equal(r.provider_checked,false);assert.equal(r.lock_changed,false);assert.equal(r.submission_repeated,false);}
});
test('original text receipt and failed/pending model observations remain distinct',async()=>{
  for(const state of ['failed','generating','pending']){const args=fixture({},true),page={evaluate:async fn=>fn===readLocation?{origin:'https://studio.tripo3d.ai',path:'/workspace/generate/'+OUTPUT}:{kind:'ready',status:state,asset_id:OUTPUT,faces:null,vertices:null,export_enabled:false}};
    const r=(await operationStatus(page,args))[0];assert.equal(r.status,state==='failed'?'failed':'pending');assert.equal(r.operation,'generate');assert.equal(r.model_completed,false);}
});
test('linked, conflicting, malformed or different-key receipts stop before provider access',()=>{
  for(const extra of [{request_key:'different'},{operation:'upload'},{fingerprint:'invalid'},{asset_id:'token'}])assert.throws(()=>readOperationReceipt(fixture(extra)),e=>e.code==='receipt_invalid');
  const conflict=fixture();writeFileSync(join(conflict.ledger,'.atm','tripo-studio-paid',hash('once')+'.json'),'{}');assert.throws(()=>readOperationReceipt(conflict),e=>e.code==='request_conflict');
  const linked=fixture();symlinkSync(linked.file,join(linked.ledger,'.atm','tripo-studio-paid','extended-'+hash('linked')+'.json'));assert.throws(()=>readOperationReceipt({...linked,key:'linked'}),e=>e.code==='receipt_invalid');
  assert.throws(()=>readOperationReceipt({ledger:'/',key:'once'}),e=>e.code==='invalid_argument');assert.throws(()=>readOperationReceipt({...fixture(),key:'missing'}),e=>e.code==='request_missing');
});
