"""Tool catalog setup hints: tool definition + local state only. Names, definition URLs and booleans;
no secret, executable path or provider request. Isolated homes and fake credentials."""
import json
from pathlib import Path
import time

from agent_tool_maker import management as mg
from agent_tool_maker.actions import set_origin
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.mcp_bridge import bind_server
from agent_tool_maker.web_recipe import save_session
from test_maker_workflows import recipe as workflow_recipe
from test_subscription_credits import install_tool
from test_web_recipe_v06 import recipe_tool, storage
from test_webapp_v04 import console, get  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]
STUDIO_QUOTE = ROOT / "generated/tripo-studio/quote/manifest.json"
# Every step kind and its exact fields: the console words each one.
FIELDS = {"credential": {"credential", "required", "configured", "expired"}, "browser": {"url"}, "desktop": {"url"},
          "human": {"url"}, "web_login": {"session", "saved", "expired"}, "cli": {"alias", "bound"},
          "mcp": {"server", "bound"}, "origin": {"provider", "set"}, "workflow": {"tools"}, "catalog_only": set()}


def setup(router, tool_id):
    return {t["id"]: t for t in mg.tools(router)["tools"]}[tool_id]["setup"]


def executable(tmp_path, name):
    path = tmp_path / name
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o700)
    return path


def test_vault_credential_step_follows_the_saved_connection(router):
    # The fixture vault holds a fake elevenlabs Key; apify has none.
    assert setup(router, "elevenlabs.tts") == [
        {"kind": "credential", "credential": "elevenlabs", "required": True, "configured": True, "expired": False}]
    assert setup(router, "apify.run") == [
        {"kind": "credential", "credential": "apify", "required": True, "configured": False, "expired": False}]
    router.vault.put("apify", "FAKE_apify", expires_at=time.time() - 60)
    assert setup(router, "apify.run") == [
        {"kind": "credential", "credential": "apify", "required": True, "configured": True, "expired": True}]


def test_host_browser_desktop_and_human_handoffs_name_the_definition_url(router):
    rows = {t["id"]: t for t in mg.tools(router)["tools"]}
    web = rows["elevenlabs.web"]
    assert web["setup"] == [{"kind": "browser", "url": "https://elevenlabs.io/app/"}]
    assert web["health"]["state"] == "browser_login_unknown" and web["paid"] is True
    assert rows["clo.handoff"]["setup"] == [{"kind": "desktop", "url": "https://developer.clo3d.com/"}]
    assert rows["fiverr.handoff"]["setup"] == [{"kind": "human", "url": "https://www.fiverr.com/"}]


def test_cli_alias_binding_and_optional_cli_credential(router, tmp_path):
    expected = [{"kind": "cli", "alias": "wrangler", "bound": False},
                {"kind": "credential", "credential": "cloudflare", "required": False, "configured": False, "expired": False}]
    assert setup(router, "wrangler.deployments") == expected
    path = executable(tmp_path, "wrangler")
    bind_cli(router.state, "wrangler", str(path))
    steps = setup(router, "wrangler.deployments")
    assert steps[0] == {"kind": "cli", "alias": "wrangler", "bound": True}
    assert str(path) not in json.dumps(steps)  # The bound path stays on the CLI page, not in the hint.


def test_opencli_website_tool_needs_the_opencliapp_alias(router, tmp_path):
    install_tool(router, json.loads(STUDIO_QUOTE.read_text()))
    assert setup(router, "tripo.studio.quote") == [{"kind": "cli", "alias": "opencliapp", "bound": False}]
    bind_cli(router.state, "opencliapp", str(executable(tmp_path, "opencliapp")))
    assert setup(router, "tripo.studio.quote") == [{"kind": "cli", "alias": "opencliapp", "bound": True}]


def test_web_recipe_login_reports_its_session_without_reading_it(router):
    tool = recipe_tool()
    tool["recipe"]["session"] = "studio"
    install_tool(router, tool)
    assert setup(router, "fixture.export") == [{"kind": "web_login", "session": "studio", "saved": False, "expired": False}]
    save_session(router.vault, "studio", ["https://fixture.example"], storage())
    assert setup(router, "fixture.export") == [{"kind": "web_login", "session": "studio", "saved": True, "expired": False}]
    with router.state.db() as db:  # Synthetic expiry of the saved row.
        db.execute("UPDATE browser_sessions SET expires_at=? WHERE name='studio'", (time.time() - 60,))
    assert setup(router, "fixture.export")[0]["expired"] is True
    assert "FAKE-browser-session-secret" not in json.dumps(mg.tools(router))


def test_web_recipe_without_a_session_needs_no_login(router):
    install_tool(router, recipe_tool())
    assert setup(router, "fixture.export") == []


def test_mcp_origin_and_workflow_steps(router, tmp_path):
    assert setup(router, "figma.mcp_tools") == [{"kind": "mcp", "server": "figma", "bound": False}]
    bind_server(router.state, "figma", {"transport": "stdio", "command": str(executable(tmp_path, "figma-mcp")), "allow_tools": ["get_file"],
                                        "env_credentials": {"FIGMA_TOKEN": "figma"}})
    # The bound server's own vault credential is a required step, as tool_health checks it.
    assert setup(router, "figma.mcp_tools") == [
        {"kind": "mcp", "server": "figma", "bound": True},
        {"kind": "credential", "credential": "figma", "required": True, "configured": False, "expired": False}]
    assert setup(router, "comfyui.queue") == [{"kind": "origin", "provider": "comfyui", "set": False}]
    set_origin(router.state, "comfyui", "http://127.0.0.1:8188")
    assert setup(router, "comfyui.queue") == [{"kind": "origin", "provider": "comfyui", "set": True}]
    assert [s["kind"] for s in setup(router, "ghost.posts")] == ["credential", "origin"]
    install_tool(router, workflow_recipe())
    assert setup(router, "workflow.media") == [{"kind": "workflow", "tools": ["imagemagick.resize", "imagemagick.webp"]}]


def test_every_catalog_row_has_known_setup_steps_and_no_secret(router):
    payload = mg.tools(router)
    assert payload["network_calls"] == 0 and payload["count"] == len(router.catalog.tools)
    for row in payload["tools"]:
        for step in row["setup"]:
            assert set(step) - {"kind"} == FIELDS[step["kind"]], (row["id"], step)
    assert all(row["setup"] for row in payload["tools"])  # Every built-in tool names where it is set up.
    assert "FAKE_" not in json.dumps(payload)


def test_fresh_home_reports_nothing_configured(tmp_path):
    router = Router(tmp_path / "state")
    try:
        steps = [s for row in mg.tools(router)["tools"] for s in row["setup"]]
    finally:
        router.close()
    assert not any(s.get("configured") or s.get("bound") or s.get("saved") or s.get("set") for s in steps)


def test_console_tools_endpoint_carries_setup_steps(console):
    response = get(console, "/api/tools")
    assert response.status_code == 200
    rows = {t["id"]: t for t in response.json()["tools"]}
    assert rows["elevenlabs.tts"]["setup"] == [
        {"kind": "credential", "credential": "elevenlabs", "required": True, "configured": False, "expired": False}]
    assert rows["elevenlabs.web"]["setup"] == [{"kind": "browser", "url": "https://elevenlabs.io/app/"}]
    server, client = console
    assert client.get("/api/tools").status_code == 401  # Still bearer-only.
