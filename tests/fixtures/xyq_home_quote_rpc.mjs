// Isolated evaluate-only native fixture, not real provider acceptance.
import {createInterface} from 'node:readline';
import {inspectFormState} from '../../examples/opencli/xyq-web/form.mjs';
import {inspectBoundHomeQuote} from '../../examples/opencli/xyq-web/home-quote.mjs';
const lines=createInterface({input:process.stdin}),pending=new Map();let sequence=0;
lines.on('line',line=>{const r=JSON.parse(line),c=pending.get(r.id);if(!c)return;pending.delete(r.id);clearTimeout(c.timer);r.error?c.reject(Error('Fixture evaluate failed')):c.resolve(r.value);});
function evaluate(fn,arg){return new Promise((resolve,reject)=>{const id=++sequence,timer=setTimeout(()=>{pending.delete(id);reject(Error('Fixture timed out'));},5000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method:'evaluate',source:fn.toString(),arg})+'\n');});}
try{const config=JSON.parse(process.argv[2]),page={evaluate},before=config.skip_before?null:(await inspectFormState(page))[0].result;
  const settings={expected_draft_sha256:before?.draft_sha256,...config.settings};
  const result=await inspectBoundHomeQuote({},settings,async()=>page);
  // The fixture needs only the baseline digest, not the old reader's raw cost observations.
  process.stdout.write(JSON.stringify({type:'done',before:before?{draft_sha256:before.draft_sha256}:null,result})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed'}})+'\n');}finally{lines.close();}
