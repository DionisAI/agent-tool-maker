import {createInterface} from 'node:readline';
import {downloadExistingResult,checkDownloadPin} from '../../examples/opencli/xyq-web/download.mjs';
import {inspectConversationResults} from '../../examples/opencli/xyq-web/results.mjs';
const config=JSON.parse(process.argv[2]),lines=createInterface({input:process.stdin}),pending=new Map();let seq=0;
lines.on('line',line=>{const r=JSON.parse(line),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.reject(Error('fixture call failed')):p.resolve(r.value);});
const call=(method,rest)=>new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(Error('fixture timeout'));},25000);pending.set(id,{resolve,reject,timer});process.stdout.write(JSON.stringify({type:'call',id,method,...rest})+'\n');});
const page={evaluate:(fn,arg)=>call('evaluate',{source:fn.toString(),arg}),nativeClick:(x,y)=>call('nativeClick',{x,y}),waitForDownload:(pattern,timeout)=>call('waitForDownload',{pattern,timeout})};
try{
  let result;
  if(config.operation==='quote'){
    const item=(await inspectConversationResults(page,config.scope,'result_inspect'))[0].result;
    result=await inspectConversationResults(page,{...config.scope,expected_result_sha256:item.result_sha256},'result_download_quote');
  }else {if(config.adapter_pin)checkDownloadPin(config.adapter_pin);result=await downloadExistingResult(page,config.settings,config.workspace);}
  process.stdout.write(JSON.stringify({type:'done',result})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_failed'}})+'\n');}
finally{for(const p of pending.values())clearTimeout(p.timer);lines.close();}
