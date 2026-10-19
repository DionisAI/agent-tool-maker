"""Owner-refreshed subscription credits from fixed, reviewed read-only account tools.

Viewing reads cached local settings only (and discards raw output a crashed
refresh left behind). A refresh is an explicit owner action:
it runs the first usable source once, with a fresh request key, and keeps only
{credits, plan}. E-mail, identity and raw tool output are never stored. No
provider exposes a renewal date today, so the renewal day is owner-set.
Subscription credits are separate from developer API balances.
"""
from __future__ import annotations

import calendar
import contextlib
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import time
import uuid
from datetime import date

from .errors import RouterError
from .storage import canonical, private_dir

# Fixed registry; owners cannot add providers or sources.
PROVIDERS = {
    "tripo_studio": {"label": "Tripo Studio", "brand": "tripo", "billing": "website subscription",
                     "sources": ("tripo.studio.account", "tripo.server.account")},
    # Prefer the official CLI: it does not drive the browser.
    "xyq": {"label": "小云雀 / Pippit", "brand": "xyq", "billing": "website / CLI subscription",
            "sources": ("pippit.cli.credit_balance", "xyq.web.account")},
    "higgsfield": {"label": "Higgsfield", "brand": "higgsfield", "billing": "CLI subscription",
                   "sources": ("higgsfield.subscription.account",)},
}
SAFE_PERMISSIONS = {"execute_code"}
MAX_CREDITS = 10**15
# Argument slots of a reviewed argv: the adapter pin / server bundle digest, and this ATM home.
DIGEST, HOME = object(), object()


def _unreadable():
    return RouterError("credits_unreadable", "The account tool returned no readable credit balance; nothing was assumed.")


def _amount(value):
    # bool is not a number here; neither is NaN, infinity, a negative or an absurd balance.
    # Integers are bounded before any float math, so a 400-digit value cannot overflow.
    try:
        readable = (type(value) is int and 0 <= value <= MAX_CREDITS
                    or type(value) is float and math.isfinite(value) and 0 <= value <= MAX_CREDITS)
    except OverflowError:
        readable = False
    if readable:
        return value
    raise _unreadable()


def _row(result):
    """OpenCLI adapters print one row; XYQ wraps its row in {"result": ...}."""
    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    if isinstance(result, dict) and set(result) == {"result"}:
        result = result["result"]
    if not isinstance(result, dict):
        raise _unreadable()
    return result


def website_credits(result):
    row = _row(result)
    if row.get("status") != "ready" or row.get("logged_in") is False:
        raise _unreadable()
    return {"credits": _amount(row.get("credits")), "plan": None}


def pippit_credits(result):
    # pippit-tool-cli (bound as xyq) prints {"total_remain_amount": "123"}; "0" is a real zero, absence is not.
    value = _row(result).get("total_remain_amount")
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,15}(?:\.[0-9]{1,6})?", value):
        value = float(value) if "." in value else int(value)
    return {"credits": _amount(value), "plan": None}


def higgsfield_credits(result):
    # Only credits and the plan name are read; e-mail and identity fields are ignored.
    row = _row(result)
    plan = row.get("subscription_plan_type")
    plan = plan if isinstance(plan, str) and re.fullmatch(r"[A-Za-z0-9 _.-]{1,40}", plan) else None
    return {"credits": _amount(row.get("credits")), "plan": plan}


# tool id -> (kind shown to the owner, pure extractor from the job result,
#             reviewed executable alias, reviewed read-only argv)
SOURCES = {
    "tripo.studio.account": ("website", website_credits, "opencliapp",
                             ("__opencli_shim", "tripo-studio", "account", "--pin", DIGEST, "-f", "json")),
    "tripo.server.account": ("website", website_credits, "atm",
                             ("--home", HOME, "studio", "adapter", "--bundle", DIGEST, "account", "--pin", DIGEST, "-f", "json")),
    "xyq.web.account": ("website", website_credits, "opencliapp",
                        ("__opencli_shim", "xyq-web", "account", "--pin", DIGEST, "-f", "json")),
    # The existing reviewed binding of pippit-tool-cli, shared with the built-in xyq.image / xyq.video.
    "pippit.cli.credit_balance": ("cli", pippit_credits, "xyq", ("get-credit-balance",)),
    "higgsfield.subscription.account": ("cli", higgsfield_credits, "higgsfield", ("account", "status", "--json")),
}


def provider(name):
    if not isinstance(name, str) or name not in PROVIDERS:
        raise RouterError("unknown_provider", "Unknown subscription credits provider; run atm credits to list them.")
    return PROVIDERS[name]


