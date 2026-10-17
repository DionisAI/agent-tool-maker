import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError,checkPin,inspect} from './core.mjs';
for (const name of ['account','surface','form-inspect','form-options']) cli({
  site:'xyq-web',name,access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,
  browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Read observed XYQ website account, navigation, current form or already-open options; no Pippit CLI, uploads or generation',
  args:[{name:'pin',type:'string',default:'',help:'Required reviewed browser adapter bundle SHA256'}],columns:['result'],
  func:async(page,args)=>{
    try { checkPin(args.pin); return await inspect(page,name); }
    catch(error) {
      if (!(error instanceof XyqError)) throw new CommandExecutionError('XYQ adapter failed; inspect the local browser. Raw diagnostics are withheld.');
      if (error.code==='login_required') throw new AuthRequiredError('xyq.jianying.com',error.message);
      if (error.code==='invalid_argument') throw new ArgumentError(error.message);
      throw new CommandExecutionError(error.code+': '+error.message);
    }
  }
});
