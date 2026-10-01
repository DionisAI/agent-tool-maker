#!/usr/bin/env python3
"""Credential-independent demo. Synthetic endpoints; only FFprobe executes for real.

Creates a temporary isolated vault and project, generates three CLI bundles, runs
the FFprobe bundle twice with one request key, and compiles API/web dry-run plans.
No supplier or coding-model request, browser navigation, credential transfer, or
modification of the user's persistent ATM configuration occurs.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.extensions import declare_credential, pack, validate_bundle, import_openapi
from agent_tool_maker.maker import read_manifest, validate_manifest, digest, install
from agent_tool_maker.management import connect_value
from agent_tool_maker.storage import State, canonical
from agent_tool_maker.vault import Vault


def demo(out):
    root=Path(__file__).resolve().parents[1];out=Path(out).resolve()
    if out.exists():raise ValueError('Choose a new output directory; existing work will not be overwritten.')
    atm=shutil.which('atm');probe=shutil.which('ffprobe')
    if not atm or not probe:raise ValueError('Install ATM and FFprobe before running the demonstration.')
    out.mkdir(parents=True)
    receipt={'synthetic':True,'supplier_calls':0,'model_calls':0,'native_browser_navigation':False,'bundles':[], 'checks':[]}
    with tempfile.TemporaryDirectory(prefix='atm-extension-demo-') as tmp:
        home=Path(tmp)/'state';workspace=Path(tmp)/'project';workspace.mkdir()
        vault=Vault(State(home),password='SYNTHETIC-ONLY-DEMO-PASSWORD');vault.init('passphrase')
        router=Router(home,vault=vault)
        try:
            declare_credential(router,'acme.production',apply=True);connect_value(router,'acme.production','FAKE-DEMO-KEY-NOT-REAL')
            receipt['checks'].append({'name':'unknown_key_saved','passed':vault.get('acme.production')=='FAKE-DEMO-KEY-NOT-REAL' and b'FAKE-DEMO-KEY-NOT-REAL' not in home.joinpath('state.sqlite3').read_bytes()})
            models=[('media',read_manifest(root/'examples/extensions/ffprobe-cli.json')),
                    ('web',read_manifest(root/'examples/extensions/web-export.json')),
                    ('api',import_openapi(json.loads((root/'examples/extensions/sample.openapi.json').read_text()),'getRecord','acme.get_record',credential='acme.production'))]
            for name,model in models:
                model=validate_manifest(model,router.catalog);directory=out/(name+'-cli')
                pack(model,directory,router.catalog)
                install(router.state,router.catalog,directory/'manifest.json',digest(model));router.catalog=Catalog(router.state)
                receipt['bundles'].append({'kind':name,'path':directory.name,'tool':model['id'],'sha256':digest(model),'checked':validate_bundle(directory)['valid']})
            bind_cli(router.state,'ffprobe',probe)
            shutil.copy(root/'tests/fixtures/tone.wav',workspace/'tone.wav')
            tasks={'media':{'path':'tone.wav'},'api':{'id':'demo'},'web':{'text':'Synthetic task; no website visit'}}
            seen=[]
            for name in ['media','media','api','web']:
                path=workspace/(name+'.json');path.write_text(canonical(tasks[name]))
                argv=[sys.executable,'-I',str(out/(name+'-cli')/'tool.py'),'--atm',atm,'--home',str(home),'--input',str(path),'--workspace',str(workspace),'--request-key','demo-'+name]
                argv += ['--allow-code'] if name=='media' else ['--dry-run']
                result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
                if result.returncode:raise RuntimeError('Generated CLI failed: '+result.stdout)
                value=json.loads(result.stdout)
                receipt['checks'].append({'name':name+('-real-cli' if name=='media' else '-dry-run'),'passed':value.get('status')=='completed' if name=='media' else value['dry_run']})
                if name=='media':
                    seen.append(value['id'])
                    if len(seen)==1:
                        (out/'media-result.json').write_text(json.dumps(value['data']['result'],indent=2))
                else:(out/(name+'-plan.json')).write_text(json.dumps(value,indent=2))
            receipt['checks'].append({'name':'repeat_did_not_reexecute','passed':seen[0]==seen[1] and len(router.state.jobs())==1})
        finally:router.close()
    receipt['passed']=all(x['passed'] for x in receipt['checks'])
    (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:
        result=demo(a.out);print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
    except (OSError,ValueError,RuntimeError) as error:
        print(json.dumps({'error':str(error)}));raise SystemExit(2)
