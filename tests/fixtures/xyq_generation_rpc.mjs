// Local native fixture only. No provider API or account execution.
import {createInterface} from 'node:readline';
import {inspectFormState} from '../../examples/opencli/xyq-web/form.mjs';
import {inspectHomeQuote} from '../../examples/opencli/xyq-web/home-quote.mjs';
import {generateHome,generationStatus} from '../../examples/opencli/xyq-web/generation.mjs';
import {runMediaOperation,checkMediaRuntimePin,mediaRuntimeDigest} from '../../examples/opencli/xyq-web/media-runtime.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let sequence=0;
lines.on('line',line=>{const r=JSON.parse(line),c=pending.get(r.id);if(!c)return;pending.delete(r.id);clearTimeout(c.timer);r.error?c.reject(Error('Fixture acknowledgement failed')):c.resolve(r.value);});
function call(method,params){return new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(Error('Fixture timed out'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method,...params})+'\n');});}
try{const config=JSON.parse(process.argv[2]),page={evaluate:(fn,arg)=>call('evaluate',{source:fn.toString(),arg}),nativeClick:(x,y)=>call('nativeClick',{x,y})};
  const state=(await inspectFormState(page))[0].result,quote=(await inspectHomeQuote(page,{expected_draft_sha256:state.draft_sha256}))[0].result;
  const settings={expected_draft_sha256:state.draft_sha256,quote_sha256:quote.quote_sha256,max_credits:6,human_confirmed:true,estimated_cost_confirmed:true,request_key:'native-once',...config.settings};
  if(config.runtime)checkMediaRuntimePin(mediaRuntimeDigest());
  const args={settings,workspace:config.workspace},factories={generation:async()=>page};
  const result=config.runtime?await runMediaOperation({},'generate',args,factories):await generateHome(page,settings,config.workspace);
  const reused=config.runtime?await runMediaOperation({},'generate',args,factories):await generateHome({},settings,config.workspace);
  const status=config.runtime?await runMediaOperation(null,'generation_status',{workspace:config.workspace,key:settings.request_key}):generationStatus(config.workspace,settings.request_key);
  process.stdout.write(JSON.stringify({type:'done',result,reused,status,runtime:config.runtime===true})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed'}})+'\n');}finally{lines.close();}
