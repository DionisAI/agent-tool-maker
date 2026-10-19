"""Subscription credits contract: isolated homes and fake CLI subprocesses only; no vendor/account access."""
from datetime import date
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import httpx
import pytest

from agent_tool_maker import credits
from agent_tool_maker import management as mg
from agent_tool_maker.catalog import Catalog
from agent_tool_maker.cli import main
from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.errors import RouterError
from agent_tool_maker.maker import digest, install, read_manifest, validate_manifest
from agent_tool_maker.storage import State

ROOT = Path(__file__).resolve().parents[1]
PIPPIT = ROOT / "examples/extensions/pippit-cli-credit-balance.json"
EMAIL = "owner-fixture@example.test"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRIPO = load("build_tripo_studio")
XYQ = load("build_xyq_web")
sys.path.insert(0, str(ROOT / "scripts"))  # build_xyq_runtime imports build_xyq_web by name.
RUNTIME = load("build_xyq_runtime")


def definitions(home):
    from agent_tool_maker.studio_cli import manifests
    return {"tripo.studio.account": TRIPO.manifest("account"), "xyq.web.account": XYQ.manifest("account"),
            "tripo.server.account": next(t for t in manifests(home) if t["id"] == "tripo.server.account"),
            "pippit.cli.credit_balance": json.loads(PIPPIT.read_text()),
            "higgsfield.subscription.account": json.loads((ROOT / "examples/extensions/higgsfield-subscription-account.json").read_text())}


def install_tool(router, tool):
    tool = validate_manifest(tool, router.catalog)
    path = router.state.home.parent / f"{tool['id']}.manifest.json"
    path.write_text(json.dumps(tool))
    install(router.state, router.catalog, path, digest(tool))
    router.catalog = Catalog(router.state)


class Fakes:
    """Real subprocesses; each logs argv/cwd and prints its configured output."""
    def __init__(self, root):
        self.root = root

    def bind(self, router, name):
        script = self.root / f"fake-{name}"
        script.write_text(f'''#!{sys.executable}
import json, os, sys, time
from pathlib import Path
root = Path({str(self.root)!r})
with (root / "calls.jsonl").open("a") as log:
    log.write(json.dumps({{"exe": {name!r}, "argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
gate = root / "{name}.gate"
if gate.exists():
    (root / "{name}.started").write_text("1")
    deadline = time.time() + 20
    while gate.exists() and time.time() < deadline:
        time.sleep(0.02)
code = root / "{name}.exit"
if code.exists():
    print("FAKE_STDERR_SECRET", file=sys.stderr)
    sys.exit(int(code.read_text()))
sys.stdout.write((root / "{name}.out.json").read_text())
''')
        script.chmod(0o700)
        bind_cli(router.state, name, str(script))

    def output(self, name, value):
        (self.root / f"{name}.out.json").write_text(json.dumps(value))

    def calls(self):
        path = self.root / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.fixture
def home(tmp_path, monkeypatch):
    router = Router(tmp_path / "state")
    monkeypatch.setattr(router.vault, "get", lambda *_: pytest.fail("credential read"))
    yield router
    router.close()


@pytest.fixture
def fakes(tmp_path):
    folder = tmp_path / "fakes"
    folder.mkdir()
    return Fakes(folder)


def tripo_row(value=6396):
    return [{"status": "ready", "logged_in": True, "credits": value, "billing": "studio_subscription",
             "source": "visible_header", "secrets_returned": False, "paid_submitted": False}]


def xyq_row(value=880):
    return [{"result": {"status": "ready", "logged_in": True, "credits": value, "billing": "website_account",
                        "source": "visible_dom", "secrets_returned": False, "paid_submitted": False}}]


HIGGSFIELD = {"credits": 1234, "subscription_plan_type": "pro", "email": EMAIL, "user_id": "FAKE-USER-ID"}


# --- Pure extractors -------------------------------------------------------------

def test_website_extractor_reads_tripo_and_xyq_rows():
    assert credits.website_credits(tripo_row(6396)) == {"credits": 6396, "plan": None}
    assert credits.website_credits(xyq_row(12.5)) == {"credits": 12.5, "plan": None}
    assert credits.website_credits(tripo_row(0)) == {"credits": 0, "plan": None}


@pytest.mark.parametrize("value", [{"total_remain_amount": "123"}, {"total_remain_amount": "0"},
                                   {"total_remain_amount": "12.5"}, {"total_remain_amount": 7}])
def test_pippit_string_amount_and_real_zero(value):
    expected = {"123": 123, "0": 0, "12.5": 12.5, 7: 7}[value["total_remain_amount"]]
    result = credits.pippit_credits(value)
    assert result == {"credits": expected, "plan": None}
    assert type(result["credits"]) is type(expected)


def test_higgsfield_keeps_plan_and_drops_email_and_identity():
    result = credits.higgsfield_credits(HIGGSFIELD)
    assert result == {"credits": 1234, "plan": "pro"}
    assert EMAIL not in json.dumps(result) and "FAKE-USER-ID" not in json.dumps(result)
    assert credits.higgsfield_credits({"credits": 3})["plan"] is None
    assert credits.higgsfield_credits({"credits": 3, "subscription_plan_type": "<b>" * 20})["plan"] is None


@pytest.mark.parametrize("extract,value", [
    (credits.pippit_credits, {}),
    (credits.pippit_credits, {"total_remain_amount": None}),
    (credits.pippit_credits, {"total_remain_amount": ""}),
    (credits.pippit_credits, {"total_remain_amount": "abc"}),
    (credits.pippit_credits, {"total_remain_amount": "-1"}),
    (credits.pippit_credits, {"total_remain_amount": "1e9"}),
    (credits.pippit_credits, {"total_remain_amount": "١٢"}),
    (credits.pippit_credits, {"total_remain_amount": True}),
    (credits.pippit_credits, {"total_remain_amount": -2}),
    (credits.pippit_credits, []),
    (credits.higgsfield_credits, {"subscription_plan_type": "pro"}),
    (credits.higgsfield_credits, {"credits": True}),
    (credits.higgsfield_credits, {"credits": False}),
    (credits.higgsfield_credits, {"credits": -1}),
    (credits.higgsfield_credits, {"credits": "856"}),
    (credits.higgsfield_credits, {"credits": math.nan}),
    (credits.higgsfield_credits, {"credits": math.inf}),
    (credits.website_credits, [{"status": "ready", "logged_in": True}]),
    (credits.website_credits, [{"status": "ready", "logged_in": True, "credits": None}]),
    (credits.website_credits, [{"status": "login_required", "credits": 5}]),
    (credits.website_credits, [{"status": "ready", "logged_in": False, "credits": 5}]),
    (credits.website_credits, tripo_row() + tripo_row()),
    (credits.website_credits, "6396"),
    (credits.website_credits, None),
    # Absurd magnitudes are unreadable, never an OverflowError or a float approximation.
    (credits.website_credits, tripo_row(10**400)),
    (credits.higgsfield_credits, {"credits": 10**400}),
    (credits.higgsfield_credits, {"credits": 10**15 + 1}),
    (credits.higgsfield_credits, {"credits": 1e300}),
    (credits.pippit_credits, {"total_remain_amount": 10**400}),
    (credits.pippit_credits, {"total_remain_amount": "9" * 400}),
    (credits.pippit_credits, {"total_remain_amount": "1" * 16}),
])
def test_unreadable_values_are_never_zero(extract, value):
    with pytest.raises(RouterError) as error:
        extract(value)
    assert error.value.code == "credits_unreadable"


