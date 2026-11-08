import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkModePin,inspectModeChoices,prepareMode} from './mode.mjs';
for(const name of ['mode-choices','mode-prepare'])cli({site:'xyq-web',name,access:'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Discover media modes or select one on an exact empty draft; no uploads or generation',columns:['result'],
  args:[{name:'pin',type:'string',default:'',help:'Reviewed mode bundle SHA256'},...(name==='mode-prepare'?[{name:'settings',type:'string',required:true,help:'JSON with mode and expected_draft_sha256'}]:[])],
  func:async(page,args)=>{try{checkModePin(args.pin);return await(name==='mode-choices'?inspectModeChoices(page):prepareMode(page,args.settings));}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ mode adapter failed; inspect the form.');
      if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,completed_steps:e.completed_steps||[],cleanup_code:e.cleanup_code||null}));}}
});
