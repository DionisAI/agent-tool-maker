"""Server-owned Chromium and same-user Unix bridge. No credential export or TCP API."""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import signal
import socket
import stat
import struct
import sys
import tempfile
import time
import uuid
from pathlib import Path

from .errors import RouterError
from .storage import atomic_write, canonical

ORIGIN = "https://studio.tripo3d.ai"
DATA = Path(__file__).parent / "data" / "tripo_server"
LIMIT = 2 * 1024 * 1024
CDP_METHODS = {"DOM.getDocument", "DOM.querySelector", "DOM.setFileInputFiles",
               "Input.dispatchKeyEvent", "Input.dispatchMouseEvent"}
TICKET_ENV = "ATM_STUDIO_TICKET"
TICKET_TTL = 60


def private_path(path: Path, *, directory=False):
    """Inspect path metadata only; never inspect browser profile contents."""
    path = path.expanduser().absolute()
    for item in [path, *path.parents]:
        if item.is_symlink():
            raise RouterError("unsafe_path", "Server state paths must not traverse symbolic links.")
    if directory:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        info = path.stat()
        if info.st_uid != os.getuid() or directory and not stat.S_ISDIR(info.st_mode):
            raise RouterError("unsafe_path", "Server state must belong to this OS user.")
        if directory:
            path.chmod(0o700)
    return path


def studio_dir(home):
    return private_path(Path(home) / "studio", directory=True)


def bundle_digest():
    h = hashlib.sha256()
    # Include driver, protocol and reviewed adapters, not mutable browser state.
    paths = sorted(DATA.iterdir()) + [Path(__file__), Path(__file__).with_name("studio_cli.py")]
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise RouterError("definition_changed", "Server bundle must contain regular reviewed files.")
        h.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()


def index():
    return json.loads((DATA / "index.json").read_text())


def validate_request(operation, argv, workspace):
    """Reverse the original fixed manifest argv and reuse its exact input schema."""
    from jsonschema import Draft202012Validator
    spec = index().get(operation)
    if not spec or not isinstance(argv, list) or any(not isinstance(v, str) for v in argv):
        raise RouterError("invalid_argument", "Unknown server operation or malformed arguments.")
    template = spec["command"]["argv"][3:]
    if len(argv) != len(template):
        raise RouterError("invalid_argument", "Arguments must match the reviewed command exactly.")
    values = {}
    for expected, actual in zip(template, argv):
        if isinstance(expected, str):
            if expected != actual:
                raise RouterError("definition_changed", "Static command arguments or source pin changed.")
        elif "workspace" in expected:
            if actual != str(workspace):
                raise RouterError("unsafe_path", "Ledger must be the exact execution workspace.")
        elif "output" in expected:
            destination = private_path(Path(actual))
            if not destination.is_absolute() or not destination.is_relative_to(workspace) or destination.name != expected["output"]:
                raise RouterError("unsafe_path", "Export output must match the fixed project artifact name.")
        else:
            field = expected.get("input", expected.get("json", expected.get("file")))
            schema = spec["schema"]["properties"][field]
            try:
                value = json.loads(actual) if "json" in expected else int(actual) if schema.get("type") == "integer" else actual
            except (ValueError, TypeError):
                raise RouterError("invalid_input", "Invalid typed command argument.") from None
            values[field] = value
            if "file" in expected:
                source = private_path(Path(actual))
                if not source.is_absolute() or not source.is_relative_to(workspace) or not source.is_file():
                    raise RouterError("unsafe_path", "Upload input must be an explicit file within this project.")
    # The static --confirm stands for the const confirmation the Router already validated
    # on the real inputs; run() executes such operations only with that Router's ticket.
    for field, schema in spec["schema"]["properties"].items():
        if schema.get("const") is True and "--confirm" in template:
            values[field] = True
    if next(Draft202012Validator(spec["schema"]).iter_errors(values), None):
        raise RouterError("invalid_input", "Server input does not satisfy the reviewed tool schema.")
    private_path(workspace)
    if not workspace.is_dir() or workspace == Path("/"):
        raise RouterError("unsafe_path", "Use an existing absolute project directory.")
    return spec


