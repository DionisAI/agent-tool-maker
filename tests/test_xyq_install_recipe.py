"""The 27-tool rebuild recipe of docs/XYQ_MEDIA_RUNTIME_CONTRACT.md: four compilers, disjoint tool IDs.

Runs the four documented compile commands as real subprocesses into temporary directories, with a fake
executable bridge, a temporary download root and a fake loader closure directory. Nothing is installed.
"""
import json
from pathlib import Path
import subprocess
import sys
from agent_tool_maker.extensions import validate_bundle

ROOT=Path(__file__).resolve().parents[1]
RECIPE=ROOT/'docs/XYQ_MEDIA_RUNTIME_CONTRACT.md'

def compile_ids(argv,out):
    subprocess.run([sys.executable,*argv,'--out',str(out)],cwd=ROOT,check=True,capture_output=True,text=True)
    ids=[]
    for manifest in sorted(out.glob('*/manifest.json')):
        assert validate_bundle(manifest.parent)['sha256']
        ids.append(json.loads(manifest.read_text())['id'])
    return ids

def test_four_compilers_emit_exactly_27_distinct_tool_ids(tmp_path):
    bridge=tmp_path/'fake-opencli-app';bridge.write_text('#!/bin/sh\nexit 0\n');bridge.chmod(0o700)
    downloads=tmp_path/'downloads';downloads.mkdir();closure=tmp_path/'reviewed';closure.mkdir();out=tmp_path/'out'
    groups={
        'runtime':compile_ids(['scripts/build_xyq_runtime.py'],out/'runtime'),
        'results':compile_ids(['scripts/build_xyq_web.py','--results-only'],out/'results'),
        'download':compile_ids(['scripts/build_xyq_download.py','--bridge',str(bridge),'--download-root',str(downloads),
                                '--adapter-dir',str(closure)],out/'download'),
        'material':compile_ids(['scripts/build_xyq_material.py'],out/'material'),
    }
    assert {k:len(v) for k,v in groups.items()}=={'runtime':20,'results':3,'download':2,'material':2}
    ids=[i for v in groups.values() for i in v]
    assert len(ids)==27 and len(set(ids))==27,sorted(ids)
    # The recipe's warning: the default website compiler reuses 18 runtime IDs with other definitions.
    default=compile_ids(['scripts/build_xyq_web.py'],tmp_path/'default')
    assert len(default)==18 and set(default)<=set(groups['runtime'])
    assert not set(default)&set(groups['results']+groups['download']+groups['material'])

def test_recipe_documents_the_same_four_commands():
    text=RECIPE.read_text(encoding='utf-8')
    for command in ('scripts/build_xyq_runtime.py --out','scripts/build_xyq_web.py --results-only --out',
                    'scripts/build_xyq_download.py --out','scripts/build_xyq_material.py --out'):
        assert command in text,command
    line=next(l for l in text.splitlines() if 'scripts/build_xyq_download.py --out' in l)
    assert all(flag in line for flag in ('--bridge','--download-root','--adapter-dir')),line
