import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkHomeUploadPin,runBoundHomeUpload,homeUploadStatus} from './home-upload.mjs';
for(const operation of ['home_reference_upload','home_upload_status']){
  const local=operation==='home_upload_status';
  const run=async(context,args)=>{try{checkHomeUploadPin(args.pin);return local?homeUploadStatus(args.workspace,args.key):await runBoundHomeUpload(context,args.settings,args.workspace);}catch(e){
    if(!(e instanceof XyqError))throw new CommandExecutionError('Homepage upload failed; preserve the original request.');
    if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
    if(['invalid_argument','confirmation_required'].includes(e.code))throw new ArgumentError(e.message);
    throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,outcome_uncertain:e.outcome_uncertain??null,native_input_attempted:e.native_input_attempted??null,retention_failure_code:e.retention_failure_code||null,automatic_retry_permitted:false}));}
  };
  cli({site:'xyq-home-upload',name:operation.replaceAll('_','-'),access:local?'read':'write',domain:'xyq.jianying.com',strategy:local?Strategy.LOCAL:Strategy.UI,browser:!local,siteSession:local?undefined:'persistent',navigateBefore:false,
    description:'One approved homepage media reference upload or original LOCAL receipt; no generation or automatic retry',columns:['result'],
    args:[{name:'pin',type:'string',required:true,help:'Reviewed complete source SHA'},{name:'workspace',type:'string',required:true,help:'Exact original project directory'},
      local?{name:'key',type:'string',required:true,help:'Original upload request key'}:{name:'settings',type:'string',required:true,help:'Exact file, draft, input, purpose and human confirmation JSON'}],
    func:local?(args,debug)=>run(null,args):(page,args)=>run(page,args)});
}
