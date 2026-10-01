"""Idempotent, local-only onboarding. Never installs packages or reads secrets."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shlex
import shutil
import sys
import uuid
from importlib.resources import files

from . import __version__
from .cli_adapter import bind_cli
from .errors import RouterError
from .storage import atomic_write

CLIENTS = {"codex": ".agents/skills", "claude": ".claude/skills"}
MAX_SKILL_BYTES = 256 * 1024


def executable_path(value: str | None = None) -> Path:
    """Select this installation, not an unrelated project's executable on PATH."""
    candidate = value or str(Path(sys.executable).parent / ("atm.exe" if os.name == "nt" else "atm"))
    path = Path(candidate).expanduser().absolute()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise RouterError("atm_not_installed", "Install ATM as a user application, or pass --atm-executable with its absolute executable path.")
    if any(c in str(path) for c in "\r\n\x00"):
        raise RouterError("unsafe_path", "Executable path contains control characters.")
    return path


def safe_target(path: Path) -> None:
    # Refuse redirecting skill writes via a symlink in any user-controlled component.
    for item in (path, *path.parents):
        if item.is_symlink():
            raise RouterError("unsafe_path", "Skill destination contains a symbolic link; choose a direct user directory.")
    if path.exists() and (not path.is_file() or path.stat().st_size > MAX_SKILL_BYTES):
        raise RouterError("unsafe_path", "Expected a bounded regular Skill file.")


def render_skill(executable: Path, state_home: Path, *, client: str | None = None) -> bytes:
    if client is not None:
        if client not in CLIENTS:
            raise RouterError("unsupported_agent", "Select an explicitly supported client.")
        prefix = shlex.join([str(executable), "--client", client])
        return ("---\nname: agent-tool-maker\ndescription: Find and inject approved API credentials into existing programs without .env files; optionally run ATM tools through the same scoped session.\n---\n"
                "# Agent Tool Maker — scoped execution\n\n"
                f"Use this exact prefix: `{prefix}`. It automatically reads your owner-only client profile; never open or print that file.\n"
                f"When a program needs an API Key, first use `{prefix} keys find ENV_NAME`. Do not create a plaintext .env.\n"
                f"Use `{prefix} exec --env ENV_NAME=atm://exact.slot --workspace /approved/project --request-key STABLE -- /absolute/program script.py` for an existing program. No tool manifest is needed.\n"
                "Discovery is metadata only. Exact mappings, command and project must be pre-approved by the Owner. A missing grant is not a missing Key.\n"
                f"Start with `{prefix} broker status`, then `search`, `describe`, `run`, or `jobs get` for optional catalog tools.\n"
                "Run accepts --input, --workspace, --request-key and --dry-run. Every run needs a stable request key.\n"
                "Permissions are in the owner grant. Never add --allow-* flags, change your profile, or bypass the broker.\n"
                "If locked, expired, revoked, unconfigured or conflicting, report the exact blocker. Do NOT fall back to direct ATM, read the vault,\n"
                "request saved supplier Keys, grant yourself access, change trust, resolve conflicts, or start an unlock service.\n"
                "The owner starts the broker once for the lease. New sessions reuse it. Same-user processes are not adversarially isolated.\n"
                "Workflows, MCP and handoffs are not supported through this v0.5 scoped broker. Do not pretend they ran.\n").encode()
    paths = [str(executable), str(state_home.expanduser().absolute())]
    if any(c in "".join(paths) for c in "\r\n\x00"):
        raise RouterError("unsafe_path", "Runtime paths contain control characters.")
    if os.name == "nt":
        quote = lambda s: "'" + s.replace("'", "''") + "'"
        prefix = "& " + quote(paths[0]) + " --home " + quote(paths[1])
        language = "powershell"
    else:
        prefix = shlex.join([paths[0], "--home", paths[1]])
        language = "sh"
    content = files("agent_tool_maker.data").joinpath("SKILL.md").read_text(encoding="utf-8")
    return (content + f"\n## Registered local runtime — ATM {__version__}\n\n"
            "Use this exact command prefix from every project; append a subcommand. "
            "Do not create another vault or depend on the project's virtualenv.\n\n"
            f"```{language}\n{prefix} doctor\n```\n\n"
            "The paths are local to this OS user. They do not connect a cloud session to this machine.\n").encode("utf-8")


def file_plan(path: Path, content: bytes, replace: bool = False) -> dict:
    safe_target(path)
    old = path.read_bytes() if path.exists() else None
    state = "create" if old is None else "unchanged" if old == content else "replace" if replace else "conflict"
    return {"path": str(path), "action": state,
            "previous_sha256": hashlib.sha256(old).hexdigest() if old is not None else None,
            "sha256": hashlib.sha256(content).hexdigest()}


def write_planned(plan: dict, content: bytes) -> dict:
    path = Path(plan["path"])
    current = file_plan(path, content, replace=plan["action"] == "replace")
    if current != plan:
        raise RouterError("setup_changed", "Skill changed after planning; run setup again and review the new plan.")
    result = dict(plan)
    if plan["action"] == "conflict":
        raise RouterError("skill_conflict", "Existing Skill differs; review it and use --replace-skills to back it up before replacement.")
    if plan["action"] == "unchanged":
        return result
    if path.exists():
        backup = path.with_name("SKILL.md.bak-" + uuid.uuid4().hex)
        atomic_write(backup, path.read_bytes())
        result["backup"] = str(backup)
    # atomic_write protects the leaf; check parents again immediately before writing.
    safe_target(path)
    atomic_write(path, content)
    return result


