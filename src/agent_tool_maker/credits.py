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
# Reviewed pins of the XYQ website account adapter, one per namespace that emits xyq.web.account:
# scripts/build_xyq_web.py (xyq-web) and scripts/build_xyq_runtime.py (xyq-media). A contract test
# recomputes both from the adapter sources, so drift fails CI until the new pins are reviewed here.
XYQ_ACCOUNT_PINS = {"xyq-web": "4183404ea6c890635af1a17d96050d6e8d4d7f8253e2ef2fe9a02cde80236f1f",
                    "xyq-media": "06d6591e8239ed0efa216b242dac86a0900bc6d40df2392fc70809837111fd23"}


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
        return abs(value)  # Only changes -0.0, which is a plain 0.0 balance.
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


def _json_command(argv):
    return {"argv": list(argv), "output": "json", "timeout": 60}


def _tripo_account():
    # The packaged Tripo Studio account adapter and its reviewed pin; the server runtime serves the same operation.
    from .studio_runtime import index
    return index()["account"]["command"]


def _tripo_server_account(home):
    # The argv studio_cli.manifests installs: this ATM home, the reviewed server bundle, the same account pin.
    from .studio_runtime import bundle_digest
    try:
        bundle = bundle_digest()
    except RouterError:
        return []  # A server bundle that is not regular reviewed files is not the reviewed one.
    command = _tripo_account()
    return [{**command, "argv": ["--home", str(home), "studio", "adapter", "--bundle", bundle, "account",
                                 *command["argv"][3:]]}]


def _xyq_account(home):
    return [_json_command(["__opencli_shim", namespace, "account", "--pin", pin, "-f", "json"])
            for namespace, pin in XYQ_ACCOUNT_PINS.items()]


# tool id -> (kind shown to the owner, pure extractor from the job result, reviewed executable alias,
#             the exact reviewed command objects (argv with pins, output, timeout) for an ATM home)
SOURCES = {
    "tripo.studio.account": ("website", website_credits, "opencliapp", lambda home: [_tripo_account()]),
    "tripo.server.account": ("website", website_credits, "atm", _tripo_server_account),
    "xyq.web.account": ("website", website_credits, "opencliapp", _xyq_account),
    # The existing reviewed binding of pippit-tool-cli, shared with the built-in xyq.image / xyq.video.
    "pippit.cli.credit_balance": ("cli", pippit_credits, "xyq", lambda home: [_json_command(["get-credit-balance"])]),
    "higgsfield.subscription.account": ("cli", higgsfield_credits, "higgsfield",
                                        lambda home: [_json_command(["account", "status", "--json"])]),
}


def provider(name):
    if not isinstance(name, str) or name not in PROVIDERS:
        raise RouterError("unknown_provider", "Unknown subscription credits provider; run atm credits to list them.")
    return PROVIDERS[name]


# The request key only a refresh uses: credits-<provider>-<uuid4 hex>.
REFRESH_KEY = re.compile("credits-(?:" + "|".join(map(re.escape, PROVIDERS)) + ")-[0-9a-f]{32}")


def refresh_job(job):
    """A job a credits refresh created. Job readers never show its result or artifacts."""
    key = job.get("request_key")
    return job.get("tool") in SOURCES and isinstance(key, str) and REFRESH_KEY.fullmatch(key) is not None


def reviewed(tool, home):
    """The same id is not enough: the definition must keep its exact reviewed read-only command."""
    _, _, executable, commands = SOURCES[tool["id"]]
    command = tool.get("command") if isinstance(tool.get("command"), dict) else {}
    return (tool.get("adapter") == "command" and tool.get("paid") is False
            and set(tool.get("permissions", [])) <= SAFE_PERMISSIONS
            and not tool.get("credential") and not command.get("credential_env")
            and tool.get("executable") == executable
            # Last: the server source hashes its reviewed bundle. Pins, output mode and timeout must all match.
            and command in commands(home))


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


def _remove_files(workspace, artifacts):
    """The files a crashed refresh left: its temporary workspace, which holds the artifact files it lists.

    Deleted only when it is a real directory named atm-credits-* directly under this process's
    temporary directory and owned by this user; anything else is left in place, and the record says so."""
    folder = Path(workspace)
    try:
        info = os.lstat(folder)
    except FileNotFoundError:
        info = None
    except OSError:
        return "left_in_place"
    if (info is not None and stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and folder.name.startswith("atm-credits-") and folder.parent == Path(tempfile.gettempdir()).resolve()):
        shutil.rmtree(folder, ignore_errors=True)
    listed = [Path(a["path"]) for a in artifacts if isinstance(a, dict) and isinstance(a.get("path"), str)]
    left = os.path.lexists(folder) or any(p.is_absolute() and os.path.lexists(p) for p in listed)
    return "left_in_place" if left else "removed"


def _discard_leftovers(state, held=None):
    """Crash-window cleanup: a refresh that died before discarding its output leaves none behind,
    neither in its job record nor in its temporary workspace.

    While a provider's lease is held (held=name) no refresh of it can be running in this home, so its
    unfinished jobs count too: one that died after writing its result file but before completing."""
    marks = ",".join("?" * len(SOURCES))
    with state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(f"SELECT id, tool, request_key, workspace, data FROM jobs WHERE tool IN ({marks}) "  # noqa: S608
                          "AND substr(request_key, 1, 8) = 'credits-' "
                          "AND json_extract(data, '$.raw_output_discarded') IS NOT 1", tuple(SOURCES)).fetchall()
        for job_id, tool, key, workspace, text in rows:
            data = json.loads(text)
            unfinished = held is not None and key.startswith(f"credits-{held}-")
            if refresh_job({"tool": tool, "request_key": key}) and ("result" in data or data.get("artifacts") or unfinished):
                files = _remove_files(workspace, data.get("artifacts") or [])
                data.update(result=None, artifacts=[], raw_output_discarded=True, raw_output_files=files)
                db.execute("UPDATE jobs SET data=?, updated=? WHERE id=?", (canonical(data), time.time(), job_id))


@contextlib.contextmanager
def _lease(state, name):
    """One refresh per provider and ATM home, across threads and CLI / console processes."""
    folder = private_dir(state.home / "locks")
    try:
        # Never follow a symbolic link; a FIFO does not block the open.
        fd = os.open(folder / f"credits-{name}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    except OSError:
        raise RouterError("unsafe_path", "The credits refresh lock must be a private regular file.") from None
    try:
        info = os.fstat(fd)
        # A hard link would let fchmod change another file's mode.
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
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
        # Files first: a crash before the record is cleaned leaves a record the next view or refresh cleans.
        shutil.rmtree(folder, ignore_errors=True)
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
        _discard_leftovers(router.state, held=name)
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
    results = []
    for name in names:
        try:
            results.append(refresh(router, name))
        except RouterError as error:  # Such as refresh_in_progress: report this provider, refresh the rest.
            results.append({**row(router, name), "refresh": "error", **_failure(error.as_dict())})
    return {"status": "failed" if any(r["refresh"] == "error" for r in results) else "ok", "providers": results}
