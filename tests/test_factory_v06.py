"""Real fake CLI subprocesses test orchestration; not real LLM calls."""
import json
import os
from pathlib import Path
import sys
import pytest
from agent_tool_maker.extensions import new_template
from agent_tool_maker.factory import draft
from agent_tool_maker.maker import read_manifest
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.errors import RouterError


def inputs(tmp_path):
    seed=tmp_path/'seed.json';seed.write_text(json.dumps(new_template('acme.cli','cli')))
    brief=tmp_path/'brief.txt';brief.write_text('Official local fixture: --version prints a version. Do not invent other arguments.')
    return seed,brief


def test_draft_preview_no_cli_network_or_secrets(router,tmp_path):
    s,b=inputs(tmp_path);out=tmp_path/'draft.json'
    router.vault.get=lambda *a:pytest.fail('No vault read permitted')
    plan=draft(router,'claude',s,b,out)
    assert plan['status']=='planned' and not out.exists() and not plan['supplier_secrets_read']


@pytest.mark.parametrize('agent',['claude','codex'])
def test_generator_real_subprocess_has_structured_output_no_supplier_env(router,tmp_path,monkeypatch,agent):
    s,b=inputs(tmp_path);out=tmp_path/'draft.json';cli=tmp_path/agent
    cli.write_text(f'''#!{sys.executable}
import os,sys,json
from pathlib import Path
assert 'ATM_VAULT_PASSWORD' not in os.environ and 'FAL_KEY' not in os.environ
text=sys.stdin.read();assert 'FAKE_never_share_key' not in text
seed=json.loads(text.split('\\nSEED:\\n')[1].split('\\nUNTRUSTED USER-SUPPLIED TASK/DOCS:\\n')[0])
seed['title']='Generated from a test protocol, not an LLM'
output={{'manifest_json':json.dumps(seed)}}
if {agent!r}=='codex':
 assert '--ignore-user-config' in sys.argv and 'read-only' in sys.argv and '--ephemeral' in sys.argv
 assert 'features.shell_tool=false' in sys.argv
 Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(output))
else:
 assert sys.argv[sys.argv.index('--tools')+1]=='' and '--strict-mcp-config' in sys.argv
 print(json.dumps({{'structured_output':output,'is_error':False}}))
''');cli.chmod(0o700)
    bind_cli(router.state,agent,str(cli));monkeypatch.setenv('ATM_VAULT_PASSWORD','FAKE_never_share_key');monkeypatch.setenv('FAL_KEY','FAKE_never_share_key')
    result=draft(router,agent,s,b,out,allow_agent=True)
    assert result['status']=='drafted' and not result['installed'] and not result['live_tested']
    assert read_manifest(out)['title']=='Generated from a test protocol, not an LLM'
    assert 'acme.cli' not in router.catalog.tools
    with pytest.raises(RouterError):draft(router,agent,s,b,out,allow_agent=True)


@pytest.mark.parametrize('body,code',[
 ('print("invalid")','draft_invalid'),
 ('import sys;sys.exit(7)','draft_failed'),
 ('import time;time.sleep(10)','draft_timeout'),
 ('print("{\\\"manifest_json\\\":\\\"{}\\\"}")','bad_manifest'),
])
def test_invalid_generator_never_installs_or_falls_back(router,tmp_path,body,code):
    s,b=inputs(tmp_path);cli=tmp_path/'claude';cli.write_text(f'#!{sys.executable}\n'+body+'\n');cli.chmod(0o700)
    bind_cli(router.state,'claude',str(cli));out=tmp_path/'draft.json'
    # Error-shape cases must not accidentally test interpreter startup speed.
    # Keep the dedicated timeout case at 1s against a 10s sleep; no runtime
    # limit or expected failure code is weakened.
    budget = 1 if code == 'draft_timeout' else 10
    with pytest.raises(RouterError) as e:draft(router,'claude',s,b,out,allow_agent=True,timeout=budget)
    assert e.value.code == code, e.value.code
    assert not out.exists() and 'acme.cli' not in router.catalog.tools


def test_unbound_generator_does_not_install_cli(router,tmp_path):
    s,b=inputs(tmp_path)
    with pytest.raises(RouterError) as e:draft(router,'codex',s,b,tmp_path/'draft.json',allow_agent=True)
    assert e.value.code=='agent_not_bound'


def test_changed_generator_binary_not_executed(router,tmp_path):
    s,b=inputs(tmp_path);cli=tmp_path/'claude';cli.write_text('#!/bin/sh\nexit 0\n');cli.chmod(0o700)
    bind_cli(router.state,'claude',str(cli));cli.write_text('#!/bin/sh\nexit 1\n')
    with pytest.raises(RouterError) as e:draft(router,'claude',s,b,tmp_path/'draft.json',allow_agent=True)
    assert e.value.code=='agent_not_bound'
