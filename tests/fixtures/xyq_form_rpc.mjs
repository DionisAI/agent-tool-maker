// Test-only native fixture bridge. No provider, authentication or production tab.
import {createInterface} from 'node:readline';
import {inspectFormState,inspectFormChoices,prepareForm} from '../../examples/opencli/xyq-web/form.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let seq=0;
lines.on('line',line=>{const r=JSON.parse(line),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.reject(new Error('Native fixture step failed.')):p.resolve(r.value);});
function rpc(method,args){return new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(new Error('Native fixture bridge timed out.'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method,...args})+'\n');});}
const page={evaluate:(fn,arg)=>rpc('evaluate',{source:fn.toString(),arg}),click:(selector,options)=>rpc('click',{selector,options}),fillText:(selector,value,options)=>rpc('fill',{selector,value,options}),pressKey:key=>rpc('key',{key})};
try{
  const config=JSON.parse(process.argv[2]),before=(await inspectFormState(page))[0].result;
  const result=config.operation==='choices'?await inspectFormChoices(page):config.operation==='state'?[{result:before}]:await prepareForm(page,{expected_draft_sha256:before.draft_sha256,...config.settings});
  process.stdout.write(JSON.stringify({type:'done',before,result})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed',phase:e.phase||null,completed_steps:e.completed_steps||[],cleanup_code:e.cleanup_code||null}})+'\n');}
finally{lines.close();}
