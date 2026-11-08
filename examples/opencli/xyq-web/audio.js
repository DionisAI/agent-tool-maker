import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkAudioPin,inspectAudioForm,uploadAudioReference} from './audio.mjs';
for(const name of ['audio-form-state','audio-reference-upload'])cli({site:'xyq-web',name,access:name==='audio-form-state'?'read':'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Inspect current single-audio-node footer or attach one approved project PCM WAV / MP3; no generation',columns:['result'],
  args:[{name:'pin',type:'string',default:'',help:'Reviewed audio adapter SHA256'},...['project','canvas','node'].map(name=>({name,type:'string',required:true,help:'Exact observed ID'})),...(name==='audio-reference-upload'?[{name:'settings',type:'string',required:true,help:'Approved typed upload JSON'},{name:'workspace',type:'string',required:true,help:'ATM project-owned receipt directory'}]:[])],
  func:async(page,args)=>{try{checkAudioPin(args.pin);const scope={project_id:args.project,canvas_id:args.canvas,node_id:args.node};return await(name==='audio-form-state'?inspectAudioForm(page,scope):uploadAudioReference(page,scope,args.settings,args.workspace));}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ audio adapter failed; inspect the current draft.');if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,completed_steps:e.completed_steps||[],outcome_uncertain:e.outcome_uncertain??false}));}}
});
