// Only fixed, reviewed Tripo adapter functions run here. No website requests or auth-file reads.
import net from 'node:net';
import { account, assets, checkPin, StudioError } from './core.mjs';
import { quote, generate, checkPaidPin } from './paid.mjs';
import * as ext from './extended.mjs';
import * as workspace from './workspace.mjs';
import * as query from './asset-query.mjs';
import * as ui from './ui-options.mjs';
import * as viewer from './viewer.mjs';
import * as image from './image-form.mjs';

const MAX = 2*1024*1024;
let raw=''; for await (const chunk of process.stdin) { raw+=chunk; if(raw.length>MAX) throw Error('input_limit'); }
const packet=JSON.parse(raw);
let step='source_pin';
function rpc(name,args){step=name+(name==='evaluate'?' '+(args[0].match(/^function ([A-Za-z0-9_]+)/)?.[1]||'reviewed_reader'):'');return new Promise((resolve,reject)=>{
  const socket=net.createConnection(packet.socket);let response='';
  socket.setTimeout(120000,()=>socket.destroy(Error('rpc_timeout')));
  socket.on('connect',()=>socket.write(JSON.stringify({method:'rpc',token:packet.token,name,args})+'\n'));
  socket.on('data',chunk=>{response+=chunk;if(response.length>MAX)socket.destroy(Error('result_limit'));
    if(response.includes('\n')){socket.end();try{const result=JSON.parse(response);if(result.error){const e=new StudioError(result.error.code,result.error.message);reject(e);}else resolve(result.result);}catch{reject(Error('bridge_protocol'));}}});
  socket.on('error',reject);socket.on('end',()=>{if(!response.includes('\n'))reject(Error('bridge_eof'));});
});}
let arm=null;
const page={
  evaluate:(fn,...args)=>rpc('evaluate',[fn.toString(),args]),
  goto:(url)=>rpc('goto',[url]),
  click:async(...args)=>{if(arm)await arm;return rpc('click',args);},
  fillText:(...args)=>rpc('fillText',args),setChecked:(...args)=>rpc('setChecked',args),
  focus:(...args)=>rpc('focus',args),hover:(...args)=>rpc('hover',args),
  pressKey:(...args)=>rpc('pressKey',args),scrollTo:(...args)=>rpc('scrollTo',args),
  cdp:(...args)=>rpc('cdp',args),
  waitForDownload:(prefix,timeout)=>{arm=rpc('download_arm',[prefix,timeout]);return arm.then(id=>rpc('download_wait',[id]));},
};
function argsOf(argv){const args={};for(let i=0;i<argv.length;i++){
  const flag=argv[i];if(flag==='--confirm'){args.confirm=true;continue;}
  if(!/^--[a-z-]+$/.test(flag)&&flag!=='-f')throw new StudioError('invalid_argument','Unknown fixed command flag.');
  const key=flag.slice(flag==='-f'?1:2);if(key in args||i+1>=argv.length)throw new StudioError('invalid_argument','Malformed fixed command arguments.');args[key]=argv[++i];
}return args;}
export const OPERATIONS = {
 account:[checkPin,(p,a)=>account(p)],assets:[checkPin,(p,a)=>assets(p,a.limit)],
 quote:[checkPaidPin,(p,a)=>quote(p)],generate:[checkPaidPin,generate],
 asset:[ext.checkExtendedPin,ext.inspectAsset],asset_resolve:[ext.checkExtendedPin,ext.resolveAsset],
 assets_all:[ext.checkExtendedPin,ext.assetsAll],
 retopo_quote:[ext.checkExtendedPin,(p,a)=>ext.operationQuote(p,{...a,operation:'retopo'})],
 retopo:[ext.checkExtendedPin,(p,a)=>ext.executePaid(p,{...a,operation:'retopo'})],
 rig_quote:[ext.checkExtendedPin,(p,a)=>ext.operationQuote(p,{...a,operation:'rig'})],
 rig:[ext.checkExtendedPin,(p,a)=>ext.executePaid(p,{...a,operation:'rig'})],
 image_quote:[ext.checkExtendedPin,ext.imageQuote],
 image_generate:[ext.checkExtendedPin,(p,a)=>ext.generateImage(p,{...a,image_sha:a['image-sha']})],
 export_quote:[ext.checkExtendedPin,ext.exportQuote],export:[ext.checkExtendedPin,ext.exportModel],
 workspace_inspect:[workspace.checkWorkspacePin,workspace.inspectWorkspace],
 workspace_prepare:[workspace.checkWorkspacePin,workspace.prepareWorkspace],
 workspace_submit:[workspace.checkWorkspacePin,workspace.submitWorkspace],
 assets_query:[query.checkQueryPin,query.queryAssets],image_preview:[query.checkQueryPin,query.previewImage],
 animation_inspect:[ui.checkUIOptionsPin,ui.inspectAnimation],animation_prepare:[ui.checkUIOptionsPin,ui.prepareAnimation],
 export_options:[ui.checkUIOptionsPin,ui.inspectExportOptions],export_prepare:[ui.checkUIOptionsPin,ui.prepareExportOptions],
 viewer_inspect:[viewer.checkViewerPin,viewer.inspectViewer],viewer_prepare:[viewer.checkViewerPin,viewer.prepareViewer],
 viewer_camera:[viewer.checkViewerPin,viewer.cameraViewer],hierarchy_prepare:[viewer.checkViewerPin,viewer.prepareHierarchy],
 hierarchy_transform:[viewer.checkViewerPin,viewer.prepareTransform],
 image_form_inspect:[image.checkImageFormPin,image.inspectImageForm],image_form_prepare:[image.checkImageFormPin,image.prepareImageForm],
};
try{
 const [check,run]=OPERATIONS[packet.operation]||[];
 if(typeof run!=='function')throw new StudioError('unsupported_operation','Operation has no reviewed server dispatcher.');
 const args=argsOf(packet.argv);check(args.pin);
 const result=await run(page,args);
 process.stdout.write(JSON.stringify(result));
}catch(error){
 const code=error instanceof StudioError?error.code:'bridge_failure';
 // Known adapter errors have redacted messages; never emit Node/Chrome diagnostics.
 const message=error instanceof StudioError?error.message:'Server browser adapter failed; inspect retained receipts before retry.';
 process.stdout.write(JSON.stringify({error:{code,message:message+' [step: '+step+']'}}));process.exitCode=2;
}
