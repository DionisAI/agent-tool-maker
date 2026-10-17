"""Explicit bound-reader contract; real supplier acceptance remains separate."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
from test_xyq_web_cli import native_page,load
from test_xyq_web_media import SCOPE,audio_html,media_adapter

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('xyq_bound_builder',ROOT/'scripts/build_xyq_web.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def test_bound_manifest_is_read_only_exact_scope():
    tool=b.audio_bound_manifest()
    assert tool['id']=='xyq.web.audio_form_state_bound'
    assert tool['permissions']==['execute_code'] and not tool['paid']
    assert tool['schema']['required']==['project_id','canvas_id','node_id']
    assert tool['schema']['additionalProperties'] is False
    assert tool['command']['argv'][1:3]==['xyq-web','audio-form-state-bound']
    assert b.bundle_digest(b.AUDIO_BOUND_FILES) in tool['command']['argv']
    assert 'credential' not in tool and 'credential_env' not in tool['command']

def test_bound_digest_matches_node():
    out=subprocess.run(['node','--input-type=module','-e',"import{audioBoundDigest}from'./examples/opencli/xyq-web/audio-bound.mjs';console.log(audioBoundDigest());"],cwd=ROOT,text=True,capture_output=True,check=True)
    assert out.stdout.strip()==b.bundle_digest(b.AUDIO_BOUND_FILES)

def test_bound_node_protocol_regressions():
    subprocess.run(['node','--test','tests/xyq_web_bound.test.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)

def test_bound_real_fake_subprocess_and_stable_request_reuse(router,workspace,tmp_path):
    from agent_tool_maker.catalog import Catalog
    from agent_tool_maker.cli_adapter import bind_cli
    from agent_tool_maker.maker import digest,install
    tool=b.audio_bound_manifest();path=tmp_path/'manifest.json';path.write_text(json.dumps(tool))
    install(router.state,router.catalog,path,digest(tool));router.catalog=Catalog(router.state)
    program=tmp_path/'fake-bound-opencliapp'
    program.write_text(f'''#!{sys.executable}
import sys,json,os
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','xyq-web','audio-form-state-bound']
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
p=Path('bound-read-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print(json.dumps([{{'result':{{'status':'fake_bound_fixture','paid_submitted':False}}}}]))
''');program.chmod(0o700);bind_cli(router.state,'opencliapp',str(program))
    router.vault.get=lambda *a:pytest.fail('No credential access')
    one=router.run(tool['id'],dict(SCOPE),workspace,request_key='bound-read-once',grants=['execute_code'])
    two=router.run(tool['id'],dict(SCOPE),workspace,request_key='bound-read-once',grants=['execute_code'])
    assert one['status']=='completed' and one['id']==two['id']
    assert (workspace/'bound-read-count').read_text()=='1'

@pytest.mark.browser
def test_native_bound_reader_preserves_existing_form(native_page):
    load(native_page,audio_html(),f"https://xyq.jianying.com/project?projectId={SCOPE['project_id']}&canvasId={SCOPE['canvas_id']}");before=native_page.locator('body').inner_html()
    out=media_adapter(native_page,{'operation':'audio_bound','scope':dict(SCOPE)})
    assert 'error' not in out,out
    result=out['result'][0]['result']
    assert result['form_sha256']==out['before']['form_sha256']
    assert result['browser_surface']=='browser' and not result['binding_changed']
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0

@pytest.mark.browser
def test_native_bound_reader_keeps_existing_layers_untouched(native_page):
    load(native_page,audio_html(),f"https://xyq.jianying.com/project?projectId={SCOPE['project_id']}&canvasId={SCOPE['canvas_id']}");native_page.evaluate("document.body.insertAdjacentHTML('beforeend','<div role=dialog>FAKE_DIALOG</div>')")
    before=native_page.locator('body').inner_html()
    out=media_adapter(native_page,{'operation':'audio_bound','scope':dict(SCOPE)})
    assert 'error' not in out,out
    assert out['result'][0]['result']['layers']==1
    assert native_page.locator('body').inner_html()==before
    assert native_page.evaluate('window.submitted')==0
