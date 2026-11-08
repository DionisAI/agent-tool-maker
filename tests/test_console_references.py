"""Console payload additions: tool references (B1) and job kinds (B2). Isolated homes, fake values only."""
import json
import threading

import httpx
import pytest

from agent_tool_maker import credits
from agent_tool_maker import management as mg
from agent_tool_maker.engine import Router
from agent_tool_maker.extensions import new_template
from agent_tool_maker.maker import validate_manifest
from agent_tool_maker.storage import State
from agent_tool_maker.webapp import Console
from test_subscription_credits import Fakes, definitions, install_tool

REFERENCES = {"credentials", "optional_credentials", "executable", "server", "oauth", "url", "session", "origins"}
ROW_KEYS = {"id", "title", "provider", "adapter", "capabilities", "implementation", "permissions", "paid", "enabled", "health"}
DETAIL_KEYS = {"id", "title", "provider", "adapter", "capabilities", "schema", "permissions", "paid", "implementation", "notes", "enabled"}
NEVER = {"command", "request", "headers", "example", "recipe", "steps", "instructions"}
PASSWORD = "fake-console-references-password"
SECRET = "FAKE-REFERENCE-SECRET-NEVER-SHOWN"


def recipe_tool():
    tool = new_template("fixture.export", "web", url="https://fixture.example/")
    tool["paid"] = False
    tool["recipe"]["session"] = "fixture-login"
    return validate_manifest(tool)


@pytest.fixture
def console(tmp_path):
    router = Router(tmp_path / "state")
    install_tool(router, recipe_tool())
    # A reviewed MCP binding that names its Key; the config itself is never returned.
    router.state.set_setting("mcp:linear", {"transport": "http", "url": "https://mcp.linear.example/mcp",
                                            "credential": "linear", "env_credentials": {}, "allow_tools": []})
    router.close()
    server = Console(tmp_path / "state", localhost=True, user_home=tmp_path / "user")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with httpx.Client(base_url=server.origin, trust_env=False, timeout=30,
                      headers={"Authorization": "Bearer " + server.token, "Origin": server.origin}) as client:
        assert client.post("/api/vault/init", json={"backend": "passphrase", "passphrase": PASSWORD}).status_code == 200
        saved = client.post("/api/connections/save", json={"provider": "elevenlabs", "value": SECRET, "passphrase": PASSWORD})
        assert saved.status_code == 200, saved.text
        yield server, client
    server.shutdown()
    server.server_close()
    thread.join(5)


def by_id(rows):
    return {row["id"]: row for row in rows}


def test_tool_rows_carry_exactly_the_non_secret_references(console):
    _, client = console
    response = client.get("/api/tools")
    assert response.status_code == 200
    rows = by_id(response.json()["tools"])
    for row in rows.values():
        assert set(row) == ROW_KEYS | REFERENCES, row["id"]
        assert not NEVER & set(row)
    assert rows["elevenlabs.tts"]["credentials"] == ["elevenlabs"]
    assert rows["elevenlabs.tts"]["url"] is None
    assert rows["elevenlabs.web"]["url"] == "https://elevenlabs.io/app/"
    assert rows["elevenlabs.web"]["credentials"] == []
    assert rows["wrangler.deploy"]["credentials"] == []
    assert rows["wrangler.deploy"]["optional_credentials"] == ["cloudflare"]
    assert rows["wrangler.deploy"]["executable"] == "wrangler"
    assert rows["ffmpeg.probe"]["executable"] == "ffprobe"
    linear = rows["linear.mcp_tools"]
    assert linear["server"] == "linear" and linear["credentials"] == ["linear"] and linear["oauth"] is None
    recipe = rows["fixture.export"]
    assert recipe["session"] == "fixture-login" and recipe["origins"] == ["https://fixture.example"]
    assert recipe["url"] is None and recipe["credentials"] == []
    assert response.text.count(SECRET) == 0 and PASSWORD not in response.text
    assert "mcp.linear.example" not in response.text  # The bound config URL is not a hand-off URL.


def test_tool_detail_carries_references_and_no_execution_details(console):
    _, client = console
    for tool_id in ["elevenlabs.tts", "elevenlabs.web", "ffmpeg.probe", "linear.mcp_tools", "fixture.export"]:
        response = client.get("/api/tools/" + tool_id)
        assert response.status_code == 200
        detail = response.json()
        assert set(detail) == DETAIL_KEYS | REFERENCES, tool_id
        assert not NEVER & set(detail)
        assert SECRET not in response.text and PASSWORD not in response.text
    assert client.get("/api/tools/elevenlabs.web").json()["url"] == "https://elevenlabs.io/app/"
    assert client.get("/api/tools/linear.mcp_tools").json()["credentials"] == ["linear"]


def test_higgsfield_oauth_binding_is_named_not_returned(tmp_path):
    router = Router(tmp_path / "state")
    try:
        router.state.set_setting("mcp:linear", {"transport": "http", "url": "https://mcp.example/mcp",
                                                "oauth": "higgsfield", "allow_tools": []})
        row = by_id(mg.tools(router)["tools"])["linear.mcp_tools"]
        assert row["oauth"] == "higgsfield" and row["credentials"] == []
    finally:
        router.close()


def test_jobs_carry_their_kind(tmp_path):
    router = Router(tmp_path / "state")
    fakes = Fakes(tmp_path)
    try:
        install_tool(router, definitions(router.state.home)["pippit.cli.credit_balance"])
        fakes.bind(router, "xyq")
        fakes.output("xyq", {"total_remain_amount": "987654"})
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        router.state.create_job("ffmpeg.probe", {"path": "fixture.wav"}, workspace, None)
        assert credits.refresh(router, "xyq")["refresh"] == "ok"
        jobs = mg.recent_jobs(router)["jobs"]
        kinds = {job["tool"]: (job["kind"], job["artifact_count"]) for job in jobs}
        assert kinds == {"ffmpeg.probe": ("tool", 0), "pippit.cli.credit_balance": ("credits_refresh", 0)}
        assert all(set(job) == {"id", "tool", "status", "created", "updated", "verification", "cost_usd",
                                "cost_status", "artifact_count", "kind"} for job in jobs)
        assert "987654" not in json.dumps([job for job in jobs if job["kind"] == "credits_refresh"])
    finally:
        router.close()
