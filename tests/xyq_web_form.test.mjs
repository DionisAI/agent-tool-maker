import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {XyqError} from '../examples/opencli/xyq-web/core.mjs';
import {parseSettings,formDigest,checkFormPin,inspectFormState,inspectFormChoices,prepareForm} from '../examples/opencli/xyq-web/form.mjs';

const clone=x=>structuredClone(x);
function fixture(){
  const d={kind:'ready',prompt:'FAKE_PRIVATE_PROMPT',prompt_tree:['P',[],['FAKE_PRIVATE_PROMPT']],rich_references:0,media:[],
    files:[{accept:'image/*',multiple:true,files:[]}],layers:0,preferences_layers:0};
  const f={mode:'视频生成',preferences:'模型选择和偏好设置：M0、720P、30秒',preferences_open:false,prompt_empty:false,prompt_characters:d.prompt.length,
    canvas:{checked:false,disabled:false},submit:{enabled:true},visible_cost_observations:[],quote_status:'not_final'};
  const o={kind:'ready',models:[{label:'M0',checked:true,disabled:false},{label:'M1',checked:false,disabled:false}],
    radios:[{group:'采样率',label:'44.1kHz',checked:true,disabled:false},{group:'采样率',label:'48kHz',checked:false,disabled:false}],
    numbers:[{label:'视频时长秒数',value:'30',min:null,max:null}],sliders:[{label:'视频秒数',min:'4',max:'30',value:'30'}],toggles:[],coverage:'currently_visible_options',all_options:false};
  const calls=[],s={d,f,o,last:null,covered:false,ignore:false,clickError:null,onClick:null};
  const pref=()=>f.preferences='模型选择和偏好设置：'+o.models.find(x=>x.checked).label+'、'+o.radios.find(x=>x.checked).label+'、'+o.numbers[0].value+'秒';
  const page={evaluate:async(fn,arg)=>{
    calls.push(['read',fn.name]);
    if(fn.name==='readHomeDOM')return{kind:'ready',agent:'创作',form:clone(f),credits:100};
    if(fn.name==='readDraftDOM')return clone(d);
    if(fn.name==='readOptionsDOM')return clone(o);
    if(fn.name==='readTargetDOM'){s.last=clone(arg);return{kind:'ready',nth:0,pointer_ready:!s.covered};}
    assert.fail('unknown reader '+fn.name);
  },click:async selector=>{
    calls.push(['click',selector]);assert.doesNotMatch(selector,/开始生成|上传素材|生成"|任务中心/);
    if(s.clickError)throw s.clickError;
    const t=s.last;
    if(t.kind==='preferences'){f.preferences_open=!f.preferences_open;d.layers=f.preferences_open?1:0;d.preferences_layers=d.layers;return;}
    if(!s.ignore){if(t.kind==='model'){for(const m of o.models)m.checked=m.label===t.label;pref();}
      if(t.kind==='radio'){for(const r of o.radios)if(r.group===t.group)r.checked=r.label===t.label;pref();}
      if(t.kind==='canvas')f.canvas.checked=!f.canvas.checked;}
    if(s.onClick)s.onClick(t);
  },pressKey:async key=>{
    assert.equal(key,'Escape');calls.push(['close',key]);
    if(s.covered)throw new XyqError('control_obscured','fixture cleanup failure');
    f.preferences_open=false;d.layers=0;d.preferences_layers=0;
  },fillText:async(selector,value)=>{
    calls.push(['fill',selector]);if(s.ignore)return;
    if(s.last.kind==='duration'){o.numbers[0].value=value;o.sliders[0].value=value;pref();}
    else{d.prompt=value;d.prompt_tree=value?['P',[],[value]]:null;f.prompt_empty=!value.trim();f.prompt_characters=value.length;}
  }};
  return{page,s,calls};
}
async function settings(x,more={}){return{expected_draft_sha256:(await inspectFormState(x.page))[0].result.draft_sha256,...more};}
test('form bundle pin covers all four modules',()=>{checkFormPin(formDigest());for(const v of ['',undefined,'0'.repeat(64)])assert.throws(()=>checkFormPin(v),e=>e.code==='definition_changed');});
test('strict schema rejects arbitrary controls before browser access',async()=>{
  for(const v of [null,[],{},'{','{"url":"https://x"}',{expected_draft_sha256:'0'.repeat(64),radios:[]},{expected_draft_sha256:'0'.repeat(64),canvas:1},{expected_draft_sha256:'0'.repeat(64),duration_seconds:0}]){
    assert.throws(()=>parseSettings(v),e=>e.code==='invalid_argument');await assert.rejects(prepareForm({evaluate:()=>assert.fail('browser read')},v),e=>e.code==='invalid_argument');}
});
test('state never reveals raw prompt or file names and only reads',async()=>{const x=fixture();x.s.d.files[0].files=[{name:'FAKE_PRIVATE_FILE',size:10,type:'image/png'}];const out=(await inspectFormState(x.page))[0].result;assert.equal(out.references.file_counts[0],1);assert.equal(out.draft_sha256.length,64);assert.doesNotMatch(JSON.stringify(out),/FAKE_PRIVATE/);assert(x.calls.every(c=>c[0]==='read'));});
test('choices opens and closes only owned menu without draft changes',async()=>{const x=fixture(),before=await settings(x);const out=(await inspectFormChoices(x.page))[0].result;assert.equal(out.draft_sha256,before.expected_draft_sha256);assert.equal(x.s.d.layers,0);assert.equal(x.calls.filter(c=>c[0]==='click').length,1);assert.deepEqual(x.calls.filter(c=>c[0]==='close'),[['close','Escape']]);});
test('existing layers are preserved with no click',async()=>{const x=fixture();x.s.d.layers=1;await assert.rejects(inspectFormChoices(x.page),e=>e.code==='dialog_open');assert(x.calls.every(c=>c[0]==='read'));});
test('stale digest stops all inputs',async()=>{const x=fixture();await assert.rejects(prepareForm(x.page,{expected_draft_sha256:'0'.repeat(64),prompt:'new'}),e=>e.code==='draft_changed'&&e.completed_steps.length===0);assert(x.calls.every(c=>c[0]==='read'));});
test('attachment-only card changes invalidate draft binding even with empty FileList',async()=>{const x=fixture(),request=await settings(x,{prompt:'new'});x.s.d.attachments=['DIV',[],['FAKE_PRIVATE_AUDIO']];x.s.d.attachment_present=true;await assert.rejects(prepareForm(x.page,request),e=>e.code==='draft_changed');assert(x.calls.every(c=>c[0]==='read'));});
test('attachment changes during preparation are preserved as explicit partial errors',async()=>{const x=fixture();x.s.d.attachments=['DIV',[],['FAKE_PRIVATE_AUDIO']];x.s.onClick=t=>{if(t.kind==='canvas')x.s.d.attachments=['DIV',[],['CHANGED_AUDIO']];};await assert.rejects(prepareForm(x.page,await settings(x,{canvas:true})),e=>e.code==='draft_changed'&&e.phase==='canvas');assert.equal(x.s.d.prompt,'FAKE_PRIVATE_PROMPT');});
test('unknown file state stops all inputs',async()=>{const x=fixture();x.s.d.files[0].files=null;await assert.rejects(prepareForm(x.page,await settings(x,{prompt:'new'})),e=>e.code==='reference_state_unknown');assert(x.calls.every(c=>c[0]==='read'));});
test('native model/radio/duration/canvas/prompt are verified and never submitted',async()=>{const x=fixture(),out=(await prepareForm(x.page,await settings(x,{model:'M1',radios:{'采样率':'48kHz'},duration_seconds:12,canvas:true,prompt:'test'})))[0].result;assert.equal(out.prepared,true);assert.equal(out.form.canvas.checked,true);assert.deepEqual(out.completed_steps,['model','radio:采样率','duration_seconds','canvas','prompt']);assert.equal(out.quote_status,'not_final');assert.equal(out.paid_submitted,false);assert.equal(out.upload_started,false);assert.equal(x.s.d.layers,0);assert.equal(x.s.d.prompt,'test');});
test('unknown dynamic choice closes owned menu and reports partial phase',async()=>{const x=fixture();await assert.rejects(prepareForm(x.page,await settings(x,{radios:{'other':'48kHz'}})),e=>e.code==='setting_unavailable'&&e.phase==='preferences');assert.equal(x.s.d.layers,0);assert.equal(x.calls.filter(c=>c[0]==='click').length,1);assert.equal(x.calls.filter(c=>c[0]==='close').length,1);});
test('out of observed duration bounds sends no duration input',async()=>{const x=fixture();await assert.rejects(prepareForm(x.page,await settings(x,{duration_seconds:31})),e=>e.code==='setting_unavailable');assert.equal(x.s.d.layers,0);assert(!x.calls.some(c=>c[0]==='fill'));});
test('ignored setting is failure, not fabricated success',async()=>{const x=fixture();x.s.ignore=true;await assert.rejects(prepareForm(x.page,await settings(x,{model:'M1'})),e=>e.code==='settings_changed'&&e.phase==='model');assert.equal(x.s.d.layers,0);});
test('model changing prompt stops before further parameter changes',async()=>{const x=fixture();x.s.onClick=t=>{if(t.kind==='model')x.s.d.prompt='changed';};await assert.rejects(prepareForm(x.page,await settings(x,{model:'M1',radios:{'采样率':'48kHz'}})),e=>e.code==='draft_changed');assert.equal(x.s.d.layers,0);assert(!x.s.o.radios[1].checked);});
test('partial preparation and failed cleanup are both traceable',async()=>{const x=fixture();x.s.onClick=t=>{if(t.kind==='model')x.s.covered=true;};await assert.rejects(prepareForm(x.page,await settings(x,{model:'M1',radios:{'采样率':'48kHz'}})),e=>e.code==='control_obscured'&&e.cleanup_code==='control_obscured'&&e.completed_steps.includes('model'));assert.equal(x.s.d.layers,1);});
test('rich reference prompt replacement stops without clearing references',async()=>{const x=fixture();x.s.d.rich_references=1;await assert.rejects(prepareForm(x.page,await settings(x,{prompt:''})),e=>e.code==='rich_prompt_present');assert(x.calls.every(c=>c[0]==='read'));});
test('disabled/covered controls never receive input',async()=>{const x=fixture();x.s.covered=true;await assert.rejects(prepareForm(x.page,await settings(x,{canvas:true})),e=>e.code==='control_obscured');assert(x.calls.every(c=>c[0]==='read'));});
test('native failures hide private diagnostics and retain phase',async()=>{const x=fixture();x.s.clickError=new Error('FAKE_PRIVATE_COOKIE');await assert.rejects(prepareForm(x.page,await settings(x,{canvas:true})),e=>e.code==='bridge_failed'&&e.phase==='canvas'&&!e.message.includes('FAKE_PRIVATE'));});
test('unrequested preference drift after canvas input is not success',async()=>{const x=fixture();x.s.onClick=t=>{if(t.kind==='canvas')x.s.f.preferences='changed';};await assert.rejects(prepareForm(x.page,await settings(x,{canvas:true})),e=>e.code==='draft_changed'&&e.phase==='final_readback');});
test('implicit changes exclude intentional settings',async()=>{const x=fixture();x.s.onClick=t=>{if(t.kind==='model'){x.s.o.radios[0].checked=false;x.s.o.radios[1].checked=true;x.s.f.canvas.checked=true;}};const out=(await prepareForm(x.page,await settings(x,{model:'M1'})))[0].result;assert.deepEqual(out.implicit_changes,{'radio:采样率':{before:'44.1kHz',after:'48kHz'},canvas:{before:false,after:true}});});
test('form source has no auth/storage, network, navigation or generic script execution',()=>{const s=readFileSync(new URL('../examples/opencli/xyq-web/form.mjs',import.meta.url),'utf8');assert.doesNotMatch(s,/document\.cookie|localStorage|sessionStorage|indexedDB|getCookies|page\.goto|fetch\(|XMLHttpRequest|\.evaluate\(['"`]/);});
