import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {StudioError} from './core.mjs';
import {checkDeliveryPin,textureQuote,texture,operationStatus} from './delivery.mjs';
const arg=(name,type,help,defaultValue='')=>({name,type,help,default:defaultValue});
for(const[name,access,args,run]of[
  ['texture-quote','write',[arg('asset','string','Exact source UUID'),arg('settings','string','Texture settings JSON','{}')],textureQuote],
  ['texture','write',[arg('asset','string','Exact source UUID'),arg('quote','string','Current texture quote SHA'),arg('budget','int','Approved credit limit',0),arg('key','string','Original stable request key'),arg('ledger','string','Exact project directory'),arg('confirm','bool','Explicit approval of this operation',false)],texture],
  ['operation-status','read',[arg('key','string','Original generation request key'),arg('ledger','string','Exact project directory'),arg('wait','int','Bounded provider read wait',0)],operationStatus],
])cli({site:'tripo-studio',name,access,domain:'studio.tripo3d.ai',description:'Tripo model delivery '+name+' with exact receipt/source/quote binding',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  args:[arg('pin','string','Reviewed delivery source SHA'),...args],columns:['result'],func:async(page,input)=>{
    try{checkDeliveryPin(input.pin);return(await run(page,input)).map(result=>({result}));}
    catch(e){if(!(e instanceof StudioError))throw new CommandExecutionError('Tripo delivery bridge failed; inspect the original operation receipt.');
      if(e.code==='login_required')throw new AuthRequiredError('studio.tripo3d.ai',e.message);
      if(['invalid_argument','confirmation_required'].includes(e.code))throw new ArgumentError(e.code+': '+e.message);
      throw new CommandExecutionError(e.code+': '+e.message);}
  }});
