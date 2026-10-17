"""Protocol, real local subprocess and isolated Chromium tests; never production login."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
from types import SimpleNamespace
import pytest
from agent_tool_maker.actions import compile_command
from agent_tool_maker.errors import RouterError
from agent_tool_maker.storage import State, canonical
from agent_tool_maker.studio_cli import dispatch, manifests
from agent_tool_maker import studio_runtime as runtime

ROOT = Path(__file__).resolve().parents[1]


def args(operation, **kwargs):
    return SimpleNamespace(operation=operation, **kwargs)


def sample(schema):
    if "const" in schema: return schema["const"]
    if "enum" in schema: return schema["enum"][0]
    if schema.get("type") == "object":
        return {key: sample(schema["properties"][key]) for key in schema.get("required", [])}
    if schema.get("type") == "integer": return max(1, schema.get("minimum", 0))
    if schema.get("type") == "boolean": return False
    pattern = schema.get("pattern", "")
    if "64" in pattern: return "a" * 64
    if "image:" in pattern: return "image:12345678-1234-1234-1234-123456789abc:0"
    if "[a-f0-9]{8}" in pattern: return "12345678-1234-1234-1234-123456789abc"
    if "A-Za-z0-9" in pattern: return "fixture-once"
    return "fixture" if schema.get("minLength", 0) or not pattern else ""


def test_packaged_adapters_are_exact_source_snapshot():
    spec = importlib.util.spec_from_file_location("server_builder", ROOT / "scripts/build_tripo_server.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert runtime.index() == builder.definitions()
    sources = list((ROOT / "examples/opencli/tripo-studio").iterdir())
    assert len(sources) == 20
    for source in sources:
        assert (runtime.DATA / source.name).read_bytes() == source.read_bytes()
    runner = (runtime.DATA / "runner.mjs").read_text()
    names = re.findall(r'^\s*([a-z_]+):\[', runner, re.M) + re.findall(r',([a-z_]+):\[', runner)
    assert set(names) == set(runtime.index())


@pytest.mark.parametrize("operation", sorted(runtime.index()))
def test_server_reuses_exact_schema_permissions_and_fixed_argv(operation, tmp_path):
    original = runtime.index()[operation]
    tool = next(t for t in manifests(tmp_path) if t["id"] == "tripo.server." + operation)
    assert tool["schema"] == original["schema"]
    assert tool["permissions"] == original["permissions"]
    assert tool["paid"] == original["paid"]
    assert tool["executable"] == "atm"
    inputs = {key: sample(value) for key, value in original["schema"]["properties"].items()}
    if "image" in inputs:
        (tmp_path / inputs["image"]).write_bytes(b"fake raster fixture")
    outdir = tmp_path / "artifacts"
    outdir.mkdir()
    argv = compile_command(None, original, inputs, tmp_path, outdir)["argv"][3:]
    runtime.validate_request(operation, argv, tmp_path)
    with pytest.raises(RouterError):
        runtime.validate_request(operation, argv + ["--arbitrary-js", "secret"], tmp_path)
    assert "credential_env" not in tool["command"]


def test_install_review_reuse_and_existing_tools_preserved(router, tmp_path):
    executable = tmp_path / "fixture-atm"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    before = set(router.catalog.tools)
    preview = dispatch(args("install", apply=False), router)
    assert preview["tool_count"] == 31
    with pytest.raises(RouterError, match="exact reviewed"):
        dispatch(args("install", apply=True, approve="wrong", atm_executable=executable), router)
    result = dispatch(args("install", apply=True, approve=preview["bundle_sha256"], atm_executable=executable), router)
    assert result["status"] == "installed"
    again = dispatch(args("install", apply=True, approve=preview["bundle_sha256"], atm_executable=executable), router)
    assert again["status"] == "installed"
    assert before <= set(router.catalog.tools)
    assert len(set(router.catalog.tools) - before) == 31


def test_missing_runtime_explicit_and_profile_symlink_rejected(tmp_path):
    with pytest.raises(RouterError) as missing:
        asyncio.run(runtime.request(tmp_path, {"method": "status"}))
    assert missing.value.code == "runtime_unavailable"
    directory = tmp_path / "symlink"
    directory.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RouterError) as unsafe:
        runtime.studio_dir(directory)
    assert unsafe.value.code == "unsafe_path"


def test_file_upload_and_cdp_are_scoped(tmp_path):
    browser = runtime.BrowserRuntime(tmp_path, SimpleNamespace(pages=[SimpleNamespace(url=runtime.ORIGIN + "/assets")]), "node")
    browser.cdp = SimpleNamespace()
    browser.active = {"workspace": tmp_path / "project"}
    outsider = tmp_path / "outside.png"
    outsider.write_bytes(b"fixture")
    for method, params, code in [("Network.getAllCookies", {}, "unsupported_cdp"),
                                 ("DOM.setFileInputFiles", {"files": [str(outsider)]}, "unsafe_path")]:
        with pytest.raises(RouterError) as error:
            asyncio.run(browser.rpc("cdp", [method, params]))
        assert error.value.code == code
    with pytest.raises(RouterError) as wrong_origin:
        asyncio.run(browser.rpc("goto", ["https://example.com/"]))
    assert wrong_origin.value.code == "origin_mismatch"


def test_runtime_busy_wrong_bundle_and_state_project_overlap(tmp_path):
    home = tmp_path / "state"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    original = runtime.index()["account"]
    argv = compile_command(None, original, {}, project, project)["argv"][3:]
    packet = {"method": "run", "operation": "account", "argv": argv, "workspace": str(project), "bundle": "wrong"}
    browser = runtime.BrowserRuntime(home, SimpleNamespace(pages=[SimpleNamespace(url="about:blank")]), "node")
    with pytest.raises(RouterError) as changed:
        asyncio.run(browser.run(packet))
    assert changed.value.code == "definition_changed"
    with pytest.raises(RouterError) as overlap:
        asyncio.run(browser.run({**packet, "workspace": str(tmp_path)}))
    assert overlap.value.code == "unsafe_workspace"
    async def busy():
        await browser.lock.acquire()
        try:
            await browser.run({**packet, "bundle": runtime.bundle_digest()})
        finally:
            browser.lock.release()
    with pytest.raises(RouterError) as concurrent:
        asyncio.run(busy())
    assert concurrent.value.code == "runtime_busy"


def test_login_viewer_fixed_ttl_loopback_and_preserved_browser(tmp_path, monkeypatch):
    commands = []
    class Process:
        returncode = None
        def terminate(self): self.returncode = 0
        async def wait(self): return self.returncode
    async def spawn(*command, **kwargs):
        commands.append(command)
        return Process()
    async def sleep(_): pass
    class Page:
        url = runtime.ORIGIN + "/assets"
        async def goto(self, *a, **kw): pass
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setattr(shutil, "which", lambda _: "/reviewed/x11vnc")
    authority = tmp_path / "fixture.authority"
    authority.write_bytes(b"synthetic Xauthority")
    browser = runtime.BrowserRuntime(tmp_path, SimpleNamespace(pages=[Page()]), "node", ":99", authority)
    async def probe():
        first = await browser.login(60, 5900)
        second = await browser.login(1800, 5900)
        assert second["reused"] and second["expires_at"] == first["expires_at"]
        await browser.expire_login(object())  # A stale timer cannot close a later entry.
        assert browser.vnc is not None
        expected = browser.vnc
        await browser.expire_login(expected)
        assert browser.vnc is None and browser.context.pages[0] is browser.page
    asyncio.run(probe())
    assert len(commands) == 1
    command = commands[0]
    assert command[command.index("-listen") + 1] == "127.0.0.1" and "-localhost" in command
    assert command[command.index("-auth") + 1] == str(authority)


def test_studio_help_hides_router_only_adapter(capsys):
    from agent_tool_maker.cli import parser
    with pytest.raises(SystemExit):
        parser().parse_args(["studio", "--help"])
    shown = capsys.readouterr().out
    assert "{serve,status,login,login-close,install,run}" in shown
    assert "==SUPPRESS==" not in shown and not re.search(r"^\s+adapter\b", shown, re.M)
    hidden = parser().parse_args(["studio", "adapter", "--bundle", "pin", "account", "--pin", "x"])
    assert hidden.operation == "adapter" and hidden.argv == ["--pin", "x"]


ROUTER_ONLY = sorted(op for op, spec in runtime.index().items() if runtime.router_only(spec))


def router_job(home, operation, project, *, paid_granted=True, request_key="fixture-ticket", inputs=None):
    """The Router's job claim and ticket issue (engine.run -> execute_command) for one server call."""
    original = runtime.index()[operation]
    if inputs is None:
        inputs = {key: sample(value) for key, value in original["schema"]["properties"].items()}
    if "image" in inputs:
        (project / inputs["image"]).write_bytes(b"fake raster fixture")
    tool = next(t for t in manifests(home) if t["id"] == "tripo.server." + operation)
    argv = compile_command(None, tool, inputs, project, project)["argv"]
    state = State(home)
    job, _ = state.create_job(tool["id"], inputs, project, request_key)
    job = state.update_job(job["id"], "submitting", paid_granted=paid_granted)
    return state, job, argv, runtime.issue_ticket(state, job, argv, project).get(runtime.TICKET_ENV)