def router_only(spec):
    """All but read-only page scripts; the server never grants write, paid or confirmation consent itself."""
    read_only = not spec["paid"] and set(spec["permissions"]) <= {"execute_code"}
    return not read_only or any(field.get("const") is True for field in spec["schema"]["properties"].values())


def _ticket_binding(operation, argv, workspace, bundle):
    return {"tool": "tripo.server." + operation, "argv_sha256": hashlib.sha256(canonical(argv).encode()).hexdigest(),
            "workspace": str(workspace), "bundle": bundle}


def issue_ticket(state, job, argv, workspace):
    """Router side, after paid/permission/broker gates and the job claim: bind ONE server call.

    argv is the installed manifest's full command: --home H studio adapter --bundle PIN OP ARGS..."""
    spec = index().get(argv[6]) if argv[2:5] == ["studio", "adapter", "--bundle"] and len(argv) > 6 else None
    if not spec or not router_only(spec):
        return {}
    secret = secrets.token_hex(32)
    ticket = {"sha256": hashlib.sha256(secret.encode()).hexdigest(), "expires_at": time.time() + TICKET_TTL,
              **_ticket_binding(argv[6], argv[7:], workspace, argv[5])}
    # Only the hash is stored; the secret reaches the adapter process environment alone.
    state.update_job(job["id"], job["status"], studio_ticket=ticket)
    return {TICKET_ENV: job["id"] + "." + secret}


def consume_ticket(home, ticket, spec, operation, argv, workspace, bundle):
    """Server side: accept a router-only call once, for its exact Router job, argv, project and bundle."""
    from .storage import State
    job_id, _, secret = ticket.partition(".") if isinstance(ticket, str) else ("", "", "")
    binding = _ticket_binding(operation, argv, workspace, bundle)
    digest = hashlib.sha256(secret.encode()).hexdigest().encode()
    with State(home).db() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT tool,status,data FROM jobs WHERE id=?", (job_id,)).fetchone()
        data = json.loads(row["data"]) if row else {}
        record = data.get("studio_ticket") or {}
        if not (row and secret and row["tool"] == binding["tool"] and row["status"] == "submitting"
                and (data.get("paid_granted") is True or not spec["paid"]) and "consumed_at" not in record
                and set(spec["permissions"]) <= set(data.get("permissions_granted") or [])
                and time.time() < record.get("expires_at", 0) and all(record.get(k) == v for k, v in binding.items())
                and hmac.compare_digest(str(record.get("sha256")).encode(), digest)):
            raise RouterError("router_ticket_required", "Write, paid or human-confirmed server operations run only through atm studio run "
                              "or atm run, which issue a single-use ticket after their gates; nothing was submitted.")
        record["consumed_at"] = time.time()
        c.execute("UPDATE jobs SET data=?,updated=? WHERE id=?", (canonical({**data, "studio_ticket": record}), record["consumed_at"], job_id))
        c.execute("INSERT INTO events(job_id,kind,at) VALUES (?,?,?)", (job_id, "studio_ticket_consumed", record["consumed_at"]))


def same_user(writer):
    sock = writer.get_extra_info("socket")
    if hasattr(socket, "SO_PEERCRED"):
        _, uid, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    elif hasattr(sock, "getpeereid"):
        uid, _ = sock.getpeereid()
    else:
        # CPython builds may omit socket.getpeereid even though macOS libc has it.
        if sys.platform != "darwin":
            raise RouterError("unsupported_peer_check", "This platform lacks a supported Unix peer-UID check.")
        import ctypes
        library = ctypes.CDLL(None, use_errno=True)
        peer = library.getpeereid
        peer.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
        peer.restype = ctypes.c_int
        user, group = ctypes.c_uint(), ctypes.c_uint()
        if peer(sock.fileno(), ctypes.byref(user), ctypes.byref(group)) != 0:
            raise RouterError("unauthorized", "Unix peer credentials could not be verified.")
        uid = user.value
    if uid != os.getuid():
        raise RouterError("unauthorized", "Server bridge accepts only the owning OS user.")


