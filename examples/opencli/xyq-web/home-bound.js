import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {HOME_BOUND_OPERATIONS,checkHomeBoundPin,runHomeBoundOperation} from './home-bound.mjs';
for(const operation of HOME_BOUND_OPERATIONS)cli({site:'xyq-web',name:operation.replaceAll('_','-')+'-bound',access:operation==='form_state'?'read':'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Explicit existing-home binding: inspect, switch an empty draft or prepare hash-bound semantic settings and plain text; no upload or generation',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed home-binding source SHA256'},...(['mode_prepare','form_prepare'].includes(operation)?[{name:'settings',type:'string',required:true,help:'Typed JSON with exact draft digest and semantic media settings'}]:[])],
  func:async(page,args)=>{try{checkHomeBoundPin(args.pin);return await runHomeBoundOperation(page,operation,args.settings);}
    catch(error){if(!(error instanceof XyqError))throw new CommandExecutionError('XYQ home binding failed; inspect the current draft.');
      if(error.code==='invalid_argument')throw new ArgumentError(error.message);
      if(error.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',error.message);
      throw new CommandExecutionError(JSON.stringify({code:error.code,message:error.message,phase:error.phase||null,input_phase:error.input_phase||null,completed_steps:error.completed_steps||[],cleanup_code:error.cleanup_code||null,outcome_uncertain:error.outcome_uncertain??false}));}}
});
