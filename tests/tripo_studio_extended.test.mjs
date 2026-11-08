import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, readdirSync, existsSync, symlinkSync, realpathSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';

test('completed Quad and triangle models expose single and current/total counts respectively',()=>{
  for(const faces of ['10368','11550 / 11550']){
    const paragraphs=[['Faces',faces],['Vertices','9511']].map(([label,value])=>({innerText:label,nextElementSibling:{innerText:value},getClientRects:()=>[1]}));
    const main={innerText:'Topology Quad',querySelectorAll:selector=>selector==='p'?paragraphs:selector==='button'?[{innerText:'Export',disabled:false,closest:()=>null}]:[]};
    globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate/11111111-2222-3333-4444-555555555555'};
    globalThis.document={querySelector:()=>main};
    const data=readAssetDOM();assert.equal(data.status,'ready');assert.equal(data.faces,Number(faces.split('/')[0]));assert.equal(data.vertices,9511);
    for(const malformed of ['unknown','10k','1.5','99999999999999999999999']){paragraphs[0].nextElementSibling.innerText=malformed;assert.equal(readAssetDOM().status,'pending');}
  }
});
import { assetId, parseSettings, quoteHash, extendedDigest, checkExtendedPin, readLocation, readRouteLinkDOM, readAssetEntryLinkDOM,
  readAssetDOM, readPanelDOM, readSubmissionDOM, readExportDOM, readCollectionDOM, readVisibleErrorDOM, findTextDOM, PANEL, EXPORT_DIALOG,
  inspectAsset, operationQuote, executePaid, inspectImageFile, imageQuote, generateImage, validateGLB,
  exportModel, exportQuote, assetsAll, claimedOperation, validateExecution, resolveAsset, readPreviewTargetDOM, readPreviewDialogDOM,
} from '../examples/opencli/tripo-studio/extended.mjs';
import { readAccountDOM } from '../examples/opencli/tripo-studio/core.mjs';
// Canonical temp root: macOS tmpdir() sits below the /var symlink, which path guards reject.
const TMP = realpathSync(tmpdir());

const ID = '11111111-2222-3333-4444-555555555555';
const OTHER = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const FORM = { kind:'ready', operation:'retopo', asset_id:ID, price:40, credits:100, button_enabled:true, blocked:false,
  settings:{topology:'Quad', polygon_count:10000, smart_mesh:true,ui_min:500,ui_max:10000},image:null };
const IMAGE = { ...FORM, operation:'image',asset_id:null,settings:{privacy:'Private',model:'H3.1',switches:['false','false']},image:{files:[],previews:[]} };
const EXPORT = { ...FORM,operation:'export',price:0,settings:{format:'GLB',texture_resolution:'4k Current'},filename:'fixture',image:null };
const hash = value => createHash('sha256').update(value).digest('hex');
const temp = () => mkdtempSync(join(TMP, 'atm-tripo-ext-'));
function args(extra = {}) { return { operation:'retopo',asset:ID,quote:quoteHash(FORM),budget:40,key:'fixture-once',confirm:true,ledger:temp(), ...extra }; }
function fixturePage(a, { form=FORM, clickFailure=false, onClick=null } = {}) {
  const calls = []; const data = structuredClone(form);
  let path = '/workspace/' + (data.operation === 'retopo' ? 'retopology/' : data.operation === 'rig' ? 'rigging/' : data.operation === 'image' ? '' : 'generate/') + (data.operation === 'image' ? 'generate' : ID);
  return { calls,data,
    evaluate:async (fn,...values) => {
      if (fn === readLocation) return {origin:'https://studio.tripo3d.ai',path};
      if (fn === readRouteLinkDOM) return {href:'/workspace/'+values[1]+'/'+values[0]};
      if (fn === readAssetDOM) return {kind:'ready',status:'ready',asset_id:ID,faces:12,vertices:8,export_enabled:true};
      if (fn === readPanelDOM) return structuredClone(data);
      if (fn === findTextDOM) return {count:1,nth:0};
      if (fn === readSubmissionDOM) return {kind:'ready',asset_id:OTHER,acceptance:'new_asset_route_observed_not_model_completion'};
      if (fn === readExportDOM) return structuredClone(data);
      assert.fail('Unexpected reader');
    },
    goto:async url => {calls.push('goto');path=new URL(url).pathname;},
    click:async selector => {
      calls.push('click:'+selector);
      if (selector === PANEL+' button.animate-button' || selector === EXPORT_DIALOG+' button.animate-button') {
        const dir=join(a.ledger,'.atm/tripo-studio-paid');
        const receipts=readdirSync(dir).filter(name=>name.endsWith('.json'));
        assert.equal(receipts.length,1);
        assert.equal(JSON.parse(readFileSync(join(dir,receipts[0]))).status,'dispatch_claimed');
        if (clickFailure) throw new Error('fixture disconnect');
        await onClick?.(selector);
      }
    },
    fillText:async (selector,text) => {calls.push('fill');if(selector.includes('maxlength'))data.filename=text;else data.settings.polygon_count=Number(text);},
    pressKey:async key => calls.push('key:'+key),
    setChecked:async (_,checked) => {calls.push('toggle');data.settings.smart_mesh=checked;},
  };
}
function glb() {
  const text=JSON.stringify({asset:{version:'2.0'},meshes:[{primitives:[{attributes:{}}]}]});
  const json=Buffer.from(text.padEnd(Math.ceil(text.length/4)*4,' '));
  const bytes=Buffer.alloc(20+json.length);bytes.write('glTF');bytes.writeUInt32LE(2,4);bytes.writeUInt32LE(bytes.length,8);
  bytes.writeUInt32LE(json.length,12);bytes.writeUInt32LE(0x4e4f534a,16);json.copy(bytes,20);return bytes;
}
function raster(directory) { const path=join(directory,'fixture.png');writeFileSync(path,Buffer.from([137,80,78,71,13,10,26,10,0,0,0,0]));return path; }

