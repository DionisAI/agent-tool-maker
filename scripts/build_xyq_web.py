"""Compile XYQ media-generation foundations; optional parked canvas adapters."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import agent_tool_maker.extensions as extensions
if not Path(extensions.__file__).resolve().is_relative_to(ROOT/'src'):
    raise RuntimeError('Use a fresh process with this reviewed repository source.')
from agent_tool_maker.maker import validate_manifest

FILES=('core.mjs','inspect.js')
OPERATIONS=('account','surface','form_inspect','form_options')
FORM_OPERATIONS=('form_state','form_choices','form_prepare')
FORM_FILES=(*FILES,'form.mjs','form.js')
MODE_FILES=(*FORM_FILES,'mode.mjs','mode.js')
MODE_OPERATIONS=('mode_choices','mode_prepare')
AUDIO_FILES=(*FILES,'audio.mjs','audio.js')
AUDIO_OPERATIONS=('audio_form_state','audio_reference_upload')
AUDIO_BOUND_FILES=(*AUDIO_FILES,'audio-bound.mjs','audio-bound.js')
AUDIO_BOUND_OPERATIONS=('audio_form_state_bound',)
HOME_BOUND_FILES=tuple(dict.fromkeys((*MODE_FILES,*AUDIO_BOUND_FILES)))+('home-bound.mjs','home-bound.js')
HOME_BOUND_OPERATIONS=('form_state','form_choices','form_prepare','mode_choices','mode_prepare')
AUDIO_PROMPT_FILES=(*AUDIO_FILES,'audio-prompt.mjs','audio-prompt.js')
AUDIO_PROMPT_OPERATIONS=('audio_prompt_prepare',)
AUDIO_SETTINGS_FILES=(*AUDIO_FILES,'audio-settings.mjs','audio-settings.js')
AUDIO_SETTINGS_OPERATIONS=('audio_choices','audio_prepare')
AUDIO_QUOTE_FILES=(*AUDIO_FILES,'audio-quote.mjs','audio-quote.js')
AUDIO_QUOTE_OPERATIONS=('audio_quote',)
AUDIO_QUOTE_BOUND_FILES=tuple(dict.fromkeys((*AUDIO_QUOTE_FILES,*AUDIO_BOUND_FILES)))+('audio-quote-bound.mjs','audio-quote-bound.js')
AUDIO_EDIT_BOUND_FILES=tuple(dict.fromkeys((*AUDIO_SETTINGS_FILES,*AUDIO_PROMPT_FILES,*AUDIO_BOUND_FILES)))+('audio-edit-bound.mjs','audio-edit-bound.js')
AUDIO_EDIT_BOUND_OPERATIONS=(*AUDIO_SETTINGS_OPERATIONS,*AUDIO_PROMPT_OPERATIONS)
AUDIO_UPLOAD_BOUND_FILES=(*AUDIO_BOUND_FILES,'audio-upload-bound.mjs','audio-upload-bound.js')
HOME_QUOTE_FILES=tuple(dict.fromkeys((*FORM_FILES,*AUDIO_BOUND_FILES)))+('home-quote.mjs','home-quote.js')
HOME_QUOTE_OPERATIONS=('home_quote',)
HISTORY_FILES=(*AUDIO_BOUND_FILES,'history.mjs','history.js')
HISTORY_OPERATIONS=('project_history_state',)
GENERATION_FILES=(*HOME_QUOTE_FILES,'generation.mjs','generation.js')
GENERATION_OPERATIONS=('generate','generation_status')
RESULT_FILES=(*AUDIO_BOUND_FILES,'results.mjs','results.js')
RESULT_OPERATIONS=('results','result_inspect','result_download_quote')
CANVAS_FILES=(*FILES,'canvas.mjs','canvas.js')
TEXT_FILES=(*CANVAS_FILES,'text.mjs','text.js')
TEXT_OPERATIONS=('text_inspect','text_prepare')

def bundle_digest(files=FILES):
    digest=hashlib.sha256()
    for name in files:
        digest.update((name+'\0').encode())
        path=ROOT/'examples/opencli/xyq-web'/name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('XYQ adapter source must be a regular reviewed file.')
        digest.update(path.read_bytes());digest.update(b'\0')
    return digest.hexdigest()

def manifest(operation):
    if operation not in OPERATIONS:
        raise ValueError('Unknown XYQ web operation')
    return validate_manifest({
        'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀网页 · '+operation,
        'capabilities':['website',operation],'adapter':'command','executable':'opencliapp','paid':False,
        'permissions':['execute_code'],
        'schema':{'type':'object','properties':{},'additionalProperties':False},'example':{},
        'command':{'argv':['__opencli_shim','xyq-web',operation.replace('_','-'),'--pin',bundle_digest(),'-f','json'],
                   'output':'json','timeout':60},
        'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Visible home UI only. Browser owns authentication. No Pippit dependency, navigation, popup consent, Cookie/storage reads, uploads, generation, purchase or publishing. Form options require an already-open preferences menu. Current UI discovery is partial, never all website functionality.',
        'completion':'JSON reports observed account/navigation/form/options only, not media creation or a final price quote.'})

def form_manifest(operation):
    if operation not in FORM_OPERATIONS:
        raise ValueError('Unknown XYQ form operation')
    prepare=operation=='form_prepare'
    properties={}
    argv=['__opencli_shim','xyq-web',operation.replace('_','-'),'--pin',bundle_digest(FORM_FILES),'-f','json']
    if prepare:
        properties['settings']={'type':'object','properties':{
            'expected_draft_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'model':{'type':'string','minLength':1,'maxLength':128},
            'radios':{'type':'object','maxProperties':10,'propertyNames':{'minLength':1,'maxLength':128},
                      'additionalProperties':{'type':'string','minLength':1,'maxLength':128}},
            'duration_seconds':{'type':'integer','minimum':1,'maximum':600},
            'canvas':{'type':'boolean'},'prompt':{'type':'string','maxLength':20000}},
            'required':['expected_draft_sha256'],'additionalProperties':False}
        argv+=['--settings',{'json':'settings'}]
    return validate_manifest({
        'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀网页 · '+operation,
        'capabilities':['website',operation],'adapter':'command','executable':'opencliapp','paid':False,
        'permissions':[] if operation=='form_state' else ['external_write'],
        'schema':{'type':'object','properties':properties,'required':list(properties),'additionalProperties':False},
        'example':{'settings':{'expected_draft_sha256':'0'*64,'radios':{'采样率':'48kHz'}}} if prepare else {},
        'command':{'argv':argv,'output':'json','timeout':180},
        'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Current creative image/video/audio composer only. State is read-only; choices opens/closes its own menu; prepare uses exact draft binding and enabled dynamic semantic choices with native input/readback. Existing layers, references and files are preserved. No mode changes, upload, generation, purchase, publication, auth capture or Pippit dependency.',
        'completion':'Prepared form and not_final cost observations only. Phase/completed-step/cleanup errors distinguish partial preparation; no automatic rollback or resubmission. Not whole website coverage or completed media.'})

def mode_manifest(operation):
    if operation not in MODE_OPERATIONS:
        raise ValueError('Unknown media-mode operation')
    prepare=operation=='mode_prepare'
    props={'settings':{'type':'object','properties':{'expected_draft_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'mode':{'enum':['图片生成','视频生成','音频生成']}},'required':['expected_draft_sha256','mode'],'additionalProperties':False}} if prepare else {}
    argv=['__opencli_shim','xyq-web',operation.replace('_','-'),'--pin',bundle_digest(MODE_FILES),'-f','json']
    if prepare:argv+=['--settings',{'json':'settings'}]
    return validate_manifest({'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀媒体 · '+operation,
        'capabilities':['website',operation],'adapter':'command','executable':'opencliapp','paid':False,'permissions':['external_write'],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        'example':{'settings':{'expected_draft_sha256':'0'*64,'mode':'音频生成'}} if prepare else {},
        'command':{'argv':argv,'output':'json','timeout':120},'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Current creative home mode menu only. Choices opens/closes its own menu; preparation binds the existing draft and changes only a known empty draft. Unknown or attached files, references, prompts and existing layers stop switching. Badge text is not a mode title. No Agent-mode selection, draft clearing, uploads, generation, purchase, auth reads or navigation.',
        'completion':'Verified current media mode and refreshed draft digest, not media submission or final quote. Model/canvas defaults may change with the mode and are reported. Partial phase/completed-step/cleanup errors require inspection, not blind retry.'})

def canvas_manifest():
    return validate_manifest({'id':'xyq.web.canvas_inspect','provider':'xyq','title':'小云雀网页 · canvas_inspect',
        'capabilities':['website','canvas_inspect'],'adapter':'command','executable':'opencliapp','paid':False,
        'permissions':['execute_code'],
        'schema':{'type':'object','properties':{k:{'type':'string','pattern':'^[0-9]{1,20}$'} for k in ('project_id','canvas_id')},
                  'required':['project_id','canvas_id'],'additionalProperties':False},
        'example':{'project_id':'1','canvas_id':'2'},
        'command':{'argv':['__opencli_shim','xyq-web','canvas-inspect','--pin',bundle_digest(CANVAS_FILES),'-f','json',
                          '--project',{'input':'project_id'},'--canvas',{'input':'canvas_id'}],'output':'json','timeout':60},
        'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Exact current /project and projectId/canvasId binding. Observed React Flow DOM node IDs/types/layout, hashed text and save-in-progress signal. No auth/thread IDs, title/prompt raw text, navigation, node edits, uploads or generation.',
        'completion':'Current canvas DOM only, not all project assets or persistent-save proof. Unknown node structure is explicit; saving=false alone is not proof of provider persistence.'})

def audio_manifest(operation):
    if operation not in AUDIO_OPERATIONS:
        raise ValueError('Unknown audio-reference operation')
    upload=operation=='audio_reference_upload'
    props={k:{'type':'string','pattern':'^[0-9]{1,20}$'} for k in ('project_id','canvas_id','node_id')}
    argv=['__opencli_shim','xyq-web',operation.replace('_','-'),'--pin',bundle_digest(AUDIO_FILES),'-f','json',
          '--project',{'input':'project_id'},'--canvas',{'input':'canvas_id'},'--node',{'input':'node_id'}]
    example={'project_id':'1','canvas_id':'2','node_id':'3'}
    if upload:
        fields={'expected_form_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
                'file':{'type':'string','pattern':'^/'},'file_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
                'request_key':{'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$'},
                'purpose':{'enum':['audio_reference']},'confirm':{'enum':[True]}}
        props['settings']={'type':'object','properties':{**fields,'mode':{'enum':['empty','append']}},'required':list(fields),'additionalProperties':False}
        argv+=['--settings',{'json':'settings'},'--workspace',{'workspace':''}]
        example['settings']={'expected_form_sha256':'0'*64,'file':'/PROJECT/test.wav','file_sha256':'0'*64,
                             'request_key':'xyq-audio-once','purpose':'audio_reference','confirm':True}
    return validate_manifest({'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀音频 · '+operation,
        'capabilities':['website',operation],'adapter':'command','executable':'opencliapp','paid':False,
        'permissions':['external_write'] if upload else [],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},'example':example,
        'command':{'argv':argv,'output':'json','timeout':180},'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Current project audio-generation footer only; one audio node per canvas is required because the portal has no node-id marker. Exact project/canvas/node and form binding. One explicitly approved project PCM WAV or bounded MPEG Layer-III MP3, up to 20 MiB and 120s client bounds, uses reviewed native DOM file input. MP3 duration counts encoded frame samples, not decoded output; frame validation is not decoder/provider acceptance. Default mode empty preserves the original contract; explicit append preserves prompts/tokens/existing image/audio references, up to three audio references total. Duplicate names and full slots fail before input. Recheck the bound draft after durable intent. No node creation, arbitrary selectors, navigation, reference replacement, prompt mention insertion, generation, auth reads or paid actions.',
        'completion':'Visible new audio-reference chip, preserved old references, file SHA and durable upload intent/result. Stable-key reuse never reuploads; old empty-upload fingerprints stay compatible; append has a separate fingerprint. Unknown outcomes retain the project lock. A chip is not voice cloning, generated audio, persistent-save or supplier processing proof. Real append/MP3/homepage/paid/delivery paths require separate acceptance.'})

def text_manifest(operation):
    if operation not in TEXT_OPERATIONS:
        raise ValueError('Unknown text-node operation')
    prepare=operation=='text_prepare'
    props={k:{'type':'string','pattern':'^[0-9]{1,20}$'} for k in ('project_id','canvas_id','node_id')}
    argv=['__opencli_shim','xyq-web',operation.replace('_','-'),'--pin',bundle_digest(TEXT_FILES),'-f','json',
          '--project',{'input':'project_id'},'--canvas',{'input':'canvas_id'},'--node',{'input':'node_id'}]
    example={'project_id':'1','canvas_id':'2','node_id':'3'}
    if prepare:
        fields={'expected_content_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'text':{'type':'string','maxLength':50000},'heading':{'enum':[None,1,2,3]},
                **{k:{'type':'boolean'} for k in ('quote','bold','italic','underline','strike')}}
        props['settings']={'type':'object','properties':fields,'required':['expected_content_sha256'],'additionalProperties':False}
        argv+=['--settings',{'json':'settings'}]
        example['settings']={'expected_content_sha256':'0'*64,'text':'ATM CLI text-node smoke test'}
    return validate_manifest({'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀网页 · '+operation,
        'capabilities':['website',operation],'adapter':'command','executable':'opencliapp','paid':False,
        'permissions':['external_write'] if prepare else [],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},'example':example,
        'command':{'argv':argv,'output':'json','timeout':240},'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Exact current project/canvas/text-node and whole HTML content digest. Native typed content and whole-text heading/quote/marks only. Selection must be observable and cover the target; toolbar pressed state alone is not formatting. Other nodes, unsubmitted editors, non-text references and layers stay intact. No HTML input, node creation/deletion, uploads, generation, purchase, publication or auth capture.',
        'completion':'Native input and DOM body readback, not provider-persistent-save proof. Partial errors retain phase/completed steps. CUA-only DOM backends may expose no Selection: report selection_unknown rather than forging it. Native fixture/source/real UI/installed CLI acceptance stay separate.'})

def audio_prompt_manifest():
    props={k:{'type':'string','pattern':'^[0-9]{1,20}$'} for k in ('project_id','canvas_id','node_id')}
    props['settings']={'type':'object','properties':{'expected_form_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
        'prompt':{'type':'string','maxLength':20000},'reference_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}},
        'required':['expected_form_sha256'],'additionalProperties':False}
    return validate_manifest({'id':'xyq.web.audio_prompt_prepare','provider':'xyq','title':'小云雀音频 · prompt_prepare',
        'capabilities':['website','audio_prompt_prepare'],'adapter':'command','executable':'opencliapp','paid':False,'permissions':['external_write'],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        'example':{'project_id':'1','canvas_id':'2','node_id':'3','settings':{'expected_form_sha256':'0'*64,'prompt':'ATM 音频引用测试：','reference_sha256':'1'*64}},
        'command':{'argv':['__opencli_shim','xyq-web','audio-prompt-prepare','--pin',bundle_digest(AUDIO_PROMPT_FILES),'-f','json',
            '--project',{'input':'project_id'},'--canvas',{'input':'canvas_id'},'--node',{'input':'node_id'},'--settings',{'json':'settings'}],'output':'json','timeout':180},
        'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Exact current single-audio-node footer and form digest. Plain text input before structured mentions; existing rich prompts stay intact. Appends one exact previously uploaded audio reference through its observed mention control with native end-caret/readback. Already mentioned reference is a zero-input no-op. Duplicate attachment names, unknown Selection/files, covered controls and existing layers stop input. No upload, reference removal, arbitrary HTML/selectors, navigation, auth reads or generation.',
        'completion':'Actual numeric Pippit asset token and unchanged literal text/previous mentions, not a textual @name or verified voice effect. Native focus/caret is checked in the intended editor. Phase/completed-step/uncertain errors report partial preparation; no automatic retry or rollback.'})

def audio_settings_manifest(operation):
    if operation not in AUDIO_SETTINGS_OPERATIONS:
        raise ValueError('Unknown audio parameter operation')
    prepare=operation=='audio_prepare'
    props={k:{'type':'string','pattern':'^[0-9]{1,20}$'} for k in ('project_id','canvas_id','node_id')}
    argv=['__opencli_shim','xyq-web',operation.replace('_','-'),'--pin',bundle_digest(AUDIO_SETTINGS_FILES),'-f','json',
          '--project',{'input':'project_id'},'--canvas',{'input':'canvas_id'},'--node',{'input':'node_id'}]
    example={'project_id':'1','canvas_id':'2','node_id':'3'}
    if prepare:
        props['settings']={'type':'object','properties':{'expected_form_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
            'model_id':{'type':'string','pattern':'^[a-z0-9_]{1,64}$'},'sample_rate_hz':{'type':'integer','minimum':8000,'maximum':192000}},
            'required':['expected_form_sha256'],'additionalProperties':False}
        argv+=['--settings',{'json':'settings'}]
        example['settings']={'expected_form_sha256':'0'*64,'sample_rate_hz':48000}
    return validate_manifest({'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀音频参数 · '+operation,
        'capabilities':['website',operation],'adapter':'command','executable':'opencliapp','paid':False,'permissions':['external_write'],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},'example':example,
        'command':{'argv':argv,'output':'json','timeout':180},'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Exact current single-audio-node project/footer. Choices open and close only owned model/rate menus; prepare binds an exact form digest and observed model ID/rate. Native input and selected readback preserve prompt, structured references and file controls. A canvas rail may cover a control center: bounded interior hit testing uses native input on that exact control, never forced clicks. Fully covered or unknown file states fail. No upload, generation, navigation, arbitrary selectors or auth reads.',
        'completion':'Current model/rate discovery or preparation only, not final billing, generated voice, persistence or full media parity. Model-induced rate defaults are actual readback. Partial errors retain phase/completed steps/uncertainty and owned-layer cleanup errors; no retry or rollback.'})

def audio_quote_manifest():
    props={k:{'type':'string','pattern':'^[0-9]{1,20}$'} for k in ('project_id','canvas_id','node_id')}
    props['settings']={'type':'object','properties':{'expected_form_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}},
        'required':['expected_form_sha256'],'additionalProperties':False}
    return validate_manifest({'id':'xyq.web.audio_quote','provider':'xyq','title':'小云雀音频 · 估算费率',
        'capabilities':['website','audio_quote'],'adapter':'command','executable':'opencliapp','paid':False,'permissions':[],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        'example':{'project_id':'1','canvas_id':'2','node_id':'3','settings':{'expected_form_sha256':'0'*64}},
        'command':{'argv':['__opencli_shim','xyq-web','audio-quote','--pin',bundle_digest(AUDIO_QUOTE_FILES),'-f','json',
            '--project',{'input':'project_id'},'--canvas',{'input':'canvas_id'},'--node',{'input':'node_id'},'--settings',{'json':'settings'}],
            'output':'json','timeout':120},'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Read only the exact current single-audio-node footer and visible estimated-credit title. Bind the expected form and bracket two price reads with three form snapshots. Preserve the displayed per-seconds denominator; no assumed output duration, price extrapolation, navigation, input, upload, auth reads or spending.',
        'completion':'quoted_rate is an estimated unit rate, never total credits or a spending ceiling. Missing/unsupported price and busy quote are explicit states; ambiguous anchors, stale drafts and changed prices fail. Actual final billing, generation, tasks and delivery remain separate.'})

def audio_bound_manifest():
    props={k:{'type':'string','pattern':'^[0-9]{1,20}$'} for k in ('project_id','canvas_id','node_id')}
    return validate_manifest({'id':'xyq.web.audio_form_state_bound','provider':'xyq','title':'小云雀音频 · 已绑定页面读取',
        'capabilities':['website','audio_form_state_bound'],'adapter':'command','executable':'opencliapp','paid':False,'permissions':[],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        'example':{'project_id':'1','canvas_id':'2','node_id':'3'},
        'command':{'argv':['__opencli_shim','xyq-web','audio-form-state-bound','--pin',bundle_digest(AUDIO_BOUND_FILES),'-f','json',
            '--project',{'input':'project_id'},'--canvas',{'input':'canvas_id'},'--node',{'input':'node_id'}],'output':'json','timeout':60},
        'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Explicit named browser-session read using the installed public Page API and inherited public profile routing. Exact project/canvas/unique audio-node DOM contract. No automatic fallback, bind/unbind, navigation, UI input, upload, auth reads or paid submission. Prior browser binding must target the reviewed project.',
        'completion':'Ready current-form metadata only. Explicit browser-session routing is separate from normal adapter-owned sessions; errors remain failures. No generated media, final billing, persistence or login migration claimed.'})

def audio_quote_bound_manifest():
    tool=audio_quote_manifest()
    argv=tool['command']['argv']
    argv[2]='audio-quote-bound'
    argv[argv.index('--pin')+1]=bundle_digest(AUDIO_QUOTE_BOUND_FILES)
    tool['notes']='Explicit site:xyq-web browser binding with inherited public profile routing; no automatic fallback or rebind. Exact project/canvas/unique audio node and full form SHA. Reuse the read-only form-price-form-price-form contract. Estimated unit rate only; no total bill, duration inference, navigation, input, upload, authentication reads or spending.'
    return validate_manifest(tool)

def audio_edit_bound_manifest(operation):
    if operation not in AUDIO_EDIT_BOUND_OPERATIONS:
        raise ValueError('Unknown explicit audio preparation operation')
    tool=audio_prompt_manifest() if operation=='audio_prompt_prepare' else audio_settings_manifest(operation)
    argv=tool['command']['argv'];argv[2]+='-bound'
    argv[argv.index('--pin')+1]=bundle_digest(AUDIO_EDIT_BOUND_FILES)
    tool['notes']='Explicit site:xyq-web/browser binding using public profile routing and native input. Exact project/canvas/unique audio footer and full form SHA. Reuse semantic model/rate and plain prompt/structured existing reference contracts. Recheck owned targets, hit points, focus/full selection/end caret/literal text; close only this operation owned menus. Zero-step existing references stay unchanged. No arbitrary selectors/keys/CDP, navigation, rebinding, authentication reads, upload or generation. Partial failures retain phase/input_phase/steps/uncertainty; no retry or rollback.'
    return validate_manifest(tool)

def audio_upload_bound_manifest():
    tool=audio_manifest('audio_reference_upload');argv=tool['command']['argv']
    argv[2]='audio-reference-upload-bound';argv[argv.index('--pin')+1]=bundle_digest(AUDIO_UPLOAD_BOUND_FILES)
    tool['notes']='Explicit site:xyq-web/browser binding with inherited public profile routing. One approved-project PCM WAV or bounded MPEG Layer-III MP3; preserve exact form, empty/append, stable key and durable one-input intent/receipt contracts. MP3 frame checks are not decoder/provider acceptance and encoded-frame duration is not a quote. Native DOM is limited to depth0 root and exact audio-input resolution; revalidate scope/input association/nodeId/file/form before exactly one public Page.setFileInput call with the fixed selector. The installed bridge owns file-chooser interception; no bare CDP file-input or in-page byte-injection fallback. Expected zero-step preflight conflicts return upload_rejected with reason and upload_accepted=false. Post-intent errors retain bounded private failure metadata and the lock, never raw bridge text. No navigation, rebinding, auth export, generation or payment.'
    tool['completion']='attached proves only an observed new audio-reference chip. Reused receipts are historical and not current form verification. upload_rejected is an explicit preflight stop: completed ATM job is not successful upload. Check result status before proceeding; unknown intent outcomes retain their lock and are never resubmitted.'
    return validate_manifest(tool)

def home_bound_manifest(operation):
    if operation not in HOME_BOUND_OPERATIONS:
        raise ValueError('Unknown explicit home-binding operation')
    tool=form_manifest(operation) if operation in FORM_OPERATIONS else mode_manifest(operation)
    argv=tool['command']['argv']
    argv[2]+='-bound'
    argv[argv.index('--pin')+1]=bundle_digest(HOME_BOUND_FILES)
    tool['notes']='Explicit site:xyq-home browser binding, not automatic adapter fallback. Exact HTTPS /home DOM; mode switches bind an empty draft, form preparation binds its exact full digest. Scoped semantic model/radio/canvas clicks and plain composer/duration native text replacement with focus/selection/literal readback. Preserve references, reject rich-prompt replacement and uncertain file state. No upload, navigation, authentication reads, generation, purchase or publication. Other tools retain their own routing.'
    return validate_manifest(tool)

def home_quote_manifest():
    props={'settings':{'type':'object','properties':{'expected_draft_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}},'required':['expected_draft_sha256'],'additionalProperties':False}}
    return validate_manifest({'id':'xyq.web.home_quote','provider':'xyq','title':'小云雀首页 · 显示积分预估',
        'capabilities':['website','home_quote'],'adapter':'command','executable':'opencliapp','paid':False,'permissions':['execute_code'],
        'schema':{'type':'object','properties':props,'required':['settings'],'additionalProperties':False},
        'example':{'settings':{'expected_draft_sha256':'0'*64}},
        'command':{'argv':['__opencli_shim','xyq-web','home-quote-bound','--pin',bundle_digest(HOME_QUOTE_FILES),'-f','json','--settings',{'json':'settings'}],'output':'json','timeout':60},
        'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Explicit site:xyq-home/browser binding; read-only actual composer price with exact full draft and stable bracketing snapshots. Displayed amount and crossed-out originalAmount are separate. Preserve per-second units. Missing/busy/unknown prices are never zero. No navigation, menu/input, auth export, upload, generation or payment; old sixteen definitions retain their routing.',
        'completion':'Displayed estimate or unit rate only, never a verified spending ceiling, final bill or permission to spend. total_credits and output_duration_seconds stay null; inspect quote_status and reported_estimate before proceeding.'})

def history_manifest():
    props={name:{'type':'string','pattern':'^[0-9]{1,20}$'} for name in ('project_id','canvas_id')}
    return validate_manifest({'id':'xyq.web.project_history_state','provider':'xyq','title':'小云雀项目 · 生成历史视图',
        'capabilities':['website','project_history_state'],'adapter':'command','executable':'opencliapp','paid':False,'permissions':['execute_code'],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},'example':{'project_id':'1','canvas_id':'2'},
        'command':{'argv':['__opencli_shim','xyq-web','project-history-state-bound','--pin',bundle_digest(HISTORY_FILES),'-f','json','--project',{'input':'project_id'},'--canvas',{'input':'canvas_id'}],'output':'json','timeout':60},
        'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Explicit site:xyq-web/browser routing. Read exact project/canvas UI and owned history popover/filter associations only; no popup/filter input, navigation, auth export, task-row extraction, uploads, generation, payment or download. Existing seventeen definitions keep their routing.',
        'completion':'Closed/loading counts are null; history_empty proves only current filtered visible empty state. all_records=false/task_count=null/row_scope_verified=false. Actual populated task IDs/status/results require their observed scoped layout; never treat an empty view as all media tasks completed.'})

def generation_manifest(operation):
    if operation not in GENERATION_OPERATIONS:
        raise ValueError('Unknown XYQ generation operation')
    generate=operation=='generate'
    props={'settings':{'type':'object','properties':{
        'expected_draft_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
        'quote_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
        'max_credits':{'type':'number','minimum':0,'maximum':10000},
        'human_confirmed':{'type':'boolean','const':True},
        'estimated_cost_confirmed':{'type':'boolean','const':True},
        'request_key':{'type':'string','pattern':'^[A-Za-z0-9_.:-]{1,160}$'}},
        'required':['expected_draft_sha256','quote_sha256','max_credits','human_confirmed','estimated_cost_confirmed','request_key'],
        'additionalProperties':False}} if generate else {'request_key':{'type':'string','pattern':'^[A-Za-z0-9_.:-]{1,160}$'}}
    argv=['__opencli_shim','xyq-web','generate-home-bound' if generate else 'generation-status','--pin',bundle_digest(GENERATION_FILES),'-f','json','--workspace',{'workspace':''}]
    argv+=['--settings',{'json':'settings'}] if generate else ['--key',{'input':'request_key'}]
    return validate_manifest({'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀媒体 · '+operation,
        'capabilities':['website',operation],'adapter':'command','executable':'opencliapp','paid':generate,
        'permissions':['execute_code']+(['external_write'] if generate else []),
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        'command':{'argv':argv,'output':'json','timeout':180},'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-07',
        'notes':'Exactly one draft-bound native home submit. Requires explicit confirmation of displayed estimate and budget; unit-rate audio remains total_quote_required. Project/canvas acknowledgement is not a provider task ID. Stable request keys and unknown operation locks are preserved; no automatic retry, uploads or auth reads.',
        'completion':'Submitted project route is not completed media. generation_status reads only the exact original local receipt; provider task polling and downloads require a separately observed UI contract. Displayed estimate is not a server-enforced spend ceiling or final bill.'})

def result_manifest(operation):
    if operation not in RESULT_OPERATIONS:
        raise ValueError('Unknown XYQ conversation-result operation')
    props={'thread_id':{'type':'string','pattern':'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$'}}
    argv=['__opencli_shim','xyq-web',operation.replace('_','-')+'-bound','--pin',bundle_digest(RESULT_FILES),'-f','json','--thread',{'input':'thread_id'}]
    if operation!='results':
        props['result_id']={'type':'string','pattern':'^[a-f0-9]{32}$'}
        argv+=['--result',{'input':'result_id'}]
    if operation=='result_download_quote':
        props['expected_result_sha256']={'type':'string','pattern':'^[a-f0-9]{64}$'}
        argv+=['--expected',{'input':'expected_result_sha256'}]
    return validate_manifest({'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀结果 · '+operation,
        'capabilities':['website',operation],'adapter':'command','executable':'opencliapp','paid':False,'permissions':['execute_code'],
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        'command':{'argv':argv,'output':'json','timeout':60},'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-08',
        'notes':'Read only the exact already-open integrated-agent conversation and its rendered image cards/selected preview. Public site:xyq-home/browser routing; no navigation, full prompts, auth files, signed query strings, generation, upload or download click. Download plan requires exact result digest and enabled unobscured preview control.',
        'completion':'Resource ID is visible media identity, not provider task ID/status. all_results=false; loaded pixels are not task association or completed local delivery. result_download_quote is an existing-file control plan, not a price or download. Video/audio and actual download events/files remain separate acceptance.'})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--include-canvas',action='store_true',help='Include parked experimental canvas/text tools, outside current media scope')
    parser.add_argument('--bound-home',action='store_true',help='Explicit browser binding for five existing home state/menu/mode/prepare tools; no automatic fallback')
    parser.add_argument('--bound-audio-quote',action='store_true',help='Explicit browser binding for the existing audio_quote tool; estimated rate only, no fallback')
    parser.add_argument('--bound-audio-edit',action='store_true',help='Explicit browser binding for three existing audio choices/parameter/prompt tools; no automatic fallback')
    parser.add_argument('--bound-audio-upload',action='store_true',help='Explicit browser binding for one approved PCM WAV / MP3; no automatic fallback')
    parser.add_argument('--include-delivery',action='store_true',help='Add reviewed single-submit and original local-receipt status tools; provider tasks/downloads remain separate')
    parser.add_argument('--include-results',action='store_true',help='Add three read-only existing-conversation image-result/preview/download-plan queries; no download click')
    parser.add_argument('--results-only',action='store_true',help='Emit only the three --include-results bundles, to install beside build_xyq_runtime.py without colliding IDs')
    args=parser.parse_args()
    stages=('include_canvas','bound_home','bound_audio_quote','bound_audio_edit','bound_audio_upload','include_delivery','include_results')
    if args.results_only and any(getattr(args,k) for k in stages):
        parser.error('--results-only cannot be combined with other stage options')
    if args.results_only:
        result=[extensions.pack(result_manifest(op),args.out/op) for op in RESULT_OPERATIONS]
        print(json.dumps({'status':'compiled','scope':'results-only','operations':list(RESULT_OPERATIONS),'result_adapter_sha256':bundle_digest(RESULT_FILES),
                          'result_binding':'explicit-browser','result_scope':'current_rendered_conversation_images','provider_delivery_verified':False,'bundles':result},ensure_ascii=False))
        return
    result=[]
    for operation in OPERATIONS:
        result.append(extensions.pack(manifest(operation),args.out/operation))
    for operation in FORM_OPERATIONS:
        tool=home_bound_manifest(operation) if args.bound_home and operation in HOME_BOUND_OPERATIONS else form_manifest(operation)
        result.append(extensions.pack(tool,args.out/operation))
    for operation in MODE_OPERATIONS:
        result.append(extensions.pack(home_bound_manifest(operation) if args.bound_home else mode_manifest(operation),args.out/operation))
    for operation in AUDIO_OPERATIONS:
        result.append(extensions.pack(audio_upload_bound_manifest() if args.bound_audio_upload and operation=='audio_reference_upload' else audio_manifest(operation),args.out/operation))
    result.append(extensions.pack(audio_bound_manifest(),args.out/'audio_form_state_bound'))
    result.append(extensions.pack(audio_edit_bound_manifest('audio_prompt_prepare') if args.bound_audio_edit else audio_prompt_manifest(),args.out/'audio_prompt_prepare'))
    for operation in AUDIO_SETTINGS_OPERATIONS:
        result.append(extensions.pack(audio_edit_bound_manifest(operation) if args.bound_audio_edit else audio_settings_manifest(operation),args.out/operation))
    result.append(extensions.pack(audio_quote_bound_manifest() if args.bound_audio_quote else audio_quote_manifest(),args.out/'audio_quote'))
    result.append(extensions.pack(home_quote_manifest(),args.out/'home_quote'))
    result.append(extensions.pack(history_manifest(),args.out/'project_history_state'))
    operations=list(OPERATIONS+FORM_OPERATIONS+MODE_OPERATIONS+AUDIO_OPERATIONS+AUDIO_BOUND_OPERATIONS+AUDIO_PROMPT_OPERATIONS+AUDIO_SETTINGS_OPERATIONS+AUDIO_QUOTE_OPERATIONS+HOME_QUOTE_OPERATIONS+HISTORY_OPERATIONS)
    if args.include_delivery:
        result.extend(extensions.pack(generation_manifest(op),args.out/op) for op in GENERATION_OPERATIONS)
        operations.extend(GENERATION_OPERATIONS)
    if args.include_results:
        result.extend(extensions.pack(result_manifest(op),args.out/op) for op in RESULT_OPERATIONS)
        operations.extend(RESULT_OPERATIONS)
    if args.include_canvas:
        result.append(extensions.pack(canvas_manifest(),args.out/'canvas_inspect'))
        for operation in TEXT_OPERATIONS:
            result.append(extensions.pack(text_manifest(operation),args.out/operation))
        operations+=['canvas_inspect',*TEXT_OPERATIONS]
    metadata={'status':'compiled','scope':'media-foundation' if not args.include_canvas else 'media-foundation+parked-canvas',
              'operations':operations,'adapter_sha256':bundle_digest(),'form_adapter_sha256':bundle_digest(FORM_FILES),'mode_adapter_sha256':bundle_digest(MODE_FILES),'audio_adapter_sha256':bundle_digest(AUDIO_FILES),'audio_bound_adapter_sha256':bundle_digest(AUDIO_BOUND_FILES),'audio_prompt_adapter_sha256':bundle_digest(AUDIO_PROMPT_FILES),'audio_settings_adapter_sha256':bundle_digest(AUDIO_SETTINGS_FILES),'audio_quote_adapter_sha256':bundle_digest(AUDIO_QUOTE_FILES),'home_quote_adapter_sha256':bundle_digest(HOME_QUOTE_FILES),'home_quote_binding':'explicit-browser','history_adapter_sha256':bundle_digest(HISTORY_FILES),'history_binding':'explicit-browser','bundles':result}
    if args.bound_home:
        metadata.update(home_binding='explicit-browser',home_bound_operations=list(HOME_BOUND_OPERATIONS),home_bound_adapter_sha256=bundle_digest(HOME_BOUND_FILES))
    if args.bound_audio_quote:
        metadata.update(audio_quote_binding='explicit-browser',audio_quote_bound_adapter_sha256=bundle_digest(AUDIO_QUOTE_BOUND_FILES))
    if args.bound_audio_edit:
        metadata.update(audio_edit_binding='explicit-browser',audio_edit_bound_operations=list(AUDIO_EDIT_BOUND_OPERATIONS),audio_edit_bound_adapter_sha256=bundle_digest(AUDIO_EDIT_BOUND_FILES))
    if args.bound_audio_upload:
        metadata.update(audio_upload_binding='explicit-browser',audio_upload_bound_adapter_sha256=bundle_digest(AUDIO_UPLOAD_BOUND_FILES))
    if args.include_canvas:
        metadata.update(canvas_adapter_sha256=bundle_digest(CANVAS_FILES),text_adapter_sha256=bundle_digest(TEXT_FILES))
    if args.include_delivery:
        metadata.update(generation_adapter_sha256=bundle_digest(GENERATION_FILES),generation_binding='explicit-browser',provider_delivery_verified=False)
    if args.include_results:
        metadata.update(result_adapter_sha256=bundle_digest(RESULT_FILES),result_binding='explicit-browser',result_scope='current_rendered_conversation_images',provider_delivery_verified=False)
    print(json.dumps(metadata,ensure_ascii=False))

if __name__=='__main__':main()
