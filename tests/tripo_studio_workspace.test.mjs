import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { MODULES, SUBMIT_MODULES, workspaceDigest, checkWorkspacePin, moduleName, readWorkspaceDOM, readWorkspaceLinkDOM,
  workspaceQuoteHash, parseWorkspaceSettings, inspectWorkspace, prepareWorkspace, submitWorkspace, readWorkspaceSubmissionDOM, readChoiceDOM } from '../examples/opencli/tripo-studio/workspace.mjs';
import { readLocation } from '../examples/opencli/tripo-studio/extended.mjs';
import { readAccountDOM } from '../examples/opencli/tripo-studio/core.mjs';
const ID='11111111-2222-3333-4444-555555555555',OTHER='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const sha=value=>createHash('sha256').update(value).digest('hex');
test('same-UUID Texture submission recognizes the exact observed HUD phrase, not another sidebar task',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/texture/'+ID};
  const progress={innerText:'Generating Texture...',getClientRects:()=>[1],closest:()=>null};
  globalThis.document={querySelectorAll:()=>[progress]};
  const accepted=readWorkspaceSubmissionDOM('texture',ID);assert.equal(accepted.kind,'ready');assert.equal(accepted.asset_id,ID);assert.equal(accepted.acceptance,'processing_ui_not_completion');
  progress.closest=()=>({});assert.equal(readWorkspaceSubmissionDOM('texture',ID).kind,'pending');
  progress.closest=()=>null;progress.innerText='Generating an unrelated task';assert.equal(readWorkspaceSubmissionDOM('texture',ID).kind,'pending');
});
const temp=()=>mkdtempSync('/private/tmp/atm-tripo-workspace-');
const FORM={kind:'ready',module:'segment',asset_id:ID,heading:'Segmentation',quoted_credits:40,credits:100,button_enabled:true,action_label:'Start Segmenting 40',warnings:[],settings:{detail_level:'Balanced'}};
function fixturePage(form=FORM,{available=true,clickError=false}={}) {
  const data=structuredClone(form),calls=[];let route=MODULES[data.module][1];
  const page={data,calls,evaluate:async(fn,...values)=>{
    if(fn===readLocation)return{origin:'https://studio.tripo3d.ai',path:'/workspace/'+route+'/'+ID};
    if(fn===readWorkspaceLinkDOM)return{kind:'ready',href:'/workspace/'+MODULES[Object.keys(MODULES).find(k=>MODULES[k][0]===values[0])][1]+'/'+ID,available};
    if(fn===readWorkspaceDOM)return structuredClone(data);
    if(fn===readWorkspaceSubmissionDOM)return{kind:'ready',asset_id:OTHER,acceptance:'new_asset_route_not_completion'};
    if(fn===readChoiceDOM)return{kind:'ready',nth:values[0]==='Simple'?0:1};
    if(fn===readAccountDOM)return{kind:'ready',credits:100};
    assert.fail('Unexpected DOM reader');
  },click:async(selector,options)=>{calls.push(['click',selector,options]);if(selector.includes('animate-button')&&clickError)throw new Error('FAKE_TOKEN=in_error');
    if(selector.endsWith(' button')){if(data.module==='segment')data.settings.detail_level=options.nth===0?'Simple':'Detailed';else data.settings.resolution=options.nth===1?'4K':'8K';}
  },fillText:async(selector,value)=>{calls.push(['fill',selector,value]);data.settings[selector.endsWith('textarea')?'prompt':'creativity_strength']=selector.endsWith('textarea')?value:Number(value);},
  pressKey:async key=>calls.push(['key',key]),setChecked:async(selector,value)=>{calls.push(['check',selector,value]);data.settings.remove_lighting=value;},goto:()=>assert.fail('No cold navigation')};
  return page;
}
const execution=(extra={})=>({module:'segment',asset:ID,quote:workspaceQuoteHash(FORM),budget:40,key:'workspace-once',confirm:true,ledger:temp(),...extra});

