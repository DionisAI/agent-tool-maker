import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { uiOptionsDigest, checkUIOptionsPin, parseUISettings, readUIContextDOM, readAnimationDOM,
  animationQuoteHash, inspectAnimation, prepareAnimation, readExportOptionsDOM, readExportListDOM, readExportListClosedDOM,
  readExportTargetDOM, readOwnExportClosedDOM, readOwnExportCloseDOM, inspectExportOptions, prepareExportOptions } from '../examples/opencli/tripo-studio/ui-options.mjs';
import { readLocation, readAssetDOM } from '../examples/opencli/tripo-studio/extended.mjs';
import { readWorkspaceLinkDOM, readWorkspaceDOM } from '../examples/opencli/tripo-studio/workspace.mjs';
const ID='11111111-2222-3333-4444-555555555555',OTHER='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const sha=value=>createHash('sha256').update(value).digest('hex');
const MOTION={kind:'ready',asset_id:ID,settings:{prompt:'',duration:5},duration_bounds:{min:1,max:10},quoted_credits:20,
  button_enabled:false,input_enabled:true,rig_prerequisite_missing:false,warnings:[],presets:['walk','dance_03'],action_label:'Generate 20'};
const EXPORT={kind:'ready',asset_id:ID,settings:{format:'GLB',texture_resolution:'4k',export_skeleton:true,vertex_colors:null,fbx_variant:null,animation_count:0},
  switches:[{nth:0,label:'Export Skeleton',checked:'true',disabled:false}],variants:[],filename:'fixture',button_enabled:true};
