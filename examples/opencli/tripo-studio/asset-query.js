import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { StudioError } from './core.mjs';
import { checkQueryPin, queryAssets, previewImage } from './asset-query.mjs';
for (const [name,args,run] of [
  ['assets-query',[
    {name:'category',type:'string',default:'Model',help:'Model or Image'},
    {name:'ownership',type:'string',default:'My Assets',help:'My Assets, Collected or Image Assets'},
    {name:'filter',type:'string',default:'All',help:'Observed category-specific filter'},
    {name:'limit',type:'int',default:100,help:'Maximum returned cards, 1-1000'},
    {name:'pages',type:'int',default:5,help:'Bounded scroll rounds, 1-50'},
  ],queryAssets],
  ['image-preview',[
    {name:'card',type:'string',default:'',help:'Exact image/multiview card_id from assets-query'},
    {name:'view',type:'int',default:0,help:'Multiview index 0-3; single images use 0'},
  ],previewImage],
]) cli({site:'tripo-studio',name,access:'read',description:'Reviewed visible '+name+'; no upload or paid action',domain:'studio.tripo3d.ai',strategy:Strategy.UI,
  browser:true,siteSession:'persistent',navigateBefore:false,
  args:[{name:'pin',type:'string',default:'',help:'Required reviewed asset query source SHA256'},...args],columns:['result'],
  func:async(page,inputs)=>{try {checkQueryPin(inputs.pin);return (await run(page,inputs)).map(result=>({result}));}
    catch (error) {
      if (!(error instanceof StudioError)) throw new CommandExecutionError('Asset query bridge failed; no upload or paid operation was submitted.');
      if (error.code==='login_required') throw new AuthRequiredError('studio.tripo3d.ai',error.message);
      if (error.code==='invalid_argument') throw new ArgumentError(error.code+': '+error.message);
      throw new CommandExecutionError(error.code+': '+error.message);
    }}});
