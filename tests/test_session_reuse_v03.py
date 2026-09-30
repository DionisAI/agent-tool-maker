"""Fresh-process regression tests from the v0.2 audit, now required to pass.
Fake provider credentials and mocked HTTP only; passphrase unlock is still explicit.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave

import pytest

SECRET = "ATM_AUDIT_FAKE_KEY_NOT_A_REAL_CREDENTIAL"
PASSWORD = "audit-only-long-passphrase-2026"


@pytest.fixture
def session(tmp_path):
    home = tmp_path / "user"
    a = tmp_path / "project-a"
    b = tmp_path / "project-b"
    for path in (home, a, b):
        path.mkdir()
    # A new process gets only a small, explicit environment, not real credentials.
    env = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT", "WINDIR") if key in os.environ}
    env.update(HOME=str(home), USERPROFILE=str(home), PYTHONIOENCODING="utf-8")

    def call(*args, cwd=None, extra=None, data=None):
        child_env = dict(env)
        child_env.update(extra or {})
        result = subprocess.run(
            [sys.executable, "-m", "agent_tool_maker", *args],
            cwd=cwd or a, env=child_env,
            input=json.dumps(data) if data is not None else "",
            text=True, capture_output=True, timeout=40,
        )
        assert SECRET not in result.stdout + result.stderr
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            raise AssertionError(f"CLI returned non-JSON (exit {result.returncode}): {result.stderr[:200]}")
        return result.returncode, payload

    return home, a, b, env, call


def initialize(session):
    home, a, b, env, call = session
    assert call("vault", "init", "--backend", "passphrase", extra={"ATM_VAULT_PASSWORD": PASSWORD})[0] == 0
    assert call("connect", "exa", "--env", "ONE_TIME_TEST_KEY", extra={
        "ATM_VAULT_PASSWORD": PASSWORD, "ONE_TIME_TEST_KEY": SECRET,
    })[0] == 0
    return home / ".local/share/agent-tool-maker"


def test_default_state_is_user_scoped_across_fresh_processes(session):
    home, a, b, env, call = session
    ca, da = call("init", cwd=a)
    cb, db = call("init", cwd=b)
    assert ca == cb == 0
    assert da["home"] == db["home"] == str(home / ".local/share/agent-tool-maker")


def test_encrypted_key_survives_new_process_without_original_key_env(session):
    state_home = initialize(session)
    home, a, b, env, call = session
    code, status = call("vault", "status", cwd=b)
    assert code == 0 and status["credential_names"] == ["exa"]
    assert status["secrets_returned"] is False
    assert SECRET.encode() not in (state_home / "state.sqlite3").read_bytes()
    # Fresh process, same state. The adapter uses the stored key; only the
    # upstream network is replaced. Output never contains the raw key.
    program = '''import os,json
from pathlib import Path
import httpx
from agent_tool_maker.engine import Router
from agent_tool_maker.network import Network
seen=[]
def server(request):
    seen.append(request.headers.get('x-api-key','').startswith('ATM_AUDIT_FAKE_KEY'))
    return httpx.Response(200,json={'results':[]})
r=Router(Path.home()/'.local/share/agent-tool-maker',network=Network(httpx.MockTransport(server)))
j=r.run('exa.search',{'query':'offline audit'},Path.cwd(),allow_paid=True)
assert j['status']=='completed' and seen==[True]
assert 'ONE_TIME_TEST_KEY' not in os.environ
print(json.dumps({'stored_key_used':True,'original_env_absent':True,'status':j['status']}))
r.close()
'''
    result = subprocess.run([sys.executable, "-c", program], cwd=b,
        env={**env, "ATM_VAULT_PASSWORD": PASSWORD}, text=True, capture_output=True, timeout=40)
    assert result.returncode == 0, result.stderr
    assert SECRET not in result.stdout + result.stderr
    assert json.loads(result.stdout)["stored_key_used"]


def test_passphrase_vault_requires_unlock_but_not_key_reentry(session):
    initialize(session)
    home, a, b, env, call = session
    code, result = call("run", "exa.search", "--input", "-", "--allow-paid", cwd=b, data={"query": "offline"})
    assert code == 2 and result["status"] == "failed"
    assert result["data"]["error"]["code"] == "interactive_required"
    assert call("vault", "status", cwd=b)[1]["credential_names"] == ["exa"]


def test_reinitialization_does_not_overwrite_existing_vault(session):
    initialize(session)
    code, data = session[-1]("vault", "init", "--backend", "passphrase", extra={"ATM_VAULT_PASSWORD": PASSWORD})
    assert code == 2 and data["error"]["code"] == "vault_exists"
    assert session[-1]("vault", "status")[1]["credential_names"] == ["exa"]


def test_real_ffprobe_binding_reused_by_two_new_sessions(session):
    probe = shutil.which("ffprobe")
    if not probe:
        pytest.skip("Install FFprobe to run this real executable check.")
    home, a, b, env, call = session
    assert call("cli", "bind", "ffprobe", probe)[0] == 0
    for folder in (a, b):
        with wave.open(str(folder / "tone.wav"), "wb") as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000); f.writeframes(b"\0\0" * 800)
        code, data = call("run", "ffmpeg.probe", "--input", "-", cwd=folder, data={"path": "tone.wav"})
        assert code == 0 and data["status"] == "completed"
        assert data["data"]["verification"] == "ffprobe"
    assert len(call("jobs", "list", cwd=b)[1]["jobs"]) == 2


def test_personal_skill_export_persists_outside_project(session):
    home, a, b, env, call = session
    for target in (home / ".agents/skills", home / ".claude/skills"):
        assert call("skill", "export", "--destination", str(target), cwd=a)[0] == 0
        assert (target / "agent-tool-maker/SKILL.md").is_file()
    assert not (a / "skills").exists() and not (b / "skills").exists()


def test_explicit_different_state_home_is_a_different_configuration(session):
    initialize(session)
    home, a, b, env, call = session
    code, data = call("--home", str(home / "another-vault"), "vault", "status", cwd=b)
    assert code == 0 and data["credential_names"] == [] and data["backend"] is None


def changed_binding(session):
    home, a, b, env, call = session
    executable = home / "test-buffer-cli"
    executable.write_text(f"#!{sys.executable}\nprint('[]')\n")
    executable.chmod(0o700)
    assert call("cli", "bind", "buffer", str(executable))[0] == 0
    executable.write_text(f"#!{sys.executable}\nprint('[1]')\n")
    return call


def test_changed_cli_is_rejected_at_execution(session):
    call = changed_binding(session)
    code, result = call("run", "buffer.channels", "--input", "-", data={})
    assert code == 2
    assert result["data"]["error"]["code"] == "executable_changed"


def test_desired_doctor_detects_changed_binary_before_execution(session):
    call = changed_binding(session)
    code, result = call("doctor")
    states = {row["id"]: row["state"] for row in result["tools"]}
    assert code == 0 and states["buffer.channels"] == "executable_changed"


def test_desired_identical_skill_registration_is_idempotent(session):
    home, a, b, env, call = session
    target = home / ".agents/skills"
    assert call("skill", "export", "--destination", str(target))[0] == 0
    assert call("skill", "export", "--destination", str(target))[0] == 0


def test_desired_headless_preflight_marks_vault_unlock_requirement(session):
    initialize(session)
    code, result = session[-1]("doctor")
    states = {row["id"]: row["state"] for row in result["tools"]}
    assert code == 0 and states["exa.search"] == "needs_unlock"