test('workspace pin binds all ten source files and unknown module never reaches UI',async()=>{
  assert.equal(workspaceDigest().length,64);checkWorkspacePin(workspaceDigest());assert.throws(()=>checkWorkspacePin(''),e=>e.code==='definition_changed');
  assert.throws(()=>checkWorkspacePin('a'.repeat(64)),e=>e.code==='definition_changed');assert.equal(Object.keys(MODULES).length,12);
  assert.throws(()=>moduleName('__proto__'),e=>e.code==='invalid_argument');
  const p=fixturePage();await assert.rejects(inspectWorkspace(p,{module:'arbitrary',asset:ID}),e=>e.code==='invalid_argument');assert.deepEqual(p.calls,[]);
});
test('inspect preserves form; missing or disabled actions remain explicit, not free',async()=>{
  for(const form of [FORM,{...FORM,quoted_credits:null,button_enabled:false}]){
    const p=fixturePage(form),result=(await inspectWorkspace(p,{module:'segment',asset:ID}))[0];
    assert.equal(result.quote_known,form.quoted_credits!==null);assert.equal(result.quote_sha256,form.quoted_credits===null?null:workspaceQuoteHash(form));
    assert.equal(result.status,form.button_enabled?'ready':'prerequisite_missing');assert.equal(result.paid_submitted,false);assert.deepEqual(p.calls,[]);
  }
  const p=fixturePage(FORM,{available:false});assert.equal((await inspectWorkspace(p,{module:'segment',asset:ID}))[0].status,'unavailable');assert.deepEqual(p.calls,[]);
});
test('typed preparation rejects arbitrary selectors, wrong module options and invalid values',()=>{
  for(const[module,settings]of [['segment',{resolution:'8K'}],['segment',{detail_level:'secret'}],['upscale',{resolution:'2K'}],['texture',{prompt:null}],['texture',{remove_lighting:'false'}],['edit',{creativity_strength:NaN}],['edit',{creativity_strength:1.1}],['pbr',{selector:'button'}],['model',{}],['texture',{expected_prompt_sha256:'f'.repeat(64)}]])
    assert.throws(()=>parseWorkspaceSettings(module,settings),e=>e.code==='invalid_argument');
  assert.deepEqual(parseWorkspaceSettings('segment','{"detail_level":"Simple"}'),{detail_level:'Simple'});
});
test('prepare selects and verifies semantic detail level without a paid click',async()=>{
  const p=fixturePage();const out=(await prepareWorkspace(p,{module:'segment',asset:ID,settings:{detail_level:'Simple'}}))[0];
  assert.equal(out.settings.detail_level,'Simple');assert.notEqual(out.quote_sha256,workspaceQuoteHash(FORM));assert.equal(p.calls.length,1);assert.doesNotMatch(p.calls[0][1],/animate-button/);
});
test('texture preparation re-reads fields; existing prompt replacement needs exact previous digest',async()=>{
  const form={...FORM,module:'texture',settings:{prompt:'human draft',resolution:'8K',remove_lighting:false}};
  for(const settings of [{prompt:'new draft'},{prompt:'new draft',expected_prompt_sha256:'f'.repeat(64)}]){
    const p=fixturePage(form);await assert.rejects(prepareWorkspace(p,{module:'texture',asset:ID,settings}),e=>e.code==='draft_present');assert.deepEqual(p.calls,[]);
  }
  const p=fixturePage(form);const out=(await prepareWorkspace(p,{module:'texture',asset:ID,settings:{prompt:'new draft',expected_prompt_sha256:sha('human draft'),resolution:'4K',remove_lighting:true}}))[0];
  assert.equal(out.settings.prompt,'new draft');assert.equal(out.settings.resolution,'4K');assert.equal(out.settings.remove_lighting,true);assert.equal(out.prompt_sha256,sha('new draft'));
  assert.equal(p.calls.some(c=>c[1]?.includes('animate-button')),false);
});
test('prepare edit strength and empty prompt with no submission',async()=>{
  const p=fixturePage({...FORM,module:'edit',settings:{prompt:'',creativity_strength:0.6}});
  const result=(await prepareWorkspace(p,{module:'edit',asset:ID,settings:{prompt:'blue fixture',creativity_strength:0.4}}))[0];
  assert.equal(result.settings.prompt,'blue fixture');assert.equal(result.settings.creativity_strength,0.4);assert.equal(result.paid_submitted,false);
});
test('random-order child navigation first opens its observed collapsed parent group',async()=>{
  for(const[module,parent]of [['upscale','texture'],['edit','texture'],['pbr','texture'],['fill_parts','segment'],['animate','rig']]){
    const p=fixturePage({...FORM,module}),original=p.evaluate;let open=false;
    p.evaluate=async(fn,...values)=>{
      if(fn===readLocation)return{origin:'https://studio.tripo3d.ai',path:'/workspace/generate/'+ID};
      if(fn===readWorkspaceLinkDOM)return{kind:'ready',href:'/workspace/'+(values[0]===MODULES[parent][0]?MODULES[parent][1]:MODULES[module][1])+'/'+ID,
        available:values[0]===MODULES[parent][0]||open,collapsed:!open,parent_label:MODULES[parent][0]};
      return original(fn,...values);
    };
    const click=p.click;p.click=async(...values)=>{open=true;await click(...values);};
    assert.equal((await inspectWorkspace(p,{module,asset:ID}))[0].module,module);
    assert.equal(p.calls.length,2);assert.match(p.calls[0][1],new RegExp('/'+MODULES[parent][1]+'/'));
  }
});
test('clearing a draft also requires its exact observed digest',async()=>{
  const form={...FORM,module:'edit',settings:{prompt:'human draft',creativity_strength:0.6}};
  const p=fixturePage(form);await assert.rejects(prepareWorkspace(p,{module:'edit',asset:ID,settings:{prompt:''}}),e=>e.code==='draft_present');assert.deepEqual(p.calls,[]);
  const out=(await prepareWorkspace(p,{module:'edit',asset:ID,settings:{prompt:'',expected_prompt_sha256:sha('human draft')}}))[0];assert.equal(out.settings.prompt,'');assert.equal(out.paid_submitted,false);
});
test('unchanged and changed prices, settings and source are independently fingerprinted',()=>{
  for(const patch of [{module:'pbr'},{asset_id:OTHER},{quoted_credits:41},{action_label:'Other 40'},{settings:{detail_level:'Simple'}},{warnings:['new warning']}])assert.notEqual(workspaceQuoteHash({...FORM,...patch}),workspaceQuoteHash(FORM));
  assert.equal(workspaceQuoteHash({...FORM,credits:80}),workspaceQuoteHash(FORM));
});
test('confirmation and budget preflight precede all browser operations',async()=>{
  for(const patch of [{confirm:false},{budget:0},{budget:1.1},{module:'image'},{asset:'not-uuid'},{quote:'bad'}]){
    const p=fixturePage();await assert.rejects(submitWorkspace(p,execution(patch)));assert.deepEqual(p.calls,[]);
  }
});
test('source, quote drift, prerequisites and balance stop before any paid click',async()=>{
  for(const patch of [{quoted_credits:41},{asset_id:OTHER},{settings:{detail_level:'Simple'}},{button_enabled:false},{credits:20},{quoted_credits:null}]){
    const p=fixturePage({...FORM,...patch});await assert.rejects(submitWorkspace(p,execution()));assert.deepEqual(p.calls,[]);
  }
});
test('one durable claim precedes one paid click; stable key reuse skips browser entirely',async()=>{
  const args=execution(),p=fixturePage(),click=p.click;
  p.click=async(...params)=>{const files=readdirSync(join(args.ledger,'.atm/tripo-studio-paid')).filter(n=>n.startsWith('extended-'));assert.equal(files.length,1);
    assert.equal(JSON.parse(readFileSync(join(args.ledger,'.atm/tripo-studio-paid',files[0]))).stage,'paid_click');await click(...params);};
  const first=(await submitWorkspace(p,args))[0];assert.equal(first.status,'submitted');assert.equal(first.asset_id,OTHER);assert.equal(first.model_completed,false);assert.equal(p.calls.length,1);
  const reuse=fixturePage();assert.equal((await submitWorkspace(reuse,args))[0].reused,true);assert.deepEqual(reuse.calls,[]);
  await assert.rejects(submitWorkspace(reuse,{...args,budget:41}),e=>e.code==='request_conflict');
});
test('all five observed paid modules share the same quote/receipt/completion gates',async()=>{
  for(const module of SUBMIT_MODULES){
    const price={segment:40,texture:30,edit:5,upscale:20,pbr:5}[module];
    const data={...FORM,module,quoted_credits:price,action_label:module+' '+price};
    const p=fixturePage(data),args=execution({module,quote:workspaceQuoteHash(data),budget:price});
    const out=(await submitWorkspace(p,args))[0];assert.equal(out.module,module);assert.equal(out.quoted_credits,price);assert.equal(out.model_completed,false);assert.equal(p.calls.length,1);
  }
});
test('uncertainty persists and blocks same/new keys without another UI action',async()=>{
  const args=execution(),p=fixturePage(FORM,{clickError:true});await assert.rejects(submitWorkspace(p,args),e=>e.code==='submission_unknown');
  const dir=join(args.ledger,'.atm/tripo-studio-paid');assert.ok(existsSync(join(dir,'active.lock')));
  const receipt=JSON.parse(readFileSync(join(dir,readdirSync(dir).find(n=>n.startsWith('extended-')))));assert.equal(receipt.status,'submission_unknown');assert.doesNotMatch(JSON.stringify(receipt),/FAKE_TOKEN|in_error/);
  const again=fixturePage();for(const key of [args.key,'other-key'])await assert.rejects(submitWorkspace(again,{...args,key}),e=>['submission_unknown','workspace_busy'].includes(e.code));assert.deepEqual(again.calls,[]);
});
test('shared older upload lock blocks these new paid modules unchanged',async()=>{
  const args=execution(),dir=join(args.ledger,'.atm/tripo-studio-paid');mkdirSync(dir,{recursive:true});writeFileSync(join(dir,'active.lock'),'fixture-unknown-upload');
  const p=fixturePage();await assert.rejects(submitWorkspace(p,args),e=>e.code==='workspace_busy');assert.deepEqual(p.calls,[]);assert.equal(readFileSync(join(dir,'active.lock'),'utf8'),'fixture-unknown-upload');
});

