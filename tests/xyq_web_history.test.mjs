import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {AUDIO_BOUND_FILES} from '../examples/opencli/xyq-web/audio-bound.mjs';
import {HISTORY_FILES,historyDigest,checkHistoryPin,historyScope,inspectProjectHistory,inspectBoundProjectHistory} from '../examples/opencli/xyq-web/history.mjs';
const scope={project_id:'1',canvas_id:'2'};
const empty={kind:'ready',view_state:'empty',selected_media:'全部',selected_status:'成功',media_filters:[{label:'全部',selected:true,disabled:false}],visible_record_count:0};
function fixture(state=empty){let reads=0;return{get reads(){return reads;},evaluate:async(fn,arg)=>{reads++;assert.equal(fn.name,'readProjectHistoryDOM');assert.deepEqual(arg,scope);return structuredClone(state);},click:()=>assert.fail('input'),cdp:()=>assert.fail('CDP'),goto:()=>assert.fail('navigation'),getCookies:()=>assert.fail('auth')};}
test('history pin has a complete independent closure and strict typed checks',()=>{
  assert.deepEqual(HISTORY_FILES,[...AUDIO_BOUND_FILES,'history.mjs','history.js']);assert.equal(HISTORY_FILES.length,8);checkHistoryPin(historyDigest());
  for(const pin of [null,[],[historyDigest()],'0'.repeat(64)])assert.throws(()=>checkHistoryPin(pin),e=>e.code==='definition_changed');
});
test('exact owned scope rejects extra fields and inherited IDs before construction',async()=>{
  assert.deepEqual(historyScope(scope),scope);
  for(const raw of [null,[],{project_id:1,canvas_id:'2'},{project_id:'1'},{...scope,url:'https://example.test'},Object.assign(Object.create({project_id:'1'}),{canvas_id:'2',other:true})])
    await assert.rejects(inspectBoundProjectHistory({},raw,()=>assert.fail('factory')),e=>e.code==='invalid_argument');
});
test('empty view is only current filtered visibility, not whole task or media completion',async()=>{
  const p=fixture(),r=(await inspectProjectHistory(p,scope))[0].result;assert.equal(p.reads,2);assert.equal(r.status,'history_empty');assert.equal(r.visible_record_count,0);
  assert.equal(r.task_count,null);assert.equal(r.selected_status,'成功');assert.equal(r.selected_media,'全部');
  for(const k of ['all_records','row_scope_verified','task_rows_parsed','secrets_returned','upload_started','paid_submitted','generation_submitted','download_started'])assert.equal(r[k],false);
});
test('closed/loading do not masquerade as zero tasks',async()=>{
  for(const s of ['closed','loading']){
    const r=(await inspectProjectHistory(fixture({...empty,view_state:s,visible_record_count:null}),scope))[0].result;
    assert.equal(r.status,s==='closed'?'history_closed':'history_pending');assert.equal(r.visible_record_count,null);assert.equal(r.task_count,null);
  }
});
test('strict and preferred routing is preserved and exposes only evaluation',async()=>{
  for(const context of [{},{contextId:'fixture'},{preferredContextId:'fixture'}]){
    const p=fixture(),r=(await inspectBoundProjectHistory(context,scope,async routing=>{assert.deepEqual(routing,context);return p;}))[0].result;
    assert.equal(r.browser_session,'site:xyq-web');assert.equal(r.browser_surface,'browser');assert.equal(r.binding_changed,false);assert.equal(p.reads,2);
  }
});
test('wrong page or unparsed actual records are errors, never fallback or an empty list',async()=>{
  for(const code of ['origin_mismatch','login_required','unsupported_surface','project_changed','canvas_changed','dialog_open','unsupported_history_records','history_context_changed']){
    const p=fixture({kind:code});let factories=0;
    await assert.rejects(inspectBoundProjectHistory({},scope,()=>{factories++;return p;}),e=>e.code===code);
    assert.equal(p.reads,1);assert.equal(factories,1);
  }
});
test('filter and view races stay errors without input or synthetic success',async()=>{
  for(const change of [{selected_status:'失败'},{selected_media:'图片'},{view_state:'closed',visible_record_count:null}]){
    let n=0;await assert.rejects(inspectProjectHistory({evaluate:async()=>structuredClone(++n===1?empty:{...empty,...change})},scope),e=>e.code==='history_changed');
  }
});
test('routing/backend failures remain sanitized without profile or auth access',async()=>{
  for(const c of [null,[],{contextId:'../TOKEN'},{contextId:1},{contextId:'a',preferredContextId:'b'}])
    await assert.rejects(inspectBoundProjectHistory(c,scope,()=>assert.fail('factory')),e=>e.code==='unsupported_backend');
  await assert.rejects(inspectBoundProjectHistory({},scope,()=>{throw Error('FAKE_PRIVATE_TOKEN');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  await assert.rejects(inspectBoundProjectHistory({},scope,()=>({})),e=>e.code==='unsupported_backend');
});
test('evaluation exceptions preserve bridge failure without secret diagnostic text',async()=>{
  await assert.rejects(inspectProjectHistory({evaluate:()=>{throw Error('FAKE_PRIVATE_TOKEN');}},scope),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
  await assert.rejects(inspectProjectHistory({evaluate:()=>null},scope),e=>e.code==='bridge_protocol');
});
test('source/registration is DOM-only, scoped and contains no task-row/private/side-effect APIs',()=>{
  const s=readFileSync(new URL('../examples/opencli/xyq-web/history.mjs',import.meta.url),'utf8');
  assert.match(s,/new Page\('site:xyq-web'/);assert.doesNotMatch(s,/localStorage|sessionStorage|document\.cookie|fetch\(|XMLHttpRequest|\.goto\(|\.cdp\(|\.click\(|writeFile|bindTab|setAttribute|dispatchEvent|\._page|querySelectorAll\('\[data-task-id/);
  const loader=readFileSync(new URL('../examples/opencli/xyq-web/history.js',import.meta.url),'utf8');assert.match(loader,/access:'read'/);assert.match(loader,/navigateBefore:false/);assert.match(loader,/name:'pin',type:'string',required:true/);
});
