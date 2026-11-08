"""Compile existing-image download + decoded-file delivery, separate from reads."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from agent_tool_maker import extensions
from agent_tool_maker.maker import validate_manifest
from agent_tool_maker.website_download import source_digest
from build_xyq_web import bundle_digest,RESULT_FILES
DOWNLOAD_FILES=(*RESULT_FILES,'download.mjs','download.js')
OPERATIONS=('result_download','result_download_status')

def manifest(operation,bridge=None,download_root=None):
    if operation not in OPERATIONS:raise ValueError('Unknown result delivery operation')
    write=operation=='result_download'
    argv=['delivery','xyq-image' if write else 'status','--pin',source_digest(),'--workspace',{'workspace':''}]
    props={'request_key':{'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$'}}
    if write:
        bridge=Path(bridge);root=Path(download_root)
        if not bridge.is_absolute() or bridge.is_symlink() or not bridge.is_file() or not os.access(bridge,os.X_OK):raise ValueError('Select a reviewed existing regular bridge executable')
        if not root.is_absolute() or str(root)=='/' or root.is_symlink() or not root.is_dir():raise ValueError('Select the exact existing regular download directory')
        if any(p.is_symlink() for p in (*bridge.parents,*root.parents)):raise ValueError('Reviewed bridge/download paths must not have linked ancestors')
        fields={'thread_id':{'type':'string','pattern':'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$'},
                'result_id':{'type':'string','pattern':'^[a-f0-9]{32}$'},'expected_result_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
                'quote_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'request_key':props['request_key'],
                'human_confirmed':{'type':'boolean','const':True}}
        props={'settings':{'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}}
        argv+=['--settings',{'json':'settings'},'--bridge',str(bridge),'--bridge-sha256',hashlib.sha256(bridge.read_bytes()).hexdigest(),
               '--adapter-pin',bundle_digest(DOWNLOAD_FILES),'--download-root',str(root)]
    else:argv+=['--request-key',{'input':'request_key'}]
    return validate_manifest({'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀交付 · '+operation,
        'capabilities':['website','media-delivery',operation],'adapter':'command','executable':'atm','paid':False,
        'permissions':['execute_code']+(['external_write'] if write else []),
        'schema':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        'command':{'argv':argv,'output':'json','timeout':120},'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-08',
        'notes':'One exact existing-image preview download through a hash-pinned public OpenCLI bridge. Original native and local intents/locks precede side effects. Event source resource identity is required; filename/blob URL alone is unverified. Read only the one observed PNG in the fixed download directory, copy without overwrite, then reuse complete media decoding. No auth, prompt, generation, upload, paid action, automatic second click or broad download enumeration.',
        'completion':'delivered requires an observed source-associated download and a stable decoded project PNG. Download freshness and provider task/generation association remain unverified. Status rechecks the exact local artifact, never browser-polled tasks. Same-key local finalization can resume an observed original download without bridge dispatch; unknown native requests stay locked. Native fixtures and actual provider download acceptance stay separate.'})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--bridge',required=True);p.add_argument('--download-root',required=True);a=p.parse_args()
    result=[extensions.pack(manifest(op,a.bridge,a.download_root),a.out/op) for op in OPERATIONS]
    print(json.dumps({'status':'compiled','scope':'existing-conversation-image-download','operations':list(OPERATIONS),
        'adapter_sha256':bundle_digest(DOWNLOAD_FILES),'pipeline_sha256':source_digest(),'bundles':result,'provider_download_verified':False}))

if __name__=='__main__':main()
