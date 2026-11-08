import test from 'node:test';
import assert from 'node:assert/strict';
import {viewerDigest,checkViewerPin,parseViewerSettings,readViewerContextDOM,readViewerDOM,readHierarchyDOM,readEnvironmentDOM,readEnvironmentListDOM,readViewerLayersClosedDOM,readViewerTargetDOM,readTransformFieldsDOM,readCanvasTargetDOM,
  inspectViewer,prepareViewer,prepareHierarchy,prepareTransform,cameraViewer,transformHash,CAMERA_ACTIONS} from '../examples/opencli/tripo-studio/viewer.mjs';
import {readLocation,readAssetDOM} from '../examples/opencli/tripo-studio/extended.mjs';
import {readWorkspaceDOM,readWorkspaceLinkDOM} from '../examples/opencli/tripo-studio/workspace.mjs';
const ID='11111111-2222-3333-4444-555555555555',NAME='fixture_mesh',VECTORS={position:[0,0,0],rotation:[0,0,0],scale:[1,1,1]};
function pageFixture({existingDialog=false,obscured=false,wrongReadback=false,cameraFailure=false,effectFallback='pbr',rotateTick=0,cleanupFailure=false}={}){
  const p={calls:[],state:{kind:'ready',asset_id:ID,settings:{render_mode:'pbr',wireframe:false,grid:false},modes:[],sidebar:'Assets',canvas:{x:100,y:100,width:600,height:600}},
    env:{surrounding:'Studio',strength:1,rotation:0,auto_rotate:false},hier:{kind:'ready',nodes:[{name:NAME,selected:false,visible:true}],selected_node:null,transform:null,coverage:'currently_rendered_hierarchy_not_authoritative_all'},values:structuredClone(VECTORS)};
  let owned=false,list=false,pressed=false;
  p.evaluate=async(fn,...args)=>{let data;
    if(fn===readViewerContextDOM)data={origin:'https://studio.tripo3d.ai',path:'/workspace/generate/'+ID,dialogs:existingDialog||owned?1:0};
    else if(fn===readLocation)data={origin:'https://studio.tripo3d.ai',path:'/workspace/generate/'+ID};
    else if(fn===readAssetDOM)data={kind:'ready',status:'ready',asset_id:ID,faces:12,vertices:8,export_enabled:true};
    else if(fn===readWorkspaceLinkDOM)data={kind:'ready',available:true,nth:0,href:'/workspace/generate/'+ID};
    else if(fn===readWorkspaceDOM)data={kind:'ready',asset_id:ID,settings:{},quoted_credits:40,button_enabled:true,module:'model'};
    else if(fn===readViewerDOM)data=structuredClone(p.state);
    else if(fn===readHierarchyDOM)data={...structuredClone(p.hier),transform:p.hier.selected_node?structuredClone(p.values):null};
    else if(fn===readEnvironmentDOM)data=owned?{kind:'ready',settings:structuredClone(p.env),bounds:[{min:0,max:2},{min:0,max:360}]}:{kind:'pending'};
    else if(fn===readEnvironmentListDOM)data=list?{kind:'ready',options:['Beach','Desert','Forest','Interior','Night','Studio'].map(label=>({label,selected:label===p.env.surrounding,disabled:false}))}:{kind:'pending'};
    else if(fn===readViewerLayersClosedDOM)data={kind:(args[0]==='list'?list:owned)?'pending':'ready'};
    else if(fn===readViewerTargetDOM){p.target=args[0];data={kind:'ready',nth:0,pointer_ready:!obscured};}
    else if(fn===readTransformFieldsDOM)data={kind:'ready',fields:{position:[0,1,2],rotation:[3,4,5],scale:[6,7,8]}};
    else if(fn===readCanvasTargetDOM)data={kind:'ready',pointer_ready:!obscured,rect:p.state.canvas};
    else assert.fail('Unexpected reader '+fn.name);
    return{session:'fixture',data};
  };
  p.click=async(selector,opts)=>{p.calls.push(['click',selector,opts]);if(selector.endsWith('[role="combobox"]')){list=true;return;}
    const{kind,label}=p.target;if(kind==='environment'){owned=true;return;}if(kind==='environment_close'){if(cleanupFailure)throw Error('fixture close failed');owned=false;return;}
    if(kind==='environment_option'){p.env.surrounding=label;list=false;return;}if(kind==='sidebar'){p.state.sidebar=label;return;}
    if(wrongReadback)return;
    if(kind==='mode'){if(label==='wireframe')p.state.settings.wireframe=!p.state.settings.wireframe;else p.state.settings.render_mode=['unlit','toon','sketch','hologram'].includes(label)&&label===p.state.settings.render_mode?effectFallback:label;}
    else if(kind==='grid')p.state.settings.grid=!p.state.settings.grid;
    else if(kind==='node'){p.hier.nodes[0].selected=true;p.hier.selected_node=NAME;}
    else if(kind==='visibility'){p.hier.nodes[0].visible=!p.hier.nodes[0].visible;p.hier.nodes[0].selected=false;p.hier.selected_node=null;}
  };
  p.fillText=async(selector,value,opts)=>{p.calls.push(['fill',selector,value,opts]);if(wrongReadback)return;if(selector.includes('dialog'))p.env[opts.nth===0?'strength':'rotation']=Number(value);else p.values[['position','rotation','scale'][Math.floor(opts.nth/3)]][opts.nth%3]=Number(value);};
  p.setChecked=async(selector,value)=>{p.calls.push(['checked',selector,value]);p.env.auto_rotate=value;if(value)p.env.rotation=(p.env.rotation+rotateTick)%360;};
  p.cdp=async(method,value)=>{p.calls.push(['cdp',method,value]);if(value.type==='mousePressed')pressed=true;if(value.type==='mouseReleased')pressed=false;if(cameraFailure&&value.type==='mouseMoved'&&pressed)throw new Error('fixture native input failed');};
  return p;
}
test('viewer source pins and semantic settings fail closed on unreviewed input',()=>{
  checkViewerPin(viewerDigest());assert.throws(()=>checkViewerPin('0'.repeat(64)),e=>e.code==='definition_changed');
  assert.deepEqual(parseViewerSettings('viewer',{render_mode:'normal',wireframe:true,environment:{strength:.5,rotation:90,auto_rotate:false}}).render_mode,'normal');
  for(const v of [{selector:'button'}, {render_mode:'arbitrary'}, {grid:1}, {environment:{strength:3}}, {environment:{rotation:-1}}, {environment:{surrounding:'Other'}}, {environment:{auto_rotate:'true'}}])assert.throws(()=>parseViewerSettings('viewer',v),e=>e.code==='invalid_argument');
  for(const v of [{select:false},{visible:true,select:'yes'},{visible:false,select:true}])assert.throws(()=>parseViewerSettings('hierarchy',v),e=>e.code==='invalid_argument');
  for(const v of [{position:[1,2,3]}, {position:[1,2],expected_transform_sha256:'a'.repeat(64)}, {scale:[Infinity,1,1],expected_transform_sha256:'a'.repeat(64)}, {rotation:[.001,0,0],expected_transform_sha256:'a'.repeat(64)}])assert.throws(()=>parseViewerSettings('transform',v),e=>e.code==='invalid_argument');
});
test('inspection reads own environment and hierarchy, restores original sidebar, never submits',async()=>{
  const p=pageFixture(),d=(await inspectViewer(p,{asset:ID}))[0];assert.equal(d.environment.available_presets.length,6);assert.equal(d.settings.render_mode,'pbr');assert.equal(d.hierarchy.nodes.length,1);
  assert.equal(p.state.sidebar,'Assets');assert.equal(d.paid_submitted,false);assert.equal(d.save_button_clicked,false);assert.equal(d.download_started,false);
  assert.equal(p.calls.some(c=>/Generate|Export|Delete|Share/.test(c[1])),false);
});
test('preexisting dialogs and obscured targets stop before their click',async()=>{
  const p=pageFixture({existingDialog:true});await assert.rejects(inspectViewer(p,{asset:ID}),e=>e.code==='dialog_open');assert.deepEqual(p.calls,[]);
  const q=pageFixture({obscured:true});await assert.rejects(inspectViewer(q,{asset:ID}),e=>e.code==='control_obscured');assert.deepEqual(q.calls,[]);
});
test('owned cleanup failure remains the error, with no sidebar click behind the stranded layer',async()=>{
  const p=pageFixture({cleanupFailure:true});
  await assert.rejects(inspectViewer(p,{asset:ID}),e=>e.code==='cleanup_failed');
  assert.equal(p.state.sidebar,'Property');assert.equal(p.target.kind,'environment_close');
});
for(const mode of ['solid','pbr','normal','unlit','toon','sketch','hologram'])test('render mode '+mode+' readback preserves independent wireframe and grid',async()=>{
  const p=pageFixture(),d=(await prepareViewer(p,{asset:ID,settings:{render_mode:mode,wireframe:true,grid:true}}))[0];assert.equal(d.settings.render_mode,mode);assert.equal(d.settings.wireframe,true);assert.equal(d.settings.grid,true);assert.equal(d.status,'prepared');
});
for(const effect of ['unlit','toon','sketch','hologram'])for(const fallback of ['pbr','solid','normal'])test('restore PBR clears '+effect+' then verifies the restored '+fallback+' base',async()=>{
  const p=pageFixture({effectFallback:fallback});p.state.settings.render_mode=effect;
  const d=(await prepareViewer(p,{asset:ID,settings:{render_mode:'pbr'}}))[0];
  assert.equal(d.settings.render_mode,'pbr');
  assert.equal(p.calls.filter(c=>c[0]==='click'&&c[1]==='main button[aria-pressed]').length,fallback==='pbr'?1:2);
  assert.deepEqual(p.target,{kind:'sidebar',label:'Assets'});
});
test('environment prepares exact preset, bounds and native numeric blur without save/export',async()=>{
  const p=pageFixture(),s={surrounding:'Forest',strength:.5,rotation:90,auto_rotate:true},d=(await prepareViewer(p,{asset:ID,settings:{environment:s}}))[0];assert.deepEqual(d.environment.settings,s);assert.equal(p.calls.filter(c=>c[0]==='cdp'&&c[2].key==='Tab').length,4);assert.equal(p.state.sidebar,'Assets');
});
test('auto rotation verifies the stopped starting angle, then returns the actual moving angle',async()=>{
  const p=pageFixture({rotateTick:1});p.env.auto_rotate=true;
  const d=(await prepareViewer(p,{asset:ID,settings:{environment:{strength:.5,rotation:90,auto_rotate:true}}}))[0];
  assert.equal(d.environment.settings.rotation,91);assert.equal(d.environment.settings.auto_rotate,true);
  assert.deepEqual(d.environment.rotation_preparation,{requested:90,verified_value:90,auto_rotate_after:true});
  assert.deepEqual(p.calls.filter(c=>c[0]==='checked').map(c=>c[2]),[false,true]);
});
test('setting a starting angle restores an already-running auto rotation when omitted',async()=>{
  const p=pageFixture({rotateTick:1});p.env.auto_rotate=true;
  const d=(await prepareViewer(p,{asset:ID,settings:{environment:{rotation:90}}}))[0];
  assert.equal(d.environment.settings.rotation,91);assert.equal(d.environment.settings.auto_rotate,true);
  assert.equal(d.environment.rotation_preparation.verified_value,90);
});
test('wrong numeric readback fails before enabling auto rotation',async()=>{
  const p=pageFixture({wrongReadback:true});
  await assert.rejects(prepareViewer(p,{asset:ID,settings:{environment:{rotation:90,auto_rotate:true}}}),e=>e.code==='settings_changed');
  assert.equal(p.calls.some(c=>c[0]==='checked'&&c[2]===true),false);
});
test('wrong render readback propagates failure, not prepared',async()=>{
  await assert.rejects(prepareViewer(pageFixture({wrongReadback:true}),{asset:ID,settings:{render_mode:'normal'}}),e=>e.code==='settings_changed');
});
test('hierarchy selection, visibility and exact transform binding are independent of paid ledger',async()=>{
  const p=pageFixture(),chosen=(await prepareHierarchy(p,{asset:ID,node:NAME,settings:{select:true}}))[0];assert.equal(chosen.selected_node,NAME);
  const d=(await prepareTransform(p,{asset:ID,node:NAME,settings:{position:[.1,0,0],rotation:[0,15,0],scale:[1.1,1,1],expected_transform_sha256:chosen.transform_sha256}}))[0];assert.deepEqual(d.transform.position,[.1,0,0]);assert.equal(d.transform.rotation[1],15);assert.equal(d.transform.scale[0],1.1);
  await assert.rejects(prepareTransform(p,{asset:ID,node:NAME,settings:{position:[0,0,0],expected_transform_sha256:chosen.transform_sha256}}),e=>e.code==='transform_changed');
  await prepareTransform(p,{asset:ID,node:NAME,settings:{...VECTORS,expected_transform_sha256:d.transform_sha256}});
  const hidden=(await prepareHierarchy(p,{asset:ID,node:NAME,settings:{visible:false}}))[0];assert.equal(hidden.nodes[0].visible,false);assert.equal(hidden.selected_node,null);
  const shown=(await prepareHierarchy(p,{asset:ID,node:NAME,settings:{visible:true}}))[0];assert.equal(shown.nodes[0].visible,true);
});
test('missing node or wrong prior digest stops before field input',async()=>{
  const p=pageFixture();await assert.rejects(prepareHierarchy(p,{asset:ID,node:'missing',settings:{select:true}}),e=>e.code==='node_missing');assert.equal(p.calls.some(c=>c[0]==='fill'),false);
  await assert.rejects(prepareTransform(p,{asset:ID,node:NAME,settings:{position:[0,0,0],expected_transform_sha256:'a'.repeat(64)}}),e=>e.code==='selection_changed');
});
for(const action of CAMERA_ACTIONS)test('camera '+action+' is bounded native input, never an invented pose',async()=>{
  const p=pageFixture(),d=(await cameraViewer(p,{asset:ID,action}))[0];assert.equal(d.camera_pose_exposed,false);assert.equal(d.acceptance,'bounded_native_camera_input_requires_rendered_visual_validation');assert.equal(d.paid_submitted,false);
  for(const c of p.calls.filter(c=>c[0]==='cdp'&&c[2].x!==undefined)){assert.ok(c[2].x>=100&&c[2].x<=700);assert.ok(c[2].y>=100&&c[2].y<=700);}
});
test('failed camera gesture still releases the pressed mouse button',async()=>{
  const p=pageFixture({cameraFailure:true});await assert.rejects(cameraViewer(p,{asset:ID,action:'orbit_left'}));assert.equal(p.calls.at(-1)[2].type,'mouseReleased');
  const q=pageFixture({obscured:true});await assert.rejects(cameraViewer(q,{asset:ID,action:'zoom_in'}),e=>e.code==='control_obscured');assert.equal(q.calls.some(c=>c[0]==='cdp'),false);
});
test('transform hash binds source, selected node and all axes',()=>{const h=transformHash(ID,NAME,VECTORS);for(const[asset,node,v]of [['other',NAME,VECTORS],[ID,'other',VECTORS],[ID,NAME,{...VECTORS,scale:[1,1,2]}]])assert.notEqual(transformHash(asset,node,v),h);});

