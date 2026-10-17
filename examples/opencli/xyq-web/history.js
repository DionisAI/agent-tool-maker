import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkHistoryPin,inspectBoundProjectHistory} from './history.mjs';
cli({site:'xyq-web',name:'project-history-state-bound',access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Read current project history view/filter/empty state, never unverified task rows',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed history view SHA'},...['project','canvas'].map(name=>({name,type:'string',required:true,help:'Exact observed ID'}))],
  func:async(page,args)=>{try{checkHistoryPin(args.pin);return await inspectBoundProjectHistory(page,{project_id:args.project,canvas_id:args.canvas});}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('Project history view failed; inspect the explicitly bound project.');
      if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));}}
});