def test_amount_bound_is_inclusive():
    assert credits.higgsfield_credits({"credits": 10**15})["credits"] == 10**15
    assert credits.pippit_credits({"total_remain_amount": "9" * 15})["credits"] == int("9" * 15)
    assert credits.website_credits(xyq_row(1e15))["credits"] == 1e15


@pytest.mark.parametrize("extract,value", [(credits.website_credits, tripo_row(-0.0)),
                                           (credits.higgsfield_credits, {"credits": -0.0}),
                                           (credits.pippit_credits, {"total_remain_amount": -0.0})])
def test_negative_zero_is_a_plain_zero(extract, value):
    result = extract(value)
    assert result["credits"] == 0 and math.copysign(1, result["credits"]) == 1
    assert "-0" not in json.dumps(result)


def test_registry_is_fixed():
    assert list(credits.PROVIDERS) == ["tripo_studio", "xyq", "higgsfield"]
    assert credits.PROVIDERS["tripo_studio"]["sources"] == ("tripo.studio.account", "tripo.server.account")
    assert credits.PROVIDERS["xyq"]["sources"] == ("pippit.cli.credit_balance", "xyq.web.account")
    assert credits.PROVIDERS["higgsfield"]["sources"] == ("higgsfield.subscription.account",)
    assert {s for p in credits.PROVIDERS.values() for s in p["sources"]} == set(credits.SOURCES)
    assert [credits.PROVIDERS[p]["brand"] for p in credits.PROVIDERS] == ["tripo", "xyq", "higgsfield"]


# --- Renewal day -------------------------------------------------------------------

@pytest.mark.parametrize("day,today,expected", [
    (31, date(2027, 2, 10), date(2027, 2, 28)),   # month-end clamp
    (31, date(2028, 2, 10), date(2028, 2, 29)),   # leap year
    (29, date(2027, 2, 28), date(2027, 2, 28)),   # clamped day is today
    (15, date(2026, 10, 15), date(2026, 10, 15)),  # today == day
    (15, date(2026, 10, 16), date(2026, 11, 15)),
    (30, date(2027, 1, 31), date(2027, 2, 28)),
    (31, date(2027, 3, 1), date(2027, 3, 31)),
    (1, date(2026, 12, 2), date(2027, 1, 1)),     # year rollover
    (31, date(2026, 12, 31), date(2026, 12, 31)),
])
def test_next_cycle_date_math(day, today, expected):
    assert credits.next_cycle(day, today) == expected


@pytest.mark.parametrize("day", [0, 32, -1, True, "5", 5.0, [5]])
def test_cycle_day_rejects_non_days(home, day):
    with pytest.raises(RouterError) as error:
        credits.set_cycle(home, "xyq", day)
    assert error.value.code == "invalid_cycle_day"
    assert home.state.setting("credits_cycle:xyq") is None


def test_cycle_set_shown_and_cleared(home):
    row = credits.set_cycle(home, "higgsfield", 31)
    assert row["cycle_day"] == 31
    assert row["next_cycle"] == {"date": credits.next_cycle(31, date.today()).isoformat(), "source": "owner"}
    assert credits.row(home, "higgsfield", today=date(2027, 2, 3))["next_cycle"]["date"] == "2027-02-28"
    cleared = credits.set_cycle(home, "higgsfield", None)
    assert cleared["cycle_day"] is None and cleared["next_cycle"] is None
    with home.state.db() as db:
        assert db.execute("SELECT count(*) FROM settings WHERE name LIKE 'credits_cycle:%'").fetchone()[0] == 0
    with pytest.raises(RouterError) as error:
        credits.set_cycle(home, "acme", 3)
    assert error.value.code == "unknown_provider"


# --- Usable sources ----------------------------------------------------------------

def test_no_source_reports_not_installed_and_runs_nothing(home, fakes):
    rows = credits.payload(home)["providers"]
    assert [r["provider"] for r in rows] == ["tripo_studio", "xyq", "higgsfield"]
    assert all(not r["installed"] and r["status"] == "not_installed" and r["credits"] is None for r in rows)
    result = credits.refresh(home, "xyq")
    assert result["refresh"] == "not_installed" and home.state.jobs() == []
    assert home.state.setting("credits:xyq") is None and fakes.calls() == []


def test_preference_order_and_disabled_tool_skipped(home, tmp_path):
    tools = definitions(home.state.home)
    for tool_id in ["xyq.web.account", "pippit.cli.credit_balance", "tripo.server.account", "tripo.studio.account"]:
        install_tool(home, tools[tool_id])
    assert credits.usable_source(home, "xyq")["id"] == "pippit.cli.credit_balance"
    assert credits.usable_source(home, "tripo_studio")["id"] == "tripo.studio.account"
    mg.set_enabled(home, "pippit.cli.credit_balance", False, apply=True)
    mg.set_enabled(home, "tripo.studio.account", False, apply=True)
    assert credits.usable_source(home, "xyq")["id"] == "xyq.web.account"
    assert credits.usable_source(home, "tripo_studio")["id"] == "tripo.server.account"
    mg.set_enabled(home, "xyq.web.account", False, apply=True)
    assert credits.usable_source(home, "xyq") is None
    row = credits.row(home, "xyq")
    assert row["installed"] is False and row["status"] == "not_installed"


@pytest.mark.parametrize("change", [{"paid": True}, {"permissions": ["execute_code", "external_write"]},
                                    {"permissions": ["execute_code", "production"]}])
def test_swapped_definition_that_could_spend_or_write_is_refused(home, fakes, change):
    install_tool(home, {**json.loads(PIPPIT.read_text()), **change})
    fakes.bind(home, "xyq")
    fakes.output("xyq", {"total_remain_amount": "9"})
    assert credits.usable_source(home, "xyq") is None
    assert credits.refresh(home, "xyq")["refresh"] == "not_installed"
    assert fakes.calls() == [] and home.state.jobs() == []


def test_non_command_definition_is_refused(home):
    home.catalog.tools["pippit.cli.credit_balance"] = {**json.loads(PIPPIT.read_text()), "adapter": "rest"}
    assert credits.usable_source(home, "xyq") is None


