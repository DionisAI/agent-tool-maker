import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {HOME_QUOTE_FILES} from '../examples/opencli/xyq-web/home-quote.mjs';
import {HOME_MATERIAL_FILES,homeMaterialDigest,checkHomeMaterialPin,parseDeclaredAccept,inspectHomeMaterials,inspectBoundHomeMaterials} from '../examples/opencli/xyq-web/material-home.mjs';
const accept='.jpg,.jpeg,.png,.webp,.bmp,.gif,image/png,.mp4,.mov,video/mp4,.wav,.mp3,audio/wav,audio/mpeg,.pdf,application/pdf';
const closed={kind:'ready',accept,multiple:true,enabled:true,selected_file_count:0,menu_open:false,choices:[]};
const opened={...closed,menu_open:true,choices:[{label:'本地上传',enabled:true,kind:'local_file'},{label:'资产库',enabled:true,kind:'asset_library'},{label:'预设提示词',enabled:true,kind:'preset_prompt'}]};
const home={kind:'ready',agent:'创作',form:{mode:'音频生成',preferences:'Seed Audio 1.0、44.1kHz',canvas:{checked:false,disabled:false},preferences_open:false}};
const draft={kind:'ready',prompt:'FIXTURE_PRIVATE_PROMPT',prompt_tree:null,rich_references:0,media:[],files:[],attachments:null,attachment_present:false,layers:0,preferences_layers:0};
function fixture(data=closed){
  const calls=[];return{calls,evaluate:async(fn,arg)=>{calls.push([fn.name,arg]);
    if(fn.name==='readHomeMaterialsDOM')return structuredClone(data);
    if(fn.name==='readHomeDOM')return structuredClone(home);
    if(fn.name==='readDraftDOM')return structuredClone(draft);
    assert.fail('Unreviewed evaluator');},nativeClick:()=>assert.fail('input'),setFileInput:()=>assert.fail('upload'),goto:()=>assert.fail('navigation'),getCookies:()=>assert.fail('auth')};
}
test('independent complete pin leaves the existing home quote source closure unchanged',()=>{
  assert.deepEqual(HOME_MATERIAL_FILES,[...HOME_QUOTE_FILES,'material-home.mjs','material-home.js']);checkHomeMaterialPin(homeMaterialDigest());
  for(const pin of [null,[],[homeMaterialDigest()],'0'.repeat(64)])assert.throws(()=>checkHomeMaterialPin(pin),e=>e.code==='definition_changed');
});
test('declared accept grammar rejects URLs, control text, duplicates, empty and oversized inputs',()=>{
  assert.deepEqual(parseDeclaredAccept('.png,image/png,audio/*'),['.png','image/png','audio/*']);
  for(const value of [null,{},'','.png,,image/png','.png,.png','https://HOST/?TOKEN','image/png\nBAD','.PNG',new Array(129).fill('.x').join(','),'a'.repeat(8001)])assert.throws(()=>parseDeclaredAccept(value),e=>e.code==='accept_changed');
});
test('state binds the complete composer digest and returns declared image, video and audio formats only',async()=>{
  const page=fixture(),r=(await inspectHomeMaterials(page))[0].result;
  assert.equal(r.status,'material_metadata_ready');assert.equal(r.draft_bound,true);assert.match(r.draft_sha256,/^[a-f0-9]{64}$/);
  assert.deepEqual(r.declared_media_extensions,{image:['.jpg','.jpeg','.png','.webp','.bmp','.gif'],video:['.mp4','.mov'],audio:['.wav','.mp3']});
  assert.equal(r.file_state_known,true);assert.equal(r.selected_file_count,0);assert.equal(page.calls.filter(x=>x[0]==='readHomeMaterialsDOM').length,2);
  assert(!JSON.stringify(r).includes('FIXTURE_PRIVATE'));assert.equal(r.limits_verified,false);
  for(const k of ['secrets_returned','upload_started','file_input_sent','asset_selected','generation_submitted','paid_submitted'])assert.equal(r[k],false);
});
test('already-open choices are read without a prompt read, menu input, asset selection or draft claim',async()=>{
  const page=fixture(opened),r=(await inspectHomeMaterials(page,'home_material_choices'))[0].result;
  assert.equal(r.draft_bound,false);assert.equal(r.draft_sha256,null);assert.equal(r.mode,null);assert.equal(r.menu_open,true);assert.deepEqual(r.choices,opened.choices);
  assert(page.calls.every(([name,arg])=>name==='readHomeMaterialsDOM'&&arg==='home_material_choices'));assert.equal(r.asset_selected,false);
});
test('unknown file state and disabled input stay metadata rather than upload acceptance',async()=>{
  const r=(await inspectHomeMaterials(fixture({...closed,selected_file_count:null,enabled:false})))[0].result;
  assert.equal(r.file_state_known,false);assert.equal(r.input_enabled,false);assert.equal(r.upload_started,false);
});
test('new webpage menu labels are explicitly unreviewed, not invented operations',async()=>{
  const page=fixture({...opened,choices:[...opened.choices,{label:'网页新入口',kind:'unreviewed',enabled:false}]});
  const r=(await inspectHomeMaterials(page,'home_material_choices'))[0].result;assert.equal(r.choices.at(-1).kind,'unreviewed');
});
test('wrong surface, existing layers and association drift fail on the first metadata read',async()=>{
  for(const kind of ['origin_mismatch','login_required','unsupported_surface','dialog_open','material_menu_closed','material_context_changed','material_input_changed','material_menu_changed']){
    const page=fixture({kind});await assert.rejects(inspectHomeMaterials(page),e=>e.code===kind);assert.equal(page.calls.length,1);
  }
});
test('transport rejects private fields, invented choice kinds and malformed metadata',async()=>{
  for(const data of [{...closed,prompt:'FIXTURE_PRIVATE'}, {...closed,multiple:false},{...closed,selected_file_count:-1},
    {...closed,menu_open:true},{...closed,choices:[{label:'本地上传',enabled:true,kind:'local_file'}]},
    {...opened,choices:[{label:'本地上传',enabled:true,kind:'asset_library'}]},
    {...opened,choices:[{label:'本地上传',enabled:true,kind:'local_file',token:'FIXTURE_PRIVATE'}]},
    {...opened,choices:[opened.choices[0],opened.choices[0]]}]){
    await assert.rejects(inspectHomeMaterials(fixture(data),data.menu_open?'home_material_choices':'home_material_state'),e=>e.code==='bridge_protocol'&&!e.message.includes('FIXTURE_PRIVATE'));
  }
});
test('metadata and complete draft races remain failures without input',async()=>{
  let reads=0;const page=fixture(),original=page.evaluate;
  page.evaluate=async(fn,arg)=>fn.name==='readHomeMaterialsDOM'?structuredClone(++reads===1?closed:{...closed,enabled:false}):original(fn,arg);
  await assert.rejects(inspectHomeMaterials(page),e=>e.code==='materials_changed');
  const race=fixture();let drafts=0;const evaluate=race.evaluate;race.evaluate=async(fn,arg)=>fn.name==='readDraftDOM'?{...draft,prompt:++drafts===1?'first':'changed'}:evaluate(fn,arg);
  await assert.rejects(inspectHomeMaterials(race),e=>e.code==='draft_changed');
});
test('public routing is inherited; the bound facade exposes evaluations only',async()=>{
  const page=fixture(),r=(await inspectBoundHomeMaterials({preferredContextId:'fixture-profile'},'home_material_state',async routing=>{assert.deepEqual(routing,{preferredContextId:'fixture-profile'});return page;}))[0].result;
  assert.equal(r.browser_session,'site:xyq-home');assert.equal(r.binding_changed,false);
  await assert.rejects(inspectBoundHomeMaterials({contextId:'a',preferredContextId:'b'},'home_material_state',()=>assert.fail('factory')),e=>e.code==='unsupported_backend');
  await assert.rejects(inspectBoundHomeMaterials({},'home_material_state',()=>{throw Error('FIXTURE_PRIVATE');}),e=>e.code==='bridge_failed'&&!e.message.includes('FIXTURE_PRIVATE'));
});
test('source and registration are read-only, with separate metadata and upload acceptance',()=>{
  const s=readFileSync(new URL('../examples/opencli/xyq-web/material-home.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(s,/localStorage|sessionStorage|document\.cookie|fetch\(|XMLHttpRequest|\.goto\(|\.cdp\(|\.click\(|setFileInput|setAttribute|dispatchEvent|writeFile/);
  const declaration=readFileSync(new URL('../examples/opencli/xyq-web/material-home.js',import.meta.url),'utf8');assert.match(declaration,/access:'read'/);assert.match(declaration,/navigateBefore:false/);
});