def _argument(expected, actual, home):
    if expected is DIGEST:
        return isinstance(actual, str) and re.fullmatch(r"[0-9a-f]{64}", actual) is not None
    return actual == (str(home) if expected is HOME else expected)


def reviewed(tool, home):
    """The same id is not enough: the definition must keep its reviewed read-only shape."""
    _, _, executable, shape = SOURCES[tool["id"]]
    command = tool.get("command") if isinstance(tool.get("command"), dict) else {}
    argv = command.get("argv")
    return (tool.get("adapter") == "command" and tool.get("paid") is False
            and set(tool.get("permissions", [])) <= SAFE_PERMISSIONS
            and not tool.get("credential") and not command.get("credential_env")
            and tool.get("executable") == executable and isinstance(argv, list) and len(argv) == len(shape)
            and all(_argument(want, got, home) for want, got in zip(shape, argv)))


def usable_source(router, name):
    """First installed, enabled source that keeps its reviewed unpaid, credential-free, read-only shape."""
    from .management import enabled
    for tool_id in provider(name)["sources"]:
        tool = router.catalog.tools.get(tool_id)
        # Defense in depth: a swapped definition that could spend, write, read a credential
        # or run another command is never run.
        if tool and enabled(router.state, tool_id) and reviewed(tool, router.state.home):
            return tool
    return None


def bound(state, alias):
    """Whether atm cli bind has an executable for this alias; refresh fails with cli_not_configured otherwise."""
    path = state.setting("cli:" + alias)
    return isinstance(path, str) and Path(path).is_file()


def next_cycle(day, today):
    """Next date on or after today with this day of month, clamped to the month end."""
    def on(year, month):
        return date(year, month, min(day, calendar.monthrange(year, month)[1]))
    current = on(today.year, today.month)
    if current >= today:
        return current
    return on(today.year + 1, 1) if today.month == 12 else on(today.year, today.month + 1)


def cycle_day(state, name):
    value = state.setting("credits_cycle:" + name)
    day = value.get("day") if isinstance(value, dict) else None
    return day if type(day) is int and 1 <= day <= 31 else None


def row(router, name, *, today=None):
    spec = provider(name)
    tool = usable_source(router, name)
    record = router.state.setting("credits:" + name)
    record = record if isinstance(record, dict) else {}
    source = record.get("source") if record.get("source") in SOURCES else tool["id"] if tool else None
    status = record.get("status") if record.get("status") in {"ok", "error"} else "not_read" if tool else "not_installed"
    day = cycle_day(router.state, name)
    renewal = {"date": next_cycle(day, today or date.today()).isoformat(), "source": "owner"} if day else None
    return {"provider": name, "label": spec["label"], "brand": spec["brand"], "billing": spec["billing"],
            "sources": list(spec["sources"]), "installed": tool is not None,
            "source": source, "source_kind": SOURCES[source][0] if source else None,
            "status": status, "credits": record.get("credits"), "plan": record.get("plan"), "unit": "credits",
            "checked_at": record.get("checked_at"), "last_ok_at": record.get("last_ok_at"),
            "error": record.get("error"), "next_cycle": renewal, "cycle_day": day,
            # What the next refresh runs, which may differ from the source of the stored value.
            "next_source": tool["id"] if tool else None,
            "next_source_kind": SOURCES[tool["id"]][0] if tool else None,
            "next_executable": tool["executable"] if tool else None,
            "bound": tool is not None and bound(router.state, tool["executable"])}


def payload(router):
    """Cached state only; never runs a tool. Raw output a crashed refresh left behind is discarded."""
    _discard_leftovers(router.state)
    return {"providers": [row(router, name) for name in PROVIDERS]}


def _failure(error):
    code = error.get("code") if isinstance(error, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    code = code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,64}", code) else "refresh_failed"
    message = message if isinstance(message, str) else "The account tool did not finish; no balance was read."
    return {"error": {"code": code, "message": re.sub(r"[\x00-\x1f]", " ", message)[:300]}}


def _forget_raw_output(router, job):
    # The job stays as an execution record, without account metadata such as e-mail.
    if "result" in job["data"] or job["data"].get("artifacts"):
        router.state.update_job(job["id"], job["status"], result=None, artifacts=[], raw_output_discarded=True)


def _discard_leftovers(state):
    """Crash-window cleanup: a refresh that died before discarding its job output leaves none behind."""
    with state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        for job_id, text in db.execute("SELECT id, data FROM jobs WHERE substr(request_key, 1, 8) = 'credits-'").fetchall():
            data = json.loads(text)
            if ("result" in data or data.get("artifacts")) and not data.get("raw_output_discarded"):
                data.update(result=None, artifacts=[], raw_output_discarded=True)
                db.execute("UPDATE jobs SET data=?, updated=? WHERE id=?", (canonical(data), time.time(), job_id))