def test_router_only_operations_are_paid_or_human_confirmed():
    assert ROUTER_ONLY == ["export", "generate", "image_generate", "image_quote", "retopo", "rig", "workspace_submit"]
    assert {op for op, spec in runtime.index().items() if spec["paid"]} <= set(ROUTER_ONLY)
    # Read-only operations keep working without a ticket.
    assert not any(runtime.router_only(spec) for spec in runtime.index().values() if spec["permissions"] == ["execute_code"])


def test_router_ticket_is_single_use_and_bound_to_its_job(tmp_path, monkeypatch):
    home, project, other = tmp_path / "state", tmp_path / "project", tmp_path / "other"
    project.mkdir()
    other.mkdir()
    state, job, argv, ticket = router_job(home, "generate", project)
    pin, rest = argv[5], argv[7:]
    def consume(value, operation="generate", arguments=rest, workspace=project):
        runtime.consume_ticket(home, value, runtime.index()[operation], operation, arguments, workspace, pin)
    job_id, secret = ticket.split(".")
    assert job_id == job["id"] and len(secret) == 64
    record = state.job(job_id)["data"]["studio_ticket"]
    assert secret not in json.dumps(state.job(job_id)) and record["expires_at"] <= runtime.time.time() + runtime.TICKET_TTL
    budget = rest.index("--budget") + 1
    for forged in [{"value": None}, {"value": ""}, {"value": job_id}, {"value": job_id + "." + "0" * 64},
                   {"value": "unknown." + secret}, {"value": ticket, "operation": "rig"},
                   {"value": ticket, "arguments": rest[:budget] + ["9999"] + rest[budget + 1:]},
                   {"value": ticket, "workspace": other}]:
        with pytest.raises(RouterError) as refused:
            consume(**forged)
        assert refused.value.code == "router_ticket_required" and not refused.value.uncertain
    assert "consumed_at" not in state.job(job_id)["data"]["studio_ticket"]
    consume(ticket)
    assert state.job(job_id)["data"]["studio_ticket"]["consumed_at"]
    with pytest.raises(RouterError, match="single-use"):
        consume(ticket)  # Replay of a consumed ticket.
    with state.db() as c:
        assert [r[0] for r in c.execute("SELECT kind FROM events WHERE job_id=?", (job_id,))].count("studio_ticket_consumed") == 1
    # Paid tickets also need the Router's paid grant, a still-submitting job and an unexpired ticket.
    _, _, _, ungranted = router_job(home, "generate", project, paid_granted=False, request_key="no-paid-grant")
    _, finished, _, settled = router_job(home, "generate", project, request_key="already-settled")
    state.update_job(finished["id"], "submission_unknown")
    _, _, _, stale = router_job(home, "generate", project, request_key="expired-ticket")
    for value in (ungranted, settled):
        with pytest.raises(RouterError, match="single-use"):
            consume(value)
    later = runtime.time.time() + runtime.TICKET_TTL + 1
    monkeypatch.setattr(runtime.time, "time", lambda: later)
    with pytest.raises(RouterError, match="single-use"):
        consume(stale)


