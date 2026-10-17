import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkResultPin,inspectBoundConversationResults} from './results.mjs';
for(const operation of ['results','result_inspect','result_download_quote'])cli({site:'xyq-web',name:operation.replaceAll('_','-')+'-bound',
  access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Read exact already-open conversation image results; resource IDs are not task IDs',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed result-reader source SHA'},{name:'thread',type:'string',required:true,help:'Exact observed conversation ID'},
    ...(operation==='results'?[]:[{name:'result',type:'string',required:true,help:'Exact media resource ID'}]),
    ...(operation==='result_download_quote'?[{name:'expected',type:'string',required:true,help:'Exact selected result digest'}]:[])],
  func:async(page,a)=>{try{checkResultPin(a.pin);return await inspectBoundConversationResults(page,{thread_id:a.thread,
    ...(operation==='results'?[]:{result_id:a.result}),...(operation==='result_download_quote'?{expected_result_sha256:a.expected}:{})},operation);}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('Conversation result query failed; inspect the explicitly bound page.');
      if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));}}
});
