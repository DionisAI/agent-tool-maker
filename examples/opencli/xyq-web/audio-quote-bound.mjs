// Explicit existing browser binding; no fallback, navigation, input or auth export.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError} from './core.mjs';
import {audioScope} from './audio.mjs';
import {AUDIO_QUOTE_FILES,parseAudioQuoteSettings,inspectAudioQuote} from './audio-quote.mjs';
import {AUDIO_BOUND_FILES,boundReadRouting,createBoundReadPage} from './audio-bound.mjs';

export const AUDIO_QUOTE_BOUND_FILES=[...new Set([...AUDIO_QUOTE_FILES,...AUDIO_BOUND_FILES]),'audio-quote-bound.mjs','audio-quote-bound.js'];
export function audioQuoteBoundDigest(){
  const h=createHash('sha256');
  for(const name of AUDIO_QUOTE_BOUND_FILES)h.update(name+'\0').update(readFileSync(new URL(name,import.meta.url))).update('\0');
  return h.digest('hex');
}
export function checkAudioQuoteBoundPin(pin){
  if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==audioQuoteBoundDigest())throw new XyqError('definition_changed','Review the explicit bound audio quote bundle.');
}
export async function inspectBoundAudioQuote(context,rawScope,rawSettings,createPage=createBoundReadPage){
  const scope=audioScope(rawScope),settings=parseAudioQuoteSettings(rawSettings);
  let page;
  try{
    page=await createPage(boundReadRouting(context));
    if(!page||typeof page.evaluate!=='function')throw new XyqError('unsupported_backend','Bound quote Page must expose the documented evaluator.');
  }catch(e){
    if(e instanceof XyqError)throw e;
    throw new XyqError('bridge_failed','The bound quote Page preparation failed; inspect the local bridge.');
  }
  const readonly=Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)});
  const output=await inspectAudioQuote(readonly,scope,settings);
  return output.map(({result})=>({result:{...result,browser_session:'site:xyq-web',browser_surface:'browser',binding_changed:false}}));
}
