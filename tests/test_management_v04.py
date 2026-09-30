import hashlib
import json
from pathlib import Path

import pytest
from agent_tool_maker import management as mg
from agent_tool_maker.cli import main
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.onboarding import setup


def exe(tmp_path):
    path = tmp_path / 'atm'
    path.write_text('#!/bin/sh\nexit 0\n')
    path.chmod(0o700)
    return str(path)


def test_cli_setup_defaults_to_both_clients(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('HOME', str(tmp_path / 'user'))
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    cmd = ['--home', str(tmp_path / 'state'), 'setup', '--atm-executable', exe(tmp_path)]
    assert main(cmd) == 0
    result = json.loads(capsys.readouterr().out)
    assert [a['agent'] for a in result['skills']] == ['claude','codex']
    assert not (tmp_path / 'user').exists()
    assert main(cmd + ['--apply']) == 0
    capsys.readouterr()
    assert main(cmd + ['--apply']) == 0
    assert all(p['action'] == 'unchanged' for p in json.loads(capsys.readouterr().out)['skills'])


def test_no_agents_mode_never_requires_an_executable(tmp_path, capsys):
    assert main(['--home', str(tmp_path / 'state'), 'setup', '--no-agents']) == 0
    assert json.loads(capsys.readouterr().out)['skills'] == []


def test_default_registration_plan_digest_and_no_network(router, tmp_path, monkeypatch):
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    monkeypatch.setattr(router.vault, 'get', lambda *_: pytest.fail('read secret'))
    kwargs = dict(executable=exe(tmp_path), user_home=tmp_path / 'user')
    plan = mg.setup_plan(router, **kwargs)
    assert [a['agent'] for a in plan['skills']] == ['claude', 'codex']
    with pytest.raises(RouterError, match='plan changed'):
        mg.apply_setup(router, approved_sha256='0' * 64, **kwargs)
    assert not (tmp_path / 'user').exists()
    result = mg.apply_setup(router, approved_sha256=plan['plan_sha256'], **kwargs)
    assert result['applied']
    status = mg.agents(router, user_home=tmp_path / 'user')
    assert all(a['state'] == 'registered_not_host_verified' for a in status['agents'])
    assert all(not a['host_load_verified'] for a in status['agents'])


def test_plan_is_invalidated_when_file_changes(router, tmp_path):
    kwargs = dict(executable=exe(tmp_path), user_home=tmp_path / 'user')
    plan = mg.setup_plan(router, **kwargs)
    target = Path(plan['skills'][0]['path']);target.parent.mkdir(parents=True);target.write_text('user edited')
    with pytest.raises(RouterError):
        mg.apply_setup(router, approved_sha256=plan['plan_sha256'], **kwargs)
    assert target.read_text() == 'user edited'


def test_unregister_backs_up_owned_file_and_preserves_credentials(router, tmp_path):
    setup(router, agents=['codex'], executable=exe(tmp_path), user_home=tmp_path / 'user', apply=True)
    old = router.state.setting('agent:codex');before = router.state.secret_names()
    plan = mg.unregister(router, 'codex');assert Path(old['path']).exists()
    result = mg.unregister(router, 'codex', apply=True)
    assert Path(result['backup']).exists() and not Path(old['path']).exists()
    assert router.state.setting('agent:codex') is None and router.state.secret_names() == before
    assert mg.unregister(router, 'codex', apply=True)['action'] == 'unchanged'


def test_unregister_never_deletes_modified_skill(router, tmp_path):
    setup(router, agents=['codex'], executable=exe(tmp_path), user_home=tmp_path / 'user', apply=True)
    target = Path(router.state.setting('agent:codex')['path']);target.write_text('my custom instructions')
    with pytest.raises(RouterError):mg.unregister(router, 'codex', apply=True)
    assert target.read_text() == 'my custom instructions'


def test_disabled_tool_is_persisted_and_cannot_run_or_route(router, workspace):
    original = len(router.state.jobs())
    assert mg.set_enabled(router,'elevenlabs.tts',False)['applied'] is False
    assert mg.enabled(router.state,'elevenlabs.tts')
    mg.set_enabled(router,'elevenlabs.tts',False,apply=True)
    with RouterContext(router.state.home) as other:
        assert other.readiness(other.catalog.get('elevenlabs.tts')) == 'disabled'
        with pytest.raises(RouterError, match='disabled'):
            other.run('elevenlabs.tts', {'text':'hello','voice_id':'voice'}, workspace, allow_paid=True)
        assert 'elevenlabs.tts' not in [x['tool'] for x in other.route('elevenlabs speech')['candidates']]
        assert len(other.state.jobs()) == original
    with pytest.raises(RouterError):mg.set_enabled(router,'elevenlabs.tts',True,apply=True,expected=True)
    mg.set_enabled(router,'elevenlabs.tts',True,apply=True,expected=False)
    assert mg.enabled(router.state,'elevenlabs.tts')


class RouterContext:
    def __init__(self,home):self.router=Router(home)
    def __enter__(self):return self.router
    def __exit__(self,*_):self.router.close()


def test_disabled_browser_is_not_a_router_fallback(router):
    mg.set_enabled(router,'tripo.web',False,apply=True)
    assert 'tripo.web' not in [x['tool'] for x in router.route('tripo',allow_browser=True,prefer='browser')['candidates']]


def test_ui_job_summary_excludes_prompts_urls_and_payloads(router, workspace):
    job,_=router.state.create_job('example.tool', {'secret':'NEVER-RENDER'},workspace,None)
    router.state.update_job(job['id'],'completed',url='https://secret/?token=NEVER-RENDER',payload={'private':'NEVER-RENDER'},artifacts=[{'path':'NEVER-RENDER'}])
    result=mg.recent_jobs(router)
    assert 'NEVER-RENDER' not in json.dumps(result)
    assert result['jobs'][0]['artifact_count']==1


def test_connections_do_not_read_values_and_repeat_connect_preserves(router, monkeypatch):
    monkeypatch.setattr(router.vault,'get',lambda *_:pytest.fail('read'))
    listing=mg.connections(router)
    assert 'FAKE_' not in json.dumps(listing) and not listing['secrets_returned']
    before=router.state.setting('credential_meta:fal')
    assert mg.connect_value(router,'fal','discarded')['status']=='already_configured'
    assert before==router.state.setting('credential_meta:fal')


@pytest.mark.parametrize('command', [['agents','list'],['cli','list'],['connections','list'],['tools','list','fal']])
def test_cli_management_is_valid_json(tmp_path,capsys,command):
    assert main(['--home',str(tmp_path/'state'),*command])==0
    assert isinstance(json.loads(capsys.readouterr().out),dict)


def test_cli_toggle_preview_and_apply(router,capsys):
    base=['--home',str(router.state.home),'tools','disable','fal.generate']
    assert main(base)==0;assert json.loads(capsys.readouterr().out)['applied'] is False
    assert mg.enabled(router.state,'fal.generate')
    assert main(base+['--apply'])==0;capsys.readouterr()
    assert not mg.enabled(router.state,'fal.generate')


def test_concurrent_compare_and_set_does_not_lose_updates(router):
    from concurrent.futures import ThreadPoolExecutor
    def change(_):
        try:return mg.set_enabled(router,'fal.generate',False,apply=True,expected=True)['action']
        except RouterError as e:return e.code
    with ThreadPoolExecutor(max_workers=6) as pool:
        result=list(pool.map(change,range(6)))
    assert result.count('disable')==1 and result.count('state_changed')==5


def test_disabled_workflow_cannot_resume_new_steps(router,workspace):
    tool={'id':'custom.flow','adapter':'workflow','schema':{'type':'object'}}
    router.catalog.tools['custom.flow']=tool
    job,_=router.state.create_job('custom.flow',{},workspace,None)
    router.state.update_job(job['id'],'running')
    mg.set_enabled(router,'custom.flow',False,apply=True)
    result=router.refresh(job['id'])
    assert result['data']['last_error']['code']=='tool_disabled'


def test_connection_rotation_changes_only_selected_key(router):
    old=router.vault.get('fal')
    mg.connect_value(router,'elevenlabs','rotated-key',replace=True)
    assert router.vault.get('elevenlabs')=='rotated-key' and router.vault.get('fal')==old


def test_agents_register_conflict_has_nonzero_exit(tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('HOME',str(tmp_path/'user'))
    args=['--home',str(tmp_path/'state'),'agents','register','--agent','codex','--atm-executable',exe(tmp_path),'--apply']
    assert main(args)==0
    plan=json.loads(capsys.readouterr().out)
    target=Path(plan['skills'][0]['path']);target.write_text('User customization')
    assert main(args)==2
    assert json.loads(capsys.readouterr().out)['error']['code']=='setup_conflict'
    assert target.read_text()=='User customization'
