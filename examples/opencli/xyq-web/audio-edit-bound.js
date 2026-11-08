import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {AUDIO_EDIT_BOUND_OPERATIONS,checkAudioEditBoundPin,runBoundAudioEdit} from './audio-edit-bound.mjs';
for(const operation of AUDIO_EDIT_BOUND_OPERATIONS)cli({site:'xyq-web',name:operation.replaceAll('_','-')+'-bound',access:operation==='audio_choices'?'read':'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Explicit bound audio model/rate or prompt/uploaded-reference preparation, never generation',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed bound audio preparation SHA256'},...['project','canvas','node'].map(name=>({name,type:'string',required:true,help:'Exact observed ID'})),...(operation==='audio_choices'?[]:[{name:'settings',type:'string',required:true,help:'Typed exact form/model/rate/prompt/reference settings'}])],
  func:async(page,args)=>{try{checkAudioEditBoundPin(args.pin);return await runBoundAudioEdit(page,operation,{project_id:args.project,canvas_id:args.canvas,node_id:args.node},args.settings);}
  catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ bound audio preparation failed; inspect the exact draft.');if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
    throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,input_phase:e.input_phase||null,completed_steps:e.completed_steps||[],outcome_uncertain:e.outcome_uncertain??false,cleanup_code:e.cleanup_code||null}));}}
});