@pytest.mark.parametrize("change", [
    {"credential": "xyq.session"},
    {"command": {"argv": ["get-credit-balance"], "output": "json", "timeout": 60,
                 "credential_env": {"PIPPIT_TOKEN": "xyq.session"}}},
])
def test_swapped_definition_that_reads_a_credential_is_refused(home, fakes, change):
    install_tool(home, {**json.loads(PIPPIT.read_text()), **change})
    fakes.bind(home, "xyq")
    fakes.output("xyq", {"total_remain_amount": "9"})
    assert credits.usable_source(home, "xyq") is None
    assert credits.refresh(home, "xyq")["refresh"] == "not_installed"
    assert fakes.calls() == [] and home.state.jobs() == []


def with_argv(tool, argv):
    return {"command": {**tool["command"], "argv": argv}}


def replaced(tool, old, new):
    return with_argv(tool, [new if item == old else item for item in tool["command"]["argv"]])


@pytest.mark.parametrize("tool_id,change", [
    ("pippit.cli.credit_balance", lambda tool, home: {"executable": "pippit-tool-cli"}),
    ("pippit.cli.credit_balance", lambda tool, home: {"executable": "higgsfield"}),
    ("pippit.cli.credit_balance", lambda tool, home: with_argv(tool, ["get-credit-balance", "--all"])),
    ("higgsfield.subscription.account", lambda tool, home: with_argv(tool, ["account", "status"])),
    ("higgsfield.subscription.account", lambda tool, home: replaced(tool, "account", "generate")),
    ("tripo.studio.account", lambda tool, home: replaced(tool, "account", "assets")),
    ("tripo.studio.account", lambda tool, home: replaced(tool, tool["command"]["argv"][4], "0" * 63)),
    ("tripo.studio.account", lambda tool, home: with_argv(tool, [*tool["command"]["argv"], "--confirm"])),
    ("tripo.studio.account", lambda tool, home: {"executable": "atm"}),
    ("xyq.web.account", lambda tool, home: replaced(tool, "xyq-web", "tripo-studio")),
    ("xyq.web.account", lambda tool, home: replaced(tool, "json", "text")),
    ("tripo.server.account", lambda tool, home: replaced(tool, str(home), str(home.parent / "other"))),
    ("tripo.server.account", lambda tool, home: replaced(tool, "adapter", "login")),
    ("tripo.server.account", lambda tool, home: {"executable": "opencliapp"}),
    # Well-formed but not the reviewed pin, bundle or namespace pair.
    ("tripo.studio.account", lambda tool, home: replaced(tool, tool["command"]["argv"][4], "a" * 64)),
    ("tripo.server.account", lambda tool, home: replaced(tool, tool["command"]["argv"][8], "a" * 64)),
    ("tripo.server.account", lambda tool, home: replaced(tool, tool["command"]["argv"][5], "b" * 64)),
    ("xyq.web.account", lambda tool, home: replaced(tool, tool["command"]["argv"][4], "c" * 64)),
    ("xyq.web.account", lambda tool, home: replaced(tool, tool["command"]["argv"][4], credits.XYQ_ACCOUNT_PINS["xyq-media"])),
    ("xyq.web.account", lambda tool, home: replaced(tool, "xyq-web", "xyq-media")),
    # Output mode, timeout and extra command fields are part of the reviewed command too.
    ("xyq.web.account", lambda tool, home: {"command": {**tool["command"], "output": "text"}}),
    ("pippit.cli.credit_balance", lambda tool, home: {"command": {**tool["command"], "output": "text"}}),
    ("higgsfield.subscription.account", lambda tool, home: {"command": {**tool["command"], "timeout": 900}}),
    ("tripo.studio.account", lambda tool, home: {"command": {k: v for k, v in tool["command"].items() if k != "timeout"}}),
    ("tripo.server.account", lambda tool, home: {"command": {**tool["command"], "outputs": ["account.json"]}}),
])
def test_same_id_with_another_executable_or_argv_is_refused(home, fakes, tool_id, change):
    tool = definitions(home.state.home)[tool_id]
    assert credits.reviewed(tool, home.state.home)  # The reviewed definition itself is accepted.
    swapped = validate_manifest({**tool, **change(tool, home.state.home)})
    assert not credits.reviewed(swapped, home.state.home)
    install_tool(home, swapped)
    fakes.bind(home, swapped["executable"])
    fakes.output(swapped["executable"], {"credits": 5, "total_remain_amount": "5"})
    name = next(p for p, spec in credits.PROVIDERS.items() if tool_id in spec["sources"])
    assert credits.usable_source(home, name) is None
    assert credits.refresh(home, name)["refresh"] == "not_installed"
    assert fakes.calls() == [] and home.state.jobs() == []


def test_reviewed_xyq_account_pins_match_both_builds(tmp_path):
    # Recomputed from the adapter sources: drift fails here until the new pins are reviewed in credits.py.
    assert credits.XYQ_ACCOUNT_PINS == {"xyq-web": XYQ.bundle_digest(),
                                        "xyq-media": RUNTIME.bundle_digest(RUNTIME.MEDIA_RUNTIME_FILES)}
    web, media = XYQ.manifest("account"), RUNTIME.runtime_manifest("account")
    assert web["id"] == media["id"] == "xyq.web.account"
    assert (web["command"]["argv"][1], media["command"]["argv"][1]) == ("xyq-web", "xyq-media")
    assert credits.reviewed(web, tmp_path) and credits.reviewed(media, tmp_path)


def test_reviewed_tripo_account_pin_comes_from_the_packaged_server_index(tmp_path):
    from agent_tool_maker.studio_cli import manifests
    from agent_tool_maker.studio_runtime import bundle_digest, index
    packaged = index()["account"]["command"]
    assert TRIPO.manifest("account")["command"] == packaged  # The local adapter build pins the same sources.
    server = next(t for t in manifests(tmp_path) if t["id"] == "tripo.server.account")
    assert server["command"]["argv"][4:6] == ["--bundle", bundle_digest()]
    assert server["command"]["argv"][7:9] == ["--pin", packaged["argv"][4]]
    assert credits.reviewed(TRIPO.manifest("account"), tmp_path) and credits.reviewed(server, tmp_path)
    assert not credits.reviewed(server, tmp_path / "other-home")


def test_xyq_media_runtime_account_refreshes(home, fakes):
    install_tool(home, RUNTIME.runtime_manifest("account"))
    fakes.bind(home, "opencliapp")
    fakes.output("opencliapp", xyq_row(55))
    assert credits.refresh(home, "xyq")["credits"] == 55
    assert fakes.calls()[0]["argv"] == ["__opencli_shim", "xyq-media", "account", "--pin",
                                        credits.XYQ_ACCOUNT_PINS["xyq-media"], "-f", "json"]