@pytest.mark.parametrize("operation", ROUTER_ONLY)
def test_server_refuses_router_only_operation_without_ticket_before_spawn(operation, tmp_path, monkeypatch):
    home, project = tmp_path / "state", tmp_path / "project"
    project.mkdir()
    state, job, argv, ticket = router_job(home, operation, project)
    class Spawned(Exception):
        pass
    async def spawn(*command, **kwargs):
        raise Spawned()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    browser = runtime.BrowserRuntime(home, SimpleNamespace(pages=[SimpleNamespace(url="about:blank")]), "node")
    packet = {"method": "run", "operation": operation, "argv": argv[7:], "workspace": str(project), "bundle": runtime.bundle_digest()}
    for forged in (None, job["id"] + "." + "0" * 64):
        with pytest.raises(RouterError) as refused:
            asyncio.run(browser.run({**packet, "ticket": forged}))
        assert refused.value.code == "router_ticket_required" and not refused.value.uncertain
    assert "consumed_at" not in state.job(job["id"])["data"]["studio_ticket"]
    with pytest.raises(Spawned):
        asyncio.run(browser.run({**packet, "ticket": ticket}))  # The Router's ticket reaches the adapter.
    assert state.job(job["id"])["data"]["studio_ticket"]["consumed_at"]


