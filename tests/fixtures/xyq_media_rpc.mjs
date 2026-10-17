// Test-only isolated native bridge, no production browser/profile/provider.
import {createInterface} from 'node:readline';
import {inspectFormState} from '../../examples/opencli/xyq-web/form.mjs';
import {inspectModeChoices,prepareMode} from '../../examples/opencli/xyq-web/mode.mjs';
import {inspectAudioForm,uploadAudioReference} from '../../examples/opencli/xyq-web/audio.mjs';
import {inspectBoundAudioForm} from '../../examples/opencli/xyq-web/audio-bound.mjs';
import {prepareAudioPrompt} from '../../examples/opencli/xyq-web/audio-prompt.mjs';
import {inspectAudioChoices,prepareAudioSettings} from '../../examples/opencli/xyq-web/audio-settings.mjs';
import {inspectAudioQuote} from '../../examples/opencli/xyq-web/audio-quote.mjs';
import {inspectBoundAudioQuote} from '../../examples/opencli/xyq-web/audio-quote-bound.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let seq=0;
lines.on('line',line=>{const r=JSON.parse(line),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.reject(new Error('Native media fixture step failed.')):p.resolve(r.value);});
function rpc(method,args){return new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(new Error('Native fixture timed out.'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method,...args})+'\n');});}
const page={evaluate:(fn,arg)=>rpc('evaluate',{source:fn.toString(),arg}),click:(selector,options)=>rpc('click',{selector,options}),fillText:(selector,value,options)=>rpc('fill',{selector,value,options}),focus:(selector,options)=>rpc('focus',{selector,options}),pressKey:key=>rpc('key',{key}),cdp:(command,args)=>rpc('cdp',{command,args})};
try{const config=JSON.parse(process.argv[2]);let before,result;
  if(config.operation.startsWith('mode')){before=(await inspectFormState(page))[0].result;result=config.operation==='mode_choices'?await inspectModeChoices(page):await prepareMode(page,{expected_draft_sha256:before.draft_sha256,...config.settings});}
  else{before=(await inspectAudioForm(page,config.scope))[0].result;result=config.operation==='audio_quote_bound'?await inspectBoundAudioQuote({contextId:'fixture'},config.scope,{expected_form_sha256:before.form_sha256,...config.settings},async()=>({evaluate:page.evaluate})):config.operation==='audio_bound'?await inspectBoundAudioForm({contextId:'fixture'},config.scope,async()=>({evaluate:page.evaluate})):config.operation==='audio_state'?[{result:before}]:config.operation==='audio_quote'?await inspectAudioQuote(page,config.scope,{expected_form_sha256:before.form_sha256,...config.settings}):config.operation==='audio_prompt'?await prepareAudioPrompt(page,config.scope,{expected_form_sha256:before.form_sha256,...config.settings}):config.operation==='audio_choices'?await inspectAudioChoices(page,config.scope):config.operation==='audio_prepare'?await prepareAudioSettings(page,config.scope,{expected_form_sha256:before.form_sha256,...config.settings}):await uploadAudioReference(page,config.scope,{expected_form_sha256:before.form_sha256,...config.settings},config.workspace);}
  process.stdout.write(JSON.stringify({type:'done',before,result})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed',phase:e.phase||null,completed_steps:e.completed_steps||[],outcome_uncertain:e.outcome_uncertain??false,cleanup_code:e.cleanup_code||null}})+'\n');}finally{lines.close();}