test('required extended source pin covers reviewed code',()=>{checkExtendedPin(extendedDigest());assert.throws(()=>checkExtendedPin(''));assert.throws(()=>checkExtendedPin('0'.repeat(64)));});
test('strict UUID and curated settings reject selectors, floats and unknown presets',()=>{
  assert.equal(assetId(ID),ID);for(const id of ['../bad','https://site',ID+'?TOKEN'])assert.throws(()=>assetId(id));
  for(const [op,settings] of [['retopo',{selector:'button'}],['retopo',{polygon_count:500.1}],['retopo',{smart_mesh:'true'}],['rig',{skeleton:'Other'}],['rig',{rigging_type:'anything'}]])assert.throws(()=>parseSettings(op,settings));
  assert.deepEqual(parseSettings('rig','{"skeleton":"UE5 Mannequin"}'),{skeleton:'UE5 Mannequin'});
});
test('budget, confirmation and project bounds are mandatory before browser work',()=>{
  for(const change of [{confirm:false},{budget:true},{budget:0},{budget:1.5},{quote:''},{key:'../x'},{ledger:'/'}])assert.throws(()=>validateExecution(args(change)));
});
test('quote fingerprint binds operation, asset and every setting but not balance',()=>{
  assert.equal(quoteHash(FORM),quoteHash({...FORM,credits:0}));
  for(const change of [{operation:'rig'},{asset_id:OTHER},{price:41},{settings:{...FORM.settings,smart_mesh:false}}])assert.notEqual(quoteHash(FORM),quoteHash({...FORM,...change}));
});
test('asset status returns observed model gate, not generation route alone',async()=>{
  const a=args();const p=fixturePage(a,{form:{...FORM,operation:'export'}});
  const result=(await inspectAsset(p,{asset:ID,wait:0}))[0];assert.equal(result.model_completed,true);assert.equal(result.faces,12);assert.deepEqual(p.calls,[]);
});
test('asset entry uses observed SPA links instead of cold UUID routes',async()=>{
  let path='/assets';const calls=[];
  const p={goto:()=>assert.fail('No cold UUID navigation'),click:async selector=>{
    calls.push(selector);path=selector.includes('"/workspace/generate"')?'/workspace/generate':'/workspace/generate/'+ID;
  },evaluate:async fn=>{
    if(fn===readLocation)return {origin:'https://studio.tripo3d.ai',path};
    if(fn===readAssetEntryLinkDOM)return {kind:'ready',href:'/workspace/generate/'+ID};
    if(fn===readAssetDOM)return {kind:'ready',asset_id:ID,status:'ready',faces:12,vertices:8,export_enabled:true};
    assert.fail('Unexpected reader');
  }};
  assert.equal((await inspectAsset(p,{asset:ID,wait:0}))[0].model_completed,true);
  assert.deepEqual(calls,['a[href="/workspace/generate"]','[role="tabpanel"] a[href="/workspace/generate/'+ID+'"]']);
});
test('an existing UUID error route recovers through Workspace, not a reload',async()=>{
  let path='/workspace/generate/'+ID,broken=true;const calls=[];
  const p={goto:()=>assert.fail('No reload'),click:async selector=>{
    calls.push(selector);broken=false;path=selector.includes('"/workspace/generate"')?'/workspace/generate':'/workspace/generate/'+ID;
  },evaluate:async fn=>{
    if(fn===readLocation)return {origin:'https://studio.tripo3d.ai',path};
    if(fn===readAssetEntryLinkDOM)return {kind:'ready',href:'/workspace/generate/'+ID};
    if(fn===readAssetDOM)return broken?{kind:'site_error'}:{kind:'ready',asset_id:ID,status:'ready',faces:12,vertices:8,export_enabled:true};
    assert.fail('Unexpected reader');
  }};
  assert.equal((await inspectAsset(p,{asset:ID,wait:0}))[0].model_completed,true);
  assert.equal(calls[0],'a[href="/workspace/generate"]');assert.equal(calls.length,2);
});
test('new Workspace sidebar waits for its requested card without repeating navigation',async()=>{
  let path='/workspace/animate/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',reads=0;const calls=[];
  const p={goto:()=>assert.fail('No reload'),click:async selector=>{
    calls.push(selector);path=selector.includes('"/workspace/generate"')?'/workspace/generate':'/workspace/generate/'+ID;
  },evaluate:async fn=>{
    if(fn===readLocation)return{origin:'https://studio.tripo3d.ai',path};
    if(fn===readAssetEntryLinkDOM)return ++reads===1?{kind:'asset_not_in_workspace',href:null}:{kind:'ready',href:'/workspace/generate/'+ID};
    if(fn===readAssetDOM)return{kind:'ready',asset_id:path.endsWith(ID)?ID:'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',status:'ready',faces:12,vertices:8,export_enabled:true};
    assert.fail('Unexpected reader');
  }};
  assert.equal((await inspectAsset(p,{asset:ID,wait:0}))[0].model_completed,true);
  assert.equal(reads,2);assert.equal(calls.length,2);assert.equal(calls.filter(s=>s==='a[href="/workspace/generate"]').length,1);
});
test('asset switch waits for only the known prior SPA source and rejects a third source',async()=>{
  const previous='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',third='bbbbbbbb-cccc-dddd-eeee-ffffffffffff';
  async function run(drift){let path='/workspace/generate/'+previous,reads=0,clicked=false;const calls=[];
    const p={click:async selector=>{calls.push(selector);clicked=true;},evaluate:async fn=>{
      if(fn===readLocation)return{origin:'https://studio.tripo3d.ai',path};
      if(fn===readAssetEntryLinkDOM)return{kind:'ready',href:'/workspace/generate/'+ID};
      if(fn===readAssetDOM){const current=clicked&&++reads>1?ID:drift&&clicked?third:previous;if(current===ID)path='/workspace/generate/'+ID;
        return{kind:'ready',asset_id:current,status:'ready',faces:12,vertices:8,export_enabled:true};}
      assert.fail('Unexpected reader');
    }};
    const result=inspectAsset(p,{asset:ID,wait:0});
    if(drift)await assert.rejects(result,e=>e.code==='asset_mismatch');else assert.equal((await result)[0].asset_id,ID);
    assert.equal(calls.length,1);
  }
  await run(false);await run(true);
});
test('quote has no paid click and reports current mesh settings',async()=>{
  const a=args();const p=fixturePage(a);const result=(await operationQuote(p,{operation:'retopo',asset:ID,settings:'{}'}))[0];
  assert.equal(result.quote_sha256,a.quote);assert.equal(result.quoted_credits,40);assert.deepEqual(p.calls,[]);
});
test('quote can apply bounded polygon count then verify UI without submitting',async()=>{
  const a=args();const p=fixturePage(a);const result=(await operationQuote(p,{operation:'retopo',asset:ID,settings:'{"polygon_count":500}'}))[0];
  assert.equal(result.settings.polygon_count,500);assert.deepEqual(p.calls,['fill','key:Tab']);
  await assert.rejects(operationQuote(p,{operation:'retopo',asset:ID,settings:'{"polygon_count":20000}'}),e=>e.code==='invalid_argument');
});
test('paid confirmation prevents all UI work',async()=>{
  const a=args({confirm:false});const p=fixturePage(a);await assert.rejects(executePaid(p,a),e=>e.code==='confirmation_required');assert.deepEqual(p.calls,[]);
});
test('price, asset, settings, prerequisites and balance fail before paid click',async()=>{
  for(const change of [{price:41},{asset_id:OTHER},{settings:{...FORM.settings,topology:'Triangle'}},{button_enabled:false},{blocked:true},{credits:10}]){
    const a=args();const p=fixturePage(a,{form:{...FORM,...change}});await assert.rejects(executePaid(p,a));assert.deepEqual(p.calls,[]);
  }
});
test('retopo and rig claim before one click, then reuse before all browser work',async()=>{
  for(const form of [FORM,{...FORM,operation:'rig',price:20,settings:{rigging_type:'Humanoid',skeleton:'UE5 Mannequin',warning:null}}]){
    const a=args({operation:form.operation,budget:form.price,quote:quoteHash(form)});const p=fixturePage(a,{form});
    const result=(await executePaid(p,a))[0];assert.equal(result.status,'submitted');assert.equal(result.paid_submitted,true);assert.match(result.acceptance,/not_model_completion/);
    p.calls.length=0;assert.equal((await executePaid(p,a))[0].reused,true);assert.deepEqual(p.calls,[]);
    await assert.rejects(executePaid(p,{...a,budget:a.budget+1}),e=>e.code==='request_conflict');
  }
});
test('unknown paid click blocks both same and new keys through shared active lock',async()=>{
  const a=args();const p=fixturePage(a,{clickFailure:true});await assert.rejects(executePaid(p,a),e=>e.code==='submission_unknown');
  assert.ok(existsSync(join(a.ledger,'.atm/tripo-studio-paid/active.lock')));p.calls.length=0;
  await assert.rejects(executePaid(p,a),e=>e.code==='submission_unknown');await assert.rejects(executePaid(p,{...a,key:'new-key'}),e=>e.code==='workspace_busy');assert.deepEqual(p.calls,[]);
});
test('ledger symlink rejected before UI; original text-generation active lock also blocks extensions',async()=>{
  const root=temp(),target=temp();const link=join(root,'linked');symlinkSync(target,link);const a=args({ledger:link});const p=fixturePage(a);
  await assert.rejects(executePaid(p,a),e=>e.code==='unsafe_path');assert.deepEqual(p.calls,[]);
  const b=args();const dir=join(b.ledger,'.atm');const {mkdirSync}=await import('node:fs');mkdirSync(join(dir,'tripo-studio-paid'),{recursive:true});writeFileSync(join(dir,'tripo-studio-paid/active.lock'),'original fixture lock');
  await assert.rejects(executePaid(fixturePage(b),b),e=>e.code==='workspace_busy');
});
test('corrupt retained receipt fails, never resubmits',async()=>{
  const a=args();await claimedOperation(a,'fixture-hash',async claim=>{await claim('fixture');return {status:'submitted'};});
  const dir=join(a.ledger,'.atm/tripo-studio-paid');const name=readdirSync(dir).find(n=>n.endsWith('.json'));writeFileSync(join(dir,name),'bad JSON');
  await assert.rejects(claimedOperation(a,'fixture-hash',()=>assert.fail('no execution')),e=>e.code==='receipt_invalid');
});
test('image validation is explicit, bounded, project-confined and rejects symlinks',()=>{
  const root=temp(),file=raster(root);assert.equal(inspectImageFile(file,root).size,12);
  const link=join(root,'link.png');symlinkSync(file,link);assert.throws(()=>inspectImageFile(link,root));assert.throws(()=>inspectImageFile(file,temp()));
  const html=join(root,'bad.png');writeFileSync(html,'<html>not image</html>');assert.throws(()=>inspectImageFile(html,root));
});
test('image upload quote requires consent before local UI mutation',async()=>{
  const root=temp();const a=args({ledger:root,file:raster(root),confirm:false});const p=fixturePage(a,{form:IMAGE});await assert.rejects(imageQuote(p,a),e=>e.code==='confirmation_required');assert.deepEqual(p.calls,[]);
});
test('upload quote claims before only upload; no generation; reuses image quote',async()=>{
  const root=temp();const a=args({ledger:root,file:raster(root)});const p=fixturePage(a,{form:IMAGE});
  p.cdp=async(method,params)=>{
    if(method==='DOM.getDocument')return {root:{nodeId:1}};
    if(method==='DOM.querySelector'){assert.equal(params.selector,PANEL+' input[type="file"]');return {nodeId:2};}
    assert.equal(method,'DOM.setFileInputFiles');assert.equal(params.nodeId,2);assert.deepEqual(params.files,[a.file]);
    const dir=join(root,'.atm/tripo-studio-paid');const receipt=readdirSync(dir).find(n=>n.endsWith('.json'));assert.equal(JSON.parse(readFileSync(join(dir,receipt))).stage,'image_upload');p.calls.push('upload');p.data.image={files:[{name:'fixture.png',size:12,last_modified:1}],previews:['blob-preview']};
  };
  const result=(await imageQuote(p,a))[0];assert.equal(result.paid_submitted,false);assert.equal(result.image_sha256,hash(readFileSync(a.file)));assert.deepEqual(p.calls,['upload']);
  p.calls.length=0;assert.equal((await imageQuote(p,a))[0].reused,true);assert.deepEqual(p.calls,[]);
});
test('uncertain image bridge failure retains typed diagnostics, lock and no-retry boundary',async()=>{
  const root=temp();const a=args({ledger:root,file:raster(root)});const p=fixturePage(a,{form:IMAGE});
  p.cdp=async method=>{if(method==='DOM.getDocument')return {root:{nodeId:1}};if(method==='DOM.querySelector')return {nodeId:2};const error=new Error('https://fixture/?TOKEN=FAKE');error.name='TargetError';error.code='not_file_input';throw error;};
  await assert.rejects(imageQuote(p,a),e=>e.code==='submission_unknown'&&/TargetError\/not_file_input/.test(e.message));
  const directory=join(root,'.atm/tripo-studio-paid');const name=readdirSync(directory).find(n=>n.endsWith('.json'));
  const receipt=JSON.parse(readFileSync(join(directory,name)));assert.equal(receipt.failure_type,'TargetError');assert.equal(receipt.bridge_error_code,'not_file_input');
  assert.doesNotMatch(JSON.stringify(receipt),/TOKEN|FAKE/);assert.ok(existsSync(join(directory,'active.lock')));
  p.calls.length=0;await assert.rejects(imageQuote(p,a),e=>e.code==='submission_unknown');
  await assert.rejects(imageQuote(p,{...a,key:'different-key'}),e=>e.code==='workspace_busy');assert.deepEqual(p.calls,[]);
});
test('image DOM/CDP preflight failure happens before file attachment or durable claim',async()=>{
  for(const response of [{},{root:{nodeId:1}}]){
    const root=temp();const a=args({ledger:root,file:raster(root)});const p=fixturePage(a,{form:IMAGE});
    p.cdp=async method=>{assert.notEqual(method,'DOM.setFileInputFiles');return method==='DOM.getDocument'?response:{nodeId:0};};
    await assert.rejects(imageQuote(p,a));const directory=join(root,'.atm/tripo-studio-paid');
    assert.equal(readdirSync(directory).filter(n=>n.endsWith('.json')).length,0);assert.equal(existsSync(join(directory,'active.lock')),false);
  }
});
test('existing image draft/private setting preserved without upload',async()=>{
  for(const change of [{image:{files:[],previews:['existing-preview']}},{settings:{...IMAGE.settings,privacy:'Sharing Only'}}]){
    const root=temp();const a=args({ledger:root,file:raster(root)});const p=fixturePage(a,{form:{...IMAGE,...change}});p.uploadFiles=()=>assert.fail('No upload');await assert.rejects(imageQuote(p,a));assert.deepEqual(p.calls,[]);
  }
});
test('image-generation binds approved preview/settings/hash and never reuploads',async()=>{
  const form={...IMAGE,image:{files:[{name:'fixture.png',size:12,last_modified:1}],previews:['blob-preview']}};
  const a=args({operation:'image_generate',image_sha:'1'.repeat(64),quote:quoteHash(form,'1'.repeat(64))});const p=fixturePage(a,{form});
  assert.equal((await generateImage(p,a))[0].status,'submitted');assert.deepEqual(p.calls,['click:'+PANEL+' button.animate-button']);
  const b=args({image_sha:'2'.repeat(64),quote:a.quote});await assert.rejects(generateImage(fixturePage(b,{form}),b),e=>e.code==='quote_changed');
});
test('GLB checks magic, length, JSON and at least one mesh primitive',()=>{
  assert.equal(validateGLB(glb()).mesh_count,1);assert.throws(()=>validateGLB(Buffer.from('<html>bad</html>')));
  const length=glb();length.writeUInt32LE(1,8);assert.throws(()=>validateGLB(length));
  const empty=glb();empty.write('nope',20);assert.throws(()=>validateGLB(empty));
});
test('export quote stops at dialog, without download',async()=>{
  const a=args({operation:'export',quote:quoteHash(EXPORT)});const p=fixturePage(a,{form:EXPORT});assert.equal((await exportQuote(p,{asset:ID}))[0].quoted_credits,0);assert.deepEqual(p.calls,[]);
});
test('export watcher precedes only click; file validated and identical key reuses without UI',async()=>{
  const a=args({operation:'export',quote:quoteHash(EXPORT),output:join(temp(),'unused.glb')});a.output=join(a.ledger,'model.glb');const p=fixturePage(a,{form:EXPORT});
  const filename='atm-tripo-'+ID+'-'+hash(a.key).slice(0,10);const source=join(a.ledger,filename+'.glb');writeFileSync(source,glb());
  p.waitForDownload=async pattern=>{assert.equal(pattern,filename);p.calls.push('watch');return {downloaded:true,state:'complete',filename:source,url:'https://host/?TOKEN=FAKE'};};
  const result=(await exportModel(p,a))[0];assert.equal(result.status,'exported');assert.equal(result.artifact.mesh_count,1);assert.ok(existsSync(a.output));assert.doesNotMatch(JSON.stringify(result),/FAKE|TOKEN/);
  assert.deepEqual(p.calls,['fill','watch','click:'+EXPORT_DIALOG+' button.animate-button']);p.calls.length=0;
  assert.equal((await exportModel(p,a))[0].reused,true);assert.deepEqual(p.calls,[]);
});
test('export dialog fails on any newly shown credit price instead of reading it as free',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate/'+ID};
  const button={innerText:'Export',disabled:false,getAttribute:()=>null};
  let text='Export\nGLB\n4k Current\nExport Skeleton\nExport',icon=null;
  const dialog={get innerText(){return text;},querySelector:s=>s==='button.animate-button'?button:s==='input[maxlength="255"]'?{value:'fixture'}:s.includes('bolt')?icon:null,
    querySelectorAll:s=>s==='[role="combobox"]'?[{innerText:'GLB'},{innerText:'4k\nCurrent'}]:s==='button.animate-button'?[button]:[]};
  globalThis.document={querySelectorAll:()=>[dialog]};
  const free=readExportDOM();assert.equal(free.kind,'ready');assert.equal(free.price,0);
  for(const priced of ['Export\nGLB\nCosts 10 credits\nExport','Export\nGLB\n消耗 10 积分\nExport','Export\nGLB\nFree 3/10\nExport','Export\nGLB\n$1.99\nExport']){
    text=priced;assert.equal(readExportDOM().kind,'export_price_changed');
  }
  text='Export\nGLB\n4k Current\nExport';icon={};assert.equal(readExportDOM().kind,'export_price_changed');
  icon=null;button.innerText='Export\n10';assert.equal(readExportDOM().kind,'export_price_changed');
});
test('export format drift and pre-existing output stop before download',async()=>{
  const a=args({operation:'export',quote:quoteHash(EXPORT)});a.output=join(a.ledger,'model.glb');
  const p=fixturePage(a,{form:{...EXPORT,settings:{format:'FBX',texture_resolution:'4k Current'}}});await assert.rejects(exportModel(p,a),e=>e.code==='format_changed');assert.deepEqual(p.calls,[]);
  writeFileSync(a.output,'keep');await assert.rejects(exportModel(p,a),e=>e.code==='unsafe_path');assert.equal(readFileSync(a.output,'utf8'),'keep');
});
test('incomplete or unrelated download remains unknown, retaining lock',async()=>{
  const a=args({operation:'export',quote:quoteHash(EXPORT)});a.output=join(a.ledger,'model.glb');const p=fixturePage(a,{form:EXPORT});
  p.waitForDownload=async()=>({downloaded:true,state:'in_progress',filename:'/private/tmp/unrelated.glb'});
  await assert.rejects(exportModel(p,a),e=>e.code==='submission_unknown');assert.ok(existsSync(join(a.ledger,'.atm/tripo-studio-paid/active.lock')));assert.equal(existsSync(a.output),false);
});
test('pagination accumulates duplicates safely; quiet scroll footer is partial not full',async()=>{
  const calls=[];let page=0;const p={goto:async()=>calls.push('goto'),scrollTo:async selector=>{assert.equal(selector,'main div.min-h-10');page++;},click:async()=>calls.push('filter'),evaluate:async fn=>{
    if(fn===readAccountDOM)return {kind:'ready',credits:100};if(fn===findTextDOM)return {count:1,nth:0};
    if(fn===readLocation)return {origin:'https://studio.tripo3d.ai',path:'/assets'};if(fn===readVisibleErrorDOM)return {site_error:false};
    if(fn===readCollectionDOM)return {kind:'ready',items:page?[{preview_task_id:ID},{preview_task_id:OTHER}]:[{preview_task_id:ID}],rendered_cards:page?2:1,scope_verified:true,at_end:true,loading:false,explicit_end:false};assert.fail('Unknown reader');}};
  const result=(await assetsAll(p,{limit:1000,pages:10},{quietMs:0}))[0];assert.equal(result.returned_count,2);assert.equal(result.all_assets,false);assert.equal(result.status,'partial');assert.match(result.stop_reason,/no_authoritative_total/);
  assert.deepEqual(result.scope,{asset_type:'Model',ownership:'My Assets',filter:'All'});
  assert.equal(result.site_wide_coverage,false);assert.equal(result.authoritative_total,null);
  assert.deepEqual(result.coverage_evidence,{scope_verified:true,rendered_cards:2,at_scroll_end:true,loading:false,explicit_ui_end:false});
});
test('pagination reports full only with explicit end, and reports requested limits separately',async()=>{
  const p={goto:async()=>{},scrollTo:async()=>{},click:async()=>{},evaluate:async fn=>fn===readAccountDOM?{kind:'ready'}:fn===readLocation?{origin:'https://studio.tripo3d.ai',path:'/assets'}:fn===readVisibleErrorDOM?{site_error:false}:fn===findTextDOM?{count:1,nth:0}:{kind:'ready',items:[{preview_task_id:ID}],at_end:true,loading:false,explicit_end:true}};
  assert.equal((await assetsAll(p,{limit:1000,pages:10}))[0].all_assets,true);
  const limited=(await assetsAll(p,{limit:1,pages:10}))[0];assert.equal(limited.all_assets,false);assert.equal(limited.stop_reason,'item_limit');
});
test('assets use visible SPA entry and wait for a mounting filter before its only click',async()=>{
  for(const broken of [false,true]){
    const clicks=[];let target='',modelReads=0;
    const p={goto:()=>assert.fail('No cold assets navigation'),click:async()=>clicks.push(target),evaluate:async(fn,...values)=>{
      if(fn===readLocation)return {origin:'https://studio.tripo3d.ai',path:'/workspace/generate/'+ID};
      if(fn===readVisibleErrorDOM)return {site_error:broken};
      if(fn===readAccountDOM)return {kind:'ready',credits:100};
      if(fn===findTextDOM){target=values[1];return {count:target==='Model'&&modelReads++===0?0:1,nth:0};}
      if(fn===readCollectionDOM)return {kind:'ready',items:[{preview_task_id:ID}],explicit_end:true};
      assert.fail('Unexpected reader');
    }};
    assert.equal((await assetsAll(p,{limit:1000,pages:10}))[0].all_assets,true);
    assert.deepEqual(clicks,[...(broken?['Home']:[]),'Assets','Model','My Assets','All']);
    assert.equal(modelReads,2);
  }
});
test('known SPA heading transition is pending; unknown heading is a contract failure',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/retopology/'+ID};
  let heading='Generate Model';globalThis.document={querySelectorAll:()=>[{querySelector:()=>({innerText:heading})}]};
  assert.equal(readPanelDOM('retopo').kind,'pending');heading='Unrecognized Panel';assert.equal(readPanelDOM('retopo').kind,'layout_changed');
  location.pathname='/workspace/generate/'+ID;assert.equal(readPanelDOM('retopo').kind,'pending');
});
function progressDOM(path,{progress=[],busy=false}={}){
  // closest() honours selector lists: a node matches when any listed ancestor encloses it.
  const node=(text,within=[])=>({innerText:text,getClientRects:()=>[1],closest:selector=>selector.split(',').some(s=>within.includes(s.trim()))?{}:null});
  const paragraphs=[node('Faces'),node('Vertices'),...progress.map(([text,within])=>node(text,within))];
  paragraphs[0].nextElementSibling={innerText:'12'};paragraphs[1].nextElementSibling={innerText:'8'};
  const action={innerText:'Retopology 40',disabled:busy,getAttribute:()=>null,closest:()=>null};
  const panel={querySelectorAll:selector=>selector==='button.animate-button'?[action]:[]};
  const main={innerText:'Retopology',querySelectorAll:selector=>selector==='p'?paragraphs:selector==='button'?[{innerText:'Export',disabled:false,closest:()=>null}]:[]};
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:path};
  globalThis.document={querySelector:selector=>selector==='main'?main:null,
    querySelectorAll:selector=>selector==='main p'?paragraphs:selector==='div.rounded-r-5:has(h2)'?[panel]:[]};
}
test('another card showing progress never proves this asset is processing or that the paid click registered',()=>{
  const route='/workspace/retopology/'+ID;
  for(const within of [['[role="tabpanel"]'],['a[href]'],['[role="dialog"]']]){
    progressDOM(route,{progress:[['Retopologizing...',within]],busy:true});
    assert.equal(readSubmissionDOM(ID).kind,'pending');
    const status=readAssetDOM();assert.equal(status.status,'ready');assert.equal(status.processing,false);
  }
  // Routed progress without this click's own change (the action is still enabled) is not evidence.
  progressDOM(route,{progress:[['Retopologizing...',[]]]});assert.equal(readSubmissionDOM(ID).kind,'pending');
  assert.equal(readAssetDOM().status,'generating');
  progressDOM(route,{progress:[['Retopologizing...',[]]],busy:true});
  assert.deepEqual(readSubmissionDOM(ID),{kind:'ready',asset_id:ID,acceptance:'processing_ui_observed_not_model_completion'});
  progressDOM('/workspace/retopology/'+OTHER);
  assert.deepEqual(readSubmissionDOM(ID),{kind:'ready',asset_id:OTHER,acceptance:'new_asset_route_observed_not_model_completion'});
});
test('another card or a dialog showing a failure never marks the ready routed asset failed',()=>{
  const route='/workspace/retopology/'+ID;
  for(const text of ['Generation failed','Unknown server error','Task failed'])
    for(const within of [['[role="tabpanel"]'],['a[href]'],['[role="dialog"]']]){
      progressDOM(route,{progress:[[text,within]]});
      const status=readAssetDOM();assert.equal(status.status,'ready');assert.equal(status.processing,false);assert.equal(status.export_enabled,true);
      // Nor does another card's failure become submission evidence for this click.
      progressDOM(route,{progress:[[text,within]],busy:true});assert.equal(readSubmissionDOM(ID).kind,'pending');
    }
  // Another card's failure does not hide this asset's own progress either.
  progressDOM(route,{progress:[['Generation failed',['[role="tabpanel"]']],['Retopologizing...',[]]]});assert.equal(readAssetDOM().status,'generating');
  // The routed asset's own failure still outranks its old mesh, Export and progress.
  for(const text of ['Generation failed','Unknown server error','Task failed']){
    progressDOM(route,{progress:[[text,[]]]});assert.equal(readAssetDOM().status,'failed');
    progressDOM(route,{progress:[['Retopologizing...',[]],[text,[]]]});assert.equal(readAssetDOM().status,'failed');
  }
});
const ELSEWHERE=selector=>['[role="tabpanel"]','[role="dialog"]','a[href]'].every(part=>selector.includes(part));
function retopoPanelDOM(own,cards=[]){
  // A card is {text, hidden, parent}: parent is an enclosing card inside the same panel.
  const nodes=cards.map(card=>({innerText:card.text,getClientRects:()=>card.hidden?[]:[1]}));
  nodes.forEach((node,i)=>{node.parentElement={closest:selector=>ELSEWHERE(selector)&&cards[i].parent!==undefined?nodes[cards[i].parent]:null};});
  // The panel text holds each rendered top-level card once; a nested card's text is in its parent's.
  const rendered=cards.filter(card=>!card.hidden&&card.parent===undefined).map(card=>card.text);
  const button={innerText:'Retopology 40',disabled:false,getAttribute:()=>null};
  const fields={'h2':{innerText:'Retopology'},'button.animate-button':button,'button[aria-pressed="true"]':{innerText:'Quad'},'input[type="text"]':{value:'10000'},
    '[role="switch"]':{getAttribute:()=> 'true'},'[role="slider"]':{getAttribute:name=>name==='aria-valuemin'?'500':'10000'}};
  const panel={innerText:[...own,...rendered].join('\n'),contains:node=>nodes.includes(node),querySelector:selector=>fields[selector]||null,
    querySelectorAll:selector=>selector==='button.animate-button'?[button]:ELSEWHERE(selector)?nodes:[]};
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/retopology/'+ID};
  globalThis.document={querySelectorAll:()=>[panel],querySelector:()=>({parentElement:{querySelector:()=>({getAttribute:()=> '100'})}})};
}
test('a failure shown by a card or dialog inside the panel never blocks this ready form',()=>{
  retopoPanelDOM(['Retopology']);const ready=readPanelDOM('retopo');assert.equal(ready.kind,'ready');assert.equal(ready.blocked,false);assert.equal(ready.button_enabled,true);
  for(const text of ['Generation failed','Unknown server error','Task failed','Not Ready for Auto-Rigging']){
    // Sidebar tabpanel, asset link and dialog cards, also an asset link nested in the sidebar.
    retopoPanelDOM(['Retopology'],[{text},{text:'Asset\n'+text},{text:text+'\nRetry'}]);assert.equal(readPanelDOM('retopo').blocked,false);
    retopoPanelDOM(['Retopology'],[{text:'Sidebar\n'+text},{text,parent:0}]);
    assert.equal(readPanelDOM('retopo').blocked,false);
  }
  // The panel's own failure still blocks, also when a card repeats it or a hidden card holds the same text.
  retopoPanelDOM(['Retopology','Task failed']);assert.equal(readPanelDOM('retopo').blocked,true);
  retopoPanelDOM(['Retopology','Task failed'],[{text:'Sidebar\nTask failed'},{text:'Task failed',parent:0}]);assert.equal(readPanelDOM('retopo').blocked,true);
  retopoPanelDOM(['Retopology','Unknown server error'],[{text:'Unknown server error',hidden:true}]);assert.equal(readPanelDOM('retopo').blocked,true);
});
test('image quote binds distinct blob preview identities even when file input is cleared',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate'};
  let blob='blob:https://studio.tripo3d.ai/'+ID+'?Signature=FAKE';
  const button={innerText:'Generate 40',disabled:false,getAttribute:()=>null};
  const file={files:[]};const image={getClientRects:()=>[1],getAttribute:()=>blob};
  const panel={innerText:'Generate Model',querySelector:selector=>selector==='h2'?{innerText:'Generate Model'}:selector==='button.animate-button'?button:selector==='input[type="file"]'?file:null,
    querySelectorAll:selector=>selector==='button.animate-button'?[button]:selector==='input[type="file"]'?[file]:selector==='[role="combobox"]'?[{innerText:'Private'},{innerText:'H3.1 – Best Quality'}]:selector==='[role="switch"]'?[{getAttribute:()=> 'false'},{getAttribute:()=> 'false'}]:selector==='img'?[image]:[]};
  globalThis.document={querySelectorAll:()=>[panel],querySelector:()=>({parentElement:{querySelector:()=>({getAttribute:()=> '100'})}})};
  const first=readPanelDOM('image');assert.equal(first.kind,'ready');assert.doesNotMatch(JSON.stringify(first),/Signature|FAKE/);
  blob='blob:https://studio.tripo3d.ai/'+OTHER;
  assert.notEqual(quoteHash(first,'1'.repeat(64)),quoteHash(readPanelDOM('image'),'1'.repeat(64)));
});
test('observed mesh, gray mesh, part and wireframe variants are accepted; signed queries never returned',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/assets'};globalThis.getComputedStyle=()=>({overflowY:'scroll'});
  let name='mesh';const img={alt:'fixture',closest:()=>({getClientRects:()=>[1]}),getAttribute:()=>`https://tripo-data-public.rg1.data.tripo3d.com/tripo-studio/20261003/${ID}/studio_${name}.webp?Signature=FAKE&Policy=FAKE`};
  const buttons=['Model','My Assets','All'].map(innerText=>({innerText,getClientRects:()=>[1],getAttribute:()=> 'active'}));
  const main={innerText:'My Assets',scrollHeight:1000,clientHeight:500,scrollTop:500,parentElement:null,querySelectorAll:selector=>selector==='button'?buttons:[img],querySelector:()=>({innerText:'',querySelector:()=>null})};
  globalThis.document={querySelector:()=>main};for(name of ['mesh','mesh_gray','part','wireframe']){const value=readCollectionDOM();assert.equal(value.kind,'ready');assert.doesNotMatch(JSON.stringify(value),/FAKE|Policy|Signature/);}
  name='undocumented';assert.equal(readCollectionDOM().kind,'thumbnail_contract_changed');
});