def test_router_passes_ticket_only_after_its_gates(router, tmp_path):
    executable = tmp_path / "fixture-atm"
    executable.write_text('#!/bin/sh\nprintf "%s" "$ATM_STUDIO_TICKET" > "$PWD/received-ticket"\necho "[]"\n')
    executable.chmod(0o700)
    preview = dispatch(args("install", apply=False), router)
    dispatch(args("install", apply=True, approve=preview["bundle_sha256"], atm_executable=executable), router)
    project = tmp_path / "project"
    project.mkdir()
    received = project / "received-ticket"
    inputs = {"prompt": "Synthetic fixture cube", "quote_sha256": "a" * 64, "max_credits": 40,
              "request_key": "router-paid-once", "human_confirmed": True}
    grants = ["execute_code", "external_write"]
    with pytest.raises(RouterError) as unpaid:
        router.run("tripo.server.generate", inputs, project, request_key="router-paid-once", grants=grants)
    assert unpaid.value.code == "paid_confirmation_required" and not received.exists()
    account = router.run("tripo.server.account", {}, project, request_key="router-read", grants=["execute_code"])
    assert account["status"] == "completed" and received.read_text() == "" and "studio_ticket" not in account["data"]
    job = router.run("tripo.server.generate", inputs, project, request_key="router-paid-once", allow_paid=True, grants=grants)
    assert job["status"] == "completed", job
    ticket = received.read_text()
    job_id, secret = ticket.split(".")
    record = job["data"]["studio_ticket"]
    assert job_id == job["id"] and record["tool"] == "tripo.server.generate" and record["workspace"] == str(project.resolve())
    assert record["sha256"] == hashlib.sha256(secret.encode()).hexdigest() and secret not in json.dumps(job)
    tool = router.catalog.get("tripo.server.generate")
    argv = compile_command(None, tool, inputs, project.resolve(), project.resolve())["argv"]
    assert record["argv_sha256"] == hashlib.sha256(canonical(argv[7:]).encode()).hexdigest()
    # Once the Router job settles, the captured ticket cannot be replayed.
    assert State(router.state.home).job(job_id)["status"] == "completed"
    with pytest.raises(RouterError, match="single-use"):
        runtime.consume_ticket(router.state.home, ticket, runtime.index()["generate"], "generate", argv[7:], project.resolve(), argv[5])
    again = router.run("tripo.server.generate", inputs, project, request_key="router-paid-once", allow_paid=True, grants=grants)
    assert again["id"] == job["id"] and received.read_text() == ticket  # Request-key reuse issues no new ticket.


