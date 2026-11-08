"""Subscription extension contract; fake CLI subprocesses, no vendor/account access."""
import json
from pathlib import Path
import sys

import httpx
import pytest

from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.maker import digest, install, validate_manifest
from agent_tool_maker.network import Network

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = ROOT / "examples/extensions"
NAMES = ("account", "models", "model", "cost")


def manifest(name):
    return json.loads((EXTENSIONS / f"higgsfield-subscription-{name}.json").read_text())


@pytest.fixture
def subscription_router(tmp_path, monkeypatch):
    def unexpected_http(request):
        pytest.fail("Subscription adapter contacted the ATM API transport")

    router = Router(tmp_path / "state", network=Network(httpx.MockTransport(unexpected_http)))
    monkeypatch.setattr(router.vault, "get", lambda *_: pytest.fail("API credential read"))
    monkeypatch.setattr(router.vault, "unlock", lambda *_: pytest.fail("Vault unlock"))
    for name in NAMES:
        tool = validate_manifest(manifest(name), router.catalog)
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(tool))
        install(router.state, router.catalog, path, digest(tool))
        router.catalog = Catalog(router.state)
    yield router
    router.close()


def fake_cli(tmp_path, router, *, failure=False):
    path = tmp_path / "higgsfield-fixture"
    path.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
assert "HOME" in os.environ
assert not any(k in os.environ for k in ("ATM_VAULT_PASSWORD", "HIGGSFIELD_API_KEY", "UNRELATED_SECRET"))
args = sys.argv[1:]
assert args[:2] in (["account", "status"], ["model", "list"], ["model", "get"], ["generate", "cost"])
assert args[-1] == "--json"
assert "--image" not in args and "create" not in args and "--video" not in args
with Path("calls.jsonl").open("a") as calls:
    calls.write(json.dumps(args) + "\\n")
if {failure!r}:
    print("FAKE_AUTH_SECRET", file=sys.stderr)
    sys.exit(4)
print(json.dumps({{"argv": args, "credits": 2}}))
''')
    path.chmod(0o700)
    bind_cli(router.state, "higgsfield", str(path))
    return path


@pytest.mark.parametrize("name", NAMES)
def test_reviewed_read_only_contract(name):
    tool = validate_manifest(manifest(name))
    assert tool["paid"] is False
    assert tool["permissions"] == ["execute_code"]
    assert "credential" not in tool
    assert "credential_env" not in tool["command"]
    assert not tool["command"].get("credential_required")
    assert tool["schema"]["additionalProperties"] is False
    assert tool["command"]["output"] == "json"


@pytest.mark.parametrize("name,inputs,expected", [
    ("account", {}, ["account", "status", "--json"]),
    ("models", {}, ["model", "list", "--json"]),
    ("model", {"model": "nano_banana_2"}, ["model", "get", "nano_banana_2", "--json"]),
    ("cost", {"model": "nano_banana_2", "prompt": "blue circle; $(echo fixture)"},
     ["generate", "cost", "nano_banana_2", "--prompt", "blue circle; $(echo fixture)", "--json"]),
])
def test_fresh_cli_runs_without_key_or_unlock(subscription_router, tmp_path, workspace,
                                             monkeypatch, name, inputs, expected):
    fake_cli(tmp_path, subscription_router)
    for key in ("ATM_VAULT_PASSWORD", "HIGGSFIELD_API_KEY", "UNRELATED_SECRET"):
        monkeypatch.setenv(key, "FAKE-should-not-forward")
    assert subscription_router.state.secret_names() == []
    kwargs = {"request_key": "readonly-once", "grants": ["execute_code"]}
    first = subscription_router.run(f"higgsfield.subscription.{name}", inputs, workspace, **kwargs)
    assert first["status"] == "completed", first
    assert first["data"]["result"]["argv"] == expected
    second = subscription_router.run(f"higgsfield.subscription.{name}", inputs, workspace, **kwargs)
    assert second["id"] == first["id"]
    assert (workspace / "calls.jsonl").read_text().splitlines() == [json.dumps(expected)]


def test_execution_permission_still_required(subscription_router, tmp_path, workspace):
    fake_cli(tmp_path, subscription_router)
    with pytest.raises(RouterError) as error:
        subscription_router.run("higgsfield.subscription.account", {}, workspace)
    assert error.value.code == "permission_required"
    assert not (workspace / "calls.jsonl").exists()


@pytest.mark.parametrize("inputs", [
    {"model": "--help", "prompt": "blue circle"},
    {"model": "nano_banana_2", "prompt": "--image=private.png"},
    {"model": "nano_banana_2", "prompt": "line one\nline two"},
    {"model": "nano_banana_2", "prompt": "blue circle", "image": "private.png"},
    {"model": "nano_banana_2", "prompt": "blue circle", "argv": ["generate", "create"]},
])
def test_cost_rejects_extra_flags_media_and_control_lines(subscription_router, tmp_path, workspace, inputs):
    fake_cli(tmp_path, subscription_router)
    with pytest.raises(RouterError) as error:
        subscription_router.run("higgsfield.subscription.cost", inputs, workspace, grants=["execute_code"])
    assert error.value.code == "invalid_input"
    assert not (workspace / "calls.jsonl").exists()


def test_nonzero_login_failure_is_not_success_or_auto_retry(subscription_router, tmp_path, workspace):
    fake_cli(tmp_path, subscription_router, failure=True)
    kwargs = {"request_key": "missing-login", "grants": ["execute_code"]}
    first = subscription_router.run("higgsfield.subscription.account", {}, workspace, **kwargs)
    assert first["status"] == "submission_unknown"
    assert first["data"]["error"]["code"] == "cli_failed"
    assert "FAKE_AUTH_SECRET" not in json.dumps(subscription_router.public_job(first))
    second = subscription_router.run("higgsfield.subscription.account", {}, workspace, **kwargs)
    assert second["id"] == first["id"]
    assert len((workspace / "calls.jsonl").read_text().splitlines()) == 1


def test_changed_binary_requires_review(subscription_router, tmp_path, workspace):
    executable = fake_cli(tmp_path, subscription_router)
    executable.write_text(executable.read_text() + "\n# new fixture build\n")
    job = subscription_router.run("higgsfield.subscription.account", {}, workspace, grants=["execute_code"])
    assert job["status"] == "failed"
    assert job["data"]["error"]["code"] == "executable_changed"
    assert not (workspace / "calls.jsonl").exists()


def test_skill_keeps_subscription_billing_separate():
    skill = (ROOT / "SKILL.md").read_text()
    assert skill == (ROOT / "src/agent_tool_maker/data/SKILL.md").read_text()
    assert "higgsfield.subscription.*" in skill
    assert "separate billing systems" in skill
    assert "ATM lock does not log out the CLI" in skill
    assert "No ATM vault unlock is needed" in skill
