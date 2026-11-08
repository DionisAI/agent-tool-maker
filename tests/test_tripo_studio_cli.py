"""Offline declarative contract and real fake subprocess tests; no Tripo login/calls."""
import importlib.util
import json
import sys
from pathlib import Path
import pytest

from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.errors import RouterError
from agent_tool_maker.extensions import pack, validate_bundle
from agent_tool_maker.maker import digest, install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tripo_build', ROOT / 'scripts/build_tripo_studio.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize('operation', ['account', 'assets', 'quote', 'generate'])
def test_generated_bundle_matches_factory_and_has_no_auth(operation):
    directory = ROOT / 'generated/tripo-studio' / operation
    info = validate_bundle(directory)
    assert info['sha256'] == digest(builder.manifest(operation))
    raw = (directory / 'manifest.json').read_text()
    assert 'credential_env' not in raw and 'credential_required' not in raw
    tool = builder.manifest(operation)
    assert tool['paid'] is (operation == 'generate')
    assert 'execute_code' in tool['permissions']
    if operation in {'quote', 'generate'}:
        assert 'external_write' in tool['permissions']


def test_paid_requires_schema_confirmation_and_explicit_paid_permission(router, workspace, tmp_path):
    tool = builder.manifest('generate')
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(tool))
    install(router.state, router.catalog, path, digest(tool))
    router.catalog = Catalog(router.state)
    data = {'prompt': 'fake fixture cube', 'max_credits': 40, 'quote_sha256': '1'*64,
            'request_key': 'fake-once', 'human_confirmed': True}
    with pytest.raises(RouterError) as denied:
        router.run(tool['id'], data, workspace, request_key='fake-once', grants=['execute_code', 'external_write'])
    assert denied.value.code == 'paid_confirmation_required'
    assert not list((workspace / '.atm').rglob('tripo-studio-paid'))
    with pytest.raises(RouterError) as invalid:
        router.run(tool['id'], {**data, 'human_confirmed': False}, workspace,
                   request_key='different-fake', allow_paid=True, grants=['execute_code', 'external_write'])
    assert invalid.value.code == 'invalid_input'


def test_readonly_real_fake_cli_no_key_and_request_key_reuse(router, workspace, tmp_path):
    tool = builder.manifest('account')
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(tool))
    install(router.state, router.catalog, path, digest(tool))
    router.catalog = Catalog(router.state)
    cli = tmp_path / 'fake-opencliapp'
    cli.write_text(f'''#!{sys.executable}
import os,sys,json
from pathlib import Path
assert sys.argv[1:4] == ['__opencli_shim','tripo-studio','account']
assert '--pin' in sys.argv
assert not any('KEY' in k or 'TOKEN' in k for k in os.environ)
count=Path('fixture-call-count.txt')
count.write_text(str(int(count.read_text())+1) if count.exists() else '1')
print(json.dumps([{{'status':'ready','credits':99,'paid_submitted':False,'secrets_returned':False}}]))
''')
    cli.chmod(0o700)
    bind_cli(router.state, 'opencliapp', str(cli))
    router.vault.get = lambda *a: pytest.fail('No credential read')
    first = router.run(tool['id'], {}, workspace, request_key='readonly-once', grants=['execute_code'])
    second = router.run(tool['id'], {}, workspace, request_key='readonly-once', grants=['execute_code'])
    assert first['status'] == second['status'] == 'completed'
    assert first['id'] == second['id']
    assert (workspace / 'fixture-call-count.txt').read_text() == '1'


def test_pack_failure_preserves_partial_bundle_and_never_removes(tmp_path, monkeypatch):
    import agent_tool_maker.extensions as ex
    real_write = ex.atomic_write
    def fail_lock(path, data):
        if path.name == 'bundle-lock.json':
            raise OSError('fixture disk write failure')
        real_write(path, data)
    monkeypatch.setattr(ex, 'atomic_write', fail_lock)
    directory = tmp_path / 'partial'
    with pytest.raises(OSError):
        pack(builder.manifest('account'), directory)
    assert (directory / 'tool.py').is_file()
    with pytest.raises(Exception):
        validate_bundle(directory)
