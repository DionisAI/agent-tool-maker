"""Source-bound definitions and real fake subprocesses, not provider output tests."""
import importlib.util
import json
from pathlib import Path
import pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.extensions import validate_bundle
from agent_tool_maker.maker import digest, install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui_options_builder', ROOT/'scripts/build_tripo_studio.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize('operation', builder.UI_OPTIONS_OPERATIONS)
def test_ui_options_bundle_is_bound_to_reviewed_source_and_permissions(operation):
    tool = builder.manifest(operation)
    assert validate_bundle(ROOT/'generated/tripo-studio-ui-options'/operation)['sha256'] == digest(tool)
    assert tool['paid'] is False
    assert set(tool['permissions']) == ({'execute_code','external_write'} if operation.endswith('_prepare') else {'execute_code'})
    assert builder.ui_options_digest() in tool['command']['argv']
    assert 'credential_env' not in tool['command']
    assert 'outputs' not in tool['command']
    # Reviewed sidebar/SPA-source waits; preserve the exact dependency assertion.
    assert builder.workspace_digest() == '3b7df85e08edf55de3dc09c777ed771c01fbc0965d13b6db0b20528536909dcc'
    assert builder.query_digest() == '13c05dc89662502d4209d7b613418b3b54ffa00a973352984206e38801b43b59'


@pytest.mark.parametrize('operation', builder.UI_OPTIONS_OPERATIONS)
def test_ui_options_real_fake_subprocess_no_vault_and_stable_key_reuse(router, workspace, tmp_path, operation):
    import sys
    tool = builder.manifest(operation)
    path = tmp_path/'tool.json'
    path.write_text(json.dumps(tool))
    install(router.state, router.catalog, path, digest(tool))
    router.catalog = Catalog(router.state)
    program = tmp_path/'fake-opencliapp'
    command = operation.replace('_','-')
    program.write_text(f'''#!{sys.executable}
import sys,os,json
from pathlib import Path
assert sys.argv[1:4] == ['__opencli_shim','tripo-studio','{command}']
assert not any('TOKEN' in n or 'KEY' in n for n in os.environ)
count=Path('options-count.txt')
count.write_text(str(int(count.read_text())+1) if count.exists() else '1')
print(json.dumps([{{'result':{{'status':'prepared','paid_submitted':False,'download_started':False}}}}]))
''')
    program.chmod(0o700)
    bind_cli(router.state,'opencliapp',str(program))
    router.vault.get = lambda *args: pytest.fail('No credential read')
    inputs = {'asset_id':'11111111-2222-3333-4444-555555555555'}
    if operation.endswith('_prepare'):
        inputs['settings'] = {'prompt':'walk','duration':3} if operation == 'animation_prepare' else {'format':'FBX','fbx_variant':'Mixamo'}
    grants = ['execute_code', *(['external_write'] if operation.endswith('_prepare') else [])]
    first = router.run(tool['id'],inputs,workspace,request_key='options-once',grants=grants)
    second = router.run(tool['id'],inputs,workspace,request_key='options-once',grants=grants)
    assert first['id'] == second['id'] and first['status'] == 'completed'
    assert first['data']['result'][0]['result']['download_started'] is False
    assert (workspace/'options-count.txt').read_text() == '1'
