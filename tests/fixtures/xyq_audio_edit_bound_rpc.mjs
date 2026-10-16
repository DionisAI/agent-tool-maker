// Isolated native fixture only; public backend APIs match reviewed runtime.
import {createInterface} from 'node:readline';
import {inspectAudioForm} from '../../examples/opencli/xyq-web/audio.mjs';
import {runBoundAudioEdit} from '../../examples/opencli/xyq-web/audio-edit-bound.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let seq=0;const calls={};
lines.on('line',line=>{const r=JSON.parse(line),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.reject(Error('Native audio fixture step failed.')):p.resolve(r.value);});
function rpc(method,args){calls[method]=(calls[method]||0)+1;return new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(Error('Native audio fixture timeout.'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method,...args})+'\n');});}
const backend={evaluate:(fn,arg)=>rpc('evaluate',{source:fn.toString(),arg}),nativeClick:(x,y)=>rpc('native_click',{x,y}),nativeKeyPress:key=>rpc('native_key',{key}),nativeType:text=>rpc('native_type',{text}),cdp:(command,event)=>rpc('native_edit',{command,event})};
try{
  const config=JSON.parse(process.argv[2]),before=(await inspectAudioForm(backend,config.scope))[0].result;
  const settings=config.operation==='audio_choices'?undefined:{expected_form_sha256:before.form_sha256,...config.settings};
  const result=await runBoundAudioEdit({contextId:'fixture'},config.operation,config.scope,settings,async()=>backend);
  process.stdout.write(JSON.stringify({type:'done',before,result,calls})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',calls,error:{code:e.code||'fixture_failed',phase:e.phase||null,input_phase:e.input_phase||null,completed_steps:e.completed_steps||[],outcome_uncertain:e.outcome_uncertain??false,cleanup_code:e.cleanup_code||null}})+'\n');}finally{lines.close();}