def test_rows_show_the_next_source_and_whether_it_is_bound(home, fakes):
    rows = credits.payload(home)["providers"]
    assert [(r["next_source"], r["next_source_kind"], r["next_executable"], r["bound"]) for r in rows] == [
        (None, None, None, False)] * 3
    tools = definitions(home.state.home)
    install_tool(home, tools["pippit.cli.credit_balance"])
    install_tool(home, tools["xyq.web.account"])
    row = credits.row(home, "xyq")
    assert (row["installed"], row["next_source"], row["next_source_kind"], row["next_executable"], row["bound"]) == (
        True, "pippit.cli.credit_balance", "cli", "xyq", False)
    fakes.bind(home, "xyq")
    assert credits.row(home, "xyq")["bound"] is True
    # The stored value came from the website; the next refresh runs the CLI again.
    mg.set_enabled(home, "pippit.cli.credit_balance", False, apply=True)
    fakes.bind(home, "opencliapp")
    fakes.output("opencliapp", xyq_row(880))
    website = credits.refresh(home, "xyq")
    assert (website["source"], website["next_source"], website["next_source_kind"], website["next_executable"],
            website["bound"]) == ("xyq.web.account", "xyq.web.account", "website", "opencliapp", True)
    mg.set_enabled(home, "pippit.cli.credit_balance", True, apply=True)
    row = credits.row(home, "xyq")
    assert (row["source"], row["source_kind"], row["next_source"], row["next_source_kind"]) == (
        "xyq.web.account", "website", "pippit.cli.credit_balance", "cli")
    (fakes.root / "fake-xyq").unlink()
    assert credits.row(home, "xyq")["bound"] is False


# --- Refresh through the real Router and fake subprocesses ------------------------------

def test_refresh_each_provider_with_fake_executables(home, fakes):
    tools = definitions(home.state.home)
    for tool_id in ["tripo.studio.account", "pippit.cli.credit_balance", "higgsfield.subscription.account"]:
        install_tool(home, tools[tool_id])
    fakes.bind(home, "opencliapp")
    fakes.bind(home, "xyq")
    fakes.bind(home, "higgsfield")
    fakes.output("opencliapp", tripo_row(6396))
    fakes.output("xyq", {"total_remain_amount": "4321"})
    fakes.output("higgsfield", HIGGSFIELD)
    results = {name: credits.refresh(home, name, clock=lambda: 1000) for name in credits.PROVIDERS}
    assert {n: (r["refresh"], r["credits"], r["plan"]) for n, r in results.items()} == {
        "tripo_studio": ("ok", 6396, None), "xyq": ("ok", 4321, None), "higgsfield": ("ok", 1234, "pro")}
    assert home.state.setting("credits:higgsfield") == {
        "provider": "higgsfield", "status": "ok", "credits": 1234, "plan": "pro", "unit": "credits",
        "source": "higgsfield.subscription.account", "checked_at": 1000, "last_ok_at": 1000, "error": None}
    assert results["tripo_studio"]["source_kind"] == "website" and results["xyq"]["source_kind"] == "cli"
    calls = fakes.calls()
    assert [c["argv"][:3] for c in calls] == [["__opencli_shim", "tripo-studio", "account"],
                                             ["get-credit-balance"], ["account", "status", "--json"]]
    # Each run used a private workspace outside the ATM home, removed afterwards.
    for call in calls:
        cwd = Path(call["cwd"])
        assert not cwd.is_relative_to(home.state.home.resolve()) and cwd.name.startswith("atm-credits-")
        assert not cwd.exists()
    jobs = home.state.jobs()
    assert sorted(j["tool"] for j in jobs) == ["higgsfield.subscription.account", "pippit.cli.credit_balance", "tripo.studio.account"]
    assert all(re.fullmatch(r"credits-(tripo_studio|xyq|higgsfield)-[0-9a-f]{32}", j["request_key"]) for j in jobs)
    assert all(j["status"] == "completed" and j["data"]["result"] is None and j["data"]["artifacts"] == [] for j in jobs)


def test_no_email_or_raw_output_is_stored(home, fakes):
    install_tool(home, definitions(home.state.home)["higgsfield.subscription.account"])
    fakes.bind(home, "higgsfield")
    fakes.output("higgsfield", HIGGSFIELD)
    assert credits.refresh(home, "higgsfield")["credits"] == 1234
    with home.state.db() as db:
        stored = [tuple(r) for table in ("settings", "jobs", "events")
                  for r in db.execute(f"SELECT * FROM {table}").fetchall()]  # noqa: S608 - fixed names
    text = json.dumps(stored, default=str)
    assert EMAIL not in text and "FAKE-USER-ID" not in text
    files = [p for p in home.state.home.rglob("*") if p.is_file() and p.name != "state.sqlite3"]
    assert all(EMAIL.encode() not in p.read_bytes() for p in files)
    assert EMAIL not in json.dumps(credits.payload(home))


def test_fresh_request_key_per_refresh_and_error_keeps_last_good_value(home, fakes, monkeypatch):
    install_tool(home, definitions(home.state.home)["pippit.cli.credit_balance"])
    fakes.bind(home, "xyq")
    seen = []
    real = home.run
    def spy(*args, **kwargs):
        seen.append(kwargs)
        return real(*args, **kwargs)
    monkeypatch.setattr(home, "run", spy)
    fakes.output("xyq", {"total_remain_amount": "123"})
    assert credits.refresh(home, "xyq", clock=lambda: 1000)["credits"] == 123
    fakes.output("xyq", {"other": "1"})
    failed = credits.refresh(home, "xyq", clock=lambda: 2000)
    assert failed["refresh"] == "error" and failed["status"] == "error"
    assert failed["error"]["code"] == "credits_unreadable"
    assert (failed["credits"], failed["checked_at"], failed["last_ok_at"]) == (123, 2000, 1000)
    (fakes.root / "xyq.exit").write_text("4")
    crashed = credits.refresh(home, "xyq", clock=lambda: 3000)
    assert crashed["error"]["code"] == "cli_failed" and crashed["credits"] == 123 and crashed["last_ok_at"] == 1000
    assert "FAKE_STDERR_SECRET" not in json.dumps(crashed)
    (fakes.root / "xyq.exit").unlink()
    fakes.output("xyq", {"total_remain_amount": "0"})
    recovered = credits.refresh(home, "xyq", clock=lambda: 4000)
    assert (recovered["status"], recovered["credits"], recovered["error"], recovered["last_ok_at"]) == ("ok", 0, None, 4000)
    assert len(fakes.calls()) == 4
    keys = [kw["request_key"] for kw in seen]
    assert len(set(keys)) == 4 and all(k.startswith("credits-xyq-") for k in keys)
    assert all(kw["grants"] == ["execute_code"] and kw["allow_paid"] is False for kw in seen)


