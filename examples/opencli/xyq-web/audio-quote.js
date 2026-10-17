import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkAudioQuotePin,inspectAudioQuote} from './audio-quote.mjs';
cli({site:'xyq-web',name:'audio-quote',access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Read the exact audio draft displayed credit rate, never a total-cost ceiling',columns:['result'],
  args:[{name:'pin',type:'string',default:'',help:'Reviewed audio quote SHA256'},...['project','canvas','node'].map(name=>({name,type:'string',required:true,help:'Exact observed ID'})),{name:'settings',type:'string',required:true,help:'Exact observed form SHA JSON'}],
  func:async(page,args)=>{try{checkAudioQuotePin(args.pin);return await inspectAudioQuote(page,{project_id:args.project,canvas_id:args.canvas,node_id:args.node},args.settings);}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ quote read failed; inspect the current draft.');if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));}}
});
