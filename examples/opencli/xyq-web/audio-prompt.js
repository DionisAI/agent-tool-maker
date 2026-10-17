import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkAudioPromptPin,prepareAudioPrompt} from './audio-prompt.mjs';
cli({site:'xyq-web',name:'audio-prompt-prepare',access:'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Prepare plain text and a structured existing audio-reference mention without generation',columns:['result'],
  args:[{name:'pin',type:'string',default:'',help:'Reviewed prompt adapter SHA256'},...['project','canvas','node'].map(name=>({name,type:'string',required:true,help:'Exact ID'})),{name:'settings',type:'string',required:true,help:'Typed exact-digest prompt/reference settings'}],
  func:async(page,args)=>{try{checkAudioPromptPin(args.pin);return await prepareAudioPrompt(page,{project_id:args.project,canvas_id:args.canvas,node_id:args.node},args.settings);}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ audio prompt adapter failed; inspect the current draft.');if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,completed_steps:e.completed_steps||[],outcome_uncertain:e.outcome_uncertain??false}));}}
});