@pytest.mark.browser
@pytest.mark.integration
def test_real_production_serve_entry_and_exclusive_profile(source_atm, tmp_path):
    pytest.importorskip("playwright")
    chromium, node = os.environ.get("ATM_CHROMIUM"), shutil.which("node")
    if not chromium or not node:
        pytest.skip("Isolated Chromium and Node required")
    home = tmp_path / "state"
    command = [str(source_atm), "--home", str(home), "studio", "serve", "--node", node, "--chromium", chromium]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready, _, _ = select.select([process.stdout], [], [], 40)
        assert ready and json.loads(process.stdout.readline())["status"] == "ready"
        code, status = cli(source_atm, home, "status")
        assert code == 0 and status["browser_connected"] and status["provider_login"] == "unchecked_use_account_tool"
        duplicate = subprocess.run(command, capture_output=True, text=True, timeout=20)
        assert duplicate.returncode == 2 and json.loads(duplicate.stdout)["error"]["code"] == "runtime_busy"
        code, headless_login = cli(source_atm, home, "login")
        assert code == 2 and headless_login["error"]["code"] == "headed_required"
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=30)


@pytest.fixture
def source_atm(tmp_path):
    executable = tmp_path / "fixture-atm"
    executable.write_text(f'#!{sys.executable}\nimport sys\nsys.path.insert(0,{str(ROOT / "src")!r})\nfrom agent_tool_maker.cli import main\nsys.exit(main())\n')
    executable.chmod(0o700)
    return executable


@pytest.fixture
def server_process(tmp_path):
    pytest.importorskip("playwright")
    chromium = os.environ.get("ATM_CHROMIUM") or shutil.which("chromium") or shutil.which("google-chrome")
    node = shutil.which("node")
    if not chromium or not node:
        pytest.skip("Real Chromium and Node.js required for isolated server integration")
    home = tmp_path / "server-home"
    processes = []
    def launch(authenticate=True):
        command = [sys.executable, str(ROOT / "tests/fixtures/studio_server_fixture.py"), "--home", str(home),
                   "--node", node, "--chromium", chromium]
        if authenticate: command += ["--authenticate"]
        stderr = (tmp_path / ("browser-" + str(len(processes)) + ".log")).open("w")
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=stderr, text=True)
        processes.append((process, stderr))
        readable, _, _ = select.select([process.stdout], [], [], 40)
        assert readable, "Fixture browser failed to start; inspect retained local browser log"
        line = process.stdout.readline()
        assert line and json.loads(line)["status"] == "ready", "Fixture runtime did not announce readiness"
        return process, home
    yield launch
    for process, stderr in processes:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=30)
        stderr.close()


def cli(executable, home, *arguments):
    result = subprocess.run([str(executable), "--home", str(home), "studio", *arguments], text=True, capture_output=True, timeout=45)
    return result.returncode, json.loads(result.stdout)


