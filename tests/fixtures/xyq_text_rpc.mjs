import {createInterface} from 'node:readline';
import {inspectText,prepareText} from '../../examples/opencli/xyq-web/text.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let seq=0;
lines.on('line',line=>{const r=JSON.parse(line),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.reject(new Error('Native fixture step failed.')):p.resolve(r.value);});
function rpc(method,args){return new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(new Error('Native fixture timeout.'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method,...args})+'\n');});}
const page={evaluate:(fn,arg)=>rpc('evaluate',{source:fn.toString(),arg}),click:(selector,options)=>rpc('click',{selector,options}),fillText:(selector,value,options)=>rpc('fill',{selector,value,options}),focus:(selector,options)=>rpc('focus',{selector,options}),cdp:(method,params)=>rpc('cdp',{cdp_method:method,params})};
try{const config=JSON.parse(process.argv[2]),scope={project_id:'1',canvas_id:'2',node_id:'3'},before=(await inspectText(page,scope))[0].result;
  const result=config.operation==='inspect'?[{result:before}]:await prepareText(page,scope,{expected_content_sha256:before.content_sha256,...config.settings});
  process.stdout.write(JSON.stringify({type:'done',before,result})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed',message:e.message,phase:e.phase||null,completed_steps:e.completed_steps||[]}})+'\n');}finally{lines.close();}
