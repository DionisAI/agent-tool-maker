import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkCanvasPin,inspectCanvas} from './canvas.mjs';
cli({site:'xyq-web',name:'canvas-inspect',access:'read',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Read the exact current project/canvas and DOM nodes; no navigation or editing',columns:['result'],
  args:[{name:'pin',type:'string',default:'',help:'Reviewed canvas bundle SHA256'},{name:'project',type:'string',required:true},{name:'canvas',type:'string',required:true}],
  func:async(page,args)=>{try{checkCanvasPin(args.pin);return await inspectCanvas(page,{project_id:args.project,canvas_id:args.canvas});}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ canvas read failed; inspect the local browser.');
      if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);throw new CommandExecutionError(e.code+': '+e.message);}}
});
