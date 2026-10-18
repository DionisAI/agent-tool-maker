"""ATM's own bound child: definite refusals vs. uncertain exits; fake executables and isolated state only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli_adapter import bind_cli, execute_cli
from agent_tool_maker.errors import RouterError
from agent_tool_maker.maker import digest, install
from agent_tool_maker.storage import canonical
from agent_tool_maker.studio_cli import dispatch, manifests

ROOT = Path(__file__).resolve().parents[1]
DOWN = {"code": "runtime_unavailable", "message": "Server browser is not reachable; no operation was replayed.", "outcome_uncertain": False}
GENERATE = {"prompt": "blue cube", "max_credits": 40, "quote_sha256": "a" * 64, "request_key": "paid-once", "human_confirmed": True}


def program(tmp_path, stdout, code=2, name="fixture-atm"):
    executable = tmp_path / name
    calls = tmp_path / (name + ".calls")
    executable.write_text(f"#!{sys.executable}\nimport sys\nopen({str(calls)!r},'a').write('x')\n"
                          f"sys.stdout.buffer.write({stdout!r})\nsys.exit({code})\n")
    executable.chmod(0o700)
    return executable, calls


def payload(value):
    return json.dumps(value, indent=2).encode()


@pytest.fixture
def studio(router, tmp_path):
    """Reviewed tripo.server account/generate definitions installed, so `atm` is a bindable reviewed executable."""
    for tool in manifests(router.state.home):
        if tool["id"] in {"tripo.server.account", "tripo.server.generate"}:
            path = tmp_path / (tool["id"] + ".json")
            path.write_text(canonical(tool))
            install(router.state, router.catalog, path, digest(tool))
    router.catalog = Catalog(router.state)
    def bind(stdout, code=2, name="fixture-atm"):
        executable, calls = program(tmp_path, stdout, code, name)
        bind_cli(router.state, "atm", str(executable))
        return calls
    return bind


def test_atm_definite_refusal_records_failed_with_real_code_and_key_reuse(router, studio, workspace):
    calls = studio(payload({"error": DOWN}))
    job = router.run("tripo.server.account", {}, workspace, request_key="account-down", grants=["execute_code"])
    assert job["status"] == "failed" and job["data"]["error"] == DOWN
    again = router.run("tripo.server.account", {}, workspace, request_key="account-down", grants=["execute_code"])
    assert again["id"] == job["id"] and again["status"] == "failed" and calls.read_text() == "x"
    assert router.refresh(job["id"])["status"] == "failed" and calls.read_text() == "x"


def test_paid_tool_definite_refusal_is_not_a_possibly_submitted_paid_job(router, studio, workspace):
    calls = studio(payload({"error": DOWN}))
    kwargs = {"request_key": "paid-down", "allow_paid": True, "grants": ["execute_code", "external_write"]}
    job = router.run("tripo.server.generate", GENERATE, workspace, **kwargs)
    assert job["status"] == "failed" and job["data"]["error"] == DOWN
    assert job["data"]["paid_granted"] is True and "upstream_may_have_charged" not in job["data"]
    again = router.run("tripo.server.generate", GENERATE, workspace, **kwargs)
    assert again["id"] == job["id"] and again["status"] == "failed" and calls.read_text() == "x"


@pytest.mark.parametrize("code", ["request_missing", "executable_changed", "definition_changed",
                                  "media_dependency_missing", "confirmation_required"])
def test_xyq_native_refusal_codes_are_definite(router, studio, workspace, code):
    studio(payload({"error": {"code": code, "message": "Refused " + "m" * 400, "outcome_uncertain": False, "phase": "source_pin"}}))
    with pytest.raises(RouterError) as error:
        execute_cli(router.state, "atm", ["delivery", "status"], workspace)
    assert error.value.code == code and not error.value.uncertain
    assert str(error.value) == ("Refused " + "m" * 400)[:300]


def test_atm_uncertain_refusal_stays_submission_unknown(router, studio, workspace):
    calls = studio(payload({"error": {"code": "runtime_transport", "message": "Bridge response was interrupted.", "outcome_uncertain": True}}))
    kwargs = {"request_key": "paid-unknown", "allow_paid": True, "grants": ["execute_code", "external_write"]}
    job = router.run("tripo.server.generate", GENERATE, workspace, **kwargs)
    assert job["status"] == "submission_unknown"
    assert job["data"]["error"]["code"] == "cli_failed" and job["data"]["error"]["outcome_uncertain"] is True
    again = router.run("tripo.server.generate", GENERATE, workspace, **kwargs)
    assert again["id"] == job["id"] and calls.read_text() == "x"


REFUSAL = payload({"error": DOWN})


@pytest.mark.parametrize("stdout,code", [
    (payload({"error": {**DOWN, "outcome_uncertain": True}}), 2),
    (payload({"error": {"code": "local_failure", "message": "Local state was invalid."}}), 2),
    (payload({"error": {**DOWN, "outcome_uncertain": 0}}), 2),
    (payload({"error": {**DOWN, "outcome_uncertain": None}}), 2),
    (payload({"error": {**DOWN, "code": "Runtime-Unavailable"}}), 2),
    (payload({"error": {**DOWN, "code": "a" * 65}}), 2),
    (payload({"error": {**DOWN, "code": ""}}), 2),
    (payload({"error": {**DOWN, "code": 7}}), 2),
    (payload({"error": {**DOWN, "message": None}}), 2),
    (payload({"error": {"message": "m", "outcome_uncertain": False}}), 2),
    (payload({"error": "runtime_unavailable"}), 2),
    (payload({"error": DOWN, "result": {"submitted": True}}), 2),
    (payload([{"error": DOWN}]), 2),
    (payload({"status": "failed", "data": {"error": DOWN}}), 2),
    (b"", 2),
    (b"{not json", 2),
    (b'{"error":\xff}', 2),
    (b"[" * 100000, 2),
    (b"[" * 60000, 2),  # under the size cap: exercises the RecursionError guard
    (b'{"error":' * 5000 + b"1" + b"}" * 5000, 2),
    (REFUSAL + b" " * (64 * 1024), 2),
    (REFUSAL + b"\n" + REFUSAL, 2),
    (REFUSAL, 1),
    (REFUSAL, 3),
], ids=lambda v: f"exit{v}" if isinstance(v, int) else f"{len(v)}b-{hashlib.sha256(v).hexdigest()[:8]}")
def test_atm_unknown_shapes_exits_and_oversized_output_stay_uncertain(router, studio, workspace, stdout, code):
    studio(stdout, code)
    with pytest.raises(RouterError) as error:
        execute_cli(router.state, "atm", [], workspace)
    assert error.value.code == "cli_failed" and error.value.uncertain


def test_unpinned_atm_binding_is_not_trusted(router, studio, workspace):
    studio(REFUSAL)
    router.state.set_setting("cli_hash:atm", None)
    with pytest.raises(RouterError) as error:
        execute_cli(router.state, "atm", [], workspace)
    assert error.value.code == "cli_failed" and error.value.uncertain


def test_non_atm_cli_printing_the_same_refusal_stays_cli_failed_uncertain(router, tmp_path, workspace):
    executable, calls = program(tmp_path, REFUSAL, 2, "xyq-fixture")
    bind_cli(router.state, "xyq", str(executable))
    with pytest.raises(RouterError) as error:
        execute_cli(router.state, "xyq", [], workspace)
    assert error.value.code == "cli_failed" and error.value.uncertain and calls.read_text() == "x"


@pytest.mark.parametrize("stdout", [b"{not json", b"[" * 200000], ids=["invalid", "nested"])
def test_exit0_nested_json_is_terminal_like_invalid_json_and_key_reuse(router, studio, workspace, stdout):
    calls = studio(stdout, 0)
    job = router.run("tripo.server.account", {}, workspace, request_key="exit0-deep", grants=["execute_code"])
    assert job["status"] == "submission_unknown" and job["data"]["error"]["code"] == "cli_protocol"
    assert job["data"]["error"]["outcome_uncertain"] is True
    again = router.run("tripo.server.account", {}, workspace, request_key="exit0-deep", grants=["execute_code"])
    assert again["id"] == job["id"] and again["status"] == "submission_unknown" and calls.read_text() == "x"
    assert router.refresh(job["id"])["status"] == "submission_unknown" and calls.read_text() == "x"


def test_exit0_parseable_json_nested_past_the_recursion_limit_is_terminal(router, studio, workspace):
    # 3.11 refuses this depth while parsing (cli_protocol); 3.12+ parses it and redaction then recurses too deep.
    calls = studio(b"[" * 5000 + b"]" * 5000, 0)
    job = router.run("tripo.server.account", {}, workspace, request_key="exit0-parsed", grants=["execute_code"])
    assert job["status"] == "submission_unknown" and job["data"]["error"]["outcome_uncertain"] is True
    assert job["data"]["error"]["code"] in {"cli_protocol", "execution_interrupted"}
    again = router.run("tripo.server.account", {}, workspace, request_key="exit0-parsed", grants=["execute_code"])
    assert again["id"] == job["id"] and calls.read_text() == "x"


@pytest.fixture
def source_atm(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "isolated-home"))
    executable = tmp_path / "source-atm"
    executable.write_text(f"#!{sys.executable}\nimport sys\nsys.path.insert(0,{str(ROOT / 'src')!r})\n"
                          "from agent_tool_maker.cli import main\nraise SystemExit(main())\n")
    executable.chmod(0o700)
    return executable


@pytest.mark.integration
def test_real_source_atm_server_down_is_definite_for_read_and_paid_tools(router, source_atm, workspace):
    preview = dispatch(SimpleNamespace(operation="install", apply=False), router)
    dispatch(SimpleNamespace(operation="install", apply=True, approve=preview["bundle_sha256"], atm_executable=source_atm), router)
    account = router.run("tripo.server.account", {}, workspace, request_key="real-account", grants=["execute_code"])
    assert account["status"] == "failed" and account["data"]["error"]["code"] == "runtime_unavailable"
    assert account["data"]["error"]["outcome_uncertain"] is False
    paid = router.run("tripo.server.generate", GENERATE, workspace, request_key="real-paid", allow_paid=True,
                      grants=["execute_code", "external_write"])
    assert paid["status"] == "failed" and paid["data"]["error"] == account["data"]["error"]


@pytest.mark.integration
def test_real_source_atm_xyq_status_missing_is_definite(router, source_atm, workspace, tmp_path):
    spec = importlib.util.spec_from_file_location("xyq_download_builder", ROOT / "scripts/build_xyq_download.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    tool = builder.manifest("result_download_status")
    path = tmp_path / "status.json"
    path.write_text(canonical(tool))
    install(router.state, router.catalog, path, digest(tool))
    router.catalog = Catalog(router.state)
    bind_cli(router.state, "atm", str(source_atm))
    job = router.run("xyq.web.result_download_status", {"request_key": "never-ran"}, workspace,
                     request_key="status-missing", grants=["execute_code"])
    assert job["status"] == "failed" and job["data"]["error"]["code"] == "request_missing"
    assert job["data"]["error"]["outcome_uncertain"] is False
    assert not (workspace / ".atm" / "xyq-result-downloads").exists()
