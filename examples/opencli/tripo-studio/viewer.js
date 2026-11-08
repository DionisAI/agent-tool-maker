import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { StudioError } from './core.mjs';
import { checkViewerPin,inspectViewer,prepareViewer,prepareHierarchy,prepareTransform,cameraViewer } from './viewer.mjs';
for(const[name,write,run,extra]of[
  ['viewer-inspect',false,inspectViewer,[]],['viewer-prepare',true,prepareViewer,['settings']],
  ['viewer-camera',true,cameraViewer,['action']],['hierarchy-prepare',true,prepareHierarchy,['node','settings']],['hierarchy-transform',true,prepareTransform,['node','settings']],
])cli({site:'tripo-studio',name,access:write?'write':'read',description:'Reviewed visible viewer/hierarchy controls and bounded native camera inputs',domain:'studio.tripo3d.ai',strategy:Strategy.UI,
  browser:true,siteSession:'persistent',navigateBefore:false,columns:['result'],args:[{name:'pin',type:'string',default:'',help:'Required reviewed viewer source SHA256'},
    {name:'asset',type:'string',default:'',help:'Exact source model UUID'},...extra.map(name=>({name,type:'string',default:name==='settings'?'{}':'',help:'Typed reviewed '+name}))],
  func:async(page,args)=>{let step='source_pin';const observed=new Proxy(page,{get(target,key){const value=Reflect.get(target,key);if(typeof value!=='function')return value;return(...values)=>{step=String(key)+(key==='evaluate'&&typeof values[0]==='function'?' '+values[0].name:'');return value.apply(target,values);};}});
    try{checkViewerPin(args.pin);return(await run(observed,args)).map(result=>({result}));}catch(error){if(!(error instanceof StudioError)){
      const hint=['selector_ambiguous','selector_not_found','selector_nth_out_of_range','not_editable','not_checkable'].includes(error?.code)?error.code:'inspect_local_state';
      throw new CommandExecutionError('Viewer bridge failed at '+step+' ('+hint+'); no raw diagnostics or credentials returned.');}
      if(error.code==='login_required')throw new AuthRequiredError('studio.tripo3d.ai',error.message);if(error.code==='invalid_argument')throw new ArgumentError(error.message);throw new CommandExecutionError(error.code+': '+error.message);}}});
