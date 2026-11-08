import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkAudioBoundPin,inspectBoundAudioForm} from './audio-bound.mjs';

cli({site:'xyq-web',name:'audio-form-state-bound',access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Explicitly read the exact audio form in the existing named browser binding; no fallback or input',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed bound-read source SHA256'},...['project','canvas','node'].map(name=>({name,type:'string',required:true,help:'Exact observed ID'}))],
  func:async(page,args)=>{try{
    checkAudioBoundPin(args.pin);
    return await inspectBoundAudioForm(page,{project_id:args.project,canvas_id:args.canvas,node_id:args.node});
  }catch(e){
    if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ bound reader failed; inspect the explicitly bound test page.');
    if(e.code==='invalid_argument')throw new ArgumentError(e.message);
    if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
    throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));
  }}
});