function domFixture(module,{price='40',disabled=false}={}) {
  const visible=()=>({width:100,height:20});
  const button=(text,selected=false,action=false)=>({innerText:text,disabled,closest:()=>null,getBoundingClientRect:visible,getAttribute:name=>name==='aria-pressed'?(selected?'true':'false'):null,classList:{contains:name=>action?name==='animate-button':selected&&name==='ring-purple-1'}});
  const labels={segment:'Start Segmenting',texture:'Generate Texture',edit:'Generate Preview',upscale:'Enhance Now',pbr:'Generate PBR',image:'Generate Image',smart_uv:'Unwrap UV',animate:'Generate'};
  const buttons=[...(module==='segment'?[button('Simple\n3-6 parts'),button('Balanced\n6-15 parts',true),button('Detailed\n15+ parts')]:module==='upscale'?[button('4K\n4096*4096'),button('8K\n8192*8192',true)]:module==='texture'?[button('2K'),button('4K'),button('8K',true)]:[]),button(labels[module]+(price?'\n'+price:''),false,true)];
  const fields=module==='texture'?[{tagName:'TEXTAREA',value:'fixture',getAttribute:()=>null}]:module==='edit'?[{tagName:'TEXTAREA',value:'',getAttribute:()=>null},{tagName:'INPUT',value:'0.6',getAttribute:n=>n==='type'?'text':null}]:[];
  for(const field of fields)field.closest=()=>null;
  const panel={getClientRects:()=>[1],querySelector:()=>({innerText:MODULES[module][2]}),innerText:MODULES[module][2],querySelectorAll:selector=>
    selector==='button'?buttons:selector.startsWith('input:not')?fields:selector==='[role="switch"]'&&module==='texture'?[{getAttribute:()=> 'false'}]:[]};
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/'+MODULES[module][1]+'/'+ID};
  globalThis.document={querySelectorAll:()=>[panel],querySelector:()=>({parentElement:{querySelector:()=>({getAttribute:()=> '20,115'})}})};
  return{buttons,panel,fields};
}
test('actual DOM reader normalizes the observed module settings and known prices',()=>{
  for(const module of ['segment','texture','edit','upscale','pbr']){domFixture(module);const value=readWorkspaceDOM(module);assert.equal(value.kind,'ready');assert.equal(value.quoted_credits,40);assert.equal(value.asset_id,ID);assert.equal(value.credits,20115);}
  domFixture('segment');assert.equal(readWorkspaceDOM('segment').settings.detail_level,'Balanced');domFixture('texture');assert.equal(readWorkspaceDOM('texture').settings.remove_lighting,false);
  domFixture('upscale');assert.equal(readWorkspaceDOM('upscale').settings.resolution,'8K');
});
test('DOM reader exposes unpriced action and rejects unknown price or selection layout',()=>{
  domFixture('image',{price:''});assert.equal(readWorkspaceDOM('image').quoted_credits,null);
  domFixture('pbr',{price:'Free 14/1000'});assert.equal(readWorkspaceDOM('pbr').kind,'workspace_price_changed');
  const f=domFixture('segment');f.buttons[0].classList.contains=name=>name==='ring-purple-1';assert.equal(readWorkspaceDOM('segment').kind,'workspace_selection_changed');
  const g=domFixture('pbr');g.buttons.push(g.buttons[0]);assert.equal(readWorkspaceDOM('pbr').kind,'workspace_action_changed');
});
test('DOM signed queries are stripped and zero-height navigation is unavailable',()=>{
  const f=domFixture('pbr');f.panel.querySelectorAll=selector=>selector==='img'?[{getAttribute:()=>`https://data.example/fixture.webp?Signature=FAKE_SECRET`}]:selector==='button'?f.buttons:[];
  assert.doesNotMatch(JSON.stringify(readWorkspaceDOM('pbr')),/FAKE_SECRET|Signature/);
  const link={innerText:'Animate',closest:()=>null,getBoundingClientRect:()=>({width:40,height:0}),getAttribute:n=>n==='href'?'/workspace/animate/'+ID:null};
  globalThis.document={querySelectorAll:()=>[link]};globalThis.getComputedStyle=()=>({visibility:'visible',display:'flex'});
  assert.equal(readWorkspaceLinkDOM('Animate').available,false);
});
test('animation preset list is separate from primary controls, with real rig prerequisite warning',()=>{
  const f=domFixture('animate',{price:'20',disabled:true});
  const preset={innerText:'walk',disabled:false,closest:()=>({}),getBoundingClientRect:()=>({width:100,height:20})};
  const query=f.panel.querySelectorAll;
  f.panel.querySelectorAll=selector=>selector==='button'?[...f.buttons,...Array(100).fill(preset)]:selector==='[role="tabpanel"] button'?[preset]:query(selector);
  f.panel.innerText='Animation\nRig the Model First\nRig the Model First';
  const out=readWorkspaceDOM('animate');assert.equal(out.kind,'ready');assert.equal(out.quoted_credits,20);assert.deepEqual(out.presets,['walk']);assert.deepEqual(out.warnings,['Rig the Model First']);assert.equal(out.button_enabled,false);
});
test('rigged same-href form shortcut does not make the inspected Animate sidebar click ambiguous',async()=>{
  const href='/workspace/animate/'+ID,link=text=>({innerText:text,closest:()=>null,parentElement:null,
    getBoundingClientRect:()=>({width:40,height:20}),getAttribute:n=>n==='href'?href:null});
  const shortcut=link('Rigged models can be used for animation'),sidebar=link('Animate');
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/rigging/'+ID};
  globalThis.document={querySelectorAll:()=>[shortcut,sidebar]};globalThis.getComputedStyle=()=>({display:'flex',visibility:'visible'});
  const observed=readWorkspaceLinkDOM('Animate');assert.equal(observed.kind,'ready');assert.equal(observed.nth,1);
  const p=fixturePage({...FORM,module:'animate'}),original=p.evaluate;
  p.evaluate=async(fn,...args)=>fn===readLocation?{origin:'https://studio.tripo3d.ai',path:'/workspace/rigging/'+ID}:fn===readWorkspaceLinkDOM?observed:original(fn,...args);
  await inspectWorkspace(p,{module:'animate',asset:ID});assert.deepEqual(p.calls[0],['click','a[href="'+href+'"]',{nth:1}]);
});
test('new source or actual processing signal is submission evidence, never completion',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/texture-pbr/'+ID};globalThis.document={querySelectorAll:()=>[]};
  assert.equal(readWorkspaceSubmissionDOM('pbr',ID).kind,'pending');location.pathname='/workspace/texture-pbr/'+OTHER;
  assert.equal(readWorkspaceSubmissionDOM('pbr',ID).asset_id,OTHER);assert.doesNotMatch(readWorkspaceSubmissionDOM('pbr',ID).acceptance,/finished/);
});
