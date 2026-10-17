import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkGenerationPin,generateBoundHome,generationStatus} from './generation.mjs';
for(const[name,access,args,run]of[
  ['generate-home-bound','write',[{name:'settings',type:'string',required:true,help:'Exact draft/quote/budget and human confirmation JSON'}],(page,a)=>generateBoundHome(page,a.settings,a.workspace)],
  ['generation-status','read',[{name:'key',type:'string',required:true,help:'Original generation request key'}],(_,a)=>generationStatus(a.workspace,a.key)],
])cli({site:'xyq-web',name,access,domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Draft-bound media '+name+'; one submit attempt, retained unknown request, no auth reads',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed generation source SHA'},{name:'workspace',type:'string',required:true,help:'Exact original project directory'},...args],
  func:async(page,args)=>{try{checkGenerationPin(args.pin);return await run(page,args);}catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('Media generation transport failed; inspect the retained request.');
    if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);if(['invalid_argument','confirmation_required'].includes(e.code))throw new ArgumentError(e.message);
    throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));}}
});
