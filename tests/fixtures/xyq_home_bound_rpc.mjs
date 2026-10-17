// Test-only native backend. No real provider, profile or authentication.
import {createInterface} from 'node:readline';
import {inspectFormState} from '../../examples/opencli/xyq-web/form.mjs';
import {runHomeBoundOperation} from '../../examples/opencli/xyq-web/home-bound.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let sequence=0;
lines.on('line',line=>{const response=JSON.parse(line),call=pending.get(response.id);if(!call)return;pending.delete(response.id);clearTimeout(call.timer);response.error?call.reject(Error('Native home fixture step failed')):call.resolve(response.value);});
const calls={};
function rpc(method,args){calls[method]=(calls[method]||0)+1;return new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(Error('Native home fixture timeout'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method,...args})+'\n');});}
const backend={evaluate:(fn,arg)=>rpc('evaluate',{source:fn.toString(),arg}),nativeClick:(x,y)=>rpc('native_click',{x,y}),nativeKeyPress:(key,modifiers=[])=>rpc('native_key',{key,modifiers}),nativeType:text=>rpc('native_type',{text}),cdp:(command,event)=>rpc('native_edit',{command,event})};
try{const config=JSON.parse(process.argv[2]),before=config.skip_before?null:(await inspectFormState(backend))[0].result;
  const settings=['mode_prepare','form_prepare'].includes(config.operation)?{expected_draft_sha256:before.draft_sha256,...config.settings}:undefined;
  const result=await runHomeBoundOperation({contextId:'fixture'},config.operation,settings,async()=>backend);
  process.stdout.write(JSON.stringify({type:'done',before,result,calls})+'\n');
}catch(error){process.stdout.write(JSON.stringify({type:'done',calls,error:{code:error.code||'fixture_failed',phase:error.phase||null,input_phase:error.input_phase||null,outcome_uncertain:error.outcome_uncertain??false,completed_steps:error.completed_steps||[],cleanup_code:error.cleanup_code||null}})+'\n');}
finally{lines.close();}
