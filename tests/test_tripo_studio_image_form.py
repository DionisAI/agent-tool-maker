"""Image form contracts and isolated real fake subprocesses, not image results."""
import importlib.util
import json
from pathlib import Path
import pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.extensions import validate_bundle
from agent_tool_maker.maker import digest, install
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('image_form_builder',ROOT/'scripts/build_tripo_studio.py')
b=importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

@pytest.mark.parametrize('op',b.IMAGE_FORM_OPERATIONS)
def test_image_form_definition_source_and_permissions(op):
    tool=b.manifest(op)
    assert validate_bundle(ROOT/'generated/tripo-studio-delivery-stage-r4'/op)['sha256']==digest(tool)
    assert tool['paid'] is False
    assert set(tool['permissions'])==({'execute_code'} if op.endswith('inspect') else {'execute_code','external_write'})
    assert b.image_form_digest() in tool['command']['argv']
    assert 'outputs' not in tool['command'] and 'credential_env' not in tool['command']
    assert b.viewer_digest()=='55ea3568db6a9eee1d3d7e9bfe5b19c20bf5ecbd2e687ab1a432d45f2fd4fdf8'
    assert b.workspace_digest()=='3684f332b267a258d7bc9a24f003cf6ebe26bc50428a7abc6c0f2a8eef387d5e'
    if op.endswith('prepare'):
        schema=tool['schema']['properties']['settings']
        assert schema['required']==['expected_draft_sha256']
        assert schema['properties']['prompt']['maxLength']==10000
        assert None in schema['properties']['aspect_ratio']['enum']

@pytest.mark.parametrize('op',b.IMAGE_FORM_OPERATIONS)
def test_image_form_real_fake_subprocess_preserves_no_vault_and_request_reuse(router,workspace,tmp_path,op):
    import sys
    tool=b.manifest(op)
    path=tmp_path/'image-form.json'
    path.write_text(json.dumps(tool))
    install(router.state,router.catalog,path,digest(tool))
    router.catalog=Catalog(router.state)
    program=tmp_path/'fake-opencliapp'
    program.write_text(f'''#!{sys.executable}
import os,sys,json
from pathlib import Path
assert sys.argv[1:4]==['__opencli_shim','tripo-studio','{op.replace('_','-')}']
assert not any('TOKEN' in k or 'KEY' in k for k in os.environ)
counter=Path('image-form-count.txt')
counter.write_text(str(int(counter.read_text())+1) if counter.exists() else '1')
print(json.dumps([{{'result':{{'status':'prepared','paid_submitted':False,'upload_started':False}}}}]))
''')
    program.chmod(0o700)
    bind_cli(router.state,'opencliapp',str(program))
    router.vault.get=lambda *args:pytest.fail('No credential read')
    inputs={'asset_id':'11111111-2222-3333-4444-555555555555'}
    if op.endswith('prepare'):
        inputs['settings']={'number_images':1,'expected_draft_sha256':'a'*64}
    grants=['execute_code',*(['external_write'] if op.endswith('prepare') else [])]
    one=router.run(tool['id'],inputs,workspace,request_key='image-form-once',grants=grants)
    two=router.run(tool['id'],inputs,workspace,request_key='image-form-once',grants=grants)
    assert one['status']=='completed' and one['id']==two['id']
    assert one['data']['result'][0]['result']['upload_started'] is False
    assert (workspace/'image-form-count.txt').read_text()=='1'
