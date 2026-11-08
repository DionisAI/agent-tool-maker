import test from 'node:test';
import assert from 'node:assert/strict';
import { queryDigest, checkQueryPin, queryScope, queryBounds, readQueryNavigationDOM, readQueryChoiceDOM, readQueryDOM,
  imageIdentity, parseQueryCards, queryAssets, readImagePreviewDOM, readPreviewCloseDOM, parsePreviewTarget, previewImage } from '../examples/opencli/tripo-studio/asset-query.mjs';
import { readAccountDOM } from '../examples/opencli/tripo-studio/core.mjs';
const ID='11111111-2222-3333-4444-555555555555',OTHER='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const IMAGE_SCOPE={asset_type:'Image',ownership:'Image Assets',filter:'All'};
const MODEL_SCOPE={asset_type:'Model',ownership:'My Assets',filter:'All'};
const image=(index=0,id=ID)=>({host:'tripo-data.rg1.data.tripo3d.com',path:`/generate-image/20261003/${id}/image${index===null?'':'_'+index}.png`,title:null});
const view=(index,id=ID)=>({host:'tripo-data.rg1.data.tripo3d.com',path:`/tripo-studio/20261003/${id}/multiview_${index}_${id}.jpeg`,title:null});
const model=(variant='mesh',id=ID)=>({host:'tripo-data-public.rg1.data.tripo3d.com',path:`/tripo-studio/20261003/${id}/studio_${variant}.webp`,title:'fixture'});
const cards=images=>images.map((images,nth)=>({nth,images}));
const FAST={quietMs:0,pause:0};
const ARGS={category:'Image',ownership:'Image Assets',filter:'All',limit:100,pages:2};
function fakePage(frames=cards([[image(0)]]),{scope=IMAGE_SCOPE,nav={},preview=null,incidentalPopover=false}={}) {
  const calls=[];let reads=0,closed=false,popover=incidentalPopover;
  const page={calls,evaluate:async(fn,...args)=>{
    if (fn===readQueryNavigationDOM) return {origin:'https://studio.tripo3d.ai',path:'/assets',links:['/assets'],dialog_open:false,...nav};
    if (fn===readAccountDOM) return {kind:'ready',credits:100};
    if (fn===readQueryChoiceDOM) return {kind:'ready',state:'active',nth:0,pointer_ready:true};
    if (fn===readQueryDOM) {
      assert.deepEqual(args[0],scope);
      const frame=typeof frames==='function'?frames(reads++):{cards:frames};
      return {kind:'ready',scope_verified:true,rendered_cards:frame.cards.length,at_end:true,loading:false,...frame};
    }
    if (fn===readImagePreviewDOM) return {kind:'ready',image:preview || image(0),fields:{'Generation Model':'GPT Image 2.5','Image dimensions':'1 : 1'},actions:[{label:'Generate HD Model',enabled:true},{label:'Generate Smart Mesh',enabled:true}]};
    if (fn===readPreviewCloseDOM) return {kind:'ready',creator_popover:popover};
    assert.fail('Unexpected DOM reader');
  },click:async(selector,options)=>{calls.push(['click',selector,options]);if(selector.includes('bg-gray-3'))closed=true;},
    focus:async(selector,options)=>calls.push(['focus',selector,options]),hover:async(selector,options)=>calls.push(['hover',selector,options]),pressKey:async key=>{calls.push(['key',key]);popover=false;},scrollTo:async selector=>calls.push(['scroll',selector]),goto:()=>assert.fail('No cold navigation')};
  return page;
}
function withDOM(document,fn) {
  const old={document:globalThis.document,location:globalThis.location,getComputedStyle:globalThis.getComputedStyle};
  globalThis.document=document;globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/assets'};
  globalThis.getComputedStyle=()=>({display:'block',visibility:'visible',overflowY:'auto'});
  try {return fn();} finally {for(const[k,v] of Object.entries(old)){if(v===undefined)delete globalThis[k];else globalThis[k]=v;}}
}
const rect=()=>({width:100,height:100});
function gridDOM({scope=IMAGE_SCOPE,raw=cards([[image(0)]]),changed=false,modal=false}={}) {
  const labels=scope.asset_type==='Image'?['Model','Image','All','multi-views']:['Model','Image','My Assets','Collected',...(scope.ownership==='Collected'?[]:['All','Smart Mesh','Untextured','Textured','Rigged'])];
  const active=new Set([scope.asset_type,scope.ownership,scope.filter]);
  const buttons=labels.map(label=>({innerText:label,getBoundingClientRect:rect,getAttribute:name=>name==='data-state'?(active.has(label)?'active':'inactive'):null}));
  const outer=raw.map(c=>({getBoundingClientRect:rect,parentElement:{closest:()=>null},querySelectorAll:()=>c.images.map(i=>({getAttribute:name=>name==='src'?'https://'+i.host+i.path+'?TOKEN=DO_NOT_RETURN':name==='alt'?i.title:null}))}));
  const footer={innerText:'',querySelector:()=>null};
  const main={innerText:labels.join('\n')+'\nImage Assets',scrollTop:0,scrollHeight:100,clientHeight:100,parentElement:null,
    querySelector:()=>footer,querySelectorAll:selector=>selector==='button'?buttons:selector==='div.group.rounded-5'&&changed?[...outer,{getBoundingClientRect:rect,parentElement:null}]:outer};
  return {buttons,main,document:{querySelector:()=>main,querySelectorAll:()=>modal?[{getBoundingClientRect:rect}]:[]}};
}

