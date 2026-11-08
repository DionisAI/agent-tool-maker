import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkFormPin,inspectFormState,inspectFormChoices,prepareForm} from './form.mjs';
for(const name of ['form-state','form-choices','form-prepare'])cli({
  site:'xyq-web',name,access:name==='form-state'?'read':'write',domain:'xyq.jianying.com',strategy:Strategy.UI,
  browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Inspect or prepare the current creative composer with exact draft binding; no uploads or generation',
  args:[{name:'pin',type:'string',default:'',help:'Required reviewed form bundle SHA256'},...(name==='form-prepare'?[{name:'settings',type:'string',required:true,help:'Typed JSON including expected_draft_sha256'}]:[])],columns:['result'],
  func:async(page,args)=>{try{checkFormPin(args.pin);return await(name==='form-state'?inspectFormState(page):name==='form-choices'?inspectFormChoices(page):prepareForm(page,args.settings));}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ form adapter failed; inspect the current draft.');
      if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      if(e.code==='invalid_argument')throw new ArgumentError(e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,completed_steps:e.completed_steps||[],cleanup_code:e.cleanup_code||null}));}}
});
