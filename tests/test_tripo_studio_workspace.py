"""Workspace manifests/paid grants and real fake subprocesses, no production login."""
import importlib.util
import json
from pathlib import Path

import pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.errors import RouterError
from agent_tool_maker.extensions import validate_bundle
from agent_tool_maker.maker import digest, install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workspace_builder', ROOT/'scripts/build_tripo_studio.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize('operation', builder.WORKSPACE_OPERATIONS)
def test_workspace_bundle_factory_permissions_and_source_pin(operation):
    tool = builder.manifest(operation)
    assert validate_bundle(ROOT/'generated/tripo-studio-delivery-stage-r4'/operation)['sha256'] == digest(tool)
    assert tool['paid'] is (operation == 'workspace_submit')
    assert 'execute_code' in tool['permissions']
    assert ('external_write' in tool['permissions']) is (operation != 'workspace_inspect')
    assert builder.workspace_digest() in tool['command']['argv']
    assert 'credential_env' not in tool['command'] and 'credential_required' not in tool['command']
    if operation == 'workspace_submit':
        assert tool['schema']['properties']['human_confirmed']['const'] is True
        assert tool['schema']['properties']['module']['enum'] == ['segment','texture','edit','upscale','pbr']
        assert json.loads((ROOT/'generated/tripo-studio-delivery-stage-r4'/operation/'inputs.example.json').read_text()) == {}


def test_new_workspace_paid_operation_requires_paid_grant(router, workspace, tmp_path):
    tool = builder.manifest('workspace_submit')
    definition = tmp_path/'workspace.json'
    definition.write_text(json.dumps(tool))
    install(router.state, router.catalog, definition, digest(tool))
    router.catalog = Catalog(router.state)
    inputs = {'module':'pbr','asset_id':'11111111-2222-3333-4444-555555555555',
        'quote_sha256':'f'*64,'max_credits':5,'request_key':'pbr-fake','human_confirmed':True}
    with pytest.raises(RouterError) as denied:
        router.run(tool['id'], inputs, workspace, request_key='pbr-fake', grants=['execute_code','external_write'])
    assert denied.value.code == 'paid_confirmation_required'
    assert not (workspace/'.atm/tripo-studio-paid').exists()


def test_workspace_inspect_real_fake_subprocess_without_key_and_request_reuse(router, workspace, tmp_path):
    import sys
    tool = builder.manifest('workspace_inspect')
    definition = tmp_path/'workspace.json'
    definition.write_text(json.dumps(tool))
    install(router.state, router.catalog, definition, digest(tool))
    router.catalog = Catalog(router.state)
    program = tmp_path/'fake-opencliapp'
    program.write_text(f'''#!{sys.executable}
import sys,os,json
from pathlib import Path
assert sys.argv[1:4] == ['__opencli_shim','tripo-studio','workspace-inspect']
assert '--pin' in sys.argv and '--module' in sys.argv
assert not any('TOKEN' in name or 'KEY' in name for name in os.environ)
count=Path('workspace-inspect-count.txt')
count.write_text(str(int(count.read_text())+1) if count.exists() else '1')
print(json.dumps([{{'result':{{'status':'prerequisite_missing','quoted_credits':None,'quote_known':False,'paid_submitted':False}}}}]))
''')
    program.chmod(0o700)
    bind_cli(router.state, 'opencliapp', str(program))
    router.vault.get = lambda *args: pytest.fail('No credential read')
    inputs = {'module':'smart_uv','asset_id':'11111111-2222-3333-4444-555555555555'}
    first = router.run(tool['id'], inputs, workspace, request_key='inspect-once', grants=['execute_code'])
    second = router.run(tool['id'], inputs, workspace, request_key='inspect-once', grants=['execute_code'])
    assert first['id'] == second['id'] and first['status'] == 'completed'
    assert first['data']['result'][0]['result']['quoted_credits'] is None
    assert (workspace/'workspace-inspect-count.txt').read_text() == '1'
