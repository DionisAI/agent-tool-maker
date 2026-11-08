import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkHomeMaterialPin,inspectBoundHomeMaterials} from './material-home.mjs';
for(const operation of ['home_material_state','home_material_choices']){
  cli({site:'xyq-material',name:operation.replaceAll('_','-'),access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
    description:'Read exact homepage material intake and already-open owned menu; no file input or asset selection',columns:['result'],
    args:[{name:'pin',type:'string',required:true,help:'Reviewed complete homepage material source SHA'}],
    func:async(page,args)=>{
      try{checkHomeMaterialPin(args.pin);return await inspectBoundHomeMaterials(page,operation);}
      catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('Material metadata discovery failed; preserve the current page.');
        if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
        if(e.code==='invalid_argument')throw new ArgumentError(e.message);
        throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));}
    }});
}