def test_absurd_balance_is_an_error_not_a_crash(home, fakes):
    install_tool(home, definitions(home.state.home)["higgsfield.subscription.account"])
    fakes.bind(home, "higgsfield")
    fakes.output("higgsfield", {**HIGGSFIELD, "credits": 10**400})
    result = credits.refresh(home, "higgsfield")
    assert (result["refresh"], result["error"]["code"], result["credits"]) == ("error", "credits_unreadable", None)
    assert len(fakes.calls()) == 1


def test_changed_binary_is_an_error_not_a_run(home, fakes):
    install_tool(home, definitions(home.state.home)["higgsfield.subscription.account"])
    fakes.bind(home, "higgsfield")
    script = fakes.root / "fake-higgsfield"
    script.write_text(script.read_text() + "\n# changed fixture build\n")
    result = credits.refresh(home, "higgsfield")
    assert result["error"]["code"] == "executable_changed" and result["credits"] is None
    assert fakes.calls() == []


def test_xyq_website_and_tripo_server_sources(home, fakes):
    tools = definitions(home.state.home)
    install_tool(home, tools["xyq.web.account"])
    install_tool(home, tools["tripo.server.account"])
    fakes.bind(home, "opencliapp")
    fakes.bind(home, "atm")
    fakes.output("opencliapp", xyq_row(880))
    fakes.output("atm", tripo_row(70))
    assert credits.refresh(home, "xyq")["credits"] == 880
    server = credits.refresh(home, "tripo_studio")
    assert (server["credits"], server["source"], server["source_kind"]) == (70, "tripo.server.account", "website")
    argv = fakes.calls()[1]["argv"]
    assert argv[:4] == ["--home", str(home.state.home), "studio", "adapter"] and "account" in argv
    # The server runtime refuses workspaces inside its state home.
    assert not Path(fakes.calls()[1]["cwd"]).is_relative_to(home.state.home.resolve())


def test_concurrent_refresh_of_one_provider_is_refused(home, fakes):
    install_tool(home, definitions(home.state.home)["pippit.cli.credit_balance"])
    fakes.bind(home, "xyq")
    fakes.output("xyq", {"total_remain_amount": "5"})
    gate = fakes.root / "xyq.gate"
    gate.write_text("hold")
    results = []
    worker = threading.Thread(target=lambda: results.append(credits.refresh(home, "xyq")))
    worker.start()
    deadline = time.time() + 15
    while not (fakes.root / "xyq.started").exists() and time.time() < deadline:
        time.sleep(0.02)
    with pytest.raises(RouterError) as busy:
        credits.refresh(home, "xyq")
    assert busy.value.code == "refresh_in_progress"
    gate.unlink()
    worker.join(20)
    assert results[0]["credits"] == 5 and len(fakes.calls()) == 1


def leftover(state, key, result, tool="higgsfield.subscription.account"):
    """A job as a refresh that crashed before discarding its output would leave it."""
    job, _ = state.create_job(tool, {}, state.home.parent / "gone", key)
    return state.update_job(job["id"], "completed", result=result, artifacts=[{"path": "out.json"}])


def test_leftover_raw_output_is_discarded_when_viewing(home):
    crashed = leftover(home.state, "credits-higgsfield-" + "0" * 32, HIGGSFIELD)
    unrelated = leftover(home.state, "user-task-1", {"note": "kept"})
    payload = credits.payload(home)
    assert EMAIL not in json.dumps(payload)
    data = home.state.job(crashed["id"])["data"]
    assert (data["result"], data["artifacts"], data["raw_output_discarded"]) == (None, [], True)
    assert home.state.job(unrelated["id"])["data"]["result"] == {"note": "kept"}  # Only credits jobs.
    with home.state.db() as db:
        assert EMAIL not in json.dumps([tuple(r) for r in db.execute("SELECT * FROM jobs").fetchall()])


def test_leftover_raw_output_is_discarded_before_running(home, fakes):
    install_tool(home, definitions(home.state.home)["pippit.cli.credit_balance"])
    fakes.bind(home, "xyq")
    fakes.output("xyq", {"total_remain_amount": "5"})
    crashed = leftover(home.state, "credits-xyq-" + "1" * 32, HIGGSFIELD)
    gate = fakes.root / "xyq.gate"
    gate.write_text("hold")
    results = []
    worker = threading.Thread(target=lambda: results.append(credits.refresh(home, "xyq")))
    worker.start()
    deadline = time.time() + 15
    while not (fakes.root / "xyq.started").exists() and time.time() < deadline:
        time.sleep(0.02)
    try:
        assert (fakes.root / "xyq.started").exists()
        data = home.state.job(crashed["id"])["data"]  # Already gone while the tool runs.
        assert (data["result"], data["artifacts"], data["raw_output_discarded"]) == (None, [], True)
    finally:
        gate.unlink()
        worker.join(20)
    assert results[0]["credits"] == 5


def test_only_refresh_jobs_are_leftovers(home, capsys):
    # A refresh job is one of the fixed sources with credits-<provider>-<32 lowercase hex>; nothing else is touched.
    kept = [leftover(home.state, key, {"note": "kept"}, tool) for tool, key in [
        ("higgsfield.subscription.account", "credits-mytask"),
        ("higgsfield.subscription.account", "credits-acme-" + "0" * 32),
        ("higgsfield.subscription.account", "credits-higgsfield-" + "A" * 32),
        ("higgsfield.subscription.account", "credits-higgsfield-" + "0" * 31),
        ("higgsfield.subscription.account", "credits-higgsfield-" + "0" * 32 + "-x"),
        ("fal.generate", "credits-higgsfield-" + "3" * 32)]]
    done = leftover(home.state, "credits-higgsfield-" + "4" * 32, None)
    home.state.update_job(done["id"], "completed", result=None, artifacts=[], raw_output_discarded=True)
    before = home.state.job(done["id"])["updated"]
    credits.payload(home)
    for job in kept:
        data = home.state.job(job["id"])["data"]
        assert (data["result"], data["artifacts"], "raw_output_discarded" in data) == ({"note": "kept"}, [{"path": "out.json"}], False)
    assert home.state.job(done["id"])["updated"] == before  # Already discarded: not rewritten.
    code, listed = run_cli(capsys, home.state.home, "jobs", "list")
    assert code == 0
    assert sorted(j["id"] for j in listed["jobs"] if j["data"]["result"] == {"note": "kept"}) == sorted(j["id"] for j in kept)


class Crash(BaseException):
    """Stands in for the process dying: no except or finally block of the refresh runs after it."""