@pytest.mark.browser
@pytest.mark.integration
def test_real_server_cli_cookie_restart_and_new_agent_reuse(server_process, source_atm, tmp_path):
    process, home = server_process(True)
    project = tmp_path / "project"
    project.mkdir()
    status, result = cli(source_atm, home, "status")
    assert status == 0 and result["execution"] == "server_owned" and not result["local_computer_required"]
    _, preview = cli(source_atm, home, "install")
    code, installed = cli(source_atm, home, "install", "--apply", "--approve", preview["bundle_sha256"], "--atm-executable", str(source_atm))
    assert code == 0 and installed["tool_count"] == 31
    inputs = tmp_path / "input.json"
    inputs.write_text("{}")
    arguments = ["run", "account", "--input", str(inputs), "--workspace", str(project), "--request-key", "fixture-once", "--allow-code"]
    code, first = cli(source_atm, home, *arguments)
    assert code == 0 and first["status"] == "completed", first
    assert first["data"]["result"][0]["credits"] == 99
    code, second = cli(source_atm, home, *arguments)
    assert code == 0 and first["id"] == second["id"]
    process.terminate()
    process.wait(timeout=30)
    assert (home / "studio/browser-profile").is_dir()
    restarted, _ = server_process(False)
    fresh = [*arguments]
    fresh[fresh.index("fixture-once")] = "after-browser-restart"
    code, third = cli(source_atm, home, *fresh)
    assert code == 0 and third["status"] == "completed", third
    assert third["id"] != first["id"] and third["data"]["result"][0]["credits"] == 99
    code, denied = cli(source_atm, home, *[v for v in fresh if v != "--allow-code"])
    assert code == 2 and "error" in denied
    with pytest.raises(RouterError) as no_token:
        asyncio.run(runtime.request(home, {"method": "rpc", "token": "fake", "name": "evaluate", "args": ["() => 1", []]}))
    assert no_token.value.code == "unauthorized"


@pytest.mark.browser
@pytest.mark.integration
def test_real_missing_login_does_not_return_success(server_process, source_atm, tmp_path):
    _, home = server_process(False)
    project = tmp_path / "project"
    project.mkdir()
    original = runtime.index()["account"]
    argv = compile_command(None, original, {}, project, project)["argv"][3:]
    with pytest.raises(RouterError) as login:
        asyncio.run(runtime.request(home, {"method": "run", "operation": "account", "argv": argv,
                                          "workspace": str(project), "bundle": runtime.bundle_digest()}))
    assert login.value.code == "login_required"
    assert not (project / ".atm/tripo-studio-paid").exists()


