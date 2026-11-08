// Evaluate-only native fixture; no authentication or real provider connection.
import {createInterface} from 'node:readline';
import {inspectBoundProjectHistory} from '../../examples/opencli/xyq-web/history.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let sequence=0;
lines.on('line',line=>{const r=JSON.parse(line),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.reject(Error('Fixture read failed')):p.resolve(r.value);});
const evaluate=(fn,arg)=>new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(Error('Fixture timeout'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method:'evaluate',source:fn.toString(),arg})+'\n');});
try{const c=JSON.parse(process.argv[2]),result=await inspectBoundProjectHistory({},c.scope,async()=>({evaluate}));process.stdout.write(JSON.stringify({type:'done',result})+'\n');}
catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed'}})+'\n');}finally{lines.close();}
