"""Offline extension contracts and real fake subprocesses; never uses browser login."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.errors import RouterError
from agent_tool_maker.extensions import validate_bundle
from agent_tool_maker.maker import digest, install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tripo_extended_build', ROOT/'scripts/build_tripo_studio.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize('operation', builder.EXTENDED_OPERATIONS)
def test_extended_bundle_matches_factory_and_permissions(operation):
    directory = ROOT/'generated/tripo-studio-delivery-stage-r4'/operation
    result = validate_bundle(directory)
    tool = builder.manifest(operation)
    assert result['sha256'] == digest(tool)
    assert tool['paid'] is (operation in {'retopo', 'rig', 'image_generate'})
    assert 'execute_code' in tool['permissions']
    assert ('external_write' in tool['permissions']) is (operation not in {'asset', 'asset_resolve', 'assets_all'})
    assert '--pin' in tool['command']['argv'] and builder.extended_digest() in tool['command']['argv']
    assert 'credential_env' not in tool['command'] and 'credential_required' not in tool['command']
    if tool['paid'] or operation in {'image_quote', 'export'}:
        assert tool['schema']['properties']['human_confirmed']['const'] is True
        assert '--ledger' in tool['command']['argv']
        assert '--key' in tool['command']['argv']
        assert json.loads((directory/'inputs.example.json').read_text()) == {}
    if operation == 'image_quote':
        assert {'file': 'image'} in tool['command']['argv']
    if operation == 'export':
        assert tool['command']['outputs'] == ['model.glb']
        assert {'output': 'model.glb'} in tool['command']['argv']


@pytest.mark.parametrize('operation', ['retopo', 'rig', 'image_generate'])
def test_paid_operations_require_separate_confirmation(router, workspace, tmp_path, operation):
    tool = builder.manifest(operation)
    path = tmp_path/'tool.json'
    path.write_text(json.dumps(tool))
    install(router.state, router.catalog, path, digest(tool))
    router.catalog = Catalog(router.state)
    inputs = {'request_key': 'fixture-once', 'human_confirmed': True, 'quote_sha256': '1'*64, 'max_credits':40}
    inputs.update({'image_sha256':'2'*64} if operation == 'image_generate' else {'asset_id':'11111111-2222-3333-4444-555555555555'})
    with pytest.raises(RouterError) as denied:
        router.run(tool['id'], inputs, workspace, request_key='fixture-once', grants=['execute_code','external_write'])
    assert denied.value.code == 'paid_confirmation_required'
    assert not (workspace/'.atm/tripo-studio-paid').exists()


def test_export_real_fake_subprocess_delivers_file_without_key_and_reuses_request(router, workspace, tmp_path):
    tool = builder.manifest('export')
    path = tmp_path/'tool.json'
    path.write_text(json.dumps(tool))
    install(router.state, router.catalog, path, digest(tool))
    router.catalog = Catalog(router.state)
    program = tmp_path/'fake-opencliapp'
    program.write_text(f'''#!{sys.executable}
import sys,os,json,struct
from pathlib import Path
assert sys.argv[1:4] == ['__opencli_shim','tripo-studio','export']
assert not any('TOKEN' in k or 'KEY' in k for k in os.environ)
assert '--confirm' in sys.argv and '--quote' in sys.argv and '--pin' in sys.argv
output=Path(sys.argv[sys.argv.index('--output')+1])
payload=json.dumps({{'asset':{{'version':'2.0'}},'meshes':[{{'primitives':[{{'attributes':{{}}}}]}}]}}).encode()
payload=payload+b' '*((-len(payload))%4)
output.write_bytes(b'glTF'+struct.pack('<IIII',2,20+len(payload),len(payload),0x4e4f534a)+payload)
count=Path('fixture-export-count.txt')
count.write_text(str(int(count.read_text())+1) if count.exists() else '1')
print(json.dumps([{{'result':{{'status':'exported','paid_submitted':False}}}}]))
''')
    program.chmod(0o700)
    bind_cli(router.state, 'opencliapp', str(program))
    router.vault.get = lambda *args: pytest.fail('No credential read')
    inputs = {'asset_id':'11111111-2222-3333-4444-555555555555','request_key':'fixture-export','human_confirmed':True,'quote_sha256':'1'*64}
    first = router.run(tool['id'],inputs,workspace,request_key='fixture-export',grants=['execute_code','external_write'])
    second = router.run(tool['id'],inputs,workspace,request_key='fixture-export',grants=['execute_code','external_write'])
    assert first['id'] == second['id'] and first['status'] == 'completed'
    assert (workspace/'fixture-export-count.txt').read_text() == '1'
    assert list((workspace/'.atm').rglob('*.glb'))
