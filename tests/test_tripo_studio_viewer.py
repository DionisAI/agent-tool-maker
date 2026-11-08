"""Definitions and real fake subprocesses; not provider persistence/mesh acceptance."""
import importlib.util
import json
from pathlib import Path
import pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.extensions import validate_bundle
from agent_tool_maker.maker import digest, install

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('viewer_builder',ROOT/'scripts/build_tripo_studio.py')
b=importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


@pytest.mark.parametrize('op',b.VIEWER_OPERATIONS)
def test_viewer_definition_source_and_permissions(op):
    tool=b.manifest(op)
    assert validate_bundle(ROOT/'generated/tripo-studio-viewer'/op)['sha256']==digest(tool)
    assert tool['paid'] is False
    assert set(tool['permissions'])==({'execute_code'} if op=='viewer_inspect' else {'execute_code','external_write'})
    assert b.viewer_digest() in tool['command']['argv']
    assert 'outputs' not in tool['command'] and 'credential_env' not in tool['command']
    assert b.workspace_digest()=='3b7df85e08edf55de3dc09c777ed771c01fbc0965d13b6db0b20528536909dcc'
    assert b.ui_options_digest()=='47aca5a146ab8b2531893e2408a1b2914f2d0efc4ea506e896d2c6655dcebfb9'


@pytest.mark.parametrize('op',b.VIEWER_OPERATIONS)
def test_viewer_real_fake_subprocess_no_vault_and_key_reuse(router,workspace,tmp_path,op):
    import sys
    tool=b.manifest(op)
    path=tmp_path/'viewer.json'
    path.write_text(json.dumps(tool))
    install(router.state,router.catalog,path,digest(tool))
    router.catalog=Catalog(router.state)
    program=tmp_path/'fake-opencliapp'
    program.write_text(f'''#!{sys.executable}
import os,sys,json
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','tripo-studio','{op.replace('_','-')}']
assert not any('TOKEN' in key or 'KEY' in key for key in os.environ)
counter=Path('viewer-count.txt')
counter.write_text(str(int(counter.read_text())+1) if counter.exists() else '1')
print(json.dumps([{{'result':{{'status':'observed','paid_submitted':False,'save_button_clicked':False}}}}]))
''')
    program.chmod(0o700)
    bind_cli(router.state,'opencliapp',str(program))
    router.vault.get=lambda *args:pytest.fail('No credential read')
    inputs={'asset_id':'11111111-2222-3333-4444-555555555555'}
    if op=='viewer_camera':inputs['action']='orbit_left'
    if op.startswith('hierarchy_'):inputs['node_name']='fixture_mesh'
    if op in ('viewer_prepare','hierarchy_prepare','hierarchy_transform'):
        inputs['settings']={'grid':True} if op=='viewer_prepare' else {'visible':True} if op=='hierarchy_prepare' else {'position':[.1,0,0],'expected_transform_sha256':'a'*64}
    grants=['execute_code',*(['external_write'] if op!='viewer_inspect' else [])]
    one=router.run(tool['id'],inputs,workspace,request_key='viewer-once',grants=grants)
    two=router.run(tool['id'],inputs,workspace,request_key='viewer-once',grants=grants)
    assert one['status']=='completed' and one['id']==two['id']
    assert one['data']['result'][0]['result']['save_button_clicked'] is False
    assert (workspace/'viewer-count.txt').read_text()=='1'
