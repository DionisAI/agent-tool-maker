"""Tool catalog setup steps: tool definition + local state only. Names, definition URLs and booleans;
no secret, executable path or provider request. Isolated homes and fake credentials."""
import json
from pathlib import Path
import time

from agent_tool_maker import management as mg
from agent_tool_maker.actions import set_origin
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.mcp_bridge import bind_server
from agent_tool_maker.oauth import OAuth, RESOURCE
from agent_tool_maker.web_recipe import save_session
from test_maker_workflows import recipe as workflow_recipe
from test_subscription_credits import install_tool
from test_web_recipe_v06 import recipe_tool, storage
from test_webapp_v04 import console, get  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]
STUDIO_QUOTE = ROOT / "generated/tripo-studio/quote/manifest.json"
# Every method and its exact fields besides `method` and `ready`; a renderer can rely on them.
FIELDS = {"api_key": {"credential", "required", "configured", "expired"}, "cli_bind": {"alias"},
          "opencli_chrome": {"alias"}, "web_login": {"session", "saved", "expired"}, "oauth": {"provider", "status"},
          "mcp": {"server"}, "origin": {"provider"}, "browser_handoff": {"url"}, "desktop_handoff": {"url"},
          "human_handoff": {"url"}, "workflow": {"tools"}, "catalog_only": set()}
UNCHECKED = {"browser_handoff", "desktop_handoff", "human_handoff", "workflow", "catalog_only"}  # ready is null


def setup(router, tool_id):
    return {t["id"]: t for t in mg.tools(router)["tools"]}[tool_id]["setup"]


def executable(tmp_path, name):
    path = tmp_path / name
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o700)
    return path


def key(name, *, required=True, configured=False, expired=False):
    return {"method": "api_key", "credential": name, "required": required, "configured": configured,
            "expired": expired, "ready": configured and not expired}


def test_api_key_step_follows_the_saved_connection(router):
    # The fixture vault holds a fake elevenlabs Key; apify has none.
    assert setup(router, "elevenlabs.tts") == [key("elevenlabs", configured=True)]
    assert setup(router, "apify.run") == [key("apify")]
    router.vault.put("apify", "FAKE_apify", expires_at=time.time() - 60)
    assert setup(router, "apify.run") == [key("apify", configured=True, expired=True)]


def test_handoffs_name_the_definition_url_and_are_not_checked(router):
    rows = {t["id"]: t for t in mg.tools(router)["tools"]}
    web = rows["elevenlabs.web"]
    assert web["setup"] == [{"method": "browser_handoff", "url": "https://elevenlabs.io/app/", "ready": None}]
    assert web["health"]["state"] == "browser_login_unknown" and web["paid"] is True
    assert rows["clo.handoff"]["setup"] == [{"method": "desktop_handoff", "url": "https://developer.clo3d.com/", "ready": None}]
    assert rows["fiverr.handoff"]["setup"] == [{"method": "human_handoff", "url": "https://www.fiverr.com/", "ready": None}]


def test_cli_bind_and_optional_cli_key(router, tmp_path):
    assert setup(router, "wrangler.deployments") == [
        {"method": "cli_bind", "alias": "wrangler", "ready": False}, key("cloudflare", required=False)]
    path = executable(tmp_path, "wrangler")
    bind_cli(router.state, "wrangler", str(path))
    steps = setup(router, "wrangler.deployments")
    assert steps[0] == {"method": "cli_bind", "alias": "wrangler", "ready": True}
    assert str(path) not in json.dumps(steps)  # The bound path stays on the CLI page, not in the setup step.


def test_opencli_website_tool_uses_the_opencliapp_alias_and_chrome(router, tmp_path):
    install_tool(router, json.loads(STUDIO_QUOTE.read_text()))
    assert setup(router, "tripo.studio.quote") == [{"method": "opencli_chrome", "alias": "opencliapp", "ready": False}]
    bind_cli(router.state, "opencliapp", str(executable(tmp_path, "opencliapp")))
    assert setup(router, "tripo.studio.quote") == [{"method": "opencli_chrome", "alias": "opencliapp", "ready": True}]


