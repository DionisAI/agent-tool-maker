"""Protocol, real local subprocess and isolated Chromium tests; never production login."""
import asyncio
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


@pytest.mark.parametrize("hint,kept", [("fake_ip_tunnel", "fake_ip_tunnel"), ("other_hint", None)])
def test_runtime_errors_keep_only_a_known_hint(tmp_path, hint, kept):
    home = tmp_path / "h"
    sock = runtime.studio_dir(home) / "s"
    async def scenario():
        async def answer(reader, writer):
            await reader.readline()
            writer.write(json.dumps({"error": {"code": "unsafe_download", "message": "fixture", "outcome_uncertain": False,
                                               "hint": hint}}).encode() + b"\n")
            await writer.drain()
            writer.close()
        server = await asyncio.start_unix_server(answer, path=str(sock))
        sock.chmod(0o600)
        (runtime.studio_dir(home) / "runtime.json").write_text(json.dumps({"status": "running", "socket": str(sock)}))
        async with server:
            return await runtime.request(home, {"method": "status"}, timeout=5)
    with pytest.raises(RouterError) as error:
        asyncio.run(scenario())
    assert error.value.code == "unsafe_download" and error.value.hint == kept


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
    code, first = cli(source_atm, home, *command, "--allow-paid")
    assert code == 0 and first["status"] == "completed", first
    assert first["data"]["result"][0]["status"] == "submitted"
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
    with pytest.raises(RouterError) as missing:
        asyncio.run(runtime.request(home, {"method": "run", "operation": "image_generate", "argv": argv,
            "workspace": str(project), "bundle": runtime.bundle_digest()}))
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