async def request(home, packet, timeout=960):
    path = private_path(studio_dir(home) / "runtime.json")
    try:
        meta = json.loads(path.read_text())
        if meta["status"] != "running":
            raise RouterError("runtime_stopped", "Start the server-owned browser service first.")
        socket_path = private_path(Path(meta["socket"]))
        if not stat.S_ISSOCK(socket_path.stat().st_mode) or socket_path.stat().st_mode & 0o077:
            raise RouterError("unsafe_path", "Runtime socket must be private and owned by this user.")
        reader, writer = await asyncio.open_unix_connection(str(socket_path), limit=LIMIT + 1)
    except (OSError, ValueError, KeyError):
        raise RouterError("runtime_unavailable", "Server browser is not reachable; no operation was replayed.") from None
    try:
        writer.write(canonical(packet).encode() + b"\n")
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout)
        result = json.loads(line)
        if "error" in result:
            error = result["error"]
            raise RouterError(error["code"], error["message"], uncertain=error.get("outcome_uncertain", False))
        return result["result"]
    except (OSError, ValueError, asyncio.TimeoutError):
        raise RouterError("runtime_transport", "Bridge response was interrupted; reconcile side effects before retry.", uncertain=packet.get("method") == "run") from None
    finally:
        writer.close()
        await writer.wait_closed()


