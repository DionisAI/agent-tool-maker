"""Regressions for the PR #3 owner-side grant approval race.

Use deterministic interleavings at the same production function boundaries,
not sleeps. No vendor call, process launch or credential disclosure is needed.
"""
from pathlib import Path

import pytest

from agent_tool_maker import broker
from agent_tool_maker.errors import RouterError
from agent_tool_maker.multidevice_web import mutate


def preview(router, workspace, tmp_path):
    user_home = tmp_path / 'user'
    body = {
        'agent': 'claude', 'tools': ['ffmpeg.probe'],
        'workspace': str(workspace), 'ttl_hours': 24,
    }
    plan = mutate(router, '/api/access/grant', body, user_home=user_home)
    return user_home, body, plan


@pytest.mark.parametrize('setting,value', [
    ('cli:ffprobe', '/different/unreviewed-program'),
    ('cli_hash:ffprobe', 'b' * 64),
])
def test_drift_between_web_approval_and_grant_creation_is_rejected(
        router, workspace, tmp_path, monkeypatch, setting, value):
    user_home, body, plan = preview(router, workspace, tmp_path)
    original = broker.grant

    def interleaved(*args, **kwargs):
        if kwargs.get('apply'):
            # Equivalent to another owner process writing after the old Web
            # digest check but before the separate grant(..., apply=True).
            router.state.set_setting(setting, value)
        return original(*args, **kwargs)

    monkeypatch.setattr(broker, 'grant', interleaved)
    with pytest.raises(RouterError) as exc:
        mutate(router, '/api/access/grant', {
            **body, 'apply': True, 'approved_sha256': plan['approval_sha256'],
        }, user_home=user_home)
    assert exc.value.code == 'plan_changed'
    assert broker.list_grants(router.state)['grants'] == []
    assert not Path(plan['profile']).exists()


def test_apply_captures_configuration_once(router, workspace, tmp_path, monkeypatch):
    user_home, body, plan = preview(router, workspace, tmp_path)
    calls = []
    original = broker._tool_pin

    def counted(*args):
        calls.append(args[1])
        return original(*args)

    monkeypatch.setattr(broker, '_tool_pin', counted)
    result = mutate(router, '/api/access/grant', {
        **body, 'apply': True, 'approved_sha256': plan['approval_sha256'],
    }, user_home=user_home)
    assert result['applied'] is True
    assert calls == ['ffmpeg.probe']
    stored = router.state.setting('access:' + result['id'])
    assert stored['pins'] == plan['pins']


def test_change_after_snapshot_never_expands_persisted_authority(
        router, workspace, tmp_path, monkeypatch):
    user_home, body, plan = preview(router, workspace, tmp_path)
    original = router.state.set_setting

    def interleaved(name, value):
        if name.startswith('access:'):
            original('cli:ffprobe', '/different/unreviewed-program')
        return original(name, value)

    monkeypatch.setattr(router.state, 'set_setting', interleaved)
    result = mutate(router, '/api/access/grant', {
        **body, 'apply': True, 'approved_sha256': plan['approval_sha256'],
    }, user_home=user_home)
    stored = router.state.setting('access:' + result['id'])
    assert stored['pins'] == plan['pins']
    # Later drift makes the old approved snapshot unusable, not more powerful.
    with pytest.raises(RouterError) as exc:
        broker.Broker._check_tool(router, stored, 'ffmpeg.probe')
    assert exc.value.code == 'grant_stale'


@pytest.mark.parametrize('approval', ['0' * 64, 'not-a-digest', '\u00e9' * 64])
def test_invalid_approval_has_no_grant_or_profile_side_effects(
        router, workspace, tmp_path, approval):
    user_home, body, plan = preview(router, workspace, tmp_path)
    with pytest.raises(RouterError) as exc:
        mutate(router, '/api/access/grant', {
            **body, 'apply': True, 'approved_sha256': approval,
        }, user_home=user_home)
    assert exc.value.code == 'plan_changed'
    assert broker.list_grants(router.state)['grants'] == []
    assert not Path(plan['profile']).exists()
