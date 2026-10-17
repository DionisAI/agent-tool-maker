// Native intercepted DOM fixture; only evaluate is exposed to the caller.
import {createInterface} from 'node:readline';
import {runMediaOperation,checkMediaRuntimePin,mediaRuntimeDigest} from '../../examples/opencli/xyq-web/media-runtime.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let sequence=0;
lines.on('line',line=>{const r=JSON.parse(line),c=pending.get(r.id);if(!c)return;pending.delete(r.id);clearTimeout(c.timer);r.error?c.reject(Error('Fixture evaluation failed')):c.resolve(r.value);});
function call(fn,arg){return new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(Error('Fixture evaluation timed out'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'evaluate',id,source:fn.toString(),arg})+'\n');});}
try{
  const config=JSON.parse(process.argv[2]);checkMediaRuntimePin(mediaRuntimeDigest());
  const page={evaluate:call},factories={homeRead:async()=>page,home:async()=>page};
  const result=await runMediaOperation({preferredContextId:'fixture-profile'},config.operation,{},factories);
  process.stdout.write(JSON.stringify({type:'done',result,provider_called:false})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed'}})+'\n');}finally{lines.close();}
