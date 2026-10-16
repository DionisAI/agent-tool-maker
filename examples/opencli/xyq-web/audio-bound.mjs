// Explicit named-browser-session read. No fallback, bind, navigation or input.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError} from './core.mjs';
import {AUDIO_FILES,audioScope,inspectAudioForm} from './audio.mjs';

export const AUDIO_BOUND_FILES=[...AUDIO_FILES,'audio-bound.mjs','audio-bound.js'];
export function audioBoundDigest(){
  const h=createHash('sha256');
  for(const name of AUDIO_BOUND_FILES)h.update(name+'\0').update(readFileSync(new URL(name,import.meta.url))).update('\0');
  return h.digest('hex');
}
export function checkAudioBoundPin(pin){
  if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==audioBoundDigest())throw new XyqError('definition_changed','Review the explicit bound-read adapter bundle.');
}
export function boundReadRouting(context){
  if(!context||typeof context!=='object'||Array.isArray(context))throw new XyqError('unsupported_backend','Use the reviewed OpenCLI Page routing context.');
  const routing={};
  for(const key of ['contextId','preferredContextId']){
    const value=context[key];
    if(value!==undefined){
      if(typeof value!=='string'||!/^[A-Za-z0-9_-]{1,128}$/.test(value))throw new XyqError('unsupported_backend','Unexpected browser profile routing metadata.');
      routing[key]=value;
    }
  }
  if(routing.contextId&&routing.preferredContextId)throw new XyqError('unsupported_backend','Ambiguous browser profile routing metadata.');
  return routing;
}
export async function createBoundReadPage(routing){
  const {Page}=await import('@jackwener/opencli/browser/page');
  // Constructor parameters are public API; private Page fields are untouched.
  const page=new Page('site:xyq-web',undefined,routing.contextId,undefined,'browser','persistent',routing.preferredContextId);
  return Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)});
}
export async function inspectBoundAudioForm(context,rawScope,createPage=createBoundReadPage){
  const scope=audioScope(rawScope);
  let page;
  try{
    const routing=boundReadRouting(context);
    page=await createPage(routing);
    if(!page||typeof page.evaluate!=='function')throw new XyqError('unsupported_backend','Bound-read Page must expose the documented evaluator.');
  }catch(e){
    if(e instanceof XyqError)throw e;
    throw new XyqError('bridge_failed','The bound browser Page could not be prepared; inspect the local bridge.');
  }
  const readonly=Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)});
  const output=await inspectAudioForm(readonly,scope);
  return output.map(({result})=>({result:{...result,browser_session:'site:xyq-web',browser_surface:'browser',binding_changed:false}}));
}