@contextlib.contextmanager
def _lease(state, name):
    """One refresh per provider and ATM home, across threads and CLI / console processes."""
    folder = private_dir(state.home / "locks")
    try:
        fd = os.open(folder / f"credits-{name}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        raise RouterError("unsafe_path", "The credits refresh lock must be a private regular file.") from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RouterError("unsafe_path", "The credits refresh lock must be a private regular file.")
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RouterError("refresh_in_progress", "This provider is already being refreshed; wait for that result.") from None
        yield
    finally:
        os.close(fd)  # Releases the lease; the kernel also releases it if this process dies.


def _read(router, name, tool):
    from .maker import digest
    inputs = copy.deepcopy(tool.get("example") or {}) if tool["schema"].get("required") else {}
    # Private 0700 directory outside the ATM home: the server runtime refuses
    # workspaces inside its state, and raw output files are deleted afterwards.
    folder = Path(tempfile.mkdtemp(prefix="atm-credits-"))
    try:
        job = router.run(tool["id"], inputs, folder, request_key=f"credits-{name}-{uuid.uuid4().hex}",
                         allow_paid=False, grants=["execute_code"], expect_definition=digest(tool))
        _forget_raw_output(router, job)
        if job["status"] != "completed":
            return _failure(job["data"].get("error") or {"code": "refresh_" + job["status"]})
        return SOURCES[tool["id"]][1](job["data"].get("result"))
    except RouterError as error:
        return _failure(error.as_dict())
    except (OSError, ValueError, TypeError, KeyError):
        return _failure(None)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _store(state, name, source, outcome, now):
    setting = "credits:" + name
    with state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        found = db.execute("SELECT value FROM settings WHERE name=?", (setting,)).fetchone()
        previous = json.loads(found[0]) if found else {}
        previous = previous if isinstance(previous, dict) else {}
        # An error keeps the last good balance visible, marked by status and error.
        record = {"provider": name, "unit": "credits", "source": source, "checked_at": now,
                  "credits": previous.get("credits"), "plan": previous.get("plan"),
                  "last_ok_at": previous.get("last_ok_at")}
        if "error" in outcome:
            record.update(status="error", error=outcome["error"])
        else:
            record.update(status="ok", error=None, last_ok_at=now, credits=outcome["credits"], plan=outcome["plan"])
        db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (setting, canonical(record)))
    return record


def refresh(router, name, *, clock=time.time):
    """Owner action. Website sources drive the owner's logged-in browser."""
    provider(name)
    tool = usable_source(router, name)
    if tool is None:
        return {**row(router, name), "refresh": "not_installed"}
    with _lease(router.state, name):
        _discard_leftovers(router.state)
        outcome = _read(router, name, tool)
        record = _store(router.state, name, tool["id"], outcome, int(clock()))
    return {**row(router, name), "refresh": record["status"]}


def set_cycle(router, name, day):
    provider(name)
    if day is not None and not (type(day) is int and 1 <= day <= 31):
        raise RouterError("invalid_cycle_day", "Renewal day must be a whole number from 1 to 31, or cleared.")
    if day is None:
        with router.state.db() as db:
            db.execute("DELETE FROM settings WHERE name=?", ("credits_cycle:" + name,))
    else:
        router.state.set_setting("credits_cycle:" + name, {"day": day})
    return row(router, name)


def add_commands(sub):
    root = sub.add_parser("credits", help="Cached subscription credits; refresh runs reviewed read-only account tools")
    ops = root.add_subparsers(dest="operation")
    run = ops.add_parser("refresh", help="Owner action: read balances now; website sources drive the logged-in browser")
    run.add_argument("provider", nargs="*", help="Default: every provider")
    cycle = ops.add_parser("cycle", help="Set or clear the owner-known renewal day of month")
    cycle.add_argument("provider")
    choice = cycle.add_mutually_exclusive_group(required=True)
    choice.add_argument("--day", type=int)
    choice.add_argument("--clear", action="store_true")


def dispatch(args, router):
    if args.operation is None:
        return payload(router)
    if args.operation == "cycle":
        return set_cycle(router, args.provider, None if args.clear else args.day)
    names = list(dict.fromkeys(args.provider or PROVIDERS))
    for name in names:
        provider(name)  # Reject a typo before any tool runs.
    results = [refresh(router, name) for name in names]
    return {"status": "failed" if any(r["refresh"] == "error" for r in results) else "ok", "providers": results}
