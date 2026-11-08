"""Compile the production media namespace without replacing older loaders."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from build_xyq_web import (
    ROOT,extensions,bundle_digest,manifest,home_bound_manifest,audio_bound_manifest,
    audio_manifest,audio_upload_bound_manifest,audio_edit_bound_manifest,audio_quote_bound_manifest,
    home_quote_manifest,history_manifest,generation_manifest,validate_manifest,
    OPERATIONS,HOME_BOUND_OPERATIONS,AUDIO_EDIT_BOUND_OPERATIONS,
    HOME_BOUND_FILES,AUDIO_EDIT_BOUND_FILES,AUDIO_UPLOAD_BOUND_FILES,AUDIO_QUOTE_BOUND_FILES,
    HOME_QUOTE_FILES,HISTORY_FILES,GENERATION_FILES,
)

MEDIA_RUNTIME_FILES=tuple(dict.fromkeys((*HOME_BOUND_FILES,*AUDIO_EDIT_BOUND_FILES,
    *AUDIO_UPLOAD_BOUND_FILES,*AUDIO_QUOTE_BOUND_FILES,*HOME_QUOTE_FILES,*HISTORY_FILES,
    *GENERATION_FILES,'media-runtime.mjs','media-runtime.js')))
MEDIA_RUNTIME_OPERATIONS=('account','surface','form_inspect','form_options',
    'form_state','form_choices','form_prepare','mode_choices','mode_prepare',
    'audio_form_state','audio_reference_upload','audio_form_state_bound','audio_prompt_prepare',
    'audio_choices','audio_prepare','audio_quote','home_quote','project_history_state','generate','generation_status')

def original_manifest(operation):
    if operation in OPERATIONS:return manifest(operation)
    if operation in HOME_BOUND_OPERATIONS:return home_bound_manifest(operation)
    if operation=='audio_form_state':return audio_manifest(operation)
    if operation=='audio_form_state_bound':return audio_bound_manifest()
    if operation=='audio_reference_upload':return audio_upload_bound_manifest()
    if operation in AUDIO_EDIT_BOUND_OPERATIONS:return audio_edit_bound_manifest(operation)
    if operation=='audio_quote':return audio_quote_bound_manifest()
    if operation=='home_quote':return home_quote_manifest()
    if operation=='project_history_state':return history_manifest()
    if operation in ('generate','generation_status'):return generation_manifest(operation)
    raise ValueError('Unknown reviewed media operation')

def runtime_manifest(operation):
    tool=copy.deepcopy(original_manifest(operation));argv=tool['command']['argv']
    argv[1]='xyq-media';argv[2]=operation.replace('_','-')
    argv[argv.index('--pin')+1]=bundle_digest(MEDIA_RUNTIME_FILES)
    tool['notes']='Complete hash-pinned reviewed media namespace. Explicit site:xyq-home/browser for homepage operations and site:xyq-web/browser for project audio/history, with inherited public profile routing and no automatic rebinding. generation_status is LOCAL and creates no Page. Existing namespace registrations remain unchanged. '+tool['notes']
    tool['checked_on']='2026-10-08'
    return validate_manifest(tool)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=[extensions.pack(runtime_manifest(op),args.out/op) for op in MEDIA_RUNTIME_OPERATIONS]
    print(json.dumps({'status':'compiled','namespace':'xyq-media','operations':list(MEDIA_RUNTIME_OPERATIONS),
      'source_files':list(MEDIA_RUNTIME_FILES),'source_sha256':bundle_digest(MEDIA_RUNTIME_FILES),
      'bundles':result,'installed':False,'provider_execution_verified':False}))

if __name__=='__main__':main()
