import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {checkTextPin,inspectText,prepareText} from './text.mjs';
for(const name of ['text-inspect','text-prepare'])cli({site:'xyq-web',name,access:name==='text-inspect'?'read':'write',domain:'xyq.jianying.com',strategy:Strategy.UI,browser:true,siteSession:'persistent',navigateBefore:false,
  description:'Inspect or edit the exact canvas text node, with full content digest and verified whole-text formatting; no generation',columns:['result'],
  args:[{name:'pin',type:'string',default:'',help:'Reviewed text bundle SHA256'},{name:'project',type:'string',required:true},{name:'canvas',type:'string',required:true},{name:'node',type:'string',required:true},...(name==='text-prepare'?[{name:'settings',type:'string',required:true,help:'Typed JSON with expected_content_sha256'}]:[])],
  func:async(page,args)=>{try{checkTextPin(args.pin);const scope={project_id:args.project,canvas_id:args.canvas,node_id:args.node};return await(name==='text-inspect'?inspectText(page,scope):prepareText(page,scope,args.settings));}
    catch(e){if(!(e instanceof XyqError))throw new CommandExecutionError('XYQ text adapter failed; inspect the current node.');
      if(e.code==='invalid_argument')throw new ArgumentError(e.message);if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
      throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,completed_steps:e.completed_steps||[]}));}}
});
