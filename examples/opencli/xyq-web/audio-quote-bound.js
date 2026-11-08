import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkAudioQuoteBoundPin,inspectBoundAudioQuote} from './audio-quote-bound.mjs';

cli({site:'xyq-web',name:'audio-quote-bound',access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Read the exact bound audio draft displayed credit rate, never total cost',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed explicit bound quote SHA256'},...['project','canvas','node'].map(name=>({name,type:'string',required:true,help:'Exact observed ID'})),{name:'settings',type:'string',required:true,help:'Exact observed form SHA JSON'}],
  func:async(page,args)=>{try{
    checkAudioQuoteBoundPin(args.pin);
    return await inspectBoundAudioQuote(page,{project_id:args.project,canvas_id:args.canvas,node_id:args.node},args.settings);
  }catch(e){
    if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ bound quote failed; inspect the explicitly bound audio draft.');
    if(e.code==='invalid_argument')throw new ArgumentError(e.message);
    if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
    throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));
  }}
});
