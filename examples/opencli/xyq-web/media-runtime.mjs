// One explicit production namespace. Existing registrations are not replaced.
// Reuses the observed contracts and their named browser/profile routing.
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {XyqError,inspect} from './core.mjs';
import {boundReadRouting,inspectBoundAudioForm} from './audio-bound.mjs';
import {HOME_BOUND_FILES,runHomeBoundOperation} from './home-bound.mjs';
import {AUDIO_EDIT_BOUND_FILES,runBoundAudioEdit} from './audio-edit-bound.mjs';
import {AUDIO_UPLOAD_BOUND_FILES,runBoundAudioUpload} from './audio-upload-bound.mjs';
import {AUDIO_QUOTE_BOUND_FILES,inspectBoundAudioQuote} from './audio-quote-bound.mjs';
import {HOME_QUOTE_FILES,createHomeQuotePage,inspectBoundHomeQuote} from './home-quote.mjs';
import {HISTORY_FILES,inspectBoundProjectHistory} from './history.mjs';
import {GENERATION_FILES,generateBoundHome,generationStatus} from './generation.mjs';

export const MEDIA_RUNTIME_FILES=[...new Set([...HOME_BOUND_FILES,...AUDIO_EDIT_BOUND_FILES,
  ...AUDIO_UPLOAD_BOUND_FILES,...AUDIO_QUOTE_BOUND_FILES,...HOME_QUOTE_FILES,...HISTORY_FILES,
  ...GENERATION_FILES,'media-runtime.mjs','media-runtime.js'])];
export const MEDIA_RUNTIME_OPERATIONS=['account','surface','form_inspect','form_options',
  'form_state','form_choices','form_prepare','mode_choices','mode_prepare',
  'audio_form_state','audio_reference_upload','audio_form_state_bound','audio_prompt_prepare',
  'audio_choices','audio_prepare','audio_quote','home_quote','project_history_state',
  'generate','generation_status'];
export function mediaRuntimeDigest(){
  const h=createHash('sha256');
  for(const n of MEDIA_RUNTIME_FILES)h.update(n+'\0').update(readFileSync(new URL(n,import.meta.url))).update('\0');
  return h.digest('hex');
}
export function checkMediaRuntimePin(pin){
  if(typeof pin!=='string'||!/^[a-f0-9]{64}$/.test(pin)||pin!==mediaRuntimeDigest())
    throw new XyqError('definition_changed','Review the complete production media source closure.');
}
export async function runMediaOperation(context,operation,args={},factories={}){
  if(!MEDIA_RUNTIME_OPERATIONS.includes(operation)||!args||typeof args!=='object'||Array.isArray(args))
    throw new XyqError('invalid_argument','Select one reviewed media operation and typed arguments.');
  // Local receipt lookup never constructs a Page, reads profile routing or polls
  // a provider, even when no browser is connected.
  if(operation==='generation_status')return generationStatus(args.workspace,args.key);
  if(['account','surface','form_inspect','form_options'].includes(operation)){
    let page;
    try{page=await (factories.homeRead||createHomeQuotePage)(boundReadRouting(context));}
    catch(e){if(e instanceof XyqError)throw e;throw new XyqError('bridge_failed','The explicit home reader was not prepared.');}
    if(!page||typeof page.evaluate!=='function')throw new XyqError('unsupported_backend','The home reader requires the public evaluator.');
    const readonly=Object.freeze({evaluate:(fn,arg)=>page.evaluate(fn,arg)});
    return inspect(readonly,operation.replaceAll('_','-'));
  }
  if(['form_state','form_choices','form_prepare','mode_choices','mode_prepare'].includes(operation))
    return runHomeBoundOperation(context,operation,args.settings,factories.home);
  const scope={project_id:args.project,canvas_id:args.canvas,node_id:args.node};
  if(['audio_form_state','audio_form_state_bound'].includes(operation))
    return inspectBoundAudioForm(context,scope,factories.audioRead);
  if(['audio_choices','audio_prepare','audio_prompt_prepare'].includes(operation))
    return runBoundAudioEdit(context,operation,scope,args.settings,factories.audioEdit);
  if(operation==='audio_reference_upload')
    return runBoundAudioUpload(context,scope,args.settings,args.workspace,factories.audioUpload);
  if(operation==='audio_quote')return inspectBoundAudioQuote(context,scope,args.settings,factories.audioRead);
  if(operation==='home_quote')return inspectBoundHomeQuote(context,args.settings,factories.homeRead);
  if(operation==='project_history_state')return inspectBoundProjectHistory(context,
    {project_id:args.project,canvas_id:args.canvas},factories.history);
  if(operation==='generate')return generateBoundHome(context,args.settings,args.workspace,factories.generation);
  throw new XyqError('invalid_argument','The reviewed media operation has no dispatch contract.');
}
