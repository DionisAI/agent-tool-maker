"""Shared CLI/Web management operations. No alternate credential store or executor."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import time
import uuid

from . import __version__
from .errors import RouterError
from .health import binary_health, doctor, parse_expiry, vault_health, verification_history
from .onboarding import CLIENTS, safe_target, setup
from .storage import canonical

DEFAULT_AGENTS = ("claude", "codex")


def enabled(state, tool_id: str) -> bool:
    return state.setting("tool_enabled:" + tool_id, True) is not False


def set_enabled(router, tool_id: str, value: bool, *, apply=False, expected=None) -> dict:
    router.catalog.get(tool_id)
    if type(value) is not bool:
        raise RouterError("invalid_toggle", "Enabled must be a boolean.")
    if expected is not None and type(expected) is not bool:
        raise RouterError("invalid_toggle", "Expected state must be a boolean.")
    def result(previous):
        if expected is not None and previous is not expected:
            raise RouterError("state_changed", "Tool state changed; refresh before applying.")
        return {"tool": tool_id, "previous_enabled": previous, "enabled": value,
                "applied": apply, "scope": "all_local_agents", "action": "unchanged" if previous == value else "enable" if value else "disable"}
    if not apply:
        return result(enabled(router.state, tool_id))
    # Compare and write in the same SQLite transaction, including across processes.
    import json
    with router.state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT value FROM settings WHERE name=?", ("tool_enabled:" + tool_id,)).fetchone()
        previous = json.loads(row[0]) is not False if row else True
        response = result(previous)
        if previous != value:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ("tool_enabled:" + tool_id, canonical(value)))
    return response


def known_credentials(router) -> list[str]:
    names = {t.get("credential") for t in router.catalog.tools.values()} - {None}
    for tool in router.catalog.tools.values():
        names.update(tool.get("command", {}).get("credential_env", {}).values())
    names.update({"google_oauth", "cloudflare", "supabase", "expo", "github"})
    for tool in router.catalog.tools.values():
        if tool.get("server"):
            cfg = router.state.setting("mcp:" + tool["server"], {})
            if cfg.get("credential"):
                names.add(cfg["credential"])
            names.update(cfg.get("env_credentials", {}).values())
    names.update(router.state.setting("credential_registry", {}))
    names.update(router.state.secret_names())  # Includes explicitly received custom slots.
    return sorted(names)


def connect_value(router, provider: str, value: str, *, replace=False, expires_at=None) -> dict:
    """Write-only input; caller must obtain it through a private human channel."""
    from .extensions import credential_name
    credential_name(provider)
    if provider not in known_credentials(router):
        raise RouterError("unknown_provider", "Select a registered credential provider.")
    if provider in router.state.secret_names() and not replace:
        return {"provider": provider, "status": "already_configured", "secrets_returned": False}
    expiry = parse_expiry(expires_at)
    router.vault.put(provider, value, expires_at=expiry)
    return {"provider": provider, "status": "saved", "saved_encrypted": True,
            "secrets_returned": False, "authentication": "not_verified"}


def connections(router) -> dict:
    stored = set(router.state.secret_names())
    known = set(known_credentials(router))
    records = []
    for name in sorted(known | stored):
        meta = router.state.setting("credential_meta:" + name, {})
        expiry = meta.get("expires_at")
        records.append({"provider": name, "label": router.state.setting("credential_registry",{}).get(name,{}).get("label",name), "configured": name in stored,
                        "configured_at": meta.get("configured_at"), "expires_at": expiry,
                        "sync_conflict": router.state.setting("sync_conflict:"+name, False),
                        "expired": bool(name in stored and expiry is not None and expiry <= time.time()),
                        "connect_supported": name in known})
    from .oauth import OAuth
    from .oauth_service import service_status
    return {"connections": records, "oauth": [{**OAuth(router.state, router.vault, router.net).status(), "service": service_status(router.state)}], "vault": vault_health(router.vault),
            "verification_history": verification_history(router.state), "secrets_returned": False}


def cli_inventory(router) -> dict:
    names = sorted(({t.get("executable") for t in router.catalog.tools.values()} - {None}) | {"claude", "codex"})
    rows = []
    for name in names:
        path = router.state.setting("cli:" + name)
        item = {"name": name, "detected_path": shutil.which(name),
                **binary_health(path, router.state.setting("cli_hash:" + name))}
        rows.append(item)
    return {"clis": rows, "programs_executed": 0}


def agents(router, *, user_home=None) -> dict:
    # doctor() already owns integrity checks for registered Skill files.
    first = next(iter(router.catalog.tools))
    report = doctor(router, tool_ids=[first])
    rows = []
    home = Path(user_home or Path.home()).expanduser().absolute()
    for name in DEFAULT_AGENTS:
        item = next(x for x in report["agents"] if x["agent"] == name)
        root = home / CLIENTS[name]
        if name == "claude" and os.environ.get("CLAUDE_CONFIG_DIR"):
            root = Path(os.environ["CLAUDE_CONFIG_DIR"]).expanduser().absolute() / "skills"
        rows.append({**item, "label": "Claude Code" if name == "claude" else "Codex",
                     "default": True, "detected_executable": shutil.which(name),
                     "default_skill_path": str(root / "agent-tool-maker" / "SKILL.md"),
                     "transport": "skill_to_shared_atm_cli", "host_load_verified": False})
    return {"agents": rows, "shared_state_home": str(router.state.home),
            "scope": "same_machine_same_os_user", "tools_shared": True}


def unregister(router, name: str, *, apply=False, user_home=None) -> dict:
    if name not in CLIENTS:
        raise RouterError("unsupported_agent", "Supported clients: claude, codex.")
    cfg = router.state.setting("agent:" + name)
    if not cfg:
        return {"agent": name, "action": "unchanged", "applied": apply}
    path = Path(cfg["path"])
    safe_target(path)
    # Never remove a user-modified Skill; retain a backup even for an owned file.
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != cfg["sha256"]:
        raise RouterError("registration_changed", "Skill was modified. Review it manually before unregistering.")
    result = {"agent": name, "action": "unregister", "path": str(path), "applied": apply,
              "credentials_removed": False, "tools_removed": False}
    if apply:
        if path.exists():
            backup = path.with_name("SKILL.md.bak-" + uuid.uuid4().hex)
            path.rename(backup)
            result["backup"] = str(backup)
        with router.state.db() as db:
            db.execute("DELETE FROM settings WHERE name=?", ("agent:" + name,))
    return result


def tools(router, *, query="", capability=None) -> dict:
    selected = router.search(query, capability)
    report = doctor(router, tool_ids=[t["id"] for t in selected]) if selected else {"tools": []}
    health = {t["id"]: t for t in report["tools"]}
    fields = ("id", "title", "provider", "adapter", "capabilities", "implementation", "permissions", "paid")
    rows = [{**{key: t.get(key) for key in fields}, "enabled": enabled(router.state, t["id"]),
             "health": health[t["id"]]} for t in selected]
    return {"tools": rows, "count": len(rows), "scope": "shared_by_claude_and_codex", "network_calls": 0}


def recent_jobs(router) -> dict:
    """Do not expose prompts, vendor responses, signed URLs, or environment to UI."""
    rows = []
    for job in router.state.jobs(limit=50):
        data = job["data"]
        rows.append({key: job[key] for key in ("id", "tool", "status", "created", "updated")})
        rows[-1].update(verification=data.get("verification"), cost_usd=data.get("cost_usd"),
                        cost_status=data.get("cost_status", "unknown"),
                        artifact_count=len(data.get("artifacts", [])))
    return {"jobs": rows, "limit": 50, "details_omitted": "Inputs, payloads, paths and signed URLs are available only through the existing local CLI, not this UI."}


def overview(router, *, user_home=None) -> dict:
    from .credits import payload as credits_payload
    rows = list(router.catalog.tools.values())
    return {"version": __version__, "home": str(router.state.home),
            "counts": {"tools": len(rows), "enabled": sum(enabled(router.state,t["id"]) for t in rows),
                       "connections": len(router.state.secret_names()), "recent_jobs": len(router.state.jobs())},
            "agents": agents(router, user_home=user_home)["agents"],
            "vault": vault_health(router.vault), "network_calls": 0,
            "credits": credits_payload(router),  # Cached only; avoids another bootstrap request.
            "note": "Configured is not live-verified. No provider requests are made when viewing this console."}


def setup_plan(router, *, agent_names=None, cli_names=(), executable=None, replace_skills=False, user_home=None) -> dict:
    result = setup(router, agents=DEFAULT_AGENTS if agent_names is None else agent_names,
                   cli_names=cli_names, executable=executable, replace_skills=replace_skills, user_home=user_home)
    # Bind approval to exact targets/content and binary hashes, not to freeform commands.
    result["plan_sha256"] = hashlib.sha256(canonical({key: result[key] for key in ("home", "skills", "clis")}).encode()).hexdigest()
    return result


def apply_setup(router, *, approved_sha256: str, agent_names=None, cli_names=(), executable=None,
                replace_skills=False, user_home=None) -> dict:
    kwargs = dict(agent_names=agent_names, cli_names=cli_names, executable=executable,
                  replace_skills=replace_skills, user_home=user_home)
    plan = setup_plan(router, **kwargs)
    if plan["plan_sha256"] != approved_sha256:
        raise RouterError("setup_changed", "Setup plan changed. Preview and review the new plan before applying.")
    return setup(router, agents=DEFAULT_AGENTS if agent_names is None else agent_names,
                 cli_names=cli_names, executable=executable, replace_skills=replace_skills,
                 user_home=user_home, apply=True)
