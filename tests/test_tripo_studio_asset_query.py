"""Isolated definitions and real fake subprocesses; no browser login or vault reads."""
import importlib.util
import json
from pathlib import Path
import pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.extensions import validate_bundle
from agent_tool_maker.maker import digest, install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('query_builder', ROOT/'scripts/build_tripo_studio.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize('operation', builder.QUERY_OPERATIONS)
def test_query_bundle_permissions_and_independent_source_pin(operation):
    tool = builder.manifest(operation)
    assert validate_bundle(ROOT/'generated/tripo-studio-asset-query'/operation)['sha256'] == digest(tool)
    assert tool['paid'] is False
    assert tool['permissions'] == ['execute_code']
    assert builder.query_digest() in tool['command']['argv']
    assert tool['command']['timeout'] == 900
    assert 'credential_env' not in tool['command']
    assert builder.adapter_digest() == 'd34bd8e9a69c55c28c176fb978577bc0390dbdf41d1b96495cc3774ae319fd46'
    # Reviewed sidebar/SPA-source waits; independent query pin stays unchanged.
    assert builder.workspace_digest() == '3b7df85e08edf55de3dc09c777ed771c01fbc0965d13b6db0b20528536909dcc'


@pytest.mark.parametrize('operation', builder.QUERY_OPERATIONS)
def test_query_real_fake_subprocess_without_key_and_stable_request_reuse(router, workspace, tmp_path, operation):
    import sys
    tool = builder.manifest(operation)
    definition = tmp_path/'query.json'
    definition.write_text(json.dumps(tool))
    install(router.state, router.catalog, definition, digest(tool))
    router.catalog = Catalog(router.state)
    program = tmp_path/'fake-opencliapp'
    command = operation.replace('_', '-')
    program.write_text(f'''#!{sys.executable}
import sys,os,json
from pathlib import Path
assert sys.argv[1:4] == ['__opencli_shim','tripo-studio','{command}']
assert '--pin' in sys.argv
assert not any('TOKEN' in name or 'KEY' in name for name in os.environ)
count=Path('query-count.txt')
count.write_text(str(int(count.read_text())+1) if count.exists() else '1')
print(json.dumps([{{'result':{{'status':'partial','all_assets':False,'paid_submitted':False}}}}]))
''')
    program.chmod(0o700)
    bind_cli(router.state, 'opencliapp', str(program))
    router.vault.get = lambda *args: pytest.fail('No credential read')
    inputs = {'category':'Image','ownership':'Image Assets','filter':'All','limit':100,'max_pages':5} if operation == 'assets_query' else {
        'card_id':'image:11111111-2222-3333-4444-555555555555:0','view_index':0}
    first = router.run(tool['id'], inputs, workspace, request_key='query-once', grants=['execute_code'])
    second = router.run(tool['id'], inputs, workspace, request_key='query-once', grants=['execute_code'])
    assert first['id'] == second['id'] and first['status'] == 'completed'
    assert first['data']['result'][0]['result']['all_assets'] is False
    assert (workspace/'query-count.txt').read_text() == '1'


def test_builder_fresh_process_uses_reviewed_repository_factory_without_pythonpath(tmp_path):
    import os
    import subprocess
    import sys
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    result = subprocess.run([sys.executable, str(ROOT/'scripts/build_tripo_studio.py'), '--stage', 'asset-query',
        '--out', str(tmp_path/'new-bundles')], env=env, capture_output=True, text=True, check=True)
    receipt = json.loads(result.stdout)
    assert receipt['installed'] is False and receipt['provider_calls'] == 0
    assert receipt['query_adapter_sha256'] == builder.query_digest()
    assert len(receipt['bundles']) == 2
    for operation in builder.QUERY_OPERATIONS:
        assert validate_bundle(tmp_path/'new-bundles'/operation)['sha256'] == digest(builder.manifest(operation))
