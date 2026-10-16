import {createInterface} from 'node:readline';
import {inspectConversationResults} from '../../examples/opencli/xyq-web/results.mjs';
const config=JSON.parse(process.argv[2]);
const lines=createInterface({input:process.stdin});let next=0;
async function evaluate(fn,arg){const id=++next;process.stdout.write(JSON.stringify({type:'call',id,method:'evaluate',source:fn.toString(),arg})+'\n');const line=await lines[Symbol.asyncIterator]().next();const value=JSON.parse(line.value);if(value.id!==id||value.error)throw Error('fixture read error');return value.value;}
try{
  const raw={thread_id:config.thread_id},page={evaluate};
  const results=await inspectConversationResults(page,raw);
  let inspect=null,quote=null;
  if(results[0].result.results.length){
    const item=results[0].result.results[0];
    inspect=await inspectConversationResults(page,{...raw,result_id:item.result_id},'result_inspect');
    if(item.surface==='artifact_preview')quote=await inspectConversationResults(page,{...raw,result_id:item.result_id,expected_result_sha256:item.result_sha256},'result_download_quote');
  }
  process.stdout.write(JSON.stringify({type:'done',results,inspect,quote})+'\n');
}catch(e){process.stdout.write(JSON.stringify({type:'done',error:{code:e.code||'fixture_error'}})+'\n');}
finally{lines.close();}
