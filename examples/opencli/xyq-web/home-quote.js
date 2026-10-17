import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkHomeQuotePin,inspectBoundHomeQuote} from './home-quote.mjs';
cli({site:'xyq-web',name:'home-quote-bound',access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Read draft-bound home media credit estimate, with explicit units and discount amount',columns:['result'],
  args:[{name:'pin',type:'string',required:true,help:'Reviewed home quote source SHA'}, {name:'settings',type:'string',required:true,help:'Exact draft SHA JSON'}],
  func:async(page,args)=>{try{checkHomeQuotePin(args.pin);return await inspectBoundHomeQuote(page,args.settings);}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('Home quote failed; inspect the explicitly bound draft.');
      if(e.code==='invalid_argument')throw new ArgumentError(e.message);
      if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message}));}}
});