def crash_after_completed_job(home, monkeypatch, name):
    real = home.run
    def run(*args, **kwargs):
        real(*args, **kwargs)
        raise Crash
    with monkeypatch.context() as patch:
        patch.setattr(home, "run", run)
        patch.setattr(credits.shutil, "rmtree", lambda *args, **kwargs: None)
        with pytest.raises(Crash):
            credits.refresh(home, name)
    return next(j for j in home.state.jobs() if j["request_key"].startswith(f"credits-{name}-"))


def test_crash_after_a_completed_job_leaves_no_raw_output_files(home, fakes, monkeypatch, capsys):
    install_tool(home, definitions(home.state.home)["higgsfield.subscription.account"])
    fakes.bind(home, "higgsfield")
    fakes.output("higgsfield", HIGGSFIELD)
    job = crash_after_completed_job(home, monkeypatch, "higgsfield")
    workspace, files = Path(job["workspace"]), [Path(a["path"]) for a in job["data"]["artifacts"]]
    # The crash left the raw account output in the record and in its private temporary workspace ...
    assert workspace.parent == Path(tempfile.gettempdir()).resolve() and workspace.name.startswith("atm-credits-")
    assert files and all(f.is_relative_to(workspace) and EMAIL.encode() in f.read_bytes() for f in files)
    assert job["data"]["result"]["email"] == EMAIL
    # ... which no job reader returns, even before the cleanup has run.
    code, listed = run_cli(capsys, home.state.home, "jobs", "list")
    assert code == 0 and EMAIL not in json.dumps(listed)
    assert (listed["jobs"][0]["data"]["result"], listed["jobs"][0]["data"]["artifacts"]) == (None, [])
    assert mg.recent_jobs(home)["jobs"][0]["artifact_count"] == 0
    assert EMAIL not in json.dumps(credits.payload(home))
    assert not workspace.exists() and not any(f.exists() for f in files)
    data = home.state.job(job["id"])["data"]
    assert (data["result"], data["artifacts"], data["raw_output_discarded"], data["raw_output_files"]) == (
        None, [], True, "removed")
    code, got = run_cli(capsys, home.state.home, "jobs", "get", job["id"])
    assert code == 0 and EMAIL not in json.dumps(got)
    # A crash before the next refresh is cleaned by that refresh before it runs.
    job = crash_after_completed_job(home, monkeypatch, "higgsfield")
    assert Path(job["workspace"]).is_dir()
    assert credits.refresh(home, "higgsfield")["credits"] == 1234
    assert not Path(job["workspace"]).exists() and home.state.job(job["id"])["data"]["raw_output_files"] == "removed"
    with home.state.db() as db:
        assert EMAIL not in json.dumps([tuple(r) for r in db.execute("SELECT * FROM jobs").fetchall()])


@pytest.mark.parametrize("where", ["elsewhere", "symlink", "other_name", "other_owner"])
def test_crash_cleanup_leaves_files_it_cannot_verify(home, tmp_path, monkeypatch, where):
    temporary = Path(tempfile.gettempdir()).resolve()
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.json").write_text(EMAIL)
    workspace = {"elsewhere": tmp_path / "atm-credits-elsewhere", "symlink": temporary / f"atm-credits-{uuid.uuid4().hex}",
                 "other_name": temporary / f"user-{uuid.uuid4().hex}", "other_owner": temporary / f"atm-credits-{uuid.uuid4().hex}"}[where]
    if where == "symlink":
        workspace.symlink_to(victim, target_is_directory=True)
    else:
        workspace.mkdir()
        (workspace / "keep.json").write_text(EMAIL)
    try:
        job, _ = home.state.create_job("higgsfield.subscription.account", {}, workspace, "credits-higgsfield-" + "5" * 32)
        home.state.update_job(job["id"], "completed", result=HIGGSFIELD, artifacts=[{"path": str(workspace / "keep.json")}])
        with monkeypatch.context() as patch:
            if where == "other_owner":
                patch.setattr(credits.os, "getuid", lambda real=os.getuid(): real + 1)
            assert EMAIL not in json.dumps(credits.payload(home))
        assert (workspace / "keep.json").read_text() == EMAIL and (victim / "keep.json").read_text() == EMAIL
        data = home.state.job(job["id"])["data"]
        assert (data["result"], data["artifacts"], data["raw_output_discarded"], data["raw_output_files"]) == (
            None, [], True, "left_in_place")
    finally:
        workspace.unlink() if workspace.is_symlink() else shutil.rmtree(workspace, ignore_errors=True)


HOLDER = """
import fcntl, os, sys
os.makedirs(os.path.dirname(sys.argv[1]), mode=0o755, exist_ok=True)
fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR, 0o644)
fcntl.flock(fd, fcntl.LOCK_EX)
print("held", flush=True)
sys.stdin.read()
"""


