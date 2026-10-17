import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { StudioError } from './core.mjs';
import { checkWorkspacePin, inspectWorkspace, prepareWorkspace, submitWorkspace } from './workspace.mjs';
const common=[{name:'pin',type:'string',default:'',help:'Required reviewed workspace adapter SHA256'},
  {name:'module',type:'string',default:'',help:'Observed Workspace module name'},
  {name:'asset',type:'string',default:'',help:'Exact source UUID, or empty only for workspace inspection'}];
for(const[name,access,args,run]of[
  ['workspace-inspect','read',[],inspectWorkspace],
  ['workspace-prepare','write',[{name:'settings',type:'string',default:'{}',help:'Reviewed module-specific settings JSON'}],prepareWorkspace],
  ['workspace-submit','write',[{name:'quote',type:'string',default:'',help:'Current approved workspace quote SHA256'},
    {name:'budget',type:'int',default:0,help:'Explicit per-operation Studio credit ceiling'},
    {name:'key',type:'string',default:'',help:'Stable request key'}, {name:'ledger',type:'string',default:'',help:'Exact project path'},
    {name:'confirm',type:'bool',default:false,help:'Only after human approval of this operation/source/cost'}],submitWorkspace],
])cli({site:'tripo-studio',name,access,description:'Visible workspace '+name+'; exact source, known price, no automatic paid retry',domain:'studio.tripo3d.ai',strategy:Strategy.UI,
  browser:true,siteSession:'persistent',navigateBefore:false,args:[...common,...args],columns:['result'],
  func:async(page,inputs)=>{try{checkWorkspacePin(inputs.pin);return(await run(page,inputs)).map(result=>({result}));}
    catch(error){if(!(error instanceof StudioError))throw new CommandExecutionError('Workspace bridge failed; inspect retained receipts.');
      if(error.code==='login_required')throw new AuthRequiredError('studio.tripo3d.ai',error.message);
      if(['invalid_argument','confirmation_required'].includes(error.code))throw new ArgumentError(error.code+': '+error.message);
      throw new CommandExecutionError(error.code+': '+error.message);}}});