@pytest.mark.browser
@pytest.mark.integration
def test_real_fake_paid_gate_and_single_submission(server_process, source_atm, tmp_path):
    _, home = server_process(True)
    project = tmp_path / "project"
    project.mkdir()
    _, preview = cli(source_atm, home, "install")
    assert cli(source_atm, home, "install", "--apply", "--approve", preview["bundle_sha256"], "--atm-executable", str(source_atm))[0] == 0
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    base = ["--workspace", str(project), "--allow-code", "--allow-write"]
    original = runtime.index()["quote"]
    argv = compile_command(None, original, {}, project, project)["argv"][3:]
    probe = asyncio.run(runtime.request(home, {"method": "run", "operation": "quote", "argv": argv,
        "workspace": str(project), "bundle": runtime.bundle_digest()}))
    assert probe[0]["quoted_credits"] == 40
    code, quoted = cli(source_atm, home, "run", "quote", "--input", str(empty), "--request-key", "fake-quote", *base)
    assert code == 0, quoted
    quote = quoted["data"]["result"][0]
    assert quote["quoted_credits"] == 40 and not quote["paid_submitted"]
    paid = tmp_path / "paid.json"
    paid.write_text(json.dumps({"prompt": "Synthetic fixture cube", "quote_sha256": quote["quote_sha256"],
                               "max_credits": 40, "request_key": "fake-paid-once", "human_confirmed": True}))
    command = ["run", "generate", "--input", str(paid), "--request-key", "fake-paid-once", *base]
    code, denied = cli(source_atm, home, *command)
    assert code == 2 and denied["error"]["code"] == "paid_confirmation_required"
    assert not (project / ".atm/tripo-studio-paid").exists()
    # The hidden adapter is not a second paid path: the installed command line, run directly
    # without (or with a forged) Router ticket, is refused before any form or paid click.
    tool = next(t for t in manifests(home) if t["id"] == "tripo.server.generate")
    direct = compile_command(None, tool, json.loads(paid.read_text()), project, project)["argv"]
    for ticket in (None, "00000000-0000-4000-8000-000000000000." + "0" * 64):
        env = {k: v for k, v in os.environ.items() if k != runtime.TICKET_ENV}
        if ticket:
            env[runtime.TICKET_ENV] = ticket
        result = subprocess.run([str(source_atm), *direct], cwd=project, env=env, text=True, capture_output=True, timeout=45)
        refused = json.loads(result.stdout)["error"]
        assert result.returncode == 2 and refused["code"] == "router_ticket_required" and not refused["outcome_uncertain"]
    with pytest.raises(RouterError) as raw:
        asyncio.run(runtime.request(home, {"method": "run", "operation": "generate", "argv": direct[7:],
            "workspace": str(project), "bundle": runtime.bundle_digest()}))
    assert raw.value.code == "router_ticket_required" and not raw.value.uncertain
    assert not (project / ".atm/tripo-studio-paid").exists()
    code, first = cli(source_atm, home, *command, "--allow-paid")
    assert code == 0 and first["status"] == "completed", first
    assert first["data"]["result"][0]["status"] == "submitted"
    ticket = first["data"]["studio_ticket"]
    assert ticket["tool"] == "tripo.server.generate" and ticket["consumed_at"]  # The Router path consumed its own ticket.
    code, second = cli(source_atm, home, *command, "--allow-paid")
    assert code == 0 and first["id"] == second["id"]
    code, account = cli(source_atm, home, "run", "account", "--input", str(empty), "--request-key", "fake-balance", *base)
    assert code == 0 and account["data"]["result"][0]["credits"] == 59  # Synthetic DOM, not real credits.


@pytest.mark.browser
@pytest.mark.integration
def test_real_image_flag_mapping_preserves_missing_draft(server_process, tmp_path):
    _, home = server_process(True)
    project = tmp_path / "project"
    project.mkdir()
    original = runtime.index()["image_generate"]
    inputs = {key: sample(value) for key, value in original["schema"]["properties"].items()}
    argv = compile_command(None, original, inputs, project, project)["argv"][3:]
    _, _, _, ticket = router_job(home, "image_generate", project, inputs=inputs)  # Paid: Router ticket required.
    with pytest.raises(RouterError) as missing:
        asyncio.run(runtime.request(home, {"method": "run", "operation": "image_generate", "argv": argv,
            "workspace": str(project), "bundle": runtime.bundle_digest(), "ticket": ticket}))
    # The original OpenCLI wrapper maps --image-sha to image_sha. Check that the
    # server reaches the real draft gate rather than rejecting a valid image hash.
    assert missing.value.code == "draft_missing"


