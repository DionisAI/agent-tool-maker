"""Bounded Playwright recipes and encrypted, device-local browser sessions.

A website CLI is browser automation, not an official API. No selector discovery,
CAPTCHA bypass, arbitrary JavaScript, browser-profile scraping or automatic retry.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .errors import RouterError
from .network import checked_url, fake_ip_tunnel, public_address
from .storage import canonical, atomic_write
from .artifacts import managed_dir

SESSION = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")
MAX_STATE = 1024 * 1024
MAX_DOWNLOAD = 64 * 1024 * 1024


def origin_of(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}".rstrip("/")


def _text(value, limit=1000):
    return isinstance(value, str) and 0 < len(value) <= limit and not any(ord(c) < 32 for c in value)


def _target(value):
    if not isinstance(value, dict):
        raise RouterError("invalid_recipe", "Target must be a CSS, label, text or role locator object.")
    if set(value) in ({"css"}, {"label"}, {"text"}):
        valid = _text(next(iter(value.values())))
    else:
        valid = set(value) == {"role", "name"} and _text(value["role"], 40) and _text(value["name"], 200)
    if not valid:
        raise RouterError("invalid_recipe", "Invalid or ambiguous locator definition.")


def validate_recipe(recipe: dict, schema: dict) -> None:
    allowed = {"version", "start_url", "allowed_origins", "steps", "session", "login_check", "timeout_ms", "total_timeout_ms"}
    if not isinstance(recipe, dict) or set(recipe)-allowed or recipe.get("version") != 1:
        raise RouterError("invalid_recipe", "Use web recipe version 1 and only documented fields.")
    checked_url(recipe.get("start_url", ""))
    origins = recipe.get("allowed_origins")
    if not isinstance(origins, list) or not 1 <= len(origins) <= 12 or any(not isinstance(x,str) for x in origins) or len(set(origins)) != len(origins):
        raise RouterError("invalid_recipe", "List 1–12 distinct fixed HTTPS origins; no wildcard hosts.")
    for origin in origins:
        checked_url(origin)
        if origin_of(origin) != origin or urlsplit(origin).path or urlsplit(origin).query or urlsplit(origin).fragment:
            raise RouterError("invalid_recipe", "Allowed origins must contain only scheme and host, without a trailing slash.")
    if origin_of(recipe["start_url"]) not in origins:
        raise RouterError("invalid_recipe", "Start URL must be in the reviewed origin list.")
    if "session" in recipe and (not isinstance(recipe["session"], str) or not SESSION.fullmatch(recipe["session"])):
        raise RouterError("invalid_recipe", "Invalid device-local browser session name.")
    if "login_check" in recipe:
        _target(recipe["login_check"])
    for name, default, maximum in (("timeout_ms", 15000, 60000), ("total_timeout_ms", 120000, 300000)):
        value = recipe.get(name, default)
        if type(value) is not int or not 100 <= value <= maximum:
            raise RouterError("invalid_recipe", "Browser timeout must be an integer within the documented bound.")
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 40:
        raise RouterError("invalid_recipe", "Provide 1–40 bounded browser steps.")
    names = set()
    output_steps = 0
    shapes = {"wait": {"op", "target"}, "fill": {"op", "target", "value"}, "select": {"op", "target", "value"},
              "click": {"op", "target"}, "expect_text": {"op", "target", "value"},
              "extract": {"op", "target", "name"}, "download": {"op", "target", "filename"}}
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("op"),str) or step.get("op") not in shapes or set(step) != shapes[step["op"]]:
            raise RouterError("invalid_recipe", "Unsupported step or fields; JavaScript, Shell and arbitrary URL requests are not steps.")
        _target(step["target"])
        if "value" in step:
            value = step["value"]
            if isinstance(value, dict):
                if set(value) != {"input"} or not isinstance(value["input"],str) or value["input"] not in schema.get("properties", {}) or schema["properties"][value["input"]].get("type") != "string":
                    raise RouterError("invalid_recipe", "Step values may reference only a declared top-level string input.")
            elif not _text(value, 20000):
                raise RouterError("invalid_recipe", "Use a bounded literal or an input reference, never a credential value.")
        if step["op"] == "extract":
            name = step["name"]
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name) or name in names:
                raise RouterError("invalid_recipe", "Output names must be distinct safe identifiers.")
            names.add(name); output_steps += 1
        if step["op"] == "download":
            name = step["filename"]
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", name) or name in names or name == "result.json":
                raise RouterError("invalid_recipe", "Download filename must be fixed, unique and not result.json.")
            names.add(name); output_steps += 1
    if not output_steps:
        raise RouterError("invalid_recipe", "Recipe must deliver an extracted value or downloaded file, not only clicks.")


def _session_table(state):
    with state.db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS browser_sessions (name TEXT PRIMARY KEY, origins TEXT NOT NULL, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL, saved_at REAL NOT NULL, expires_at REAL)")


def sessions(state) -> dict:
    _session_table(state)
    with state.db() as db:
        rows = db.execute("SELECT name,origins,saved_at,expires_at FROM browser_sessions ORDER BY name").fetchall()
    return {"sessions": [{"name": r[0], "origins": json.loads(r[1]), "saved_at": r[2], "expires_at": r[3],
                          "expired": r[3] is not None and r[3] <= time.time()} for r in rows],
            "secrets_returned": False, "synced": False}


def _validate_storage(value, origins):
    """Reject sessions for unapproved sites. Do not serialize existing user profiles."""
    if not isinstance(value, dict) or set(value) - {"cookies", "origins"}:
        raise RouterError("invalid_browser_state", "Unsupported browser storage state.")
    if not isinstance(value.get("cookies",[]),list) or not isinstance(value.get("origins",[]),list):
        raise RouterError("invalid_browser_state", "Storage cookies and origins must be arrays.")
    hosts = {urlsplit(o).hostname for o in origins}
    for cookie in value.get("cookies", []):
        if not isinstance(cookie, dict) or not isinstance(cookie.get("domain"),str) or cookie["domain"].lstrip(".") not in hosts:
            raise RouterError("browser_state_scope", "Browser session contains an unapproved cookie domain.")
    for item in value.get("origins", []):
        if not isinstance(item, dict) or item.get("origin") not in origins:
            raise RouterError("browser_state_scope", "Browser session contains unapproved origin storage.")
    raw = canonical(value).encode()
    if len(raw) > MAX_STATE:
        raise RouterError("browser_state_limit", "Browser session exceeds 1 MiB; this site needs a dedicated integration.")
    return raw


def save_session(vault, name, origins, value, *, replace=False, expires_at=None):
    if not isinstance(name, str) or not SESSION.fullmatch(name):
        raise RouterError("invalid_browser_session", "Invalid session name.")
    if not isinstance(origins,list) or not 1 <= len(origins) <= 12 or any(not isinstance(x,str) for x in origins) or len(origins)!=len(set(origins)):
        raise RouterError("invalid_browser_session", "List distinct exact approved origins.")
    if expires_at is not None:
        if isinstance(expires_at,bool) or not isinstance(expires_at,(int,float)) or not math.isfinite(expires_at) or expires_at <= time.time():
            raise RouterError("invalid_expiry", "Session expiry must be a future finite timestamp.")
        expires_at = float(expires_at)
    for o in origins:
        checked_url(o)
        if o != origin_of(o):
            raise RouterError("invalid_browser_session", "Use exact HTTPS origins.")
    raw = _validate_storage(value, origins)
    _session_table(vault.state)
    nonce = os.urandom(12); origin_json = canonical(sorted(origins))
    aad = canonical(["atm-browser-session-v1", name, sorted(origins), expires_at]).encode()
    encrypted = AESGCM(vault.unlock()).encrypt(nonce, raw, aad)
    with vault.state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM browser_sessions WHERE name=?", (name,)).fetchone() and not replace:
            raise RouterError("browser_session_exists", "Existing session preserved; explicitly replace after review.")
        db.execute("INSERT OR REPLACE INTO browser_sessions VALUES (?,?,?,?,?,?)", (name, origin_json, nonce, encrypted, time.time(), expires_at))
    return {"session": name, "saved_encrypted": True, "origins": sorted(origins), "synced": False, "secrets_returned": False}


def load_session(vault, name, origins):
    _session_table(vault.state)
    with vault.state.db() as db:
        row = db.execute("SELECT origins,nonce,ciphertext,expires_at FROM browser_sessions WHERE name=?", (name,)).fetchone()
    if not row:
        raise RouterError("browser_session_missing", "Owner: use atm web login for this tool. Do not copy cookies or default browser profiles.")
    if json.loads(row[0]) != sorted(origins):
        raise RouterError("browser_session_scope", "Session origins differ from the reviewed recipe; log in again with explicit approval.")
    if row[3] is not None and row[3] <= time.time():
        raise RouterError("browser_session_expired", "Renew this site's login; do not recreate the whole vault.")
    try:
        aad = canonical(["atm-browser-session-v1", name, sorted(origins), row[3]]).encode()
        value = json.loads(AESGCM(vault.unlock()).decrypt(row[1], row[2], aad))
        _validate_storage(value, origins)
        # Do not echo session values if a page happens to expose them as visible text.
        for cookie in value.get("cookies",[]):
            if isinstance(cookie.get("value"),str) and cookie["value"]:
                vault._used_secrets.append(cookie["value"])
        for site in value.get("origins",[]):
            for item in site.get("localStorage",[]):
                if isinstance(item,dict) and isinstance(item.get("value"),str) and item["value"]:
                    vault._used_secrets.append(item["value"])
        return value
    except (InvalidTag, ValueError):
        raise RouterError("browser_session_corrupt", "Browser session authentication failed.") from None


def remove_session(state, name):
    _session_table(state)
    with state.db() as db:
        db.execute("DELETE FROM browser_sessions WHERE name=?", (name,))
    return {"removed": name, "provider_session_revoked": False, "synced": False}


def recipe_plan(tool, inputs) -> dict:
    recipe = tool["recipe"]
    validate_recipe(recipe, tool["schema"])
    return {"adapter": "web_recipe", "start_url": recipe["start_url"], "allowed_origins": recipe["allowed_origins"],
            "session": recipe.get("session"), "steps": [s["op"] for s in recipe["steps"]],
            "execution_started": False, "browser_auth_loaded": False, "network_calls": 0}


@contextmanager
def open_context(storage=None, *, headed=False):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RouterError("browser_dependency_missing", "Install ATM [web] extra and its Chromium runtime explicitly.") from None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed, executable_path=os.environ.get("ATM_CHROMIUM") or None)
        try:
            context = browser.new_context(storage_state=storage, accept_downloads=True, service_workers="block")
            yield context
        finally:
            browser.close()


def restrict_context(context, router, recipe):
    allowed = set(recipe["allowed_origins"])
    # Fail early on configured private destinations; DNS pinning is not an OS egress sandbox.
    for origin in allowed:
        public_address(origin, router.net.resolver, fake_ip=fake_ip_tunnel(router.state))
    blocked = []
    def guard(route):
        url = route.request.url
        if origin_of(url) not in allowed or urlsplit(url).scheme != "https":
            blocked.append("unapproved_request")
            route.abort("blockedbyclient")
        else:
            route.fallback()
    context.route("**/*", guard)
    # WebSocket/service-worker sites need a dedicated reviewed integration in v0.6.
    if hasattr(context, "route_web_socket"):
        context.route_web_socket("**/*", lambda ws: ws.close())
    return blocked


def locate(page, target):
    if "css" in target:
        return page.locator(target["css"])
    if "role" in target:
        return page.get_by_role(target["role"], name=target["name"], exact=True)
    if "label" in target:
        return page.get_by_label(target["label"], exact=True)
    return page.get_by_text(target["text"], exact=True)


def execute_web(router, tool, job, *, _context_factory=None):
    """Execute installed recipe once. Injected context is used only by synthetic tests."""
    from .actions import output_record
    recipe, inputs = tool["recipe"], job["data"]["inputs"]
    validate_recipe(recipe, tool["schema"])
    storage = load_session(router.vault, recipe["session"], recipe["allowed_origins"]) if recipe.get("session") else None
    factory = _context_factory or open_context
    attempted_effect = False
    step_index = -1
    artifacts, extracted = [], {}
    deadline = time.monotonic() + recipe.get("total_timeout_ms", 120000)/1000
    try:
        with factory(storage) as context:
            blocked = restrict_context(context, router, recipe)
            page = context.new_page()
            page.set_default_timeout(recipe.get("timeout_ms", 15000))
            page.goto(recipe["start_url"], wait_until="domcontentloaded", timeout=recipe.get("timeout_ms", 15000))
            if "login_check" in recipe and locate(page, recipe["login_check"]).is_visible():
                return router.state.update_job(job["id"], "login_required", verification="browser_login_required", browser_steps_completed=0)
            outdir = managed_dir(Path(job["workspace"]), job["id"])
            for step_index, step in enumerate(recipe["steps"]):
                remaining = int((deadline-time.monotonic())*1000)
                if remaining <= 0:
                    raise RouterError("browser_timeout", "Browser recipe exceeded its total deadline.", uncertain=attempted_effect)
                timeout = min(remaining, recipe.get("timeout_ms", 15000))
                target = locate(page, step["target"])
                op = step["op"]
                value = step.get("value")
                if isinstance(value, dict):
                    value = inputs.get(value["input"])
                    if not isinstance(value, str):
                        raise RouterError("invalid_input", "A required browser string input is absent.")
                if op in {"fill", "select", "click", "download"}:
                    attempted_effect = True  # May trigger autosave/generation, not necessarily a charge.
                if op == "wait": target.wait_for(state="visible", timeout=timeout)
                elif op == "fill": target.fill(value, timeout=timeout)
                elif op == "select": target.select_option(value, timeout=timeout)
                elif op == "click": target.click(timeout=timeout)
                elif op == "expect_text":
                    from playwright.sync_api import expect
                    expect(target).to_have_text(value, timeout=timeout)
                elif op == "extract":
                    text = target.inner_text(timeout=timeout)
                    if len(text) > 20000:
                        raise RouterError("browser_result_limit", "Extracted field exceeds 20,000 characters.", uncertain=attempted_effect)
                    extracted[step["name"]] = router.vault.redact(text)
                elif op == "download":
                    with page.expect_download(timeout=timeout) as pending:
                        target.click(timeout=timeout)
                    download = pending.value
                    # Only approved HTTPS assets or same-page blob/data downloads.
                    u = urlsplit(download.url)
                    if u.scheme not in {"blob", "data"} and origin_of(download.url) not in recipe["allowed_origins"]:
                        raise RouterError("browser_download_origin", "Download origin was not approved.", uncertain=True)
                    source = download.path()
                    if source is None or Path(source).stat().st_size > MAX_DOWNLOAD:
                        raise RouterError("browser_download_limit", "Download exceeds the 64 MiB delivery limit.", uncertain=True)
                    target_path = outdir / step["filename"]
                    if target_path.exists() or target_path.is_symlink():
                        raise RouterError("unsafe_path", "Download output already exists.", uncertain=True)
                    atomic_write(target_path, Path(source).read_bytes())
                    artifacts.append(output_record(job["workspace"], target_path))
                if origin_of(page.url) not in recipe["allowed_origins"]:
                    raise RouterError("browser_navigation_denied", "Page navigated outside approved origins.", uncertain=attempted_effect)
            path = outdir / "result.json"
            atomic_write(path, canonical({"extracted": extracted, "steps_completed": len(recipe["steps"]),
                                          "blocked_requests": len(blocked), "site_acceptance": "not_independently_verified"}).encode())
            artifacts.append(output_record(job["workspace"], path))
            return router.state.update_job(job["id"], "completed", artifacts=artifacts,
                verification="browser_recipe_steps_and_files", result=extracted,
                browser_steps_completed=len(recipe["steps"]), blocked_requests=len(blocked), cost_usd=None)
    except RouterError as error:
        if attempted_effect and not error.uncertain:
            raise RouterError(error.code,str(error),uncertain=True) from None
        raise
    except Exception as error:
        if "ERR_BLOCKED_BY_ADMINISTRATOR" in str(error):
            raise RouterError("browser_policy_blocked", "Browser policy denied navigation. Use an authorized environment; no bypass or retry was attempted.", uncertain=attempted_effect) from None
        # Playwright errors frequently embed page content/URLs/selectors. Do not return those.
        raise RouterError("browser_execution_failed", f"Browser step {step_index + 1} failed. Check login/site changes; no automatic retry or repair was executed.", uncertain=attempted_effect) from None


def login(router, tool_id, *, replace=False, expires_at=None):
    """Interactive login in a NEW browser context; encrypted storage state only."""
    if not sys.stdin.isatty():
        raise RouterError("interactive_required", "Run login in the owner's terminal; do not automate consent or copy browser cookies.")
    tool = router.catalog.get(tool_id)
    if tool["adapter"] != "web_recipe" or not tool["recipe"].get("session"):
        raise RouterError("browser_session_required", "Install a reviewed web recipe with a named session first.")
    recipe = tool["recipe"]; name = recipe["session"]
    if any(x["name"] == name for x in sessions(router.state)["sessions"]) and not replace:
        return {"session": name, "status": "already_configured", "login_not_rechecked": True}
    router.vault.unlock()
    with open_context(headed=True) as context:
        restrict_context(context, router, recipe)
        page = context.new_page(); page.goto(recipe["start_url"], wait_until="domcontentloaded")
        confirm = input("Complete official login in this new browser. Type SAVE to encrypt this site's session, anything else cancels: ")
        if confirm != "SAVE":
            return {"status": "cancelled", "session_saved": False}
        if "login_check" in recipe and locate(page, recipe["login_check"]).is_visible():
            raise RouterError("browser_login_required", "The declared login screen is still visible; session not saved.")
        storage = context.storage_state(indexed_db=True)
        return save_session(router.vault, name, recipe["allowed_origins"], storage, replace=replace, expires_at=expires_at)


def health(router, tool):
    import importlib.util
    result = {"state": "configured_not_verified", "authentication": "not_verified", "browser_started": False}
    if importlib.util.find_spec("playwright") is None:
        return {**result, "state": "browser_dependency_missing", "next_action": "Install the reviewed [web] extra and its Chromium runtime."}
    recipe = tool["recipe"]
    if recipe.get("session"):
        record = next((s for s in sessions(router.state)["sessions"] if s["name"] == recipe["session"]), None)
        if record is None:
            return {**result, "state": "browser_session_missing", "next_action": "Owner: atm web login TOOL, using the reviewed site origins."}
        if record["origins"] != sorted(recipe["allowed_origins"]):
            return {**result, "state": "browser_session_scope"}
        if record["expired"]:
            return {**result, "state": "browser_session_expired"}
        from .health import vault_health
        v = vault_health(router.vault)
        if v["state"] not in {"unlocked_in_this_process", "unlock_not_checked"}:
            return {**result, "state": v["state"]}
    return {**result, "browser_binary": "not_started_or_verified", "live_site": "not_verified"}