function visible(extra={}){return{getClientRects:()=>[1],getBoundingClientRect:()=>({x:0,y:0,width:100,height:100}),...extra};}
function classList(names){return{contains:n=>names.includes(n)};}
test('actual viewer DOM decodes exclusive bases and rejects invalid effect combinations',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate/'+ID};
  const modes=['wireframe','solid','pbr','normal','unlit','toon','sketch','hologram'].map(mode=>visible({disabled:false,closest:()=>null,querySelector:()=>({getAttribute:()=>'/studio-prod/viewer/images/'+mode+'.png'}),getAttribute:n=>n==='aria-pressed'?(mode==='pbr'?'true':'false'):null}));
  const grid=visible({getAttribute:()=> 'false'}),tabs=['Assets','Property'].map(label=>({innerText:label,getAttribute:()=>label==='Assets'?'true':'false'}));
  globalThis.document={querySelectorAll:s=>s==='main canvas'?[visible()]:s.includes(':has(img)')?modes:s.includes('line-visible')?[grid]:s==='main [role="tab"]'?tabs:[]};
  assert.equal(readViewerDOM().settings.render_mode,'pbr');assert.equal(readViewerDOM().settings.grid,false);
  modes[4].getAttribute=()=> 'true';assert.equal(readViewerDOM().settings.render_mode,'unlit');
  modes[5].getAttribute=()=> 'true';assert.equal(readViewerDOM().kind,'viewer_selection_changed');
  modes[5].getAttribute=()=> 'false';modes[2].getAttribute=()=> 'false';modes[1].getAttribute=()=> 'true';assert.equal(readViewerDOM().kind,'viewer_selection_changed');
  modes[4].getAttribute=()=> 'false';assert.equal(readViewerDOM().settings.render_mode,'solid');
  modes[2].getAttribute=()=> 'true';assert.equal(readViewerDOM().kind,'viewer_selection_changed');
});
for(const effect of ['unlit','toon','sketch','hologram'])test('actual DOM accepts PBR plus '+effect+' with independent Wireframe',()=>{
  globalThis.location={origin:'https://studio.tripo3d.ai',pathname:'/workspace/generate/'+ID};
  const modes=['wireframe','solid','pbr','normal','unlit','toon','sketch','hologram'].map(mode=>visible({disabled:false,closest:()=>null,querySelector:()=>({getAttribute:()=>'/studio-prod/viewer/images/'+mode+'.png'}),getAttribute:n=>n==='aria-pressed'?(['wireframe','pbr',effect].includes(mode)?'true':'false'):null}));
  const grid=visible({getAttribute:()=> 'false'}),tabs=['Assets','Property'].map(label=>({innerText:label,getAttribute:()=>label==='Assets'?'true':'false'}));
  globalThis.document={querySelectorAll:s=>s==='main canvas'?[visible()]:s.includes(':has(img)')?modes:s.includes('line-visible')?[grid]:s==='main [role="tab"]'?tabs:[]};
  const d=readViewerDOM();assert.equal(d.kind,'ready');assert.equal(d.settings.render_mode,effect);assert.equal(d.settings.wireframe,true);
});
test('actual hierarchy DOM reads direct labels, selected node and semantic XYZ groups',()=>{
  const inputs=(values)=>values.map((value,i)=>({value:value.toFixed(2),getAttribute:()=> 'text',parentElement:{innerText:['X','Y','Z'][i]}}));
  const icons=['position','rotation','scale'].map(k=>({classList:classList(['i-tripo:'+k]),parentElement:{querySelectorAll:()=>inputs(VECTORS[k])}}));
  const row=visible({classList:classList(['bg-purple-20']),querySelector:()=>({innerText:NAME}),querySelectorAll:()=>[{classList:classList(['i-tripo:visible'])}]});
  const pane=visible({querySelector:()=>({innerText:'Hierarchy'}),querySelectorAll:s=>s==='li'?[row]:s==='[class]'?icons:[]});globalThis.document={querySelectorAll:()=>[pane]};
  const d=readHierarchyDOM();assert.deepEqual(d.transform,VECTORS);assert.equal(d.selected_node,NAME);assert.equal(d.nodes[0].visible,true);
  row.classList=classList([]);assert.equal(readHierarchyDOM().kind,'hierarchy_selection_changed');
});
test('actual environment DOM enforces observed numeric bounds and synchronized inputs',()=>{
  const values=['1','0'],sliders=[{min:'0',max:'2',now:'1'},{min:'0',max:'360',now:'0'}].map(v=>({getAttribute:n=>v[n.replace('aria-value','')]}));
  const d=visible({innerText:'Environment Settings',getAttribute:()=> 'open',querySelectorAll:s=>s==='[role="combobox"]'?[{innerText:'Studio'}]:s==='input[type="text"]'?values.map(value=>({value})):s==='[role="slider"]'?sliders:s==='[role="switch"]'?[{getAttribute:()=> 'false',parentElement:{innerText:'Auto Rotate'}}]:[]});
  globalThis.document={querySelectorAll:()=>[d]};assert.equal(readEnvironmentDOM().kind,'ready');values[0]='3';assert.equal(readEnvironmentDOM().kind,'environment_fields_changed');
});
test('layers marked closed remain pending until their layout disappears',()=>{const layer=visible({getAttribute:()=> 'closed'});globalThis.document={querySelectorAll:()=>[layer]};assert.equal(readViewerLayersClosedDOM('dialog').kind,'pending');layer.getClientRects=()=>[];assert.equal(readViewerLayersClosedDOM('list').kind,'ready');});
