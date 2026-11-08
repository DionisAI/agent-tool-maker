import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkAudioSettingsPin,inspectAudioChoices,prepareAudioSettings} from './audio-settings.mjs';
for(const name of ['audio-choices','audio-prepare'])cli({site:'xyq-web',name,access:name==='audio-choices'?'read':'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Discover or prepare current audio-node model/sample-rate controls; no upload or generation',columns:['result'],
  args:[{name:'pin',type:'string',default:'',help:'Reviewed audio settings adapter SHA256'},...['project','canvas','node'].map(name=>({name,type:'string',required:true,help:'Exact observed ID'})),...(name==='audio-prepare'?[{name:'settings',type:'string',required:true,help:'Typed form-digest/model/rate settings'}]:[])],
  func:async(page,args)=>{try{checkAudioSettingsPin(args.pin);const scope={project_id:args.project,canvas_id:args.canvas,node_id:args.node};return await(name==='audio-choices'?inspectAudioChoices(page,scope):prepareAudioSettings(page,scope,args.settings));}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ audio settings adapter failed; inspect the current draft.');if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,completed_steps:e.completed_steps||[],outcome_uncertain:e.outcome_uncertain??false,cleanup_code:e.cleanup_code||null}));}}
});