function pageFixture({motion=MOTION,existingDialog=false,obscured=false,brokenSetting=false,bridgeFailure=false}={}) {
  const data=structuredClone(motion),exp=structuredClone(EXPORT),calls=[];let route='animate',owned=false,list=null;
  const page={data,exp,calls,evaluate:async(fn,...args)=>{
    if(fn===readUIContextDOM)return{origin:'https://studio.tripo3d.ai',path:'/workspace/'+route+'/'+ID,dialogs:existingDialog?1:0};
    if(fn===readLocation)return{origin:'https://studio.tripo3d.ai',path:'/workspace/'+route+'/'+ID};
    if(fn===readWorkspaceLinkDOM)return{kind:'ready',available:true,href:'/workspace/'+(args[0]==='Model'?'generate':'animate')+'/'+ID};
    if(fn===readWorkspaceDOM)return{kind:'ready',settings:{},button_enabled:true,quoted_credits:20,module:args[0],asset_id:ID};
    if(fn===readAnimationDOM)return structuredClone(data);
    if(fn===readAssetDOM)return{kind:'ready',status:'ready',asset_id:ID,export_enabled:true};
    if(fn===readExportOptionsDOM)return owned?structuredClone(exp):{kind:'pending'};
    if(fn===readExportTargetDOM)return{kind:'ready',nth:0,pointer_ready:!obscured};
    if(fn===readExportListDOM)return list===null?{kind:'pending'}:{kind:'ready',options:(list===0?['USD','FBX','OBJ','STL','GLB','3MF']:['512','1k','2k','4k','8k Current']).map(label=>({label,disabled:false,selected:label.replace(/ Current$/,'')===exp.settings[list===0?'format':'texture_resolution']}))};
    if(fn===readOwnExportClosedDOM)return{kind:owned?'pending':'ready'};
    if(fn===readOwnExportCloseDOM)return{kind:'ready',pointer_ready:true};
    if(fn===readExportListClosedDOM)return{kind:list===null?'ready':'pending'};
    assert.fail('Unreviewed DOM reader '+fn.name);
  },click:async(selector,opts)=>{
    calls.push(['click',selector,opts]);
    if(selector.startsWith('a[href=')){route=selector.includes('/generate/')?'generate':'animate';return;}
    if(selector==='main button'){owned=true;return;}
    if(selector.includes('i-tripo:close')){owned=false;return;}
    if(selector.endsWith('[role="combobox"]')){list=opts.nth;return;}
    if(selector.startsWith('[role="listbox"]')){
      // Match the last requested target read, injected by wrapper below.
      const label=page.lastTarget.label.replace(/ Current$/,'');
      if(!brokenSetting)exp.settings[list===0?'format':'texture_resolution']=label;
      list=null;
      exp.variants=exp.settings.format==='FBX'?['Blender','Mixamo','3dsmax'].map((label,nth)=>({nth,label,selected:nth===0?'true':'false'})):[];
      exp.settings.fbx_variant=exp.variants.length?'Blender':null;
      exp.settings.vertex_colors=exp.settings.format==='OBJ'?false:null;
      exp.switches=[{nth:0,label:'Export Skeleton',checked:String(exp.settings.export_skeleton),disabled:false},...(exp.settings.format==='OBJ'?[{nth:1,label:'Export Vertex Colors',checked:'false',disabled:false}]:[])];return;
    }
    if(selector.endsWith('button[aria-pressed]')){exp.settings.fbx_variant=page.lastTarget.label;return;}
    assert.fail('Unexpected click '+selector);
  },fillText:async(selector,value)=>{calls.push(['fill',selector,value]);if(bridgeFailure)throw new Error('FAKE_TOKEN_SECRET');if(brokenSetting)return;
    if(selector.includes('textarea')){data.settings.prompt=value;data.button_enabled=!!value.trim();}else data.settings.duration=Number(value);},
    setChecked:async(selector,value,opts)=>{calls.push(['check',selector,value,opts]);if(bridgeFailure)throw new Error('FAKE_TOKEN_SECRET');if(brokenSetting)return;
      const control=exp.switches[opts.nth];control.checked=String(value);exp.settings[control.label==='Export Skeleton'?'export_skeleton':'vertex_colors']=value;},
    focus:async selector=>calls.push(['focus',selector]),cdp:async(method,params)=>{calls.push(['cdp',method,params]);if(params.type==='rawKeyDown'&&!brokenSetting)data.settings.duration+=params.key==='ArrowUp'?1:-1;},
    pressKey:async(key)=>{calls.push(['key',key]);if(key==='Escape'){if(list!==null)list=null;else owned=false;}},goto:()=>assert.fail('No cold route guesses')};
  const evaluate=page.evaluate;page.evaluate=async(fn,...args)=>{if(fn===readExportTargetDOM)page.lastTarget=args[0];return{session:'fake',data:await evaluate(fn,...args)};};
  return page;
}
test('new UI pin includes all imported sources without changing old adapter files',()=>{
  assert.equal(uiOptionsDigest().length,64);checkUIOptionsPin(uiOptionsDigest());
  for(const pin of ['',null,'a'.repeat(64)])assert.throws(()=>checkUIOptionsPin(pin),e=>e.code==='definition_changed');
  const source=readFileSync(new URL('../examples/opencli/tripo-studio/ui-options.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(source,/getCookies|fetch\(|localStorage|sessionStorage|waitForDownload|claimedOperation|\.unlink|rmtree/);
});
test('settings reject malformed objects, injected selectors, bounds and cross-format fields',()=>{
  for(const[op,value]of [['animation','{'],['animation',[]],['animation',{duration:0}],['animation',{duration:11}],['animation',{duration:1.1}],['animation',{prompt:null}],['animation',{prompt:'x'.repeat(1001)}],['animation',{expected_prompt_sha256:'f'.repeat(64)}],['export',{format:'GLTF'}],['export',{texture_resolution:'16k'}],['export',{export_skeleton:'false'}],['export',{format:'OBJ',fbx_variant:'Mixamo'}],['export',{format:'FBX',vertex_colors:true}],['export',{selector:'button'}],['other',{}]])assert.throws(()=>parseUISettings(op,value),e=>e.code==='invalid_argument');
  assert.deepEqual(parseUISettings('animation','{"duration":1}'),{duration:1});
  assert.deepEqual(parseUISettings('export',{format:'OBJ',vertex_colors:false}),{format:'OBJ',vertex_colors:false});
});
test('an existing dialog prevents all new option navigation and UI changes',async()=>{
  for(const run of [inspectAnimation,prepareAnimation,inspectExportOptions,prepareExportOptions]){
    const p=pageFixture({existingDialog:true});await assert.rejects(run(p,{asset:ID,settings:{}}),e=>e.code==='dialog_open');assert.deepEqual(p.calls,[]);
  }
});
test('animation distinguishes empty draft, rig prerequisite and ready form, not completed motion',async()=>{
  for(const[state,patch]of [['draft_empty',{}],['rig_prerequisite_missing',{rig_prerequisite_missing:true,warnings:['Rig the Model First'],input_enabled:false}],['ready',{settings:{prompt:'walk',duration:5},button_enabled:true}]]){
    const p=pageFixture({motion:{...MOTION,...patch}}),out=(await inspectAnimation(p,{asset:ID}))[0];
    assert.equal(out.status,state);assert.equal(out.paid_submitted,false);assert.equal(out.quote_sha256.length,64);assert.equal(out.presets.length,2);assert.deepEqual(p.calls,[]);
  }
});
test('animation preparation reads back prompt/duration and never clicks generation',async()=>{
  const p=pageFixture(),before=animationQuoteHash(MOTION),out=(await prepareAnimation(p,{asset:ID,settings:{prompt:'Make the character walk in place.',duration:3}}))[0];
  assert.equal(out.settings.duration,3);assert.equal(out.status,'ready');assert.notEqual(out.quote_sha256,before);assert.equal(out.prompt_sha256,sha(out.settings.prompt));
  assert.equal(p.calls.filter(c=>c[0]==='fill').length,1);assert.equal(p.calls.some(c=>c[0]==='click'),false);
  const native=p.calls.filter(c=>c[0]==='cdp');assert.equal(native.length,4);assert.equal(native[0][2].windowsVirtualKeyCode,40);assert.equal(native[0][2].code,'ArrowDown');
});
test('numeric preparation fails before draft edits on a backend without native keyboard support',async()=>{
  const p=pageFixture();delete p.cdp;
  await assert.rejects(prepareAnimation(p,{asset:ID,settings:{duration:3,prompt:'fixture'}}),e=>e.code==='unsupported_backend');assert.deepEqual(p.calls,[]);
});
test('existing prompt replacement and clearing require the exact current digest',async()=>{
  for(const requested of ['new','']){
    const motion={...MOTION,settings:{prompt:'human draft',duration:5},button_enabled:true};
    const p=pageFixture({motion});await assert.rejects(prepareAnimation(p,{asset:ID,settings:{prompt:requested}}),e=>e.code==='draft_present');assert.deepEqual(p.calls,[]);
    const allowed=pageFixture({motion});assert.equal((await prepareAnimation(allowed,{asset:ID,settings:{prompt:requested,expected_prompt_sha256:sha('human draft')}}))[0].settings.prompt,requested);
  }
});
test('invalid input and rig prerequisite stop before form preparation',async()=>{
  for(const settings of [{duration:0},{selector:'Generate'}]){const p=pageFixture();await assert.rejects(prepareAnimation(p,{asset:ID,settings}),e=>e.code==='invalid_argument');assert.deepEqual(p.calls,[]);}
  const p=pageFixture({motion:{...MOTION,rig_prerequisite_missing:true}});await assert.rejects(prepareAnimation(p,{asset:ID,settings:{prompt:'walk'}}),e=>e.code==='prerequisite_missing');assert.deepEqual(p.calls,[]);
});
test('animation readback mismatch and changed source fail instead of reporting prepared',async()=>{
  const p=pageFixture({brokenSetting:true});await assert.rejects(prepareAnimation(p,{asset:ID,settings:{duration:3}}),e=>e.code==='settings_changed');
  const q=pageFixture({motion:{...MOTION,asset_id:OTHER}});await assert.rejects(inspectAnimation(q,{asset:ID}),e=>e.code==='asset_changed');assert.deepEqual(q.calls,[]);
});
test('export inspection reports six actual formats with unknown price and closes its own modal',async()=>{
  const p=pageFixture(),out=(await inspectExportOptions(p,{asset:ID}))[0];
  assert.equal(out.available_formats.length,6);assert.equal(out.available_texture_resolutions.length,5);assert.equal(out.settings.export_skeleton,true);
  assert.equal(out.download_started,false);assert.equal(out.quoted_credits,null);assert.equal(out.dialog_closed,true);assert.equal(out.status,'observed');
  assert.equal(p.calls.filter(c=>c[0]==='key'&&c[1]==='Escape').length,0);assert.equal(p.calls.some(c=>c[1]?.includes('animate-button')),false);
});
for(const format of ['USD','FBX','OBJ','STL','GLB','3MF'])test('export prepares and verifies '+format+' without download',async()=>{
  const p=pageFixture(),settings={format,texture_resolution:'2k',export_skeleton:false,...(format==='FBX'?{fbx_variant:'Mixamo'}:format==='OBJ'?{vertex_colors:true}:{})};
  const out=(await prepareExportOptions(p,{asset:ID,settings}))[0];
  for(const[k,v]of Object.entries(settings))assert.equal(out.settings[k],v);
  assert.equal(out.status,'prepared');assert.equal(out.download_started,false);assert.equal(out.options_lifetime,'ui_may_remember_options_recheck_before_any_export');
  assert.equal(p.calls.some(c=>c[1]?.includes('animate-button')),false);
});
test('covered export target stops before the opening click',async()=>{
  const p=pageFixture({obscured:true});await assert.rejects(inspectExportOptions(p,{asset:ID}),e=>e.code==='control_obscured');assert.equal(p.calls.filter(c=>c[1]==='main button').length,0);
});
test('format-specific setting unavailable closes own dialog with a typed failure',async()=>{
  const p=pageFixture();await assert.rejects(prepareExportOptions(p,{asset:ID,settings:{vertex_colors:true}}),e=>e.code==='setting_unavailable');
  assert.equal((await p.evaluate(readExportOptionsDOM)).data.kind,'pending');assert.equal(p.calls.some(c=>c[1]?.includes('animate-button')),false);
});
test('export readback mismatch preserves an error and still closes only owned modal',async()=>{
  const p=pageFixture({brokenSetting:true});await assert.rejects(prepareExportOptions(p,{asset:ID,settings:{export_skeleton:false}}),e=>e.code==='settings_changed');assert.equal((await p.evaluate(readExportOptionsDOM)).data.kind,'pending');
});
test('bridge failure propagates and cleanup does not fabricate success',async()=>{
  const p=pageFixture({bridgeFailure:true});await assert.rejects(prepareExportOptions(p,{asset:ID,settings:{export_skeleton:false}}));assert.equal((await p.evaluate(readExportOptionsDOM)).data.kind,'pending');
});

function animationDOMFixture({prompt='',duration='5',min='1',max='10',warning='',disabled=false}={}) {
  const input=(value)=>({value,disabled:false,getAttribute:n=>n==='min'?min:n==='max'?max:null});
  const text=input(prompt),number=input(duration),range=input(duration),action={innerText:'Generate\n20',disabled,getAttribute:()=>null};
  const p={innerText:'Animation\n'+warning,getClientRects:()=>[1],querySelector:()=>({innerText:'Animation'}),querySelectorAll:s=>s.startsWith('textarea')?[text]:s.includes('number')?[number]:s.includes('range')?[range]:s==='button.animate-button'?[action]:s.includes('tabpanel')?[{innerText:'walk',getClientRects:()=>[1]}]:[]};
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/animate/'+ID};globalThis.document={querySelectorAll:()=>[p]};return{p,range,number,action};
}
test('actual animation DOM reads synchronized duration bounds and source prerequisite',()=>{
  animationDOMFixture({warning:'Rig the Model First\nRig the Model First',disabled:true});const out=readAnimationDOM();
  assert.equal(out.kind,'ready');assert.equal(out.rig_prerequisite_missing,true);assert.equal(out.button_enabled,false);assert.deepEqual(out.warnings,['Rig the Model First']);
  assert.deepEqual(out.duration_bounds,{min:1,max:10});assert.deepEqual(out.presets,['walk']);
});
test('animation drifted limits, mismatched range and unknown price fail clearly',()=>{
  animationDOMFixture({max:'30'});assert.equal(readAnimationDOM().kind,'animation_fields_changed');
  const f=animationDOMFixture();f.range.value='4';assert.equal(readAnimationDOM().kind,'animation_fields_changed');
  const g=animationDOMFixture();g.action.innerText='Generate Free';assert.equal(readAnimationDOM().kind,'animation_price_changed');
  animationDOMFixture();location.origin='https://other.example';assert.equal(readAnimationDOM().kind,'origin_mismatch');
});
test('animation quote binds exact source, draft, duration, price and warnings',()=>{
  for(const change of [{asset_id:OTHER},{settings:{prompt:'',duration:4}},{settings:{prompt:'changed',duration:5}},{quoted_credits:40},{warnings:['new warning']}])assert.notEqual(animationQuoteHash({...MOTION,...change}),animationQuoteHash(MOTION));
});
test('UI context and own-dialog closure wait for closed layers to leave layout, preserve changed source',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate/'+ID};
  const closed={getBoundingClientRect:()=>({width:100,height:100}),getClientRects:()=>[1],getAttribute:()=> 'closed'};
  globalThis.document={querySelectorAll:()=>[closed]};assert.equal(readUIContextDOM().dialogs,1);assert.equal(readOwnExportClosedDOM(ID).kind,'pending');
  closed.getClientRects=()=>[];closed.getBoundingClientRect=()=>({width:0,height:0});
  assert.equal(readUIContextDOM().dialogs,0);assert.equal(readOwnExportClosedDOM(ID).kind,'ready');
  location.pathname='/workspace/generate/'+OTHER;assert.equal(readOwnExportClosedDOM(ID).kind,'asset_changed');
});
test('export target pointer guard checks a live hit before dispatch',()=>{
  const b={innerText:'Export',getClientRects:()=>[1],getBoundingClientRect:()=>({x:0,y:0,width:100,height:20}),getAttribute:()=>null,closest:()=>null,contains:()=>false};
  globalThis.document={querySelectorAll:()=>[b],elementFromPoint:()=>({})};assert.equal(readExportTargetDOM({kind:'open',label:'Export'}).pointer_ready,false);
  document.elementFromPoint=()=>b;assert.equal(readExportTargetDOM({kind:'open',label:'Export'}).pointer_ready,true);
});
function exportDOMFixture({format='GLB',checked='false',duplicate=false}={}) {
  const switchNode={disabled:false,parentElement:{innerText:'Export Skeleton'},getAttribute:n=>n==='aria-checked'?checked:null};
  const combos=[{innerText:format},{innerText:'4k'}],action={innerText:'Export',disabled:false,getAttribute:()=>null};
  const variants=format==='FBX'?['Blender','Mixamo','3dsmax'].map((label,nth)=>({innerText:label,getAttribute:()=>nth===0?'true':'false'})):[];
  const d={getClientRects:()=>[1],getAttribute:()=> 'open',querySelector:()=>({value:'fixture'}),querySelectorAll:s=>s==='[role="combobox"]'?combos:s==='button.animate-button'?[action]:s==='[role="switch"]'?(duplicate?[switchNode,switchNode]:[switchNode]):s==='button[aria-pressed]'?variants:s==='button'?[{innerText:'0',getAttribute:()=>null}]:[]};
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate/'+ID};globalThis.document={querySelectorAll:()=>[d]};return{d,combos,action,variants};
}
test('export DOM preserves false skeleton state rather than confusing absent and false',()=>{
  exportDOMFixture();const out=readExportOptionsDOM();assert.equal(out.kind,'ready');assert.equal(out.settings.export_skeleton,false);assert.equal(out.settings.vertex_colors,null);assert.equal(out.settings.animation_count,0);
  exportDOMFixture({checked:'true'});assert.equal(readExportOptionsDOM().settings.export_skeleton,true);
  const f=exportDOMFixture();const query=f.d.querySelectorAll;f.d.querySelectorAll=s=>s==='[role="switch"]'?[]:query(s);assert.equal(readExportOptionsDOM().settings.export_skeleton,null);
});
test('export DOM rejects repeated switches, unobserved formats and variant drift',()=>{
  exportDOMFixture({duplicate:true});assert.equal(readExportOptionsDOM().kind,'export_fields_changed');
  exportDOMFixture({format:'GLTF'});assert.equal(readExportOptionsDOM().kind,'export_fields_changed');
  const f=exportDOMFixture({format:'FBX'});assert.equal(readExportOptionsDOM().settings.fbx_variant,'Blender');f.variants[1].getAttribute=()=> 'true';assert.equal(readExportOptionsDOM().kind,'export_fields_changed');
});
test('numeric 512 texture combobox is not an animation-count control',()=>{
  const f=exportDOMFixture({format:'USD'}),query=f.d.querySelectorAll;
  f.combos[1].innerText='512';f.d.querySelectorAll=s=>s==='button'?[{innerText:'512',getAttribute:()=> 'combobox'},...query(s)]:query(s);
  const out=readExportOptionsDOM();assert.equal(out.kind,'ready');assert.equal(out.settings.texture_resolution,'512');assert.equal(out.settings.animation_count,0);
});
test('export list DOM retains disabled/selected evidence and rejects duplicate option labels',()=>{
  const items=['4k','8k Current'].map(label=>({innerText:label,getAttribute:n=>n==='aria-selected'?'true':'false'}));
  const list={getClientRects:()=>[1],getAttribute:()=> 'open',querySelectorAll:()=>items};globalThis.document={querySelectorAll:()=>[list]};
  const data=readExportListDOM();assert.equal(data.kind,'ready');assert.equal(data.options[1].label,'8k Current');
  items.push(items[0]);assert.equal(readExportListDOM().kind,'export_list_changed');document.querySelectorAll=()=>[];assert.equal(readExportListDOM().kind,'pending');
});
test('closing old format list is not mistaken for newly opening texture list',()=>{
  const items=['USD','FBX','OBJ','STL','GLB','3MF'].map(label=>({innerText:label,getAttribute:()=>null}));
  const list={getClientRects:()=>[1],getAttribute:()=> 'open',querySelectorAll:()=>items};globalThis.document={querySelectorAll:()=>[list]};
  assert.equal(readExportListDOM(0).kind,'ready');assert.equal(readExportListDOM(1).kind,'pending');assert.equal(readExportListClosedDOM().kind,'pending');
  list.getAttribute=()=> 'closed';assert.equal(readExportListDOM(0).kind,'pending');assert.equal(readExportListClosedDOM().kind,'pending');
  list.getClientRects=()=>[];assert.equal(readExportListClosedDOM().kind,'ready');
});
