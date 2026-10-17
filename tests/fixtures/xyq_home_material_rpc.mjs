// Evaluate-only RPC against an intercepted native DOM, never a provider.
import {createInterface} from 'node:readline';
import {inspectBoundHomeMaterials,checkHomeMaterialPin,homeMaterialDigest} from '../../examples/opencli/xyq-web/material-home.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let sequence=0;
lines.on('line',line=>{const response=JSON.parse(line),call=pending.get(response.id);if(!call)return;pending.delete(response.id);clearTimeout(call.timer);response.error?call.reject(Error('Fixture evaluation failed')):call.resolve(response.value);});
const evaluate=(fn,arg)=>new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(Error('Fixture evaluation timed out'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'evaluate',id,source:fn.toString(),arg})+'\n');});
try{
  checkHomeMaterialPin(homeMaterialDigest());
  const operation=JSON.parse(process.argv[2]).operation;
  const result=await inspectBoundHomeMaterials({preferredContextId:'fixture-profile'},operation,async()=>({evaluate}));
  process.stdout.write(JSON.stringify({type:'done',result,provider_called:false})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed'}})+'\n');}finally{lines.close();}