def export_skill(destination: Path, *, replace: bool = False) -> dict:
    target = destination.expanduser().absolute() / "agent-tool-maker" / "SKILL.md"
    content = files("agent_tool_maker.data").joinpath("SKILL.md").read_bytes()
    item = file_plan(target, content, replace)
    result = write_planned(item, content)
    return {"skill_path": str(target), **result,
            "host_registration": "Export only. Use atm setup --agent NAME for user-level registration."}


def setup(router, *, agents=(), cli_names=(), executable=None, apply=False,
          replace_skills=False, user_home=None, broker=False) -> dict:
    """Preview by default. Explicit --apply changes selected non-secret configuration."""
    agents, cli_names = list(dict.fromkeys(agents)), list(dict.fromkeys(cli_names))
    if any(a not in CLIENTS for a in agents):
        raise RouterError("unsupported_agent", "Supported user-level clients: codex, claude.")
    allowed = ({t.get("executable") for t in router.catalog.tools.values()} - {None}) | {"claude", "codex"}
    if any(name not in allowed for name in cli_names):
        raise RouterError("unsupported_cli", "Choose a CLI present in atm list; no automatic third-party plugin installation.")
    home = Path(user_home or Path.home()).expanduser().absolute()
    exe = executable_path(executable) if agents else None
    contents = {a: render_skill(exe, router.state.home, client=a if broker else None) for a in agents}
    skill_plans = []
    for agent in agents:
        root = home / CLIENTS[agent]
        if agent == "claude" and os.environ.get("CLAUDE_CONFIG_DIR"):
            root = Path(os.environ["CLAUDE_CONFIG_DIR"]).expanduser().absolute() / "skills"
        target = root / "agent-tool-maker" / "SKILL.md"
        skill_plans.append({"agent": agent, **file_plan(target, contents[agent], replace_skills)})
    cli_plans = []
    for name in cli_names:
        bound = router.state.setting("cli:" + name)
        candidate = bound or shutil.which(name)
        item = {"name": name, "path": candidate, "action": "missing_program"}
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            digest = hashlib.sha256(Path(candidate).read_bytes()).hexdigest()
            expected = router.state.setting("cli_hash:" + name)
            item.update(path=str(Path(candidate).resolve()), sha256=digest,
                        action="bind" if not bound else "unchanged" if expected == digest else "review_required")
        elif bound:
            item["action"] = "review_required"
        cli_plans.append(item)
    conflicts = [p for p in skill_plans if p["action"] == "conflict"]
    conflicts += [p for p in cli_plans if p["action"] == "review_required"]
    if apply and conflicts:
        raise RouterError("setup_conflict", "No selected binding or Skill was changed. Review changed binaries with atm cli bind, or review differing Skills with --replace-skills.")
    # Preflight every destination/binary before making any selected change.
    if apply:
        for item in cli_plans:
            if item["action"] in {"bind", "unchanged"}:
                if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
                    raise RouterError("setup_changed", "Executable changed after planning; rerun setup.")
        for item in skill_plans:
            if file_plan(Path(item["path"]), contents[item["agent"]], replace_skills) != {k: v for k, v in item.items() if k != "agent"}:
                raise RouterError("setup_changed", "Skill changed after planning; rerun setup.")
        for item in cli_plans:
            if item["action"] == "bind":
                bind_cli(router.state, item["name"], item["path"])
        for i, item in enumerate(skill_plans):
            written = write_planned({k: v for k, v in item.items() if k != "agent"}, contents[item["agent"]])
            skill_plans[i] = {"agent": item["agent"], **written}
            router.state.set_setting("agent:" + item["agent"], {
                "path": item["path"], "executable": str(exe), "home": str(router.state.home),
                "sha256": item["sha256"], "version": __version__, "mode": "broker" if broker else "direct"})
    backend = router.state.setting("vault", {}).get("backend")
    next_steps = []
    if not backend:
        next_steps.append("Human: initialize a native keyring once with atm vault init --backend keyring; no vault is reset by setup.")
    for p in cli_plans:
        if p["action"] == "missing_program":
            next_steps.append(f"Install and review {p['name']} from its maintained distribution, then rerun the same setup command.")
        elif p["action"] == "review_required":
            next_steps.append(f"Review the changed {p['name']} installation; explicitly rebind it instead of resetting credentials.")
    next_steps.append("Human: connect only missing credentials privately and complete vendor login/consent when required. Existing logins are reused, not verified by setup.")
    return {"version": __version__, "home": str(router.state.home), "applied": apply,
            "status": "needs_review" if conflicts else "needs_dependencies" if any(p["action"] == "missing_program" for p in cli_plans) else "applied" if apply else "planned",
            "skills": skill_plans, "clis": cli_plans, "vault_backend": backend,
            "network_calls": 0, "secrets_read": False, "programs_installed": 0,
            "next_steps": next_steps,
            "note": "Plan may initialize local ATM state. Filesystem and SQLite writes are not a cross-resource transaction; rerun after a filesystem error."}
