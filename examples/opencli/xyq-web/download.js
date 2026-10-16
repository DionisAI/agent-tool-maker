import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkDownloadPin,downloadBoundResult} from './download.mjs';
cli({site:'xyq-web',name:'result-download-bound',access:'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'One exact already-open image-result download; retained unknown intent, no generation',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed one-download closure SHA'},{name:'workspace',type:'string',required:true,help:'Exact original project directory'},
    {name:'settings',type:'string',required:true,help:'Exact result/draft plan/key and human confirmation JSON'}],
  func:async(page,args)=>{try{checkDownloadPin(args.pin);return await downloadBoundResult(page,args.settings,args.workspace);}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('Download transport failed; inspect the original receipt, not a second request.');
      if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);if(['invalid_argument','confirmation_required'].includes(e.code))throw new ArgumentError(e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));}}
});
