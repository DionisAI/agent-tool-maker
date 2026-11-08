// Strategy UI_SELECTOR / visible-ui plus exact project-owned operation receipt.
// No authentication reads, paid retries, lock release or invented task IDs.
import {createHash} from 'node:crypto';
import {readFileSync,existsSync,lstatSync,openSync,closeSync,fstatSync,constants} from 'node:fs';
import {resolve,dirname,join,isAbsolute} from 'node:path';
import {StudioError} from './core.mjs';
import {inspectAsset} from './extended.mjs';
import {WORKSPACE_FILES,prepareWorkspace,submitWorkspace} from './workspace.mjs';
export const DELIVERY_FILES=[...WORKSPACE_FILES,'delivery.mjs','delivery.js'];
const sha=v=>createHash('sha256').update(v).digest('hex');
const fail=(code,message)=>{throw new StudioError(code,message);};
export function deliveryDigest(){const h=createHash('sha256');for(const name of DELIVERY_FILES)h.update(name+'\0').update(readFileSync(new URL(name,import.meta.url))).update('\0');return h.digest('hex');}
export function checkDeliveryPin(pin){if(typeof pin!=='string'||pin!==deliveryDigest())fail('definition_changed','Review the Tripo delivery source closure.');}
export async function textureQuote(page,args){return prepareWorkspace(page,{asset:args.asset,module:'texture',settings:args.settings});}
export async function texture(page,args){return submitWorkspace(page,{...args,module:'texture'});}
export function readOperationReceipt(raw){
  if(!raw||!isAbsolute(raw.ledger||'')||raw.ledger==='/'||resolve(raw.ledger)!==raw.ledger||/[\x00-\x1f]/.test(raw.ledger)||!/^[A-Za-z0-9_.:-]{1,160}$/.test(raw.key||''))fail('invalid_argument','Use the exact project path and original request key.');
  const directory=join(raw.ledger,'.atm','tripo-studio-paid');
  for(let path=directory;;path=dirname(path)){
    if(existsSync(path)){const info=lstatSync(path);if(info.isSymbolicLink()||!info.isDirectory())fail('unsafe_path','Operation receipts must stay in the original regular project directory.');}
    if(dirname(path)===path)break;
  }
  const files=[join(directory,sha(raw.key)+'.json'),join(directory,'extended-'+sha(raw.key)+'.json')].filter(existsSync);
  if(!files.length)fail('request_missing','No retained operation receipt for this request key.');
  if(files.length!==1)fail('request_conflict','Multiple operations use this request key; select the original request.');
  let fd,record;
  try{fd=openSync(files[0],constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);const info=fstatSync(fd);
    if(!info.isFile()||info.nlink!==1||info.size<2||info.size>25000)fail('receipt_invalid','Expected a bounded single-link operation receipt.');
    record=JSON.parse(readFileSync(fd,'utf8'));
  }catch(e){if(e instanceof StudioError)throw e;fail('receipt_invalid','The retained operation receipt is inaccessible or malformed.');}finally{if(fd!==undefined)closeSync(fd);}
  if(!record||Array.isArray(record)||record.request_key!==raw.key||!/^[a-f0-9]{64}$/.test(record.fingerprint||'')||!['submitted','submission_unknown','dispatch_claimed'].includes(record.status))fail('receipt_invalid','Expected a retained model submission, not an upload or export receipt.');
  const operation=record.operation||'generate';
  if(!['generate','retopo','rig','image_generate','workspace_segment','workspace_texture','workspace_edit','workspace_upscale','workspace_pbr'].includes(operation))fail('receipt_invalid','This receipt does not identify a supported model operation.');
  const uuid=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
  for(const key of ['asset_id','source_asset_id'])if(record[key]!==undefined&&!uuid.test(record[key]))fail('receipt_invalid','The retained model identity is malformed.');
  return{request_key:raw.key,operation,receipt_status:record.status,asset_id:record.asset_id||null,source_asset_id:record.source_asset_id||null};
}
export async function operationStatus(page,args){
  const wait=Number(args.wait||0);if(!Number.isInteger(wait)||wait<0||wait>120)fail('invalid_argument','wait must be 0-120 seconds.');
  const receipt=readOperationReceipt(args),base={...receipt,paid_submitted:false,submission_repeated:false,lock_changed:false,secrets_returned:false};
  if(receipt.receipt_status!=='submitted'||!receipt.asset_id)return[{...base,status:'submission_unknown',model_completed:false,provider_checked:false}];
  // Processing on the source route is submission evidence, not a result UUID.
  // Never mark a formerly ready source complete on behalf of its child job.
  if(receipt.source_asset_id===receipt.asset_id)return[{...base,status:'needs_output_reference',model_completed:false,provider_checked:false}];
  const observed=(await inspectAsset(page,{asset:receipt.asset_id,wait}))[0];
  if(observed.asset_id!==receipt.asset_id)fail('asset_mismatch','Provider readback differs from the original output identity.');
  return[{...base,status:observed.status==='ready'?'completed':observed.status==='failed'?'failed':'pending',provider_status:observed.status,
    model_completed:observed.model_completed,provider_checked:true,faces:observed.faces,vertices:observed.vertices,export_enabled:observed.export_enabled}];
}
