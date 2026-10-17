import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {homeBoundDigest,checkHomeBoundPin,homeBoundSettings,homeBoundPage,runHomeBoundOperation} from '../examples/opencli/xyq-web/home-bound.mjs';
const sha='a'.repeat(64);
test('home pin covers complete source closure and requires an exact typed digest',()=>{
  checkHomeBoundPin(homeBoundDigest());for(const pin of [null,[homeBoundDigest()],'0'.repeat(64)])assert.throws(()=>checkHomeBoundPin(pin),e=>e.code==='definition_changed');
});
test('home operation/settings validation precedes Page construction',async()=>{
  for(const[op,settings]of [['generate',undefined],['form_state',{}],['mode_prepare',{expected_draft_sha256:[sha],mode:'图片生成'}],['mode_prepare',{expected_draft_sha256:sha,mode:'Agent模式'}],['mode_prepare',{expected_draft_sha256:sha,mode:'视频生成',prompt:'x'}]])
    await assert.rejects(runHomeBoundOperation({},op,settings,()=>assert.fail('no constructor')),e=>e.code==='invalid_argument');
  assert.equal(homeBoundSettings('mode_prepare',JSON.stringify({expected_draft_sha256:sha,mode:'音频生成'})).mode,'音频生成');
});
test('state wrapper exposes only evaluate; no auth/navigation or input capabilities',()=>{
  const page=homeBoundPage({evaluate:()=>1,click:()=>assert.fail('synthetic'),getCookies:()=>assert.fail('auth')},'form_state');
  assert.deepEqual(Object.keys(page),['evaluate']);assert(Object.isFrozen(page));
});
test('menu wrapper computes coordinates immediately before native input',async()=>{
  const calls=[];
  const page=homeBoundPage({evaluate:async(fn,arg)=>{calls.push([fn.name,arg]);return{kind:'ready',x:42,y:64};},nativeClick:async(...args)=>calls.push(args)},'form_choices');
  await page.click('INTERNAL_TARGET',{nth:0});
  assert.deepEqual(calls,[['readHomeBoundInputDOM',{kind:'click',selector:'INTERNAL_TARGET',nth:0}],[42,64]]);
});
test('wrong/covered home target and invalid coordinates cause zero input',async()=>{
  for(const result of [{kind:'origin_mismatch'},{kind:'unsupported_surface'},{kind:'control_obscured'},{kind:'ready',x:NaN,y:1},{kind:'ready',x:-1,y:1}]){
    const page=homeBoundPage({evaluate:async()=>result,nativeClick:()=>assert.fail('no input')},'form_choices');
    await assert.rejects(page.click('INTERNAL',{nth:0}),e=>e.code===result.kind||e.code==='control_changed');
  }
});
test('owned Escape uses nativeKeyPress and does not expose other key input',async()=>{
  const calls=[],page=homeBoundPage({evaluate:async()=>({kind:'ready'}),nativeKeyPress:async key=>calls.push(key)},'mode_choices');
  await page.pressKey('Escape');assert.deepEqual(calls,['Escape']);
  await assert.rejects(page.pressKey('Enter'),e=>e.code==='invalid_argument');
});
test('changed menu association and missing native input APIs are explicit failures',async()=>{
  const page=homeBoundPage({evaluate:async()=>({kind:'dialog_open'}),nativeKeyPress:()=>assert.fail('no key')},'mode_choices');
  await assert.rejects(page.pressKey('Escape'),e=>e.code==='dialog_open');
  await assert.rejects(homeBoundPage({evaluate:async()=>({kind:'ready'})},'form_choices').click('INTERNAL',{nth:0}),e=>e.code==='unsupported_backend');
});
test('profile/factory diagnostics are sanitized and never trigger rebinding',async()=>{
  await assert.rejects(runHomeBoundOperation({contextId:'../SECRET'},'form_state',undefined,()=>assert.fail('no constructor')),e=>e.code==='unsupported_backend');
  await assert.rejects(runHomeBoundOperation({},'form_state',undefined,()=>{throw Error('FAKE_PRIVATE_TOKEN');}),e=>e.code==='bridge_failed'&&!e.message.includes('FAKE_PRIVATE'));
});
test('wrong page remains a single failed read rather than a fallback or empty success',async()=>{
  let factories=0,reads=0;
  await assert.rejects(runHomeBoundOperation({},'form_state',undefined,async()=>{factories++;return{evaluate:async()=>{reads++;return{kind:'origin_mismatch'};}};}),e=>e.code==='origin_mismatch');
  assert.equal(factories,1);assert.equal(reads,1);
});
test('an existing masked menu fails fast before polling or sending any input',async()=>{
  let reads=0;
  await assert.rejects(runHomeBoundOperation({},'form_state',undefined,async()=>({evaluate:async fn=>{reads++;assert.equal(fn.name,'readHomeBoundSurfaceDOM');return{kind:'dialog_open'};},nativeClick:()=>assert.fail('no input'),nativeKeyPress:()=>assert.fail('no key')})),e=>e.code==='dialog_open');
  assert.equal(reads,1);
});
test('native input failure is sanitized, uncertain and never retried',async()=>{
  let clicks=0,keys=0;
  const page=homeBoundPage({evaluate:async()=>({kind:'ready',x:4,y:8}),nativeClick:()=>{clicks++;throw Error('FAKE_PRIVATE_TOKEN');},nativeKeyPress:()=>{keys++;throw Error('FAKE_PRIVATE_TOKEN');}},'mode_choices');
  for(const action of [()=>page.click('INTERNAL',{nth:0}),()=>page.pressKey('Escape')])await assert.rejects(action(),e=>e.code==='bridge_failed'&&e.outcome_uncertain===true&&!e.message.includes('FAKE_PRIVATE'));
  assert.equal(clicks,1);assert.equal(keys,1);
});
test('home transport uses public native APIs without DOM mutation, auth or tab mutation',()=>{
  const source=readFileSync(new URL('../examples/opencli/xyq-web/home-bound.mjs',import.meta.url),'utf8');
  assert.match(source,/new Page\('site:xyq-home'/);assert.match(source,/backend\.nativeClick/);assert.match(source,/backend\.nativeKeyPress/);
  assert.doesNotMatch(source,/getCookies|document\.cookie|localStorage|sessionStorage|indexedDB|\.goto\(|\.click\(\)|dispatchEvent|setAttribute|fetch\(|\._page|\.surface\s*=|bindTab/);
});

test('bound form preparation accepts semantic settings and rejects untyped digests before construction',async()=>{
  assert.deepEqual(homeBoundSettings('form_prepare',{expected_draft_sha256:sha,model:'OBSERVED',radios:{'比例':'16:9'},duration_seconds:12,canvas:false,prompt:'测试'}),{expected_draft_sha256:sha,model:'OBSERVED',radios:{'比例':'16:9'},duration_seconds:12,canvas:false,prompt:'测试'});
  for(const settings of [{expected_draft_sha256:[sha]},{expected_draft_sha256:sha,selector:'button'},{expected_draft_sha256:sha,duration_seconds:1.5}])await assert.rejects(runHomeBoundOperation({},'form_prepare',settings,()=>assert.fail('no constructor')),e=>e.code==='invalid_argument');
});
const editor='#title-section-prompt-container [role="textbox"][contenteditable="true"]';
function textBackend(calls,overrides={}){return{evaluate:async(fn,arg)=>{calls.push(['read',fn.name,arg.kind]);return arg.kind==='target'?{kind:'ready',x:30,y:40,text:'old',modifier:'Control'}:{kind:'ready'};},nativeClick:async(...args)=>calls.push(['click',...args]),nativeKeyPress:async(...args)=>calls.push(['key',...args]),nativeType:async value=>calls.push(['type',value]),cdp:async(method,event)=>calls.push(['edit',method,event]),...overrides};}
test('bound preparation exposes scoped fill only and verifies focus and selection around native replacement',async()=>{
  const calls=[],page=homeBoundPage(textBackend(calls),'form_prepare');
  assert(Object.isFrozen(page));assert.equal(typeof page.fillText,'function');
  assert.equal(homeBoundPage(textBackend([]),'form_choices').fillText,undefined);
  await page.fillText(editor,'新\n稿',{nth:0});
  assert.deepEqual(calls,[['read','readHomeBoundTextDOM','target'],['click',30,40],['read','readHomeBoundTextDOM','focus'],['edit','Input.dispatchKeyEvent',{type:'keyDown',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2,commands:['selectAll']}],['edit','Input.dispatchKeyEvent',{type:'keyUp',key:'a',code:'KeyA',windowsVirtualKeyCode:65,modifiers:2}],['read','readHomeBoundTextDOM','selected'],['type','新'],['read','readHomeBoundTextDOM','caret'],['edit','Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,modifiers:8,commands:['insertLineBreak']}],['edit','Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,modifiers:8}],['read','readHomeBoundTextDOM','caret'],['type','稿'],['read','readHomeBoundTextDOM','readback']]);
});
test('empty native replacement uses verified Backspace, not an empty insert or submit key',async()=>{
  const calls=[];await homeBoundPage(textBackend(calls),'form_prepare').fillText(editor,'',{nth:0});
  assert.deepEqual(calls.filter(x=>x[0]==='edit'&&x[2].type==='keyDown').map(x=>x[2].commands),[['selectAll'],['deleteBackward']]);
  assert.equal(calls.filter(x=>x[0]==='type').length,0);
});
test('fill rejects arbitrary selectors and values or missing native APIs before input',async()=>{
  for(const[selector,value,nth]of [['button[aria-label="开始生成"]','x',0],[editor,[],0],[editor,'x',1],[editor,'x'.repeat(20001),0],['section[aria-label="偏好设置"] input[aria-label="视频时长秒数"]','1e2',0]]){
    const calls=[];await assert.rejects(homeBoundPage(textBackend(calls),'form_prepare').fillText(selector,value,{nth}),e=>e.code==='invalid_argument');assert.deepEqual(calls,[]);
  }
  const calls=[];await assert.rejects(homeBoundPage(textBackend(calls,{nativeType:undefined}),'form_prepare').fillText(editor,'x',{nth:0}),e=>e.code==='unsupported_backend');assert.deepEqual(calls,[]);
});
test('changed focus or selection prevents native text replacement without a repeat',async()=>{
  for(const stage of ['focus','selected']){
    let clicks=0,types=0;
    const page=homeBoundPage(textBackend([],{evaluate:async(fn,arg)=>arg.kind==='target'?{kind:'ready',x:1,y:2,text:'old',modifier:'Meta'}:arg.kind===stage?{kind:'selection_changed'}:{kind:'ready'},nativeClick:async()=>clicks++,nativeType:async()=>types++}),'form_prepare');
    await assert.rejects(page.fillText(editor,'new',{nth:0}),e=>e.code==='selection_changed'&&e.input_phase===stage);
    assert.equal(clicks,1);assert.equal(types,0);
  }
});
test('native replacement failure retains input phase and sanitized uncertain outcome, once',async()=>{
  let types=0;
  const page=homeBoundPage(textBackend([],{nativeType:async()=>{types++;throw Error('FAKE_PRIVATE_TOKEN');}}),'form_prepare');
  await assert.rejects(page.fillText(editor,'new',{nth:0}),e=>e.code==='bridge_failed'&&e.outcome_uncertain===true&&e.input_phase==='replace'&&!e.message.includes('FAKE_PRIVATE'));
  assert.equal(types,1);
});
test('literal readback mismatch is an explicit applied-input failure, not a retry',async()=>{
  let types=0;
  const page=homeBoundPage(textBackend([],{evaluate:async(fn,arg)=>arg.kind==='target'?{kind:'ready',x:1,y:2,text:'old',modifier:'Control'}:arg.kind==='readback'?{kind:'settings_changed'}:{kind:'ready'},nativeType:async()=>types++}),'form_prepare');
  await assert.rejects(page.fillText(editor,'new',{nth:0}),e=>e.code==='settings_changed'&&e.outcome_uncertain===true&&e.input_phase==='readback');assert.equal(types,1);
});
