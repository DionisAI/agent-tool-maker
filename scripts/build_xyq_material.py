"""Compile homepage reference-format discovery; file upload is a separate gate."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from build_xyq_web import extensions,validate_manifest,bundle_digest,HOME_QUOTE_FILES
FILES=(*HOME_QUOTE_FILES,'material-home.mjs','material-home.js')
OPERATIONS=('home_material_state','home_material_choices')
def manifest(operation):
    if operation not in OPERATIONS:raise ValueError('Select a reviewed homepage material discovery operation')
    return validate_manifest({'id':'xyq.web.'+operation,'provider':'xyq','title':'小云雀首页素材 · '+operation,
      'capabilities':['website','reference-media',operation],'adapter':'command','executable':'opencliapp','paid':False,
      'permissions':['execute_code'],'schema':{'type':'object','properties':{},'required':[],'additionalProperties':False},'example':{},
      'command':{'argv':['__opencli_shim','xyq-material',operation.replace('_','-'),'--pin',bundle_digest(FILES),'-f','json'],'output':'json','timeout':60},
      'sources':['https://xyq.jianying.com/'],'checked_on':'2026-10-08',
      'notes':'Exact site:xyq-home named browser binding and public profile routing, no automatic rebind. State binds the complete current draft and declared local-upload file input. Choices reads only an already-open mutually associated material menu with its exact owned Radix mask. No navigation, menu input, file chooser, auth reads, uploads, asset selection, generation or download.',
      'completion':'Declared format and menu metadata, not verified provider limits, accepted files, voice effects or generated media. Choices intentionally has no complete draft digest while the owned material menu is open.'})
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    result=[extensions.pack(manifest(op),args.out/op) for op in OPERATIONS]
    print(json.dumps({'status':'compiled','operations':list(OPERATIONS),'source_files':list(FILES),
      'source_sha256':bundle_digest(FILES),'bundles':result,'installed':False,'provider_upload_verified':False}))
if __name__=='__main__':main()