test('separate query pin requires all three reviewed files and preserves older pins',()=>{
  assert.equal(queryDigest().length,64);checkQueryPin(queryDigest());
  for(const pin of ['', 'a'.repeat(64),'invalid']) assert.throws(()=>checkQueryPin(pin),e=>e.code==='definition_changed');
});
test('category/ownership/filter combinations are whitelisted before browser access',async()=>{
  for(const args of [{...ARGS,category:'__proto__'},{...ARGS,ownership:'Collected'},{...ARGS,filter:'Rigged'},
    {category:'Model',ownership:'Collected',filter:'Rigged'},{...ARGS,limit:0},{...ARGS,pages:51},{...ARGS,limit:1.5}]) {
    const p=fakePage();await assert.rejects(queryAssets(p,args,FAST),e=>e.code==='invalid_argument');assert.deepEqual(p.calls,[]);
  }
  assert.equal(queryScope({category:'Model',ownership:'Collected',filter:'All'}).filter,null);
  assert.equal(queryBounds({...ARGS,limit:1000,pages:50}).limit,1000);
});
test('four single images from one task remain four distinct cards, including no-alt images',()=>{
  const items=parseQueryCards(cards([[image(0)],[image(1)],[image(2)],[image(3)]]),IMAGE_SCOPE);
  assert.equal(items.length,4);assert.equal(new Set(items.map(i=>i.card_id)).size,4);assert.deepEqual(items.map(i=>i.image_index),[0,1,2,3]);
  assert.equal(imageIdentity(image(null)).card_id,'image:'+ID+':single');
});
test('four multiview images produce one card in normalized view order',()=>{
  const out=parseQueryCards(cards([[view(0),view(1),view(3),view(2)]]),IMAGE_SCOPE);
  assert.equal(out.length,1);assert.deepEqual(out[0].view_indices,[0,1,2,3]);assert.equal(out[0].image_task_id,ID);
});
test('all four observed model variants and collection scope preserve preview identity',()=>{
  for(const variant of ['mesh','mesh_gray','part','wireframe']) {
    const out=parseQueryCards(cards([[model(variant)]]),MODEL_SCOPE)[0];assert.equal(out.preview_task_id,ID);assert.equal(out.task_status,null);
  }
});
test('unknown hosts/variants, mismatched filenames and oversized indices fail without silently dropping cards',()=>{
  for(const entry of [{...image(),host:'other.example'},{...image(),path:'/generate-image/20261003/'+ID+'/image_100.png'},
    {...view(0),path:view(0).path.replace('multiview_0_'+ID,'multiview_0_'+OTHER)},
    {...image(),path:image().path.replace('.png','.webp')}]) assert.throws(()=>imageIdentity(entry),e=>e.code==='thumbnail_contract_changed');
  assert.throws(()=>parseQueryCards(cards([[model('new_variant')]]),MODEL_SCOPE),e=>e.code==='thumbnail_contract_changed');
});
test('duplicate cards, mixed identities, missing multiview views and single images in multiview scope fail',()=>{
  for(const raw of [cards([[image(0)],[image(0)]]),cards([[image(0),image(1)]]),cards([[view(0),view(1),view(2)]]),
    cards([[view(0),view(1),view(2),view(2)]])]) assert.throws(()=>parseQueryCards(raw,IMAGE_SCOPE),e=>e.code==='collection_card_identity_changed');
  assert.throws(()=>parseQueryCards(cards([[image(0)]]),{...IMAGE_SCOPE,filter:'multi-views'}),e=>e.code==='collection_card_identity_changed');
});
test('DOM reader uses outer no-alt cards and strips signed parameters at the boundary',()=>{
  const dom=gridDOM();const out=withDOM(dom.document,()=>readQueryDOM(IMAGE_SCOPE));
  assert.equal(out.kind,'ready');assert.equal(out.rendered_cards,1);assert.equal(out.cards[0].images[0].title,null);
  assert.doesNotMatch(JSON.stringify(out),/TOKEN|DO_NOT_RETURN|https:\/\//);
});
test('DOM scope drift, visible modal and unmatched outer card contracts are explicit errors',()=>{
  for(const [options,code] of [[{changed:true},'collection_card_contract_changed'],[{modal:true},'dialog_open']]) {
    const dom=gridDOM(options);assert.equal(withDOM(dom.document,()=>readQueryDOM(IMAGE_SCOPE)).kind,code);
  }
  const dom=gridDOM();dom.buttons.find(b=>b.innerText==='All').getAttribute=()=> 'inactive';
  assert.equal(withDOM(dom.document,()=>readQueryDOM(IMAGE_SCOPE)).kind,'collection_scope_mismatch');
});
test('zero cards is pending, not a fabricated empty full collection',()=>{
  const dom=gridDOM({raw:[]});assert.equal(withDOM(dom.document,()=>readQueryDOM(IMAGE_SCOPE)).kind,'pending');
});
test('selected category/read-only scan uses nested sentinel, dedupes rounds and remains partial at quiet end',async()=>{
  const p=fakePage(n=>({cards:n<1?cards([[image(0)]]):cards([[image(0)],[image(1)]])}));
  const out=(await queryAssets(p,ARGS,FAST))[0];assert.equal(out.returned_count,2);assert.equal(out.all_assets,false);
  assert.equal(out.authoritative_total,null);assert.equal(out.site_wide_coverage,false);assert.equal(out.status,'partial');
  assert.equal(out.stop_reason,'quiet_scroll_end_no_authoritative_total');assert.equal(out.paid_submitted,false);
  assert.ok(p.calls.every(c=>c[0]==='scroll'&&c[1]==='main div.min-h-10'));
});
test('item limits and page limits are explicit, not full coverage',async()=>{
  const p=fakePage(cards([[image(0)],[image(1)]]));const out=(await queryAssets(p,{...ARGS,limit:1},FAST))[0];
  assert.equal(out.returned_count,1);assert.equal(out.stop_reason,'item_limit');assert.deepEqual(p.calls,[]);
  const page=fakePage(n=>({cards:n===0?cards([[image(0)]]):cards([[image(0)],[image(1)]]),at_end:false}));
  assert.equal((await queryAssets(page,{...ARGS,pages:1},FAST))[0].stop_reason,'page_limit');
});
test('pagination loading and selected scope drift fail rather than return misleading completeness',async()=>{
  const p=fakePage(n=>({cards:cards([[image(0)]]),loading:n>0}));await assert.rejects(queryAssets(p,ARGS,FAST),e=>e.code==='page_not_ready');
  const changed=fakePage();const original=changed.evaluate;changed.evaluate=async(fn,...args)=>fn===readQueryDOM?{kind:'collection_scope_mismatch'}:original(fn,...args);
  await assert.rejects(queryAssets(changed,ARGS,FAST),e=>e.code==='collection_scope_mismatch');
});
test('existing visible dialogs are preserved before any navigation or scope changes',async()=>{
  const p=fakePage(undefined,{nav:{dialog_open:true}});await assert.rejects(queryAssets(p,ARGS,FAST),e=>e.code==='dialog_open');assert.deepEqual(p.calls,[]);
});
test('inactive observed tabs are selected once and then verified, not assumed from click success',async()=>{
  const p=fakePage();let active=false;const original=p.evaluate;
  p.evaluate=async(fn,...args)=>fn===readQueryChoiceDOM?{kind:'ready',state:active?'active':'inactive',nth:1,pointer_ready:true}:original(fn,...args);
  const click=p.click;p.click=async(...args)=>{active=true;await click(...args);};
  await queryAssets(p,{...ARGS,limit:1},FAST);assert.equal(p.calls.length,1);assert.deepEqual(p.calls[0],['click','main button',{nth:1}]);
});
test('preview identifiers reject arbitrary selectors/model IDs and wrong single-image view',()=>{
  for(const args of [{card:'model:'+ID,view:0},{card:'image:'+ID+':0',view:1},{card:'multiview:'+ID,view:4},{card:'image:'+ID+':0"]',view:0}])
    assert.throws(()=>parsePreviewTarget(args),e=>e.code==='invalid_argument');
  assert.equal(parsePreviewTarget({card:'multiview:'+ID,view:3}).view,3);
});
test('exact image preview is opened/read/closed with no Generate or signed URL selectors',async()=>{
  const p=fakePage(),out=(await previewImage(p,{card:'image:'+ID+':0',view:0},FAST))[0];
  assert.equal(out.preview_verified,true);assert.equal(out.preview_closed,true);assert.equal(out.generation_model,'GPT Image 2.5');
  assert.equal(out.model_completed,false);assert.equal(out.paid_submitted,false);
  const clicks=p.calls.filter(c=>c[0]==='click');assert.equal(clicks.length,2);assert.match(clicks[0][1],/img\[src\*=/);assert.match(clicks[1][1],/bg-gray-3/);
  assert.deepEqual(p.calls.filter(c=>c[0]==='hover'),[['hover','main button',{nth:0}]]);
  assert.doesNotMatch(JSON.stringify(clicks),/TOKEN|Generate/);
});
test('multiview preview binds the requested view independently of DOM order',async()=>{
  const p=fakePage(cards([[view(0),view(1),view(3),view(2)]]),{preview:view(3)});
  const out=(await previewImage(p,{card:'multiview:'+ID,view:3},FAST))[0];assert.equal(out.view_index,3);
  assert.match(p.calls.find(c=>c[0]==='click')[1],/multiview_3_/);
});
test('wrong provider preview and absent card stop before further actions',async()=>{
  const p=fakePage(undefined,{preview:image(1)});await assert.rejects(previewImage(p,{card:'image:'+ID+':0',view:0},FAST),e=>e.code==='asset_mismatch');
  assert.equal(p.calls.filter(c=>c[0]==='click').length,1);
  const absent=fakePage();await assert.rejects(previewImage(absent,{card:'image:'+OTHER+':0',view:0},FAST),e=>e.code==='asset_not_visible');
  assert.equal(absent.calls.filter(c=>c[0]==='click').length,0);
});
test('preview DOM excludes hidden header popovers and reads only observed details without signed sources',()=>{
  const labels=['Generation Model','Image dimensions'];
  const spans=labels.map((label,index)=>({innerText:label,nextElementSibling:{innerText:index===0?'GPT Image 2.5':'1 : 1'}}));
  const dialog={getBoundingClientRect:rect,querySelectorAll:selector=>selector==='img[alt="preview"]'?[{getAttribute:()=> 'https://'+image().host+image().path+'?TOKEN=HIDDEN'}]:
    selector==='span'?spans:selector==='button'?[{innerText:'Generate HD Model',disabled:false},{innerText:'Generate Smart Mesh',disabled:false}]:[{}]};
  const document={querySelectorAll:()=>[{getBoundingClientRect:()=>({width:0,height:0})},dialog]};
  const result=withDOM(document,readImagePreviewDOM);assert.equal(result.kind,'ready');assert.equal(result.fields['Generation Model'],'GPT Image 2.5');
  assert.doesNotMatch(JSON.stringify(result),/TOKEN|HIDDEN|https:\/\//);
  spans.splice(0,1);assert.equal(withDOM(document,readImagePreviewDOM).kind,'ready');
  spans.splice(0,1);assert.equal(withDOM(document,readImagePreviewDOM).kind,'layout_changed');
});
test('only the newly triggered known Creator hover popover is dismissed after own preview closes',async()=>{
  const page=fakePage(undefined,{incidentalPopover:true}),result=(await previewImage(page,{card:'image:'+ID+':0',view:0},FAST))[0];
  assert.equal(result.incidental_creator_popover_dismissed,true);assert.deepEqual(page.calls.filter(c=>c[0]==='key'),[['key','Escape']]);
  const existing=fakePage(undefined,{incidentalPopover:true,nav:{dialog_open:true}});
  await assert.rejects(previewImage(existing,{card:'image:'+ID+':0',view:0},FAST),e=>e.code==='dialog_open');assert.deepEqual(existing.calls,[]);
});
test('preview-close DOM waits for own preview animation and preserves unknown dialogs',()=>{
  const known={getBoundingClientRect:rect,querySelector:()=>null,classList:{contains:name=>name==='creator-growth-header-popover'},getAttribute:()=> 'open'};
  const document={querySelectorAll:()=>[known]};
  assert.deepEqual(withDOM(document,readPreviewCloseDOM),{kind:'ready',creator_popover:true});
  known.classList.contains=()=>false;assert.equal(withDOM(document,readPreviewCloseDOM).kind,'dialog_open');
  known.querySelector=()=>({});assert.equal(withDOM(document,readPreviewCloseDOM).kind,'pending');
});
test('covered category control is focused and returned Home before exactly one scope click',async()=>{
  const p=fakePage();let uncovered=false,active=false;const original=p.evaluate;
  p.evaluate=async(fn,...args)=>fn===readQueryChoiceDOM?{kind:'ready',state:active?'active':'inactive',nth:1,pointer_ready:uncovered}:original(fn,...args);
  const press=p.pressKey;p.pressKey=async key=>{uncovered=true;await press(key);};
  const click=p.click;p.click=async(...args)=>{active=true;await click(...args);};
  await queryAssets(p,{...ARGS,limit:1},FAST);
  assert.deepEqual(p.calls.slice(0,3),[['focus','main button',{nth:1}],['key','Home'],['click','main button',{nth:1}]]);
});
test('a still-covered scope control fails before any pointer click',async()=>{
  const p=fakePage(),original=p.evaluate;
  p.evaluate=async(fn,...args)=>fn===readQueryChoiceDOM?{kind:'ready',state:'inactive',nth:0,pointer_ready:false}:original(fn,...args);
  await assert.rejects(queryAssets(p,ARGS,FAST),e=>e.code==='control_obscured');assert.equal(p.calls.some(c=>c[0]==='click'),false);
});
test('actual choice DOM verifies pointer hits as well as active state',()=>{
  const button={innerText:'Model',getBoundingClientRect:()=>({x:20,y:0,width:80,height:24}),getAttribute:()=> 'inactive',contains:e=>e?.child===true};
  const document={querySelector:()=>({querySelectorAll:()=>[button]}),elementFromPoint:()=>({tagName:'HEADER'})};
  assert.equal(withDOM(document,()=>readQueryChoiceDOM('Model')).pointer_ready,false);
  document.elementFromPoint=()=>({child:true});assert.equal(withDOM(document,()=>readQueryChoiceDOM('Model')).pointer_ready,true);
  assert.equal(withDOM(document,()=>readQueryChoiceDOM('Image')).kind,'pending');
});
test('navigation DOM reports only the observed Assets link and obstruction/error state',()=>{
  const link={getBoundingClientRect:rect,innerText:'Assets',getAttribute:()=> '/assets'};
  const document={querySelector:()=>({innerText:'Something went wrong'}),querySelectorAll:selector=>selector==='[role="dialog"]'?[]:[link]};
  assert.deepEqual(withDOM(document,readQueryNavigationDOM),{origin:'https://studio.tripo3d.ai',path:'/assets',dialog_open:false,site_error:true,links:['/assets']});
});
test('foreign fresh page enters through official Home and observed Assets link, never cold asset URL',async()=>{
  const p=fakePage(),original=p.evaluate;let navReads=0;
  p.evaluate=async(fn,...args)=>fn===readQueryNavigationDOM?{origin:navReads++?'https://studio.tripo3d.ai':'null',path:'/',dialog_open:false,links:['/assets']}:original(fn,...args);
  p.goto=async url=>p.calls.push(['goto',url]);
  await queryAssets(p,{...ARGS,limit:1},FAST);
  assert.deepEqual(p.calls,[['goto','https://studio.tripo3d.ai/'],['click','header a[href="/assets"]',undefined]]);
  for(const nav of [{site_error:true},{path:'/',links:[]}]) {
    const blocked=fakePage(undefined,{nav});await assert.rejects(queryAssets(blocked,ARGS,FAST));assert.deepEqual(blocked.calls,[]);
  }
});
test('key-only bridge fallback supplies the documented Home virtual code and still verifies the hit',async()=>{
  const p=fakePage();let uncovered=false,active=false;const original=p.evaluate;
  p.evaluate=async(fn,...args)=>fn===readQueryChoiceDOM?{kind:'ready',state:active?'active':'inactive',nth:1,pointer_ready:uncovered}:original(fn,...args);
  p.cdp=async(method,args)=>{p.calls.push(['cdp',method,args]);if(args.type==='keyUp')uncovered=true;};
  const click=p.click;p.click=async(...args)=>{active=true;await click(...args);};
  await queryAssets(p,{...ARGS,limit:1},FAST);
  assert.deepEqual(p.calls.filter(c=>c[0]==='cdp').map(c=>c[2]),[
    {type:'rawKeyDown',key:'Home',code:'Home',windowsVirtualKeyCode:36},
    {type:'keyUp',key:'Home',code:'Home',windowsVirtualKeyCode:36},
  ]);
  assert.equal(p.calls.filter(c=>c[0]==='click').length,1);
});
