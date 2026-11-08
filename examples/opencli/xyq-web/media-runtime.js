import {cli,Strategy} from '@jackwener/opencli/registry';
import {ArgumentError,AuthRequiredError,CommandExecutionError} from '@jackwener/opencli/errors';
import {XyqError} from './core.mjs';
import {MEDIA_RUNTIME_OPERATIONS,checkMediaRuntimePin,runMediaOperation} from './media-runtime.mjs';

const scoped=new Set(['audio_form_state','audio_form_state_bound','audio_reference_upload',
  'audio_choices','audio_prepare','audio_prompt_prepare','audio_quote']);
const settings=new Set(['form_prepare','mode_prepare','audio_reference_upload',
  'audio_prepare','audio_prompt_prepare','audio_quote','home_quote','generate']);
const writes=new Set(['form_choices','form_prepare','mode_choices','mode_prepare',
  'audio_choices','audio_prepare','audio_prompt_prepare','audio_reference_upload','generate']);
for(const operation of MEDIA_RUNTIME_OPERATIONS){
  const local=operation==='generation_status';
  const args=[{name:'pin',type:'string',required:true,help:'Reviewed complete media runtime SHA'}];
  if(scoped.has(operation)||operation==='project_history_state')
    args.push(...(operation==='project_history_state'?['project','canvas']:['project','canvas','node'])
      .map(name=>({name,type:'string',required:true,help:'Exact observed project/canvas/audio-node ID'})));
  if(settings.has(operation))args.push({name:'settings',type:'string',required:true,help:'Typed exact-draft settings and operation-specific confirmation'});
  if(['audio_reference_upload','generate','generation_status'].includes(operation))
    args.push({name:'workspace',type:'string',required:true,help:'Exact original approved project directory'});
  if(local)args.push({name:'key',type:'string',required:true,help:'Original generation request key; local receipt only'});
  cli({site:'xyq-media',name:operation.replaceAll('_','-'),access:writes.has(operation)?'write':'read',
    domain:'xyq.jianying.com',strategy:local?Strategy.LOCAL:Strategy.UI,browser:!local,
    siteSession:local?undefined:'persistent',navigateBefore:false,columns:['result'],args,
    description:'Reviewed media '+operation+'; explicit bound browser, retained original requests, no auth-state export',
    func:async(first,second)=>{
      // The SDK calls browser:false handlers as func(args, debug), not
      // func(page, args, debug). Keep LOCAL receipt lookup Page-free.
      const page=local?null:first,values=local?first:second;
      try{checkMediaRuntimePin(values.pin);return await runMediaOperation(page,operation,values);}
      catch(e){
        if(!(e instanceof XyqError))throw new CommandExecutionError('Media runtime failed; inspect the retained operation without resubmission.');
        if(e.code==='login_required')throw new AuthRequiredError('xyq.jianying.com',e.message);
        if(['invalid_argument','confirmation_required'].includes(e.code))throw new ArgumentError(e.message);
        throw new CommandExecutionError(JSON.stringify({code:e.code,message:e.message,phase:e.phase||null,
          input_phase:e.input_phase||null,completed_steps:e.completed_steps||[],cleanup_error:e.cleanup_error||null,
          outcome_uncertain:e.outcome_uncertain===true,retention_failure_code:e.retention_failure_code||null}));
      }
    }});
}