const PREVIEW='cccccccc-dddd-eeee-ffff-000000000000',SHIFTED='dddddddd-eeee-ffff-0000-111111111111';
function resolvePage(dialogPreview){
  const calls=[];
  const thumbnail=id=>`https://tripo-data-public.rg1.data.tripo3d.com/tripo-studio/20261003/${id}/studio_mesh.webp?Signature=FAKE`;
  return {calls,goto:()=>assert.fail('No cold navigation'),click:async(selector,options)=>{calls.push([selector,options?.nth]);},
    evaluate:async(fn,...values)=>{
      if(fn===readLocation)return{origin:'https://studio.tripo3d.ai',path:'/assets'};
      if(fn===readVisibleErrorDOM)return{site_error:false};
      if(fn===readAccountDOM)return{kind:'ready',credits:100};
      if(fn===findTextDOM)return{count:1,nth:0};
      if(fn===readPreviewTargetDOM)return{count:1,nth:0};
      if(fn===readAssetDOM)return{kind:'ready',status:'ready',asset_id:dialogPreview===PREVIEW?ID:OTHER,faces:12,vertices:8,export_enabled:true};
      // Any other reader runs against the card dialog that the positional nth click opened.
      const opened=calls.some(([selector])=>selector==='main div.group > a');
      const dialog={getClientRects:()=>[1],innerText:'Edit in Workspace',
        querySelectorAll:selector=>selector==='button'?[{innerText:'Edit in Workspace'}]:selector.startsWith('img')?[{getAttribute:()=>thumbnail(dialogPreview)}]:[]};
      globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/assets'};
      globalThis.document={querySelectorAll:selector=>selector==='[role="dialog"]'&&opened?[dialog]:[]};
      return fn(...values);
    }};
}
test('asset resolve binds the opened card dialog to the requested preview before Edit in Workspace',async()=>{
  // The grid re-rendered between the target read and the nth click: nth 0 now opens another card.
  const shifted=resolvePage(SHIFTED);
  await assert.rejects(resolveAsset(shifted,{preview:PREVIEW}),e=>e.code==='asset_mismatch');
  assert.equal(shifted.calls.some(([selector])=>selector==='[role="dialog"] button'),false);
  const exact=resolvePage(PREVIEW);const out=(await resolveAsset(exact,{preview:PREVIEW}))[0];
  assert.equal(out.asset_id,ID);assert.equal(out.preview_task_id,PREVIEW);assert.equal(out.paid_submitted,false);
  assert.deepEqual(exact.calls.slice(-2),[['main div.group > a',0],['[role="dialog"] button',0]]);
});
test('card dialog identity waits for its thumbnail and rejects ambiguous dialogs',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/assets'};
  let images=[];const dialog={getClientRects:()=>[1],querySelectorAll:s=>s==='button'?[{innerText:'Edit in Workspace'}]:images};
  let dialogs=[];globalThis.document={querySelectorAll:()=>dialogs};
  assert.equal(readPreviewDialogDOM(PREVIEW).kind,'pending');dialogs=[dialog];assert.equal(readPreviewDialogDOM(PREVIEW).kind,'pending');
  images=[{getAttribute:()=>'/tripo-studio/20261003/'+PREVIEW+'/studio_part.webp'},{getAttribute:()=>'/static/icon.svg'}];
  assert.deepEqual(readPreviewDialogDOM(PREVIEW),{kind:'ready',preview_task_id:PREVIEW});
  images.push({getAttribute:()=>'/tripo-studio/20261003/'+SHIFTED+'/studio_mesh.webp'});assert.equal(readPreviewDialogDOM(PREVIEW).kind,'asset_mismatch');
  dialogs=[dialog,dialog];assert.equal(readPreviewDialogDOM(PREVIEW).kind,'layout_changed');
});
function collectionDOMFixture(){
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/assets'};
  globalThis.getComputedStyle=()=>({overflowY:'scroll'});
  const states={Model:'active','My Assets':'active',All:'active',Image:'inactive'};
  const buttons=Object.keys(states).map(innerText=>({innerText,getClientRects:()=>[1],getAttribute:()=>states[innerText]}));
  const card={getClientRects:()=>[1]};let host='tripo-data-public.rg1.data.tripo3d.com';
  const img={alt:'fixture',closest:()=>card,getAttribute:()=>`https://${host}/tripo-studio/20261003/${ID}/studio_mesh.webp?Signature=FAKE`};
  const images=[img];const footer={innerText:'',querySelector:()=>null};
  const main={innerText:'Model\nImage\nMy Assets\nAll',scrollHeight:1000,clientHeight:500,scrollTop:500,parentElement:null,
    querySelectorAll:selector=>selector==='button'?buttons:images,querySelector:()=>footer};
  globalThis.document={querySelector:()=>main};
  return{states,buttons,images,card,setHost:value=>{host=value;}};
}
test('collection checks actual selected category, ownership and filter instead of trusting clicks',()=>{
  for(const label of ['Model','My Assets','All']){
    const f=collectionDOMFixture();assert.equal(readCollectionDOM().scope_verified,true);
    f.states[label]='inactive';assert.equal(readCollectionDOM().kind,'collection_scope_mismatch');
    f.states[label]=null;assert.equal(readCollectionDOM().kind,'collection_scope_changed');
  }
  const f=collectionDOMFixture();f.states.Model='inactive';f.states.Image='active';f.buttons.splice(1,1);
  assert.equal(readCollectionDOM().kind,'collection_scope_mismatch');
});
test('collection never silently drops a card with a changed thumbnail host or duplicate identity',()=>{
  const f=collectionDOMFixture();f.setHost('other.example');assert.equal(readCollectionDOM().kind,'thumbnail_contract_changed');
  f.setHost('tripo-data-public.rg1.data.tripo3d.com');
  f.images.push({...f.images[0],closest:()=>({getClientRects:()=>[1]})});
  assert.equal(readCollectionDOM().kind,'collection_card_identity_changed');
});
test('collection counts unique cards even when a card contains repeated thumbnail elements',()=>{
  const f=collectionDOMFixture();f.images.push(f.images[0]);
  const result=readCollectionDOM();assert.equal(result.kind,'ready');assert.equal(result.rendered_cards,1);assert.equal(result.items.length,1);
});
test('scope drift during pagination fails, including after previously valid cards',async()=>{
  let scrolled=false;
  const p={scrollTo:async()=>{scrolled=true;},click:async()=>{},evaluate:async fn=>{
    if(fn===readLocation)return{origin:'https://studio.tripo3d.ai',path:'/assets'};
    if(fn===readVisibleErrorDOM)return{site_error:false};if(fn===readAccountDOM)return{kind:'ready',credits:100};
    if(fn===findTextDOM)return{count:1,nth:0};
    if(fn===readCollectionDOM)return scrolled?{kind:'collection_scope_mismatch'}:{kind:'ready',items:[{preview_task_id:ID}],scope_verified:true,at_end:false,loading:false,explicit_end:false};
    assert.fail('Unexpected reader');
  }};
  await assert.rejects(assetsAll(p,{limit:1000,pages:10},{quietMs:0}),error=>error.code==='collection_scope_mismatch');
});
