"""Local preflight. No vendor traffic, package installation or implicit secret prompts."""
from __future__ import annotations

from datetime import datetime
import hashlib
import os
from pathlib import Path
import sys
import time

from .errors import RouterError


def parse_expiry(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.timestamp()
    except (ValueError, TypeError, OverflowError):
        raise RouterError("bad_expiry", "Use an ISO-8601 expiry with timezone, e.g. 2026-10-01T12:00:00Z.") from None


def credential_revision(state, name: str) -> str | None:
    with state.db() as db:
        row = db.execute("SELECT nonce,ciphertext FROM secrets WHERE name=?", (name,)).fetchone()
    return hashlib.sha256(bytes(row[0]) + bytes(row[1])).hexdigest() if row else None


def vault_health(vault, *, check_unlock=False) -> dict:
    backend = vault.state.setting("vault", {}).get("backend")
    result = {"backend": backend, "state": "not_initialized", "unlock_checked": False,
              "vendor_secrets_read": False, "interactive_available": bool(sys.stdin.isatty())}
    if not backend:
        result["next_action"] = "Initialize once in a human terminal: atm vault init --backend keyring."
        return result
    if vault._key is not None:
        result.update(state="unlocked_in_this_process", unlock_checked=True)
    elif check_unlock:
        try:
            vault.unlock()  # Explicitly requested; the native OS keyring may ask for approval.
            result.update(state="unlocked_in_this_process", unlock_checked=True)
        except RouterError as error:
            result.update(state=error.code, unlock_checked=True)
    elif backend == "passphrase":
        available = bool(vault.password or os.environ.get("ATM_VAULT_PASSWORD"))
        result["state"] = "unlock_not_checked" if available else "needs_unlock"
    else:
        try:
            vault._keyring()  # Inspect backend availability; do not retrieve the master key.
            result["state"] = "unlock_not_checked"
        except RouterError as error:
            result["state"] = error.code
    if result["state"] not in {"unlocked_in_this_process", "unlock_not_checked"}:
        result["next_action"] = "Unlock or repair this existing vault in a human terminal; do not reset it or reconnect every provider."
    return result


def binary_health(path, expected) -> dict:
    if not path:
        return {"state": "cli_not_configured"}
    p = Path(path)
    try:
        if not p.is_file():
            return {"state": "executable_missing", "path": str(p)}
        if not os.access(p, os.X_OK):
            return {"state": "executable_not_executable", "path": str(p)}
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return {"state": "executable_unreadable", "path": str(p)}
    return {"state": "configured_not_verified" if expected == actual else "executable_changed" if expected else "executable_unpinned",
            "path": str(p), "hash_checked": True}


def tool_health(router, tool: dict, *, vault=None, cache=None) -> dict:
    from .management import enabled
    if not enabled(router.state, tool["id"]):
        return {"id": tool["id"], "state": "disabled", "authentication": "not_verified"}
    if tool["adapter"]=="web_recipe":
        from .web_recipe import health
        return {"id":tool["id"],**health(router,tool)}
    state, kind = router.state, tool["adapter"]
    result = {"id": tool["id"], "state": "configured_not_verified", "authentication": "not_verified"}
    if kind in {"browser", "desktop", "human", "catalog_only", "workflow"}:
        result["state"] = {"browser": "browser_login_unknown", "desktop": "host_desktop_required",
                           "human": "host_human_required", "catalog_only": "catalog_only",
                           "workflow": "workflow_dependencies_not_verified"}[kind]
        return result
    credentials = [tool["credential"]] if tool.get("credential") else []
    # Command credential_env is optional: existing official CLI login is a valid route.
    optional = list(tool.get("command", {}).get("credential_env", {}).values())
    credentials += [name for name in optional if tool.get("command",{}).get("credential_required") or name in state.secret_names()]
    if optional:
        result["cli_authentication"] = "vault_override" if credentials else "vendor_login_not_verified"
    path, expected = None, None
    if kind == "mcp":
        config = state.setting("mcp:" + tool["server"])
        if not config:
            return {**result, "state": "mcp_not_configured", "next_action": "Bind the reviewed MCP configuration once."}
        if config.get("transport") == "stdio":
            path, expected = config.get("command"), config.get("sha256")
        if config.get("credential"):
            credentials.append(config["credential"])
        credentials += list(config.get("env_credentials", {}).values())
    elif tool.get("executable"):
        name = tool["executable"]
        path, expected = state.setting("cli:" + name), state.setting("cli_hash:" + name)
        if not path:
            return {**result, "state": "cli_not_configured", "next_action": f"Review atm setup --cli {name}, then --apply."}
    if path:
        key = (path, expected)
        cache = cache if cache is not None else {}
        if key not in cache:
            cache[key] = binary_health(path, expected)
        result["binary"] = cache[key]
        if cache[key]["state"] != "configured_not_verified":
            return {**result, "state": cache[key]["state"], "next_action": "Review the installation change and explicitly rebind the executable; do not reset credentials."}
    names = set(state.secret_names())
    for name in dict.fromkeys(credentials):
        if state.setting("sync_conflict:" + name, False):
            return {**result, "state": "sync_conflict", "credential": name, "next_action": "An owner must resolve conflicting revisions; do not reconnect or pick by timestamp."}
        if name not in names:
            return {**result, "state": "missing_credential", "credential": name,
                    "next_action": f"Human: atm connect {name} in a private local terminal."}
        metadata = state.setting("credential_meta:" + name, {})
        expiry = metadata.get("expires_at")
        if expiry is not None and expiry <= time.time():
            return {**result, "state": "credential_expired", "credential": name,
                    "next_action": "Renew only this credential with its provider; automatic OAuth refresh is not implemented."}
    if credentials:
        access = vault if vault is not None else vault_health(router.vault)
        result["vault_access"] = access["state"]
        result["expiry_status"] = "unknown_unless_supplied_at_connect"
        if access["state"] not in {"unlocked_in_this_process", "unlock_not_checked"}:
            return {**result, "state": access["state"], "next_action": access.get("next_action", "Unlock the existing vault.")}
    if tool.get("request", {}).get("origin_setting") and not state.setting("origin:" + tool["provider"]):
        result.update(state="missing_origin", next_action="Set and approve the exact non-secret provider origin once.")
    return result


def verification_history(state) -> list[dict]:
    with state.db() as db:
        names = [row[0] for row in db.execute("SELECT name FROM settings WHERE name LIKE 'verification:%'")]
    result = []
    for name in names:
        record = state.setting(name)
        revision = record.pop("credential_revision", None)
        changed = revision != credential_revision(state, record["provider"])
        age = max(0, time.time() - record["checked_at"])
        record.update(age_seconds=round(age), credential_changed=changed,
                      current_status="stale_credential" if changed else "stale_time" if age > 86400 else "historical_only")
        result.append(record)
    return result


def doctor(router, *, tool_ids=(), check_unlock=False) -> dict:
    tools = [router.catalog.get(t) for t in tool_ids] if tool_ids else list(router.catalog.tools.values())
    access = vault_health(router.vault, check_unlock=check_unlock)
    cache = {}
    items = [tool_health(router, t, vault=access, cache=cache) for t in tools]
    allowed = {"configured_not_verified", "browser_login_unknown", "host_desktop_required", "host_human_required",
               "workflow_dependencies_not_verified", "catalog_only"}
    agents = []
    for name in ("codex", "claude"):
        config = router.state.setting("agent:" + name)
        if not config:
            agents.append({"agent": name, "state": "not_registered"})
            continue
        path = Path(config["path"])
        try:
            matched = not path.is_symlink() and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == config["sha256"]
        except OSError:
            matched = False
        exe = Path(config["executable"])
        agents.append({"agent": name, "state": "registered_not_host_verified" if matched and exe.is_file() and os.access(exe, os.X_OK) else "registration_changed",
                       "skill_path": str(path), "host_load_verified": False})
    from .network import network_settings
    return {"home": str(router.state.home), "vault": access["backend"] or "not_initialized", "vault_health": access,
            # Read-only. No CLI command writes it; only the console endpoint does, which any program running as
            # this user can also reach (SECURITY.md). Each change is an `events` row, not an identity.
            "network": {"fake_ip_tunnel": network_settings(router.state)["fake_ip_tunnel"], "write_path": "console_only"},
            "tools": items, "agents": agents, "verification_history": verification_history(router.state),
            "local_blockers": sum(t["state"] not in allowed for t in items), "network_calls": 0,
            "notes": ["No vendor authentication was performed. Cached probes are historical and never guarantee future calls.",
                      "Default doctor does not retrieve keys or prompt. --check-unlock may ask for OS-keyring approval.",
                      "A new session reuses configuration only in the same OS user and persistent state directory."]}
