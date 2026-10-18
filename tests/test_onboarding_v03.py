"""Real local state/files/processes; all vendor HTTP is simulated, never billed."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, PathDistribution
from importlib.resources import files
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import httpx
import pytest

from agent_tool_maker import onboarding
from agent_tool_maker.cli import main
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.health import doctor, parse_expiry, verification_history, vault_health
from agent_tool_maker.network import Network
from agent_tool_maker.onboarding import export_skill, setup
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault
from agent_tool_maker.verification import verify


def executable(tmp_path, name="atm"):
    p = tmp_path / name
    p.write_text("#!/bin/sh\nexit 0\n")
    p.chmod(0o700)
    return p


def test_setup_preview_does_not_bind_write_skill_or_read_secret(router, tmp_path, monkeypatch):
    exe = executable(tmp_path)
    monkeypatch.setattr(router.vault, "get", lambda *_: pytest.fail("secret read"))
    result = setup(router, agents=["codex", "claude"], executable=str(exe), user_home=tmp_path / "user")
    assert result["network_calls"] == 0 and not result["applied"]
    assert all(p["action"] == "create" and not Path(p["path"]).exists() for p in result["skills"])


def test_setup_repeat_preserves_secrets_and_skill_mtime(router, tmp_path):
    exe = executable(tmp_path)
    with router.state.db() as db:
        before = [tuple(x) for x in db.execute("SELECT * FROM secrets")]
    args = dict(agents=["codex", "claude"], executable=str(exe), user_home=tmp_path / "user", apply=True)
    first = setup(router, **args)
    paths = [Path(x["path"]) for x in first["skills"]]
    mtimes = [x.stat().st_mtime_ns for x in paths]
    second = setup(router, **args)
    assert [x["action"] for x in second["skills"]] == ["unchanged", "unchanged"]
    assert mtimes == [x.stat().st_mtime_ns for x in paths]
    with router.state.db() as db:
        assert before == [tuple(x) for x in db.execute("SELECT * FROM secrets")]
    assert str(router.state.home) in paths[0].read_text()
    assert str(exe) in paths[0].read_text()
    assert all(x["state"] == "registered_not_host_verified" for x in doctor(router)["agents"])


def test_setup_conflict_preflights_every_selected_change(router, tmp_path, monkeypatch):
    exe = executable(tmp_path)
    program = executable(tmp_path, "ffprobe")
    monkeypatch.setattr(shutil, "which", lambda name: str(program))
    root = tmp_path / "user"
    existing = root / ".claude/skills/agent-tool-maker/SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("manual user instructions")
    with pytest.raises(RouterError, match="No selected"):
        setup(router, agents=["codex", "claude"], cli_names=["ffprobe"], executable=str(exe), user_home=root, apply=True)
    assert not (root / ".agents").exists()
    assert router.state.setting("cli:ffprobe") is None
    assert existing.read_text() == "manual user instructions"


def test_setup_replacement_backs_up_user_skill(router, tmp_path):
    exe = executable(tmp_path)
    args = dict(agents=["codex"], executable=str(exe), user_home=tmp_path / "user", apply=True)
    original = setup(router, **args)
    target = Path(original["skills"][0]["path"])
    target.write_text("custom instructions")
    changed = setup(router, replace_skills=True, **args)
    assert Path(changed["skills"][0]["backup"]).read_text() == "custom instructions"


def test_setup_changed_binary_is_not_silently_rebound(router, tmp_path):
    path = executable(tmp_path, "ffprobe")
    bind_cli(router.state, "ffprobe", str(path))
    old_hash = router.state.setting("cli_hash:ffprobe")
    path.write_text("#!/bin/sh\nexit 1\n")
    with pytest.raises(RouterError):
        setup(router, cli_names=["ffprobe"], apply=True)
    assert router.state.setting("cli_hash:ffprobe") == old_hash
    report = doctor(router, tool_ids=["ffmpeg.probe"])
    assert report["tools"][0]["state"] == "executable_changed"
    assert report["local_blockers"] == 1


@pytest.mark.parametrize("change,expected", [("delete", "executable_missing"), ("mode", "executable_not_executable")])
def test_doctor_reports_broken_binary(router, tmp_path, change, expected):
    path = executable(tmp_path, "ffprobe")
    bind_cli(router.state, "ffprobe", str(path))
    path.unlink() if change == "delete" else path.chmod(0o600)
    assert doctor(router, tool_ids=["ffmpeg.probe"])["tools"][0]["state"] == expected


def test_setup_missing_cli_is_a_gap_not_an_install(router, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    report = setup(router, cli_names=["ffprobe"], apply=True)
    assert report["status"] == "needs_dependencies" and report["programs_installed"] == 0
    assert router.state.setting("cli:ffprobe") is None


def test_setup_unsupported_selection_is_rejected(router):
    with pytest.raises(RouterError):
        setup(router, cli_names=["unreviewed-plugin"])
    with pytest.raises(RouterError):
        setup(router, agents=["unknown-client"])


def test_registration_rejects_symlink_parent(router, tmp_path):
    user = tmp_path / "user"
    user.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (user / ".agents").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(RouterError):
        setup(router, agents=["codex"], executable=str(executable(tmp_path)), user_home=user, apply=True)
    assert list(elsewhere.iterdir()) == []


def test_claude_custom_config_root(router, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "custom claude"))
    result = setup(router, agents=["claude"], executable=str(executable(tmp_path)), apply=True)
    assert Path(result["skills"][0]["path"]).is_relative_to(tmp_path / "custom claude")


def test_export_idempotent_and_conflict(tmp_path):
    first = export_skill(tmp_path / "skills")
    assert export_skill(tmp_path / "skills")["action"] == "unchanged"
    target = Path(first["path"])
    target.write_text("user changes")
    with pytest.raises(RouterError):
        export_skill(tmp_path / "skills")
    assert Path(export_skill(tmp_path / "skills", replace=True)["backup"]).read_text() == "user changes"


ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "docs/, scripts/, examples/ and deploy/ paths in this Skill are relative to it; the installed package does not include them."
UNKNOWN = ("docs/, scripts/, examples/ and deploy/ paths in this Skill refer to a reviewed checkout of this repository, "
           "which the installed package does not include. Ask the owner for its location; do not download another copy.")
NO_DIST = object()
PACKAGED_SKILL = files("agent_tool_maker.data").joinpath("SKILL.md").read_bytes()


def checkout(root, name="agent-tool-maker-local"):
    (root / "scripts").mkdir(parents=True)
    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.8.0"\n')
    (root / "SKILL.md").write_bytes(PACKAGED_SKILL)
    (root / "scripts/build_tripo_studio.py").write_text("")
    return root


def installed(monkeypatch, tmp_path, direct_url, package_dir=None):
    """Simulated dist-info and module location; nothing is installed."""
    dist = tmp_path / "site/agent_tool_maker_local-0.8.0.dist-info"
    dist.mkdir(parents=True)
    if direct_url not in (None, NO_DIST):
        (dist / "direct_url.json").write_text(direct_url if isinstance(direct_url, str) else json.dumps(direct_url))
    def distribution(name):
        assert name == "agent-tool-maker-local"
        if direct_url is NO_DIST:
            raise PackageNotFoundError(name)
        return PathDistribution(dist)
    monkeypatch.setattr(onboarding, "distribution", distribution)
    monkeypatch.setattr(onboarding, "PACKAGE_DIR", package_dir or tmp_path / "site/agent_tool_maker")


def runtime_block(tmp_path):
    text = onboarding.render_skill(executable(tmp_path), tmp_path / "state").decode()
    assert text.startswith(ROOT.joinpath("SKILL.md").read_text())
    return text.split("\n## Registered local runtime — ATM ", 1)[1]


@pytest.mark.parametrize("dir_info", [{}, {"editable": True}])
def test_full_skill_names_pep610_directory_checkout(monkeypatch, tmp_path, dir_info):
    root = checkout(tmp_path / "reviewed atm")
    installed(monkeypatch, tmp_path, {"url": root.as_uri(), "dir_info": dir_info})
    block = runtime_block(tmp_path)
    assert f"\n\nSource checkout: `{root.resolve()}`. {RELATIVE}\n\nThe paths are local to this OS user." in block
    assert UNKNOWN not in block
    scoped = onboarding.render_skill(executable(tmp_path), tmp_path / "state", client="claude").decode()
    assert "Source checkout" not in scoped and "deploy/" not in scoped and str(root) not in scoped


@pytest.mark.parametrize("direct_url", [
    lambda root: {"url": root.as_uri(), "archive_info": {"hashes": {"sha256": "0" * 64}}},
    lambda root: {"url": root.as_uri(), "vcs_info": {"vcs": "git", "commit_id": "0" * 40}},
    lambda root: {"url": "file://build-host" + root.as_posix(), "dir_info": {}},
    lambda root: {"url": str(root), "dir_info": {}},
    lambda root: {"url": "file:reviewed", "dir_info": {}},
    lambda root: {"dir_info": {}},
    lambda root: [root.as_uri(), "dir_info"],
    lambda root: "{not json",
    lambda root: None,
    lambda root: NO_DIST,
], ids=["archive", "vcs", "remote-host", "not-url", "relative", "no-url", "list", "bad-json", "no-direct-url", "no-distribution"])
def test_full_skill_falls_back_without_local_directory_install(monkeypatch, tmp_path, direct_url):
    root = checkout(tmp_path / "reviewed")
    monkeypatch.chdir(tmp_path)
    installed(monkeypatch, tmp_path, direct_url(root))
    block = runtime_block(tmp_path)
    assert f"\n\n{UNKNOWN}\n\nThe paths are local to this OS user." in block
    assert "Source checkout" not in block and str(root) not in block


@pytest.mark.parametrize("change", ["other-project", "no-skill", "no-factory", "no-pyproject", "bad-pyproject", "no-project-table", "absent"])
def test_full_skill_rejects_non_atm_directory(monkeypatch, tmp_path, change):
    root = checkout(tmp_path / "other", "other-project" if change == "other-project" else "agent-tool-maker-local")
    {"no-skill": lambda: (root / "SKILL.md").unlink(),
     "no-factory": lambda: (root / "scripts/build_tripo_studio.py").unlink(),
     "no-pyproject": lambda: (root / "pyproject.toml").unlink(),
     "bad-pyproject": lambda: (root / "pyproject.toml").write_text("[project\n"),
     "no-project-table": lambda: (root / "pyproject.toml").write_text('name = "agent-tool-maker-local"\n'),
     "absent": lambda: shutil.rmtree(root)}.get(change, lambda: None)()
    installed(monkeypatch, tmp_path, {"url": root.as_uri(), "dir_info": {}})
    block = runtime_block(tmp_path)
    assert UNKNOWN in block and "Source checkout" not in block


@pytest.mark.parametrize("name", ["bad\nrepo", "bad\rrepo"])
@pytest.mark.parametrize("where", ["direct-url", "in-source"])
def test_full_skill_control_character_checkout_falls_back(monkeypatch, tmp_path, name, where):
    root = checkout(tmp_path / name)
    if where == "direct-url":
        installed(monkeypatch, tmp_path, {"url": root.as_uri(), "dir_info": {}})
    else:
        installed(monkeypatch, tmp_path, NO_DIST, root / "src/agent_tool_maker")
    block = runtime_block(tmp_path)
    assert UNKNOWN in block and "Source checkout" not in block and name not in block


def test_full_skill_prefers_the_imported_src_checkout_over_pep610(monkeypatch, tmp_path):
    # data/SKILL.md and the code are loaded from the imported tree, so it names that tree.
    recorded = checkout(tmp_path / "recorded")
    imported = checkout(tmp_path / "imported")
    installed(monkeypatch, tmp_path, {"url": recorded.as_uri(), "dir_info": {"editable": True}}, imported / "src/agent_tool_maker")
    block = runtime_block(tmp_path)
    assert f"Source checkout: `{imported.resolve()}`." in block and str(recorded) not in block


def test_full_skill_requires_this_revision_of_the_skill(monkeypatch, tmp_path):
    root = checkout(tmp_path / "reviewed")
    (root / "SKILL.md").write_bytes(PACKAGED_SKILL + b"\nedited after install\n")
    installed(monkeypatch, tmp_path, {"url": root.as_uri(), "dir_info": {}})
    assert UNKNOWN in runtime_block(tmp_path)


@pytest.mark.parametrize("name", ["tick`repo", "sep\u2028repo", "tab\trepo", "ff\x0crepo"])
def test_full_skill_never_renders_markdown_breaking_paths(monkeypatch, tmp_path, name):
    root = checkout(tmp_path / name)
    installed(monkeypatch, tmp_path, {"url": root.as_uri(), "dir_info": {}})
    block = runtime_block(tmp_path)
    assert UNKNOWN in block and "Source checkout" not in block and name not in block


def test_full_skill_ignores_non_regular_pyproject(monkeypatch, tmp_path):
    root = checkout(tmp_path / "reviewed")
    (root / "pyproject.toml").unlink()
    os.mkfifo(root / "pyproject.toml")  # a FIFO must not block setup
    installed(monkeypatch, tmp_path, {"url": root.as_uri(), "dir_info": {}})
    assert UNKNOWN in runtime_block(tmp_path)


def test_full_skill_nul_url_falls_back(monkeypatch, tmp_path):
    root = checkout(tmp_path / "reviewed")
    installed(monkeypatch, tmp_path, {"url": root.as_uri() + "%00", "dir_info": {}})
    assert UNKNOWN in runtime_block(tmp_path)


def test_full_skill_names_in_source_checkout(monkeypatch, tmp_path):
    root = checkout(tmp_path / "checkout")
    installed(monkeypatch, tmp_path, NO_DIST, root / "src/agent_tool_maker")
    assert f"Source checkout: `{root.resolve()}`. {RELATIVE}" in runtime_block(tmp_path)
    monkeypatch.setattr(onboarding, "PACKAGE_DIR", root / "lib/agent_tool_maker")
    assert UNKNOWN in runtime_block(tmp_path)
    gone = checkout(tmp_path / "moved")
    installed(monkeypatch, tmp_path / "again", {"url": gone.as_uri(), "dir_info": {}}, root / "src/agent_tool_maker")
    shutil.rmtree(gone)
    assert f"Source checkout: `{root.resolve()}`. {RELATIVE}" in runtime_block(tmp_path)


def test_setup_installs_skill_naming_this_editable_checkout(router, tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    # Uses the real PEP 610 record written for the contract environment's `pip install -e .`.
    args = dict(agents=["claude", "codex"], executable=str(executable(tmp_path)), user_home=tmp_path / "user", apply=True)
    for item in setup(router, **args)["skills"]:
        text = Path(item["path"]).read_text()
        assert f"Source checkout: `{ROOT}`. {RELATIVE}" in text and UNKNOWN not in text
    assert all(x["action"] == "unchanged" for x in setup(router, **args)["skills"])
    assert onboarding.source_checkout() == ROOT


def test_doctor_headless_locked_vault_does_not_prompt(router, monkeypatch):
    router.vault = Vault(router.state)
    for name in ("ATM_VAULT_PASSWORD", "ATR_VAULT_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("agent_tool_maker.vault.prompt_secret", lambda *_: pytest.fail("unexpected prompt"))
    report = doctor(router, tool_ids=["elevenlabs.tts"])
    assert report["vault_health"]["state"] == "needs_unlock"
    assert report["tools"][0]["state"] == "needs_unlock"
    assert report["network_calls"] == 0


def test_check_unlock_distinguishes_wrong_password(router):
    router.vault = Vault(router.state, password="wrong-but-long-password")
    assert doctor(router, tool_ids=["elevenlabs.tts"])["vault_health"]["state"] == "unlock_not_checked"
    assert doctor(router, tool_ids=["elevenlabs.tts"], check_unlock=True)["vault_health"]["state"] == "vault_locked"


def test_expiry_and_rotation_preserve_other_connections(router):
    other = router.vault.get("fal")
    router.vault.put("elevenlabs", "expired-fixture", expires_at=time.time() - 60)
    assert doctor(router, tool_ids=["elevenlabs.tts"])["tools"][0]["state"] == "credential_expired"
    router.vault.put("elevenlabs", "new-fixture")
    assert doctor(router, tool_ids=["elevenlabs.tts"])["tools"][0]["state"] == "configured_not_verified"
    assert router.vault.get("fal") == other


@pytest.mark.parametrize("value", ["2026-10-01", "no-date", "2026-10-01T10:00:00", "infinity"])
def test_bad_expiry_rejected(value):
    with pytest.raises(RouterError):
        parse_expiry(value)


def test_expiry_timezone_parsed():
    assert parse_expiry("2026-10-01T00:00:00Z") == parse_expiry("2026-10-01T08:00:00+08:00")


def test_repeated_connect_does_not_prompt_or_replace(router, capsys, monkeypatch):
    monkeypatch.setattr("agent_tool_maker.cli.prompt_secret", lambda *_: pytest.fail("prompt"))
    assert main(["--home", str(router.state.home), "connect", "elevenlabs"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "already_configured"
    assert router.vault.get("elevenlabs") == "FAKE_elevenlabs"


def test_verify_preview_and_unsupported_read_nothing(router, monkeypatch):
    monkeypatch.setattr(router.vault, "get", lambda *_: pytest.fail("secret"))
    monkeypatch.setattr(router.net, "request", lambda *_a, **_kw: pytest.fail("network"))
    assert verify(router, "elevenlabs")["status"] == "planned"
    assert verify(router, "fal", allow_network=True)["status"] == "unsupported_probe"


@pytest.mark.parametrize("provider,url,header,prefix,payload", [
    ("elevenlabs", "https://api.elevenlabs.io/v1/user", "xi-api-key", "", {"user_id": "private-user", "first_name": "DO_NOT_PUBLISH"}),
    ("tripo", "https://openapi.tripo3d.ai/v3/account/balance", "Authorization", "Bearer ", {"code": 0, "data": {"balance": 9999, "frozen": 0}}),
    ("cloudflare", "https://api.cloudflare.com/client/v4/user/tokens/verify", "Authorization", "Bearer ", {"success": True, "result": {"status": "active"}}),
    ("github", "https://api.github.com/user", "Authorization", "Bearer ", {"login": "private-user"}),
])
def test_probes_use_independent_exact_protocol_and_keep_no_body(router, provider, url, header, prefix, payload):
    router.vault.put(provider, "fixture-secret")
    seen = []
    def respond(req):
        assert req.method == "GET" and str(req.url) == url
        assert req.headers[header] == prefix + "fixture-secret"
        assert req.content == b""
        seen.append(True)
        return httpx.Response(200, json=payload)
    router.net.close()
    router.net = Network(httpx.MockTransport(respond))
    result = verify(router, provider, allow_network=True)
    assert result["status"] == "probe_passed" and len(seen) == 1
    serialized = json.dumps(result) + json.dumps(router.state.setting("verification:" + provider))
    for value in ["fixture-secret", "private-user", "DO_NOT_PUBLISH", "9999"]:
        assert value not in serialized


@pytest.mark.parametrize("status,expected", [(401, "auth_or_scope_rejected"), (403, "auth_or_scope_rejected"), (429, "rate_limited"), (503, "service_unavailable"), (302, "upstream_http")])
def test_probe_failures_no_retries_or_body_leaks(router, status, expected):
    seen = []
    def respond(req):
        seen.append(str(req.url))
        return httpx.Response(status, headers={"location": "https://evil.example"}, text="DO_NOT_PUBLISH")
    router.net.close()
    router.net = Network(httpx.MockTransport(respond))
    result = verify(router, "elevenlabs", allow_network=True)
    assert result["status"] == expected and len(seen) == 1
    assert "DO_NOT_PUBLISH" not in json.dumps(result)


def test_probe_http200_is_not_always_success(router):
    router.net.close()
    router.net = Network(httpx.MockTransport(lambda req: httpx.Response(200, json={"error": "not authenticated"})))
    assert verify(router, "tripo", allow_network=True)["status"] == "unexpected_or_rejected_response"


def test_cached_probe_stale_after_rotation(router):
    router.net.close()
    router.net = Network(httpx.MockTransport(lambda req: httpx.Response(200, json={"user_id": "fixture"})))
    verify(router, "elevenlabs", allow_network=True)
    assert verification_history(router.state)[0]["current_status"] == "historical_only"
    router.vault.put("elevenlabs", "rotated-fixture")
    assert verification_history(router.state)[0]["current_status"] == "stale_credential"


def test_verify_missing_or_expired_credentials_never_call(router, monkeypatch):
    monkeypatch.setattr(router.net, "request", lambda *_a, **_kw: pytest.fail("network"))
    assert verify(router, "github", allow_network=True)["status"] == "missing_credential"
    router.vault.put("tripo", "expired", expires_at=1)
    assert verify(router, "tripo", allow_network=True)["status"] == "credential_expired"


@pytest.mark.integration
def test_two_fresh_processes_projects_reuse_binding(tmp_path):
    binary = shutil.which("ffprobe")
    if not binary:
        pytest.skip("ffprobe required")
    user = tmp_path / "user"
    user.mkdir()
    env = {**os.environ, "HOME": str(user)}
    for name in ["ATM_HOME", "ATR_HOME", "ATM_VAULT_PASSWORD", "ATR_VAULT_PASSWORD", "FAL_KEY"]:
        env.pop(name, None)
    home = tmp_path / "persistent"
    prefix = [sys.executable, "-m", "agent_tool_maker", "--home", str(home)]
    def call(args, cwd):
        result = subprocess.run(prefix + args, cwd=cwd, env=env, text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir(); project_b.mkdir()
    call(["cli", "bind", "ffprobe", binary], project_a)
    for project in [project_a, project_b]:
        shutil.copyfile(Path(__file__).parent / "fixtures/tone.wav", project / "tone.wav")
        (project / "input.json").write_text('{"path":"tone.wav"}')
        result = call(["run", "ffmpeg.probe", "--input", "input.json", "--workspace", str(project)], project)
        assert result["status"] == "completed"
    assert len(call(["jobs", "list"], project_b)["jobs"]) == 2
    assert not (project_a / "state.sqlite3").exists()
    assert not (project_b / "state.sqlite3").exists()


def test_cli_own_login_not_misdiagnosed_as_missing_api_key(router, tmp_path):
    path = executable(tmp_path, "wrangler")
    bind_cli(router.state, "wrangler", str(path))
    report = doctor(router, tool_ids=["wrangler.deploy"])
    assert report["tools"][0]["state"] == "configured_not_verified"
    assert report["tools"][0]["cli_authentication"] == "vendor_login_not_verified"


def test_explicit_unlock_uses_mock_native_backend_but_does_not_expose_keys(tmp_path):
    class MockKeyring:
        entries = {}
        def set_password(self, service, account, value):
            self.entries[service, account] = value
        def get_password(self, service, account):
            return self.entries.get((service, account))
    state = State(tmp_path / "native-test")
    backend = MockKeyring()
    original = Vault(state, keyring_backend=backend)
    original.init("keyring")
    original.put("elevenlabs", "fixture-native-secret")
    fresh = Vault(state, keyring_backend=backend)
    assert vault_health(fresh)["state"] == "unlock_not_checked"
    result = vault_health(fresh, check_unlock=True)
    assert result["state"] == "unlocked_in_this_process"
    assert "fixture-native-secret" not in json.dumps(result)
