import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {imageFormDigest,checkImageFormPin,parseImageFormSettings,imageDraftHash,readImageFormDOM,readImageContextDOM,readImageChoicesDOM,readImageLayerClosedDOM,readImageTargetDOM,inspectImageForm,prepareImageForm,IMAGE_MODELS,IMAGE_TEMPLATES} from '../examples/opencli/tripo-studio/image-form.mjs';
import {readLocation} from '../examples/opencli/tripo-studio/extended.mjs';
import {readWorkspaceDOM,readWorkspaceLinkDOM} from '../examples/opencli/tripo-studio/workspace.mjs';
const ID='11111111-2222-3333-4444-555555555555';
const settings=()=>({model:'GPT Image 2.5',prompt:'',aspect_ratio:null,number_images:4,resolution_4k:false,template:null});
function fixture({existing=false,obscured=false,resolutionObscured=false,wrong=false,cleanup=false,refChange=false,fileChange=false}={}){
  const p={calls:[],data:{kind:'ready',asset_id:ID,settings:settings(),references:[],file_counts:[0],controls:{aspect_ratios:['1:1','16:9','9:16','4:3','3:4'].map(value=>({value,disabled:false})),number_images:[1,2,3,4].map(value=>({value,disabled:false})),resolution_4k:{disabled:false},prompt_enabled:true},button_enabled:false,action_label:'Generate Image',billing_observation:{free_allowance:'Free 14/1000',quoted_credits:null,quote_known:false}}};
  let layer=null,scrolled=false;const remembered=settings();
  p.evaluate=async(fn,arg)=>{let d;
    if(fn===readImageContextDOM)d={origin:'https://studio.tripo3d.ai',path:'/workspace/generate-image/'+ID,layers:existing||layer?1:0};
    else if(fn===readLocation)d={origin:'https://studio.tripo3d.ai',path:'/workspace/generate-image/'+ID};
    else if(fn===readWorkspaceLinkDOM)d={kind:'ready',available:true,href:'/workspace/generate-image/'+ID,nth:0};
    else if(fn===readWorkspaceDOM)d={kind:'ready',module:'image',asset_id:ID,settings:{},button_enabled:false,quoted_credits:null};
    else if(fn===readImageFormDOM)d=structuredClone(p.data);
    else if(fn===readImageChoicesDOM)d={kind:'ready',options:(arg==='model'?IMAGE_MODELS:IMAGE_TEMPLATES).map(label=>({label,disabled:false,selected:label===p.data.settings[arg==='model'?'model':'template']}))};
    else if(fn===readImageLayerClosedDOM)d={kind:layer===arg?'pending':'ready'};
    else if(fn===readImageTargetDOM){p.target=arg;d={kind:'ready',nth:0,pointer_ready:!obscured&&!(arg.kind==='resolution'&&resolutionObscured&&!scrolled)};}
    else assert.fail('Unexpected reader '+fn.name);
    return{session:'fixture',data:d};
  };
  p.click=async(selector,opts)=>{p.calls.push(['click',selector,opts]);const{kind,label}=p.target;
    if(kind==='model'||kind==='template'){layer=kind;return;}
    if(kind==='template_close'){if(cleanup)throw Error('local cleanup failure');layer=null;return;}
    if(wrong)return;
    if(kind==='model_option'){p.data.settings.model=label;layer=null;if(refChange)p.data.references.push({src:'https://fixture.invalid/changed'});
      if(label==='Midjourney v8.2'){p.data.file_counts=[];for(const k of ['aspect_ratio','number_images','resolution_4k']){remembered[k]=p.data.settings[k];p.data.settings[k]=null;}}else {p.data.file_counts=[0];for(const k of ['aspect_ratio','number_images','resolution_4k'])if(p.data.settings[k]===null&&k!=='aspect_ratio')p.data.settings[k]=remembered[k];}}
    if(kind==='template_option')p.data.settings.template=p.data.settings.template===label?null:label;
    if(kind==='toggle'){if(label.includes(':'))p.data.settings.aspect_ratio=p.data.settings.aspect_ratio===label?null:label;else p.data.settings.number_images=Number(label);}
    if(kind==='resolution')p.data.settings.resolution_4k=!p.data.settings.resolution_4k;
  };
  p.focus=async(selector,opts)=>{p.calls.push(['focus',selector,opts]);};
  p.pressKey=async(key)=>{p.calls.push(['key',key]);if(cleanup)throw Error('local cleanup failure');if(key!=='End')layer=null;};
  p.cdp=async(method,params)=>{p.calls.push(['cdp',method,params]);assert.equal(method,'Input.dispatchKeyEvent');if(params.type==='keyUp'&&params.key==='End'&&params.windowsVirtualKeyCode===35)scrolled=true;};
  p.fillText=async(selector,value)=>{p.calls.push(['fill',selector,value]);if(!wrong)p.data.settings.prompt=value;if(fileChange)p.data.file_counts=[];};
  p.setChecked=async(selector,value)=>{p.calls.push(['checked',selector,value]);if(!wrong)p.data.settings.resolution_4k=value;};
  return p;
}
test('image source integrity and strict semantic settings',()=>{
  checkImageFormPin(imageFormDigest());assert.throws(()=>checkImageFormPin('0'.repeat(64)),e=>e.code==='definition_changed');
  const bind={expected_draft_sha256:'a'.repeat(64)};
  assert.equal(parseImageFormSettings({...bind,prompt:'x'.repeat(10000)}).prompt.length,10000);
  for(const value of [null,[],{}, {...bind,url:'https://other.invalid'}, {...bind,model:'other'}, {...bind,aspect_ratio:'auto'}, {...bind,number_images:0},{...bind,number_images:1.2},{...bind,resolution_4k:1},{...bind,template:'other'},{...bind,prompt:'x'.repeat(10001)}])assert.throws(()=>parseImageFormSettings(value),e=>e.code==='invalid_argument');
  assert.throws(()=>parseImageFormSettings('{bad'),e=>e.code==='invalid_argument');
  assert.throws(()=>parseImageFormSettings({...bind,model:'Midjourney v8.2',number_images:1}),e=>e.code==='setting_unavailable');
});
test('inspection opens and closes only its own model and template choices',async()=>{
  const p=fixture(),d=(await inspectImageForm(p,{asset:ID}))[0];assert.equal(d.available_models.length,6);assert.equal(d.available_templates.length,9);assert.equal(d.settings.aspect_ratio,null);assert.equal(d.billing_observation.quoted_credits,null);assert.equal(d.paid_submitted,false);assert.equal(d.upload_started,false);assert.equal(d.download_started,false);
  assert.equal(p.calls.some(c=>/Generate|Export|Upload|Regenerate/.test(c[1])),false);
});
test('preexisting layers and blocked pointer preserve state',async()=>{
  const p=fixture({existing:true});await assert.rejects(inspectImageForm(p,{asset:ID}),e=>e.code==='dialog_open');assert.deepEqual(p.calls,[]);
  const q=fixture({obscured:true});await assert.rejects(inspectImageForm(q,{asset:ID}),e=>e.code==='control_obscured');assert.deepEqual(q.calls,[]);
});
test('stale draft rejects before setting changes',async()=>{
  const p=fixture();await assert.rejects(prepareImageForm(p,{asset:ID,settings:{model:'Nano Banana',expected_draft_sha256:'0'.repeat(64)}}),e=>e.code==='draft_changed');assert.equal(p.data.settings.model,'GPT Image 2.5');
});
for(const ratio of ['1:1','16:9','9:16','4:3','3:4'])test('ratio '+ratio+' uses stable value marker, not hovered innerText',async()=>{
  const p=fixture(),d=(await prepareImageForm(p,{asset:ID,settings:{aspect_ratio:ratio,expected_draft_sha256:imageDraftHash(p.data)}}))[0];assert.equal(d.settings.aspect_ratio,ratio);assert.equal(d.status,'prepared');
  assert.ok(p.calls.some(c=>c[0]==='click'&&c[1].includes('button[value][aria-pressed]')));
});
test('clear selected ratio and template restores null without upload',async()=>{
  const p=fixture();p.data.settings.aspect_ratio='1:1';p.data.settings.template='T Pose';const d=(await prepareImageForm(p,{asset:ID,settings:{aspect_ratio:null,template:null,expected_draft_sha256:imageDraftHash(p.data)}}))[0];assert.equal(d.settings.aspect_ratio,null);assert.equal(d.settings.template,null);assert.equal(d.upload_started,false);
});
for(const count of [1,2,3,4])test('image count '+count+' readback',async()=>{
  const p=fixture(),d=(await prepareImageForm(p,{asset:ID,settings:{number_images:count,expected_draft_sha256:imageDraftHash(p.data)}}))[0];assert.equal(d.settings.number_images,count);
});
for(const template of IMAGE_TEMPLATES)test('template '+template+' prepared without changing reference files',async()=>{
  const p=fixture(),d=(await prepareImageForm(p,{asset:ID,settings:{template,expected_draft_sha256:imageDraftHash(p.data)}}))[0];assert.equal(d.settings.template,template);assert.deepEqual(d.references,[]);assert.equal(d.upload_started,false);
});
test('prompt, 4K and full exact digest support restoration',async()=>{
  const p=fixture();let d=(await prepareImageForm(p,{asset:ID,settings:{prompt:'fixture blue square',resolution_4k:true,expected_draft_sha256:imageDraftHash(p.data)}}))[0];assert.equal(d.settings.prompt,'fixture blue square');assert.equal(d.settings.resolution_4k,true);
  d=(await prepareImageForm(p,{asset:ID,settings:{prompt:'',resolution_4k:false,expected_draft_sha256:d.draft_sha256}}))[0];assert.equal(d.settings.prompt,'');assert.equal(d.settings.resolution_4k,false);
});
test('4K uses one observed click and fresh DOM readback',async()=>{
  const p=fixture();p.setChecked=async()=>{throw Error('Custom switch SDK state shortcut failed');};
  const d=(await prepareImageForm(p,{asset:ID,settings:{resolution_4k:true,expected_draft_sha256:imageDraftHash(p.data)}}))[0];
  assert.equal(d.settings.resolution_4k,true);assert.equal(p.calls.filter(c=>c[0]==='click'&&c[1].includes('[role="switch"]')).length,1);
  assert.equal(p.calls.filter(c=>c[0]==='checked').length,0);
});
test('fixed footer covering 4K uses native End virtual code and fresh hit test',async()=>{
  const p=fixture({resolutionObscured:true}),d=(await prepareImageForm(p,{asset:ID,settings:{resolution_4k:true,expected_draft_sha256:imageDraftHash(p.data)}}))[0];
  assert.equal(d.settings.resolution_4k,true);assert.deepEqual(d.resolution_preparation,{viewport_repair:'focus_end',requested:true,verified_value:true});
  assert.equal(p.calls.filter(c=>c[0]==='focus'&&c[1].includes('[role="switch"]')).length,1);
  assert.deepEqual(p.calls.filter(c=>c[0]==='cdp').map(c=>c[2]),['rawKeyDown','keyUp'].map(type=>({type,key:'End',code:'End',windowsVirtualKeyCode:35})));
});
test('covered 4K fails distinctly on a backend without native key support',async()=>{
  const p=fixture({resolutionObscured:true});delete p.cdp;
  await assert.rejects(prepareImageForm(p,{asset:ID,settings:{resolution_4k:true,expected_draft_sha256:imageDraftHash(p.data)}}),e=>e.code==='unsupported_backend');
  assert.equal(p.calls.filter(c=>c[0]==='click'&&c[1].includes('[role="switch"]')).length,0);
});
test('unresolved 4K covering still fails without a switch click',async()=>{
  const p=fixture(),evaluate=p.evaluate;p.evaluate=async(fn,arg)=>{const d=await evaluate(fn,arg);if(fn===readImageTargetDOM&&arg.kind==='resolution')d.data.pointer_ready=false;return d;};
  await assert.rejects(prepareImageForm(p,{asset:ID,settings:{resolution_4k:true,expected_draft_sha256:imageDraftHash(p.data)}}),e=>e.code==='control_obscured');
  assert.equal(p.calls.filter(c=>c[0]==='click'&&c[1].includes('[role="switch"]')).length,0);
});
test('hidden Midjourney controls report null and implicit changes, never invented values',async()=>{
  const p=fixture(),d=(await prepareImageForm(p,{asset:ID,settings:{model:'Midjourney v8.2',expected_draft_sha256:imageDraftHash(p.data)}}))[0];assert.equal(d.settings.number_images,null);assert.equal(d.settings.resolution_4k,null);assert.deepEqual(d.implicit_changes.number_images,{before:4,after:null});
  assert.deepEqual(d.file_counts,[]);assert.deepEqual(d.implicit_control_changes.file_input_count,{before:1,after:0});
});
test('restoring Midjourney restores the observed empty file input, not uploaded files',async()=>{
  const p=fixture();let d=(await prepareImageForm(p,{asset:ID,settings:{model:'Midjourney v8.2',expected_draft_sha256:imageDraftHash(p.data)}}))[0];
  d=(await prepareImageForm(p,{asset:ID,settings:{model:'GPT Image 2.5',expected_draft_sha256:d.draft_sha256}}))[0];
  assert.deepEqual(d.file_counts,[0]);assert.deepEqual(d.implicit_control_changes.file_input_count,{before:0,after:1});
});
test('non-model empty input loss and nonempty FileList loss still fail',async()=>{
  const p=fixture({fileChange:true});await assert.rejects(prepareImageForm(p,{asset:ID,settings:{prompt:'fixture',expected_draft_sha256:imageDraftHash(p.data)}}),e=>e.code==='draft_changed');
  const q=fixture();q.data.file_counts=[1];await assert.rejects(prepareImageForm(q,{asset:ID,settings:{model:'Midjourney v8.2',expected_draft_sha256:imageDraftHash(q.data)}}),e=>e.code==='draft_changed');
});
test('a new nonempty FileList or unexpected input shape is not a model visibility change',async()=>{
  for(const counts of [[1],[0,0]]){const p=fixture(),click=p.click;p.click=async(...args)=>{await click(...args);if(p.target.kind==='model_option')p.data.file_counts=counts;};
    await assert.rejects(prepareImageForm(p,{asset:ID,settings:{model:'Midjourney v8.2',expected_draft_sha256:imageDraftHash(p.data)}}),e=>e.code==='draft_changed');}
});
test('wrong readback, reference changes and owned-layer cleanup fail distinctly',async()=>{
  const p=fixture({wrong:true});await assert.rejects(prepareImageForm(p,{asset:ID,settings:{number_images:1,expected_draft_sha256:imageDraftHash(p.data)}}),e=>e.code==='settings_changed');
  const q=fixture({refChange:true});await assert.rejects(prepareImageForm(q,{asset:ID,settings:{model:'Nano Banana',expected_draft_sha256:imageDraftHash(q.data)}}),e=>e.code==='draft_changed');
  const r=fixture({cleanup:true});await assert.rejects(inspectImageForm(r,{asset:ID}),e=>e.code==='cleanup_failed');
});
function element(attrs={},text=''){return{innerText:text,value:'',disabled:false,parentElement:{innerText:'',querySelector:()=>null,parentElement:{innerText:'4K Resolution',querySelector:s=>s==='p'?{innerText:'4K Resolution'}:null}},getAttribute:k=>attrs[k]??null,hasAttribute:k=>Object.hasOwn(attrs,k),getClientRects:()=>[{}],getBoundingClientRect:()=>({x:0,y:0,width:10,height:10}),contains:()=>true};}
function domFixture({hover=false,model='GPT Image 2.5',duplicate=false,fileUnknown=false,wrongSwitchLabel=false}={}){
  const prompt=element({maxlength:'10000'}),combo=element({},model),action=element({},'Generate Image');prompt.value='fixture';action.disabled=false;
  const ratios=['1:1','16:9','9:16','4:3','3:4'].map((v,i)=>element({value:v,'aria-pressed':i===0?'true':'false','data-state':i===0?'on':'off'},hover&&i===0?'':v));
  const counts=[1,2,3,4].map(v=>element({value:String(v),'aria-pressed':v===4?'true':'false','data-state':v===4?'on':'off'},String(v))),sw=element({'aria-checked':'false'}),file=element();if(!fileUnknown)file.files={length:0};
  if(wrongSwitchLabel)sw.parentElement.parentElement.querySelector=()=>({innerText:'Other setting'});
  const panel={...element({},'Generate Image\nFree 14/1000'),querySelector:s=>s==='h2'?element({},'Generate Image'):null,querySelectorAll:s=>s==='textarea'?[prompt]:s==='[role="combobox"]'?[combo]:s==='button.animate-button'?[action]:s==='button[value][aria-pressed]'?(model==='Midjourney v8.2'?[]:[...ratios,...counts,...(duplicate?[ratios[0]]:[])]):s==='[role="switch"]'?(model==='Midjourney v8.2'?[]:[sw]):s==='input[type="file"]'?[file]:[]};
  return{location:{origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate-image/'+ID},URL,document:{querySelectorAll:s=>s==='div.rounded-r-5:has(h2)'?[panel]:[],querySelector:()=>panel,elementFromPoint:()=>ratios[0]}};
}
test('serialized real DOM reader survives hovered hidden ratio text',()=>{
  const d=vm.runInNewContext('('+readImageFormDOM.toString()+')()',domFixture({hover:true}));assert.equal(d.kind,'ready');assert.equal(d.settings.aspect_ratio,'1:1');assert.equal(d.billing_observation.quoted_credits,null);
});
test('serialized DOM reader distinguishes absent model controls and changed fields',()=>{
  const run=o=>vm.runInNewContext('('+readImageFormDOM.toString()+')()',domFixture(o));assert.equal(run({model:'Midjourney v8.2'}).settings.number_images,null);assert.equal(run({duplicate:true}).kind,'image_form_changed');assert.equal(run({fileUnknown:true}).kind,'image_references_changed');
});
test('real wrapper fix retains the exact 4K label assertion',()=>{
  const d=vm.runInNewContext('('+readImageFormDOM.toString()+')()',domFixture({wrongSwitchLabel:true}));assert.equal(d.kind,'image_form_changed');
});
function choiceDom({kind='model',selected=1,duplicate=false,hidden=false,heading='Templates',disabled=false}={}){
  const labels=kind==='model'?IMAGE_MODELS:IMAGE_TEMPLATES;
  const items=labels.map((name,i)=>element({'aria-selected':i<selected?'true':'false','data-state':i<selected?'on':'off',...(disabled&&i===0?{'data-disabled':''}:{})},name));
  if(duplicate)items.push(items[0]);
  const layer={...element({},heading+'\nCategory'),querySelectorAll:()=>items};
  if(hidden)layer.getBoundingClientRect=()=>({x:0,y:0,width:0,height:0});
  return{document:{querySelectorAll:()=>hidden?[]:[layer]}};
}
test('serialized model choice reader verifies unique selected and disabled markers',()=>{
  const run=opts=>vm.runInNewContext('('+readImageChoicesDOM.toString()+')("model")',choiceDom(opts));
  const d=run({disabled:true});assert.equal(d.kind,'ready');assert.equal(d.options.length,6);assert.equal(d.options[0].selected,true);assert.equal(d.options[0].disabled,true);
  for(const opts of [{selected:0},{selected:2},{duplicate:true}])assert.equal(run(opts).kind,'image_choices_changed');
  assert.equal(run({hidden:true}).kind,'pending');
});
test('serialized template reader checks owned layer heading and single selection',()=>{
  const run=opts=>vm.runInNewContext('('+readImageChoicesDOM.toString()+')("template")',choiceDom({kind:'template',selected:0,...opts}));
  assert.equal(run({}).options.length,9);assert.equal(run({heading:'User dialog'}).kind,'image_choices_changed');assert.equal(run({selected:2}).kind,'image_choices_changed');
});
test('serialized context and layer-close readers inspect layout, not just DOM presence',()=>{
  const visible=element(),hidden=element();hidden.getBoundingClientRect=()=>({width:0,height:0});
  const dom={location:{origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate-image/'+ID},document:{querySelectorAll:()=>[visible,hidden]}};
  assert.equal(vm.runInNewContext('('+readImageContextDOM.toString()+')()',dom).layers,1);
  assert.equal(vm.runInNewContext('('+readImageLayerClosedDOM.toString()+')("template")',dom).kind,'pending');
  dom.document.querySelectorAll=()=>[hidden];
  assert.equal(vm.runInNewContext('('+readImageLayerClosedDOM.toString()+')("model")',dom).kind,'ready');
});
test('serialized target reader binds exact nth and rejects changed controls or covered pointer',()=>{
  const a=element({value:'1:1'}),b=element({value:'16:9'});
  const panel={querySelectorAll:()=>[a,b]};let hit=b;
  a.contains=b.contains=e=>e===a||e===b;
  const dom={document:{querySelector:()=>panel,elementFromPoint:()=>hit,querySelectorAll:()=>[]}};
  const run=(kind,label)=>vm.runInNewContext('('+readImageTargetDOM.toString()+')('+JSON.stringify({kind,label})+')',dom);
  assert.equal(run('toggle','16:9').nth,1);assert.equal(run('toggle','16:9').pointer_ready,true);
  hit=element();assert.equal(run('toggle','16:9').pointer_ready,false);
  assert.equal(run('toggle','9:16').kind,'image_control_changed');assert.equal(run('other','').kind,'invalid_argument');
});
test('draft hash binds actual references, files and source as well as settings',()=>{
  const p=fixture(),original=imageDraftHash(p.data);
  for(const changes of [{asset_id:'22222222-2222-3333-4444-555555555555'},{references:[{src:'https://fixture.invalid/reference'}]},{file_counts:[1]},{settings:{...p.data.settings,prompt:'changed'}}])assert.notEqual(imageDraftHash({...p.data,...changes}),original);
});
test('inspection detects unrelated draft changes while still closing its own layer',async()=>{
  const p=fixture(),click=p.click;p.click=async(...args)=>{await click(...args);if(p.target.kind==='template_close')p.data.settings.prompt='concurrent draft';};
  await assert.rejects(inspectImageForm(p,{asset:ID}),e=>e.code==='draft_changed');
  assert.equal(p.calls.filter(c=>c[0]==='click'&&c[1].includes('i-tripo:close')).length,1);
});
test('different source is rejected before catalog or setting clicks',async()=>{
  const p=fixture();p.data.asset_id='22222222-2222-3333-4444-555555555555';
  await assert.rejects(inspectImageForm(p,{asset:ID}),e=>e.code==='asset_changed');assert.deepEqual(p.calls,[]);
});