def test_refresh_lease_is_held_across_processes(home, fakes):
    tools = definitions(home.state.home)
    install_tool(home, tools["pippit.cli.credit_balance"])
    install_tool(home, tools["higgsfield.subscription.account"])
    fakes.bind(home, "xyq")
    fakes.bind(home, "higgsfield")
    fakes.output("xyq", {"total_remain_amount": "5"})
    fakes.output("higgsfield", HIGGSFIELD)
    lock = home.state.home / "locks" / "credits-xyq.lock"
    holder = subprocess.Popen([sys.executable, "-I", "-c", HOLDER, str(lock)], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(RouterError) as busy:
            credits.refresh(home, "xyq")
        assert busy.value.code == "refresh_in_progress"
        assert fakes.calls() == [] and home.state.jobs() == []
        assert credits.refresh(home, "higgsfield")["credits"] == 1234  # The lease is per provider.
    finally:
        holder.stdin.close()
        holder.wait(10)
    assert credits.refresh(home, "xyq")["credits"] == 5
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600 and stat.S_IMODE(lock.parent.stat().st_mode) == 0o700


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_refresh_lock_must_be_a_private_regular_file(home, fakes, tmp_path, kind):
    install_tool(home, definitions(home.state.home)["pippit.cli.credit_balance"])
    fakes.bind(home, "xyq")
    fakes.output("xyq", {"total_remain_amount": "5"})
    victim = tmp_path / "victim.txt"
    victim.write_text("owner file")
    victim.chmod(0o644)
    lock = home.state.home / "locks" / "credits-xyq.lock"
    lock.parent.mkdir(mode=0o700, exist_ok=True)
    {"symlink": lambda: lock.symlink_to(victim), "hardlink": lambda: os.link(victim, lock),
     "fifo": lambda: os.mkfifo(lock)}[kind]()
    with pytest.raises(RouterError) as error:
        credits.refresh(home, "xyq")
    assert error.value.code == "unsafe_path"
    assert stat.S_IMODE(victim.stat().st_mode) == 0o644 and victim.read_text() == "owner file"
    assert fakes.calls() == [] and home.state.jobs() == [] and home.state.setting("credits:xyq") is None


# --- CLI ---------------------------------------------------------------------------

def run_cli(capsys, home_dir, *argv):
    code = main(["--home", str(home_dir), *argv])
    return code, json.loads(capsys.readouterr().out)


def test_cli_lists_refreshes_and_sets_cycle_with_exit_codes(home, fakes, capsys):
    install_tool(home, definitions(home.state.home)["pippit.cli.credit_balance"])
    fakes.bind(home, "xyq")
    directory = home.state.home
    code, listed = run_cli(capsys, directory, "credits")
    assert code == 0 and [r["status"] for r in listed["providers"]] == ["not_installed", "not_read", "not_installed"]
    assert fakes.calls() == []  # Listing never runs a tool.
    fakes.output("xyq", {"total_remain_amount": "77"})
    code, refreshed = run_cli(capsys, directory, "credits", "refresh")
    assert code == 0 and refreshed["status"] == "ok"
    assert {r["provider"]: r["refresh"] for r in refreshed["providers"]} == {
        "tripo_studio": "not_installed", "xyq": "ok", "higgsfield": "not_installed"}
    code, only = run_cli(capsys, directory, "credits", "refresh", "higgsfield")
    assert code == 0 and [r["refresh"] for r in only["providers"]] == ["not_installed"]
    fakes.output("xyq", {})
    code, failed = run_cli(capsys, directory, "credits", "refresh", "xyq")
    assert code == 2 and failed["status"] == "failed" and failed["providers"][0]["credits"] == 77
    calls = len(fakes.calls())
    code, typo = run_cli(capsys, directory, "credits", "refresh", "xyq", "acme")
    assert code == 2 and typo["error"]["code"] == "unknown_provider" and len(fakes.calls()) == calls
    code, cycle = run_cli(capsys, directory, "credits", "cycle", "xyq", "--day", "31")
    assert code == 0 and cycle["cycle_day"] == 31 and cycle["next_cycle"]["source"] == "owner"
    code, bad = run_cli(capsys, directory, "credits", "cycle", "xyq", "--day", "32")
    assert code == 2 and bad["error"]["code"] == "invalid_cycle_day"
    code, cleared = run_cli(capsys, directory, "credits", "cycle", "xyq", "--clear")
    assert code == 0 and cleared["next_cycle"] is None
    with pytest.raises(SystemExit):
        main(["--home", str(directory), "credits", "cycle", "xyq"])
    capsys.readouterr()


def test_cli_refresh_reports_a_busy_provider_and_continues(home, fakes, capsys):
    tools = definitions(home.state.home)
    install_tool(home, tools["pippit.cli.credit_balance"])
    install_tool(home, tools["higgsfield.subscription.account"])
    fakes.bind(home, "xyq")
    fakes.bind(home, "higgsfield")
    fakes.output("xyq", {"total_remain_amount": "5"})
    fakes.output("higgsfield", HIGGSFIELD)
    lock = home.state.home / "locks" / "credits-xyq.lock"
    holder = subprocess.Popen([sys.executable, "-I", "-c", HOLDER, str(lock)], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        code, result = run_cli(capsys, home.state.home, "credits", "refresh", "xyq", "higgsfield", "tripo_studio")
    finally:
        holder.stdin.close()
        holder.wait(10)
    assert code == 2 and result["status"] == "failed"
    assert [(r["provider"], r["refresh"]) for r in result["providers"]] == [
        ("xyq", "error"), ("higgsfield", "ok"), ("tripo_studio", "not_installed")]
    busy = result["providers"][0]
    assert busy["error"]["code"] == "refresh_in_progress" and busy["credits"] is None
    assert result["providers"][1]["credits"] == 1234
    assert [c["exe"] for c in fakes.calls()] == ["higgsfield"]
    assert home.state.setting("credits:xyq") is None  # Nothing is stored for the provider that did not run.


def test_extension_manifest_validates_installs_and_binds(tmp_path, capsys):
    tool = validate_manifest(read_manifest(PIPPIT))
    assert (tool["id"], tool["provider"], tool["executable"]) == ("pippit.cli.credit_balance", "xyq", "xyq")
    assert tool["paid"] is False and tool["permissions"] == ["execute_code"]
    assert tool["command"] == {"argv": ["get-credit-balance"], "output": "json", "timeout": 60}
    assert "credential" not in tool and "credential_env" not in tool["command"]
    assert tool["schema"]["additionalProperties"] is False and "total_remain_amount" in tool["notes"]
    directory = tmp_path / "state"
    code, checked = run_cli(capsys, directory, "make", "validate", str(PIPPIT))
    assert code == 0 and checked["sha256"] == digest(tool) and checked["execution_started"] is False
    code, installed = run_cli(capsys, directory, "make", "install", str(PIPPIT), "--approve", checked["sha256"])
    assert code == 0 and installed["installed"] == "pippit.cli.credit_balance"
    fake = tmp_path / "pippit-tool-cli"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o700)
    code, bound = run_cli(capsys, directory, "cli", "bind", "xyq", str(fake))
    assert code == 0 and bound["bound"] == "xyq"
    router = Router(directory)
    try:
        # The same reviewed binding of pippit-tool-cli as the built-in XYQ tools.
        tools = router.catalog.tools
        assert tools["xyq.image"]["executable"] == tools["xyq.video"]["executable"] == tool["executable"]
        assert credits.row(router, "xyq")["bound"] is True
    finally:
        router.close()


def test_skill_and_docs_describe_cached_owner_refresh():
    skill = (ROOT / "SKILL.md").read_text()
    assert skill == (ROOT / "src/agent_tool_maker/data/SKILL.md").read_text()
    assert "atm credits" in skill and "only refresh when the owner asks" in skill
    doc = (ROOT / "docs/SUBSCRIPTION_CREDITS.md").read_text()
    assert "pippit.cli.credit_balance" in doc and "credits_cycle:" in doc
    assert "atm cli bind xyq" in doc and "atm cli bind pippit-tool-cli" not in doc
    assert "授予 `execute_code`" in doc and "严格客户端配置" in doc


def test_strict_client_profile_cannot_refresh(home, fakes, capsys, tmp_path):
    install_tool(home, definitions(home.state.home)["pippit.cli.credit_balance"])
    fakes.bind(home, "xyq")
    fakes.output("xyq", {"total_remain_amount": "5"})
    for argv in [("credits", "refresh"), ("credits", "refresh", "xyq"), ("credits",)]:
        code, denied = run_cli(capsys, home.state.home, "--client-profile", str(tmp_path / "client.json"), *argv)
        assert code == 2 and denied["error"]["code"] == "operation_denied"
    assert fakes.calls() == [] and home.state.jobs() == [] and home.state.setting("credits:xyq") is None


# --- Sync stays local ----------------------------------------------------------------

def test_credits_records_never_enter_a_sync_packet(tmp_path):
    from agent_tool_maker.sync import Sync
    from agent_tool_maker.vault import Vault
    nodes = []
    for label in ["laptop", "server"]:
        vault = Vault(State(tmp_path / label), password="test-only-long-passphrase")
        vault.init("passphrase")
        node = Sync(vault)
        node.initialize(label)
        nodes.append(node)
    a, b = nodes
    for x, y in [(a, b), (b, a)]:
        x.trust(y.identity(), y.identity()["id"], send=["fal"], receive=["fal"], apply=True)
    a.vault.put("fal", "FAKE-sync-key")
    a.state.set_setting("credits:xyq", {"provider": "xyq", "status": "ok", "credits": 5})
    a.state.set_setting("credits_cycle:xyq", {"day": 3})
    assert set(a._snapshot(b.identity()["id"])["records"]) == {"fal"}
    b.import_packet(a.export_packet(b.identity()["id"]), apply=True)
    assert b.state.setting("credits:xyq") is None and b.state.setting("credits_cycle:xyq") is None
    assert b.vault.get("fal") == "FAKE-sync-key"


# --- Console routes ----------------------------------------------------------------------

@pytest.fixture
def console(tmp_path, monkeypatch):
    from agent_tool_maker.webapp import Console
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    router = Router(tmp_path / "state")
    fakes = Fakes(tmp_path)
    install_tool(router, definitions(router.state.home)["pippit.cli.credit_balance"])
    fakes.bind(router, "xyq")
    fakes.output("xyq", {"total_remain_amount": "4321"})
    router.close()
    server = Console(tmp_path / "state", user_home=tmp_path / "user")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with httpx.Client(base_url=server.origin, timeout=30, trust_env=False) as client:
        yield server, client, fakes
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def get(console, path, **headers):
    server, client, _ = console
    return client.get(path, headers={"Authorization": "Bearer " + server.token, **headers})


def post(console, path, body, **headers):
    server, client, _ = console
    return client.post(path, json=body, headers={"Authorization": "Bearer " + server.token, "Origin": server.origin, **headers})


def test_web_get_is_cached_only_and_included_in_overview(console):
    fakes = console[2]
    response = get(console, "/api/credits")
    assert response.status_code == 200
    rows = response.json()["providers"]
    assert [r["provider"] for r in rows] == ["tripo_studio", "xyq", "higgsfield"]
    xyq = rows[1]
    assert (xyq["installed"], xyq["source"], xyq["status"], xyq["next_cycle"]) == (True, "pippit.cli.credit_balance", "not_read", None)
    assert set(xyq) >= {"provider", "label", "brand", "installed", "source", "status", "credits", "plan",
                        "checked_at", "last_ok_at", "error", "next_cycle", "cycle_day",
                        "next_source", "next_source_kind", "next_executable", "bound"}
    assert (xyq["next_source"], xyq["next_source_kind"], xyq["bound"]) == ("pippit.cli.credit_balance", "cli", True)
    assert get(console, "/api/overview").json()["credits"] == response.json()
    assert fakes.calls() == []


def test_web_refresh_and_cycle_return_updated_record(console):
    server, _, fakes = console
    refreshed = post(console, "/api/credits/refresh", {"provider": "xyq"})
    assert refreshed.status_code == 200
    assert (refreshed.json()["refresh"], refreshed.json()["credits"]) == ("ok", 4321)
    assert len(fakes.calls()) == 1
    assert post(console, "/api/credits/refresh", {"provider": "higgsfield"}).json()["refresh"] == "not_installed"
    cycle = post(console, "/api/credits/cycle", {"provider": "xyq", "day": 31})
    assert cycle.status_code == 200 and cycle.json()["next_cycle"]["date"] == credits.next_cycle(31, date.today()).isoformat()
    assert post(console, "/api/credits/cycle", {"provider": "xyq", "day": None}).json()["cycle_day"] is None
    for body in [{"provider": "xyq", "day": 0}, {"provider": "xyq", "day": True}, {"provider": "xyq", "day": "5"},
                 {"provider": "xyq"}, {"provider": "acme", "day": 3}, {"provider": "xyq", "day": 3, "extra": 1}]:
        assert post(console, "/api/credits/cycle", body).status_code == 400
    for body in [{}, {"provider": "acme"}, {"provider": "xyq", "tool": "fal.generate"}, {"provider": ["xyq"]}]:
        assert post(console, "/api/credits/refresh", body).status_code == 400
    assert len(fakes.calls()) == 1
    state = State(server.home)
    assert state.setting("credits:xyq")["credits"] == 4321 and state.setting("credits_cycle:xyq") is None


@pytest.mark.parametrize("path,body", [("/api/credits/refresh", {"provider": "xyq"}),
                                       ("/api/credits/cycle", {"provider": "xyq", "day": 3})])
def test_web_writes_require_bearer_and_exact_origin(console, path, body):
    server, client, fakes = console
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers={"Origin": server.origin}).status_code == 401
    assert client.post(path, json=body, headers={"Authorization": "Bearer wrong", "Origin": server.origin}).status_code == 401
    assert client.post(path, json=body, headers={"Authorization": "Bearer " + server.token}).status_code == 403
    for headers in [{"Origin": "https://evil.example"}, {"Origin": "null"}, {"Host": "evil.example"}, {"Sec-Fetch-Site": "cross-site"}]:
        assert post(console, path, body, **headers).status_code == 403
    assert client.post(path, content="provider=xyq", headers={"Authorization": "Bearer " + server.token, "Origin": server.origin,
                                                              "Content-Type": "application/x-www-form-urlencoded"}).status_code == 400
    assert get(console, "/api/credits?provider=xyq").status_code == 403
    assert client.get("/api/credits").status_code == 401
    assert fakes.calls() == [] and State(server.home).setting("credits_cycle:xyq") is None


def test_web_refresh_does_not_block_the_console(console):
    server, client, fakes = console
    gate = fakes.root / "xyq.gate"
    gate.write_text("hold")
    results = []
    worker = threading.Thread(target=lambda: results.append(post(console, "/api/credits/refresh", {"provider": "xyq"})))
    worker.start()
    deadline = time.time() + 15
    while not (fakes.root / "xyq.started").exists() and time.time() < deadline:
        time.sleep(0.02)
    assert (fakes.root / "xyq.started").exists()
    started = time.monotonic()
    assert get(console, "/api/overview").status_code == 200
    assert post(console, "/api/tools/toggle", {"tool": "fal.generate", "enabled": False, "expected_enabled": True}).status_code == 200
    assert time.monotonic() - started < 5
    busy = post(console, "/api/credits/refresh", {"provider": "xyq"})
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "refresh_in_progress"
    gate.unlink()
    worker.join(20)
    assert results[0].status_code == 200 and results[0].json()["credits"] == 4321
    assert len(fakes.calls()) == 1