class BrowserRuntime:
    def __init__(self, home, context, node, display=None, authority=None):
        self.home, self.context, self.node, self.display = Path(home), context, node, display
        self.authority = authority
        self.page = context.pages[0] if context.pages else None
        self.lock = asyncio.Lock()
        self.active = None
        self.downloads = []
        self.download_event = asyncio.Event()
        self.download_arms = {}
        self.vnc = None
        self.login_until = 0
        self.login_timer = None
        self.bridge = None

    async def start(self):
        if self.page is None:
            self.page = await self.context.new_page()
        self.page.set_default_timeout(15000)
        self.page.on("download", self._download)
        self.cdp = await self.context.new_cdp_session(self.page)

    def _download(self, download):
        self.downloads.append(download)
        self.download_event.set()

    async def close_login(self):
        if self.vnc:
            if self.vnc.returncode is None:
                self.vnc.terminate()
            await self.vnc.wait()
            self.vnc = None
        if self.login_timer:
            self.login_timer.cancel()
            self.login_timer = None
        self.login_until = 0
        return {"status": "closed", "browser_kept_running": True, "profile_preserved": True}

    async def expire_login(self, expected):
        async with self.lock:
            if self.vnc is expected:
                await self.close_login()

    async def login(self, ttl=600, port=5900):
        import shutil
        if not self.display or not self.authority:
            raise RouterError("headed_required", "Start serve with --virtual-display for the temporary server login viewer.")
        if not isinstance(ttl, int) or not 60 <= ttl <= 1800 or not isinstance(port, int) or not 1024 <= port <= 65535:
            raise RouterError("invalid_argument", "Login viewer TTL must be 60-1800 seconds and port 1024-65535.")
        if self.vnc and self.vnc.returncode is None:
            return {"status": "pending", "port": self.login_port, "expires_at": self.login_until, "reused": True}
        executable = shutil.which("x11vnc")
        if not executable:
            raise RouterError("dependency_missing", "Install reviewed x11vnc on the server for the temporary login viewer.")
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise RouterError("login_port_busy", "Choose a free loopback login-viewer port.") from None
        await self.page.goto(ORIGIN + "/assets", wait_until="domcontentloaded")
        self.vnc = await asyncio.create_subprocess_exec(executable, "-display", self.display, "-auth", str(self.authority), "-listen", "127.0.0.1",
            "-localhost", "-rfbport", str(port), "-nopw", "-forever", "-shared", "-noxdamage",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.sleep(0.5)
        if self.vnc.returncode is not None:
            raise RouterError("login_viewer_failed", "Server viewer exited; check display dependencies locally.")
        self.login_port, self.login_until = port, time.time() + ttl
        current = self.vnc
        self.login_timer = asyncio.get_running_loop().call_later(ttl, lambda: asyncio.create_task(self.expire_login(current)))
        return {"status": "pending", "listen": "127.0.0.1", "port": port, "expires_at": self.login_until,
                "transport": "ssh_forwarded_vnc", "human_login_required": True, "secrets_returned": False}

    async def locator(self, selector, options):
        if not isinstance(selector, str) or len(selector) > 4096:
            raise RouterError("invalid_selector", "Invalid reviewed DOM selector.")
        target = self.page.locator(selector)
        count = await target.count()
        if "nth" in options:
            nth = options["nth"]
            if not isinstance(nth, int) or isinstance(nth, bool) or not 0 <= nth < count:
                raise RouterError("selector_nth_out_of_range", "Reviewed selector index is outside the current DOM.")
            return target.nth(nth)
        if count != 1:
            raise RouterError("selector_ambiguous" if count else "selector_not_found", "Reviewed selector must identify exactly one element.")
        return target

    async def rpc(self, method, args):
        if self.page.url != "about:blank" and not self.page.url.startswith(ORIGIN + "/"):
            raise RouterError("origin_mismatch", "Tool actions require the Tripo Studio origin; finish human login first.")
        if method == "goto":
            if not args[0].startswith(ORIGIN + "/"):
                raise RouterError("origin_mismatch", "Adapter navigation is limited to Tripo Studio.")
            await self.page.goto(args[0], wait_until="domcontentloaded")
        elif method == "evaluate":
            return await self.page.evaluate("p => (0,eval)('(' + p.code + ')')(...p.args)", {"code": args[0], "args": args[1]})
        elif method in {"click", "focus", "hover", "scrollTo", "fillText", "setChecked"}:
            options = args[-1] if isinstance(args[-1], dict) else {}
            target = await self.locator(args[0], options)
            if method == "click":
                await target.click()
            elif method == "focus":
                await target.focus()
            elif method == "hover":
                await target.hover()
            elif method == "scrollTo":
                await target.scroll_into_view_if_needed()
            elif method == "fillText":
                await target.fill(args[1])
            else:
                await target.set_checked(args[1])
        elif method == "pressKey":
            await self.page.keyboard.press(args[0])
        elif method == "cdp":
            name, params = args
            if name not in CDP_METHODS:
                raise RouterError("unsupported_cdp", "Only reviewed DOM and native-input CDP methods are available.")
            if name == "DOM.setFileInputFiles":
                for filename in params.get("files", []):
                    path = private_path(Path(filename))
                    if not path.is_relative_to(self.active["workspace"]) or not path.is_file():
                        raise RouterError("unsafe_path", "Upload must be an explicit file inside the current project.")
            return await self.cdp.send(name, params)
        elif method == "download_arm":
            identifier = uuid.uuid4().hex
            self.download_arms[identifier] = (len(self.downloads), args[0], args[1])
            return identifier
        elif method == "download_wait":
            start, prefix, timeout = self.download_arms.pop(args[0])
            async def wait():
                while True:
                    self.download_event.clear()
                    for download in self.downloads[start:]:
                        name = download.suggested_filename
                        if Path(name).name == name and name.startswith(prefix) and name.lower().endswith(".glb"):
                            directory = private_path(studio_dir(self.home) / "downloads" / uuid.uuid4().hex, directory=True)
                            destination = directory / name
                            await download.save_as(destination)
                            return {"downloaded": True, "state": "complete", "filename": str(destination)}
                    await self.download_event.wait()
            return await asyncio.wait_for(wait(), timeout / 1000)
        else:
            raise RouterError("unsupported_method", "Unknown server browser method.")
        return None

    async def run(self, packet):
        operation, argv = packet["operation"], packet["argv"]
        workspace = Path(packet["workspace"])
        if not workspace.is_absolute():
            raise RouterError("unsafe_path", "Execution workspace must be absolute.")
        home = self.home.absolute()
        if workspace == home or workspace.is_relative_to(home) or home.is_relative_to(workspace):
            raise RouterError("unsafe_workspace", "Browser state and its ancestors/descendants must be separate from the execution project.")
        spec = validate_request(operation, argv, workspace)
        if packet.get("bundle") != bundle_digest():
            raise RouterError("definition_changed", "Review and reinstall the changed server runtime bundle.")
        if self.lock.locked():
            raise RouterError("runtime_busy", "One browser operation is already active; no request was queued or replayed.")
        async with self.lock:
            if self.vnc and self.vnc.returncode is None:
                raise RouterError("human_login_active", "Close the temporary login viewer before Agent execution.")
            if router_only(spec):
                consume_ticket(self.home, packet.get("ticket"), spec, operation, argv, workspace, packet["bundle"])
            token = uuid.uuid4().hex
            self.active = {"token": token, "workspace": workspace}
            env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "TMPDIR") if k in os.environ}
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec(self.node, str(DATA / "runner.mjs"), cwd=workspace, env=env,
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True, limit=LIMIT)
                payload = canonical({"socket": self.bridge, "token": token, "operation": operation, "argv": argv})
                stdout, _ = await asyncio.wait_for(proc.communicate(payload.encode()), spec["command"]["timeout"])
                if len(stdout) > LIMIT:
                    raise RouterError("result_limit", "Server result exceeded its bound.", uncertain=True)
                result = json.loads(stdout)
                if proc.returncode or "error" in result:
                    error = result.get("error", {})
                    raise RouterError(error.get("code", "adapter_failed"), error.get("message", "Reviewed adapter failed; inspect retained receipts."), uncertain=True)
                return result
            except (ValueError, OSError, asyncio.TimeoutError):
                raise RouterError("adapter_interrupted", "Server adapter was interrupted; reconcile receipts before retry.", uncertain=True) from None
            finally:
                if proc and proc.returncode is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    await proc.wait()
                self.active = None
                self.download_arms.clear()

    async def handle(self, reader, writer):
        try:
            same_user(writer)
            line = await asyncio.wait_for(reader.readline(), 10)
            if len(line) > LIMIT:
                raise RouterError("request_limit", "Bridge request exceeded its bound.")
            packet = json.loads(line)
            method = packet["method"]
            if method == "run":
                result = await self.run(packet)
            elif method == "status":
                result = {"status": "running", "browser_connected": self.context.browser.is_connected(),
                          "busy": self.lock.locked(), "login_viewer_active": bool(self.vnc and self.vnc.returncode is None),
                          "execution": "server_owned", "local_computer_required": False, "secrets_returned": False,
                          "provider_login": "unchecked_use_account_tool"}
            elif method in {"login", "login_close"}:
                if self.lock.locked():
                    raise RouterError("runtime_busy", "An adapter is active; login entry was left unchanged.")
                async with self.lock:
                    result = await self.login(packet.get("ttl", 600), packet.get("port", 5900)) if method == "login" else await self.close_login()
            elif method == "rpc":
                if not self.active or packet.get("token") != self.active["token"]:
                    raise RouterError("unauthorized", "Browser RPC requires an active reviewed adapter invocation.")
                result = await self.rpc(packet["name"], packet["args"])
            else:
                raise RouterError("unsupported_method", "Unknown runtime request.")
            response = {"result": result}
        except RouterError as error:
            response = {"error": error.as_dict()}
        except Exception:
            # Never include page text, auth URLs or upstream diagnostics.
            response = {"error": {"code": "bridge_failure", "message": "Browser bridge failed; inspect local runtime state and retained receipts.", "outcome_uncertain": True}}
        try:
            writer.write(canonical(response).encode() + b"\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


async def serve(home, *, node, executable=None, headed=False, virtual_display=None, browser_factory=None):
    directory = studio_dir(home)
    lock_path = private_path(directory / "runtime.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise RouterError("runtime_busy", "This server profile already has a running browser service.") from None
    display = virtual_display or (os.environ.get("DISPLAY") if headed else None)
    xvfb, context, runtime, service, authority = None, None, None, None, None
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopped.set)
    metadata = directory / "runtime.json"
    try:
        profile = private_path(directory / "browser-profile", directory=True)
        downloads = private_path(directory / "downloads", directory=True)
        artifacts = private_path(directory / "browser-artifacts", directory=True)
        if virtual_display:
            import re
            import shutil
            if sys.platform != "linux" or not re.fullmatch(r":[1-9][0-9]{0,3}", virtual_display):
                raise RouterError("invalid_display", "Virtual display requires Linux and a display like :99.")
            xbin = shutil.which("Xvfb")
            if not xbin:
                raise RouterError("dependency_missing", "Install reviewed Xvfb on the server.")
            # Xauthority is private runtime material, never returned or synchronized.
            authority = directory / ("display-" + uuid.uuid4().hex + ".authority")
            parts = [socket.gethostname().encode(), virtual_display[1:].encode(), b"MIT-MAGIC-COOKIE-1", os.urandom(16)]
            record = struct.pack(">H", 256) + b"".join(struct.pack(">H", len(p)) + p for p in parts)
            atomic_write(authority, record)
            xvfb = await asyncio.create_subprocess_exec(xbin, virtual_display, "-screen", "0", "1920x1080x24", "-nolisten", "tcp", "-auth", str(authority),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await asyncio.sleep(0.5)
            if xvfb.returncode is not None:
                raise RouterError("display_start_failed", "Virtual display exited; choose an unused display.")
            headed = True
        if browser_factory:
            context = await browser_factory(profile)
        else:
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                raise RouterError("dependency_missing", "Install ATM's reviewed server optional dependency and Chromium on the server.") from None
            manager = await async_playwright().start()
            context = await manager.chromium.launch_persistent_context(profile, executable_path=executable,
                headless=not headed, chromium_sandbox=True, accept_downloads=True, locale="en-US", viewport={"width": 1920, "height": 1080},
                downloads_path=downloads, artifacts_dir=artifacts, env={**{k: os.environ[k] for k in
                    ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS") if k in os.environ}, **({"DISPLAY": display} if display else {}),
                                                                   **({"XAUTHORITY": str(authority)} if authority else {})})
        runtime = BrowserRuntime(home, context, node, display, authority)
        await runtime.start()
        base = private_path(Path(tempfile.gettempdir()).resolve() / ("atm-studio-" + str(os.getuid())), directory=True)
        runtime.bridge = str(base / (uuid.uuid4().hex[:16] + ".sock"))
        kwargs = {"cleanup_socket": False} if sys.version_info >= (3, 13) else {}
        service = await asyncio.start_unix_server(runtime.handle, path=runtime.bridge, limit=LIMIT + 1, **kwargs)
        Path(runtime.bridge).chmod(0o600)
        atomic_write(metadata, canonical({"status": "running", "pid": os.getpid(), "socket": runtime.bridge}).encode())
        context.on("close", stopped.set)
        print(canonical({"status": "ready", "execution": "server_owned", "headed": headed,
                         "local_computer_required": False, "secrets_returned": False}), flush=True)
        await stopped.wait()
    finally:
        if service:
            service.close()
            await service.wait_closed()
        if runtime:
            await runtime.close_login()
        if context:
            await context.close()
        if "manager" in locals():
            await manager.stop()
        if xvfb and xvfb.returncode is None:
            xvfb.terminate()
            await xvfb.wait()
        atomic_write(metadata, canonical({"status": "stopped", "profile_preserved": True}).encode())
        os.close(fd)
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)
        # Retain stale socket/lock/profile. No unlink, rmtree or credential cleanup.