@pytest.mark.browser
@pytest.mark.integration
def test_real_driver_dom_upload_and_download_primitives(tmp_path):
    pytest.importorskip("playwright")
    from playwright.async_api import Error as PlaywrightError, async_playwright
    chromium = os.environ.get("ATM_CHROMIUM")
    if not chromium:
        pytest.skip("Isolated Chromium required")
    project = tmp_path / "project"
    project.mkdir()
    source = project / "fixture.txt"
    source.write_text("synthetic upload")
    html = '''<!doctype html><meta charset="utf-8"><title>Driver fixture</title>
    <button class="choice" onclick="this.dataset.clicked='yes'">First</button>
    <button class="choice" onclick="this.dataset.clicked='yes'">Second</button>
    <button id="switch" role="switch" aria-checked="false" data-count="0"
      onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='false'?'true':'false');this.dataset.count=String(Number(this.dataset.count)+1)">Toggle</button>
    <button id="broken" role="switch" aria-checked="false">No change</button>
    <input id="check" type="checkbox"><input id="text"><input id="file" type="file">
    <a id="download" href="/fixture.glb">Download</a><div style="height:2000px"></div><p id="end">End</p>'''
    async def probe():
        async with async_playwright() as manager:
            context = await manager.chromium.launch_persistent_context(tmp_path / "profile", executable_path=chromium,
                headless=True, chromium_sandbox=True, accept_downloads=True, artifacts_dir=tmp_path / "artifacts")
            try:
                async def route_handler(route):
                    if route.request.url == runtime.ORIGIN + "/fixture.glb":
                        await route.fulfill(body=b"synthetic downloaded bytes", content_type="model/gltf-binary",
                            headers={"Content-Disposition": 'attachment; filename="atm-fixture.glb"'})
                    elif route.request.url.startswith(runtime.ORIGIN + "/"):
                        await route.fulfill(body=html, content_type="text/html")
                    else:
                        await route.abort()
                await context.route("**/*", route_handler)
                browser = runtime.BrowserRuntime(tmp_path / "state", context, "node")
                await browser.start()
                browser.active = {"workspace": project}
                await browser.rpc("goto", [runtime.ORIGIN + "/fixture"])
                with pytest.raises(RouterError) as ambiguous:
                    await browser.rpc("click", [".choice"])
                assert ambiguous.value.code == "selector_ambiguous"
                await browser.rpc("click", [".choice", {"nth": 1}])
                assert await browser.page.locator(".choice").nth(1).get_attribute("data-clicked") == "yes"
                await browser.rpc("hover", [".choice", {"nth": 0}])
                await browser.rpc("fillText", ["#text", "fixture text"])
                await browser.rpc("focus", ["#text"])
                await browser.rpc("pressKey", ["Tab"])
                assert await browser.page.locator("#text").input_value() == "fixture text"
                await browser.rpc("setChecked", ["#switch", True])
                await browser.rpc("setChecked", ["#switch", True])
                assert await browser.page.locator("#switch").get_attribute("data-count") == "1"
                await browser.rpc("setChecked", ["#switch", False])
                assert await browser.page.locator("#switch").get_attribute("aria-checked") == "false"
                await browser.rpc("setChecked", ["#check", True])
                assert await browser.page.locator("#check").is_checked()
                # The native API supports ARIA switches and rejects a click that
                # leaves state unchanged; the daemon redacts native errors at RPC.
                with pytest.raises(PlaywrightError, match="did not change its state"):
                    await browser.rpc("setChecked", ["#broken", True])
                document = await browser.rpc("cdp", ["DOM.getDocument", {"depth": 0}])
                target = await browser.rpc("cdp", ["DOM.querySelector", {"nodeId": document["root"]["nodeId"], "selector": "#file"}])
                await browser.rpc("cdp", ["DOM.setFileInputFiles", {"nodeId": target["nodeId"], "files": [str(source)]}])
                assert await browser.page.locator("#file").evaluate("e=>e.files[0].name") == "fixture.txt"
                arm = await browser.rpc("download_arm", ["atm-fixture", 10000])
                waiting = asyncio.create_task(browser.rpc("download_wait", [arm]))
                await browser.rpc("click", ["#download"])
                completed = await waiting
                assert completed["state"] == "complete" and completed["downloaded"]
                assert Path(completed["filename"]).read_bytes() == b"synthetic downloaded bytes"
                await browser.rpc("scrollTo", ["#end"])
                assert await browser.page.evaluate("window.scrollY") > 0
            finally:
                await context.close()
    asyncio.run(probe())
