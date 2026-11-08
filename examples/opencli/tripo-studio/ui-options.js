import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { StudioError } from './core.mjs';
import { checkUIOptionsPin, inspectAnimation, prepareAnimation, inspectExportOptions, prepareExportOptions } from './ui-options.mjs';
for(const[name,access,prepare,run]of[
  ['animation-inspect','read',false,inspectAnimation],['animation-prepare','write',true,prepareAnimation],
  ['export-options','read',false,inspectExportOptions],['export-prepare','write',true,prepareExportOptions],
])cli({site:'tripo-studio',name,access,description:'Reviewed transient animation/export UI options; no generation or download',domain:'studio.tripo3d.ai',strategy:Strategy.UI,
  browser:true,siteSession:'persistent',navigateBefore:false,columns:['result'],args:[
    {name:'pin',type:'string',default:'',help:'Required reviewed UI options source SHA256'},
    {name:'asset',type:'string',default:'',help:'Exact source model UUID'},
    ...(prepare?[{name:'settings',type:'string',default:'{}',help:'Typed animation or export settings JSON'}]:[]),
  ],func:async(page,args)=>{let step='source_pin';
    const observed=new Proxy(page,{get(target,key){const value=Reflect.get(target,key);if(typeof value!=='function')return value;
      return(...values)=>{step=String(key)+(key==='evaluate'&&typeof values[0]==='function'?' '+values[0].name:'');return value.apply(target,values);};}});
    try{checkUIOptionsPin(args.pin);return(await run(observed,args)).map(result=>({result}));}
    catch(error){if(!(error instanceof StudioError)){
      const type=['TypeError','ReferenceError','SyntaxError','Error','TargetError'].includes(error?.name)?error.name:'bridge_error';
      // Strictly classify known SDK mistakes; never emit raw exception text.
      const hint=['selector_ambiguous','selector_not_found','not_editable','selector_nth_out_of_range','not_checkable'].includes(error?.code)?error.code:/page\.evaluate.*function|function.*page\.evaluate/i.test(error?.message||'')?'evaluate_contract':
        /not a function/.test(error?.message||'')?'method_contract':/Target not found|No elements found/i.test(error?.message||'')?'target_missing':'inspect_local_state';
      throw new CommandExecutionError('UI options bridge failed at '+step+' ('+type+', '+hint+'); no raw diagnostic or credentials returned.');}
      if(error.code==='login_required')throw new AuthRequiredError('studio.tripo3d.ai',error.message);
      if(error.code==='invalid_argument')throw new ArgumentError(error.code+': '+error.message);
      throw new CommandExecutionError(error.code+': '+error.message);}}});
