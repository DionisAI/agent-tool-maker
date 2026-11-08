import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkAudioUploadBoundPin,runBoundAudioUpload} from './audio-upload-bound.mjs';
cli({site:'xyq-web',name:'audio-reference-upload-bound',access:'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Attach one approved PCM WAV / MP3 on the exact bound audio footer; preflight conflicts stop explicitly',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed explicit bound upload SHA256'},...['project','canvas','node'].map(name=>({name,type:'string',required:true,help:'Exact observed ID'})),{name:'settings',type:'string',required:true,help:'Approved typed PCM WAV / MP3, draft, key and mode JSON'},{name:'workspace',type:'string',required:true,help:'Project-owned file/receipt directory'}],
  func:async(page,args)=>{try{checkAudioUploadBoundPin(args.pin);return await runBoundAudioUpload(page,{project_id:args.project,canvas_id:args.canvas,node_id:args.node},args.settings,args.workspace);}
  catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ bound audio attachment failed; inspect the retained draft and intent.');if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
    throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,completed_steps:e.completed_steps||[],outcome_uncertain:e.outcome_uncertain??true,diagnostic_status:e.diagnostic_status||null}));}}
});