def test_web_login_reports_its_session_without_reading_it(router):
    tool = recipe_tool()
    tool["recipe"]["session"] = "studio"
    install_tool(router, tool)
    step = {"method": "web_login", "session": "studio", "saved": False, "expired": False, "ready": False}
    assert setup(router, "fixture.export") == [step]
    save_session(router.vault, "studio", ["https://fixture.example"], storage())
    assert setup(router, "fixture.export") == [{**step, "saved": True, "ready": True}]
    with router.state.db() as db:  # Synthetic expiry of the saved row.
        db.execute("UPDATE browser_sessions SET expires_at=? WHERE name='studio'", (time.time() - 60,))
    assert setup(router, "fixture.export") == [{**step, "saved": True, "expired": True}]
    assert "FAKE-browser-session-secret" not in json.dumps(mg.tools(router))


def test_web_recipe_without_a_session_needs_no_login(router):
    install_tool(router, recipe_tool())
    assert setup(router, "fixture.export") == []


def test_mcp_with_its_own_key_origin_and_workflow(router, tmp_path):
    assert setup(router, "figma.mcp_tools") == [{"method": "mcp", "server": "figma", "ready": False}]
    bind_server(router.state, "figma", {"transport": "stdio", "command": str(executable(tmp_path, "figma-mcp")),
                                        "allow_tools": ["get_file"], "env_credentials": {"FIGMA_TOKEN": "figma"}})
    # The bound server's own vault Key is required, as tool_health checks it.
    assert setup(router, "figma.mcp_tools") == [{"method": "mcp", "server": "figma", "ready": True}, key("figma")]
    assert setup(router, "comfyui.queue") == [{"method": "origin", "provider": "comfyui", "ready": False}]
    set_origin(router.state, "comfyui", "http://127.0.0.1:8188")
    assert setup(router, "comfyui.queue") == [{"method": "origin", "provider": "comfyui", "ready": True}]
    assert [s["method"] for s in setup(router, "ghost.posts")] == ["api_key", "origin"]
    install_tool(router, workflow_recipe())
    assert setup(router, "workflow.media") == [
        {"method": "workflow", "tools": ["imagemagick.resize", "imagemagick.webp"], "ready": None}]


def test_mcp_bound_to_atm_oauth_reports_the_local_login(router, monkeypatch):
    bind_server(router.state, "notion", {"transport": "http", "url": RESOURCE, "oauth": "higgsfield", "allow_tools": ["search"]})
    assert setup(router, "notion.mcp_tools") == [
        {"method": "mcp", "server": "notion", "ready": True},
        {"method": "oauth", "provider": "higgsfield", "status": "missing", "ready": False}]
    status = OAuth.status
    monkeypatch.setattr(OAuth, "status", lambda self, name="higgsfield": {**status(self, name), "status": "ready"})
    assert setup(router, "notion.mcp_tools")[1] == {"method": "oauth", "provider": "higgsfield", "status": "ready", "ready": True}


def test_every_catalog_row_has_known_setup_steps_and_no_secret(router):
    payload = mg.tools(router)
    assert payload["network_calls"] == 0 and payload["count"] == len(router.catalog.tools)
    for row in payload["tools"]:
        assert row["setup"], row["id"]  # Every built-in tool names where it is set up.
        for step in row["setup"]:
            assert set(step) - {"method", "ready"} == FIELDS[step["method"]], (row["id"], step)
            assert step["ready"] is None if step["method"] in UNCHECKED else type(step["ready"]) is bool, (row["id"], step)
    assert "FAKE_" not in json.dumps(payload)


def test_fresh_home_reports_nothing_ready(tmp_path):
    router = Router(tmp_path / "state")
    try:
        steps = [s for row in mg.tools(router)["tools"] for s in row["setup"]]
    finally:
        router.close()
    assert not any(s["ready"] for s in steps)


def test_console_tools_endpoint_carries_setup_steps(console):
    response = get(console, "/api/tools")
    assert response.status_code == 200
    rows = {t["id"]: t for t in response.json()["tools"]}
    assert rows["elevenlabs.tts"]["setup"] == [key("elevenlabs")]
    assert rows["elevenlabs.web"]["setup"] == [{"method": "browser_handoff", "url": "https://elevenlabs.io/app/", "ready": None}]
    server, client = console
    assert client.get("/api/tools").status_code == 401  # Still bearer-only.
