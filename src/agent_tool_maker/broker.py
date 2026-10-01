"""Local capability broker: one vault unlock, bounded reusable agent authorization.

A dedicated Unix socket, not the Web console. Owner CLI creates random bearer
profiles with exact tool-definition/configuration/workspace constraints. The
broker never returns a secret and never offers management, key lookup, sync or
arbitrary Shell RPC. Separate OS users are required for hostile-client isolation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import socket
import socketserver
import stat
import struct
import threading
import time
import uuid

from .engine import Router
from .errors import RouterError
from .storage import State, atomic_write, canonical
from .sync import strict_json
from .vault import Vault

MAX_MESSAGE = 1024 * 1024
ALLOWED_ADAPTERS = {"web_recipe", "rest", "command", "elevenlabs", "fal", "higgsfield", "tripo", "exa", "firecrawl", "ffprobe", "ffmpeg", "xyq"}
# Workflows and MCP can transitively execute capabilities; v0.5 deliberately
# excludes them from broker grants rather than accidentally widening authority.


def client_path(agent: str, user_home=None) -> Path:
    if agent not in {"claude", "codex"}:
        raise RouterError("unsupported_agent", "Use claude or codex, or an explicit private --profile path.")
    return Path(user_home or Path.home()).expanduser().absolute() / ".config/agent-tool-maker/clients" / (agent + ".json")


def socket_path(state: State) -> Path:
    return state.home / "broker.sock"


def safe_path(path: Path, *, secret=False) -> Path:
    path = Path(path).expanduser().absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise RouterError("unsafe_profile_path", "Profile/socket paths must not traverse symbolic links.")
    if secret and path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536 or (os.name == "posix" and (info.st_mode & 0o077 or info.st_uid != os.getuid())):
            raise RouterError("unsafe_profile_permissions", "Client profile must be an owner-only regular file.")
    return path


def _tool_pin(router, tool_id: str) -> dict:
    from .maker import digest
    tool = router.catalog.get(tool_id)
    if tool["adapter"] not in ALLOWED_ADAPTERS:
        raise RouterError("broker_unsupported_tool", "This broker version permits direct registered API/CLI and bounded web recipes, not MCP, workflows or handoffs.")
    selected = {"definition": digest(tool)}
    if tool.get("executable"):
        name = tool["executable"]
        selected["cli"] = {"path": router.state.setting("cli:" + name), "sha256": router.state.setting("cli_hash:" + name)}
    if tool.get("request", {}).get("origin_setting"):
        selected["origin"] = router.state.setting("origin:" + tool["provider"])
    return selected


def resolve_group(value):
    if os.name != "posix":
        raise RouterError("broker_platform", "Unix group sockets are not available on this platform.")
    import grp
    try:
        gid = grp.getgrnam(value).gr_gid if isinstance(value, str) else grp.getgrgid(value).gr_gid
    except (KeyError, TypeError):
        raise RouterError("unknown_group", "Choose an existing local group; ATM does not create OS users/groups.") from None
    if os.geteuid() != 0 and gid not in set(os.getgroups()) | {os.getgid()}:
        raise RouterError("group_denied", "The broker owner is not a member of this group.")
    return gid


def _ttl(hours, maximum=720):
    if type(hours) not in (int, float) or not math.isfinite(hours) or not 0 < hours <= maximum:
        raise RouterError("invalid_ttl", f"Duration must be positive and at most {maximum} hours.")
    return float(hours) * 3600


def grant(router, agent: str, *, tools, workspace: Path, output: Path | None = None,
          socket_file: Path | None = None, ttl_hours=168, grants=(), allow_paid=False,
          apply=False, user_home=None, client_uid=None, socket_group=None,
          expected_plan_sha256: str | None = None) -> dict:
    if os.name != "posix":
        raise RouterError("broker_platform", "Broker grants require macOS/Linux; Windows support is deferred.")
    uid = os.getuid() if client_uid is None else client_uid
    if type(uid) is not int or not 0 <= uid < 2**31:
        raise RouterError("invalid_uid", "Use a numeric local client UID.")
    gid = resolve_group(socket_group) if socket_group is not None else None
    if not isinstance(agent, str) or not agent or len(agent) > 80 or any(ord(c) < 32 for c in agent):
        raise RouterError("invalid_agent", "Use a bounded client label.")
    if not isinstance(tools, (list, tuple)) or not 1 <= len(tools) <= 100 or len(set(tools)) != len(tools):
        raise RouterError("invalid_grant", "Select 1–100 distinct exact tool IDs.")
    if set(grants) - {"external_write", "production", "execute_code"} or type(allow_paid) is not bool:
        raise RouterError("invalid_grant", "Unknown permission; no grant was created.")
    workspace = safe_path(workspace)
    if not workspace.is_dir():
        raise RouterError("workspace_missing", "Create the explicitly approved project directory first.")
    # Never grant the vault/config directory or a parent of it as an output workspace.
    state_home = router.state.home.resolve()
    if state_home == workspace or state_home.is_relative_to(workspace) or workspace.is_relative_to(state_home):
        raise RouterError("unsafe_workspace", "The broker state directory and its ancestors/descendants cannot be a project workspace.")
    path = safe_path(output or client_path(agent, user_home), secret=True)
    sock = safe_path(socket_file or socket_path(router.state))
    seconds = _ttl(ttl_hours)
    pins = {t: _tool_pin(router, t) for t in tools}
    for tool_id in tools:
        tool = router.catalog.get(tool_id)
        if set(tool.get("permissions", [])) - set(grants) or (tool.get("paid") and not allow_paid):
            raise RouterError("insufficient_grant", "The selected tool requires additional explicitly approved permissions or spending.")
    if path.exists():
        raise RouterError("profile_exists", "Existing bearer profile preserved. Revoke the old grant and choose a new profile path for rotation.")
    base = {"agent": agent, "tools": sorted(tools), "workspace": str(workspace), "profile": str(path),
            "socket": str(sock), "ttl_hours": ttl_hours, "client_uid": uid, "socket_owner_uid": os.getuid(), "socket_gid": gid, "permissions": sorted(set(grants)), "allow_paid": allow_paid, "pins": pins}
    plan = {**base, "applied": False, "status": "planned", "secrets_returned": False}
    if not apply:
        return plan
    if expected_plan_sha256 is not None:
        actual_digest = hashlib.sha256(canonical(plan).encode()).hexdigest()
        if (not isinstance(expected_plan_sha256, str) or not expected_plan_sha256.isascii()
                or not hmac.compare_digest(expected_plan_sha256, actual_digest)):
            raise RouterError("plan_changed", "Review the exact current grant before applying.")
    # Validate and persist the SAME snapshot: never re-read configuration after
    # checking the approved digest. Later drift makes these pins stale at broker
    # admission rather than granting authority absent from the approved plan.
    identifier, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
    policy = {**base, "id": identifier, "pins": pins, "token_hash": hashlib.sha256(token.encode()).hexdigest(),
              "created_at": time.time(), "expires_at": time.time() + seconds, "revoked": False}
    # Fail closed if file creation fails: an orphan DB grant has no retrievable token.
    router.state.set_setting("access:" + identifier, policy)
    try:
        raw = canonical({"format": "atm-client-v1", "id": identifier, "agent": agent, "socket": str(sock), "token": token, "socket_owner_uid": os.getuid(), "socket_gid": gid}).encode()
        from .sync import write_sync_file
        write_sync_file(path, raw)
    except BaseException:
        router.state.set_setting("access:" + identifier, {**policy, "revoked": True})
        raise
    return {**base, "id": identifier, "expires_at": policy["expires_at"], "applied": True, "secrets_returned": False}


def list_grants(state: State) -> dict:
    with state.db() as db:
        values = [json.loads(r[0]) for r in db.execute("SELECT value FROM settings WHERE name LIKE 'access:%' ORDER BY name")]
    fields = ("id", "agent", "tools", "workspace", "permissions", "allow_paid", "created_at", "expires_at", "revoked", "client_uid")
    return {"grants": [{**{k: v[k] for k in fields}, "kind": v.get("kind", "tools"),
                       "credential_scope": sorted({name for rule in v.get("exec_rules", []) for name in rule["environment"].values()}),
                       "exec_rules": v.get("exec_rules", [])} for v in values if v.get("kind") != "session_owner"],
            "secrets_returned": False, "clock": time.time()}



def revoke(state: State, identifier: str, *, apply=False) -> dict:
    with state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        from .sync import _get, _set
        value = _get(db, "access:" + identifier)
        if not value:
            raise RouterError("grant_not_found", "No such local broker grant.")
        if apply:
            _set(db, "access:" + identifier, {**value, "revoked": True})
    return {"id": identifier, "revoked": apply, "note": "Effective on next admission; does not cancel an already admitted upstream call."}


class Broker(getattr(socketserver, "ThreadingUnixStreamServer", socketserver.ThreadingTCPServer)):
    daemon_threads = True
    block_on_close = True

    def __init__(self, home, *, socket_file=None, ttl_hours=8, vault=None, router_factory=None, socket_group=None):
        if os.name != "posix":
            raise RouterError("broker_platform", "The session broker requires Unix-domain sockets on macOS/Linux. Windows support is deferred.")
        self.gid = resolve_group(socket_group) if socket_group is not None else None
        if self.gid is not None and not hasattr(socket, "SO_PEERCRED"):
            raise RouterError("broker_platform", "Cross-UID group sockets currently require Linux peer credentials.")
        self.state = State(Path(home))
        self.vault = vault or Vault(self.state)
        self.deadline = time.monotonic() + _ttl(ttl_hours, maximum=720)
        self.started_at = time.time()
        self.router_factory = router_factory
        self.lock = threading.RLock()
        self.path = safe_path(socket_file or socket_path(self.state))
        if len(os.fsencode(str(self.path))) > 100:
            raise RouterError("socket_path_too_long", "Choose a shorter owner-only Unix socket path with --socket.")
        if self.path.exists():
            raise RouterError("broker_socket_exists", "Existing socket preserved. Stop the running broker or inspect/remove a confirmed stale socket.")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.parent.stat().st_mode & 0o022:
            raise RouterError("unsafe_socket_directory", "Socket directory must not be group/world writable.")
        self._key = self.vault.unlock()  # Only after local argument/path validation.
        super().__init__(str(self.path), BrokerHandler)
        if self.gid is not None:
            os.chown(self.path, -1, self.gid)
        self.path.chmod(0o600 if self.gid is None else 0o660)
        self.socket_inode = self.path.stat().st_ino
        self.vault.password = None
        self.vault._used_secrets.clear()
        self.state.set_setting("broker_status", {"pid": os.getpid(), "socket": str(self.path), "started_at": self.started_at,
                                                  "lease_expires_at": self.started_at + _ttl(ttl_hours), "state": "running"})

    def handle_error(self, request, client_address):
        pass  # No tracebacks containing user inputs, tokens, credentials or responses.

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(15)
        return sock, address

    def open_router(self):
        if self.router_factory:
            return self.router_factory()
        router = Router(self.state.home)
        router.vault._key = self._key
        return router

    def _authorize(self, request, peer_uid, *, require_unlocked=True):
        if require_unlocked and (time.monotonic() >= self.deadline or self._key is None):
            raise RouterError("broker_locked", "Broker lease ended. An owner must unlock a new session; no direct-vault fallback is permitted.")
        if not isinstance(request, dict) or set(request) != {"id", "token", "operation", "args"} or not isinstance(request["args"], dict):
            raise RouterError("invalid_request", "Malformed broker request.")
        identifier, token = request["id"], request["token"]
        if not isinstance(identifier, str) or len(identifier) != 32 or not isinstance(token, str) or len(token) > 100:
            raise RouterError("unauthorized", "Broker credential rejected.")
        policy = self.state.setting("access:" + identifier)
        valid = policy and not policy["revoked"] and time.time() < policy["expires_at"]
        if not valid or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), policy["token_hash"]):
            raise RouterError("unauthorized", "Broker credential expired, revoked or invalid.")
        if peer_uid != policy["client_uid"]:
            raise RouterError("peer_uid_denied", "This grant is bound to a different OS user.")
        if policy["socket_gid"] != self.gid or policy["socket_owner_uid"] != os.getuid():
            raise RouterError("unauthorized", "Socket identity does not match this grant.")
        if policy["socket"] != str(self.path):
            raise RouterError("unauthorized", "Grant is bound to a different socket.")
        return policy

    @staticmethod
    def _workspace(policy, value):
        if not isinstance(value, str):
            raise RouterError("workspace_denied", "An explicit authorized workspace is required.")
        path = safe_path(Path(value))
        approved = Path(policy["workspace"])
        if not path.is_dir() or (path != approved and not path.is_relative_to(approved)):
            raise RouterError("workspace_denied", "Workspace is outside this grant.")
        return path

    @staticmethod
    def _check_tool(router, policy, tool_id):
        if not isinstance(tool_id, str) or tool_id not in policy["tools"]:
            raise RouterError("tool_denied", "Tool is outside this agent grant.")
        if _tool_pin(router, tool_id) != policy["pins"][tool_id]:
            raise RouterError("grant_stale", "Tool definition or approved executable/origin changed. Owner review is required.")
        tool = router.catalog.get(tool_id)
        credentials = [tool["credential"]] if tool.get("credential") else []
        credentials += list(tool.get("command", {}).get("credential_env", {}).values())
        for name in credentials:
            if router.state.setting("sync_conflict:" + name, False):
                raise RouterError("sync_conflict", "Credential conflict blocks execution until an owner resolves it.")
            meta = router.state.setting("credential_meta:" + name, {})
            if meta.get("expires_at") is not None and meta["expires_at"] <= time.time():
                raise RouterError("credential_expired", "Renew the selected upstream credential; session reuse cannot bypass its expiry.")
        return tool

    def handle(self, request, *, peer_uid=None):
        # Admission lock makes revoke/lock behavior easy to reason about in this version.
        # Long-running external tasks are not cancelled, and only one call executes at a time.
        with self.lock:
            policy = self._authorize(request, os.getuid() if peer_uid is None else peer_uid)
            op, args = request["operation"], request["args"]
            allowed_fields = {"status": set(), "search": {"query", "capability"}, "describe": {"tool"},
                              "run": {"tool", "inputs", "workspace", "request_key", "dry_run", "expect_definition"}, "job": {"id", "refresh"}}
            if op not in allowed_fields or set(args) - allowed_fields[op]:
                raise RouterError("operation_denied", "Broker supports only status, search, describe, run and owned-job query.")
            if op == "status":
                return {"agent": policy["agent"], "grant_id": policy["id"], "tools": policy["tools"],
                        "workspace": policy["workspace"], "expires_at": policy["expires_at"],
                        "broker_seconds_remaining": max(0, int(self.deadline-time.monotonic())), "secrets_returned": False}
            router = self.open_router()
            try:
                if op == "search":
                    query, capability = args.get("query", ""), args.get("capability")
                    if not isinstance(query, str) or len(query) > 2000 or capability is not None and not isinstance(capability, str):
                        raise RouterError("invalid_request", "Invalid capability query.")
                    return {"tools": [{k: t[k] for k in ("id", "title", "capabilities", "readiness")} for t in router.search(query, capability) if t["id"] in policy["tools"]]}
                if op in {"run", "describe"}:
                    tool = self._check_tool(router, policy, args.get("tool"))
                    if op == "describe":
                        return {k: tool.get(k) for k in ("id", "title", "schema", "permissions", "paid", "capabilities")}
                    from .maker import digest
                    if args.get("expect_definition") is not None and args["expect_definition"]!=digest(tool):
                        raise RouterError("definition_changed","Generated CLI definition differs from the installed tool.")
                    path = self._workspace(policy, args.get("workspace"))
                    inputs = args.get("inputs")
                    if not isinstance(inputs, dict) or type(args.get("dry_run", False)) is not bool:
                        raise RouterError("invalid_request", "Inputs must be an object and dry_run must be boolean.")
                    key = args.get("request_key")
                    if not isinstance(key, str) or not 1 <= len(key) <= 120:
                        raise RouterError("request_key_required", "Broker calls require a stable request key of 1–120 characters.")
                    if args.get("dry_run"):
                        from .actions import preflight
                        router.catalog.validate(tool["id"], inputs)
                        return {"dry_run": True, "plan": preflight(router, tool, inputs, path), "credentials_read": False}
                    job = router.run(tool["id"], inputs, path, request_key="broker:"+policy["id"]+":"+key,
                                     allow_paid=policy["allow_paid"], grants=policy["permissions"])
                    # Ownership also follows the namespaced request key after an admission crash.
                    return router.public_job(job)
                jid = args.get("id")
                if not isinstance(jid, str) or len(jid) > 100 or type(args.get("refresh", False)) is not bool:
                    raise RouterError("invalid_request", "Invalid job request.")
                job = router.state.job(jid)
                if not job["request_key"].startswith("broker:"+policy["id"]+":"):
                    raise RouterError("job_denied", "This grant cannot read another grant's task.")
                self._workspace(policy, job["workspace"])
                self._check_tool(router, policy, job["tool"])
                return router.public_job(router.refresh(jid) if args.get("refresh") else job)
            finally:
                router.close()
                router.vault._used_secrets.clear()
                router.vault._key = None
                router.vault.password = None

    def server_close(self):
        super().server_close()
        self._key = None
        self.vault._key = None
        self.vault.password = None
        self.vault._used_secrets.clear()
        try:
            if self.path.is_socket() and self.path.stat().st_ino == self.socket_inode:
                self.path.unlink()
        except OSError:
            pass
        self.state.set_setting("broker_status", {"state": "stopped", "at": time.time(), "socket": str(self.path)})


class BrokerHandler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            raw = self.rfile.readline(MAX_MESSAGE + 1)
            if not raw.endswith(b"\n") or len(raw) > MAX_MESSAGE:
                raise RouterError("invalid_request", "Broker request is too large or incomplete.")
            if hasattr(socket, "SO_PEERCRED"):
                peer_uid = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[1]
            else:
                # Owner-only socket mode; group sockets are rejected on these platforms.
                peer_uid = os.getuid()
            result = self.server.handle(strict_json(raw, limit=MAX_MESSAGE), peer_uid=peer_uid)
            raw_response = canonical({"result": result}).encode()
            if len(raw_response) > MAX_MESSAGE:
                raise RouterError("response_too_large", "Task response exceeds broker limit; inspect the existing task without resubmitting it.", uncertain=True)
        except RouterError as error:
            raw_response = canonical({"error": error.as_dict()}).encode()
        except Exception:
            raw_response = canonical({"error": {"code": "broker_failure", "message": "Request failed; reconcile existing tasks before retrying.", "outcome_uncertain": True}}).encode()
        try:
            self.wfile.write(raw_response + b"\n")
        except OSError:
            pass


def call(profile: Path, operation: str, args: dict, *, timeout=300):
    path = safe_path(profile, secret=True)
    if not path.exists():
        raise RouterError("client_not_configured", "No client profile. Ask the Owner for the specific command/credential grant, not the raw Key.")
    cfg = strict_json(path.read_bytes(), limit=65536)
    if not isinstance(cfg, dict) or set(cfg) != {"format", "id", "agent", "socket", "token", "socket_owner_uid", "socket_gid"} or cfg["format"] != "atm-client-v1":
        raise RouterError("invalid_profile", "Malformed broker profile; do not print it in a transcript.")
    sockpath = safe_path(Path(cfg["socket"]))
    info = sockpath.stat() if sockpath.exists() else None
    mode = 0o600 if cfg["socket_gid"] is None else 0o660
    if not sockpath.is_socket() or info.st_mode & 0o777 != mode or info.st_uid != cfg["socket_owner_uid"] or cfg["socket_gid"] is not None and info.st_gid != cfg["socket_gid"]:
        raise RouterError("broker_unavailable", "Owner-only broker socket is unavailable. No fallback or password prompt was attempted.")
    message = canonical({"id": cfg["id"], "token": cfg["token"], "operation": operation, "args": args}).encode() + b"\n"
    if len(message) > MAX_MESSAGE:
        raise RouterError("request_too_large", "Broker request exceeds 1 MiB.")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(timeout)
            conn.connect(str(sockpath))
            if hasattr(socket, "SO_PEERCRED"):
                server_uid = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[1]
                if server_uid != cfg["socket_owner_uid"]:
                    raise RouterError("server_uid_denied", "Connected broker UID differs from the approved owner.")
            conn.sendall(message)
            with conn.makefile("rb") as stream:
                response = stream.readline(MAX_MESSAGE + 1)
    except OSError:
        raise RouterError("broker_unavailable", "Broker is stopped, locked or unreachable. Reconcile the stable request key; no direct-vault fallback occurred.", uncertain=operation in {"run", "exec"}) from None
    value = strict_json(response, limit=MAX_MESSAGE)
    if "error" in value:
        error = value["error"]
        raise RouterError(error["code"], error["message"], uncertain=error.get("outcome_uncertain", False))
    return value["result"]


def serve(home, *, socket_file=None, ttl_hours=8, socket_group=None):
    server = Broker(home, socket_file=socket_file, ttl_hours=ttl_hours, socket_group=socket_group)
    try:
        print(canonical({"socket": str(server.path), "unlocked": True, "lease_hours": ttl_hours,
                         "pid": os.getpid(), "note": "Foreground broker; Ctrl-C stops it. Client grants are independent and scoped. No key is printed."}), flush=True)
        # Expiry stops servicing secrets even if the process has not yet terminated.
        def expire():
            remaining = max(0, server.deadline - time.monotonic())
            if not stopped.wait(remaining):
                server.shutdown()
        stopped = threading.Event()
        watcher = threading.Thread(target=expire, daemon=True)
        watcher.start()
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        server.server_close()
    return 0
