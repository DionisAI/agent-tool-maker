"""Local management console; never a remotely exposed tool-execution server.

Static assets are public shell only. Every data request requires a per-process
bearer, exact Host, same-origin writes, bounded JSON, and a whitelisted endpoint.
Two bearer-less exceptions return nothing else: the `atm ui` challenge (an HMAC
proof of the token) and the exact-Origin exchange of a one-time launch code.
No arbitrary file read, shell, generation, deployment or job-refresh endpoint.
The one owner-triggered tool run is the subscription credits refresh: fixed,
reviewed, unpaid read-only account tools, outside the console-wide lock.
"""
from __future__ import annotations

import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import errno
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import socketserver
import stat
import threading
import time
import webbrowser

from . import __version__, management as mg
from .engine import Router
from .errors import RouterError
from .storage import State, atomic_write
from .vault import Vault

MAX_BODY = 65536
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/assets/brand-data.js": ("brand-data.js", "text/javascript; charset=utf-8"),
          "/assets/brands.js": ("brands.js", "text/javascript; charset=utf-8"),
          "/assets/passkeys.js": ("passkeys.js", "text/javascript; charset=utf-8"),
          "/assets/model.js": ("model.js", "text/javascript; charset=utf-8"),
          "/assets/app.css": ("app.css", "text/css; charset=utf-8")}
TOKEN_FILE = re.compile(r"ui-session-([1-9][0-9]{3,4})\.token")
TOKEN_VALUE = re.compile(r"[A-Za-z0-9_-]{32,128}")
LAUNCH_CODE = re.compile(r"[A-Za-z0-9_-]{43}")
CHALLENGE = re.compile(r"[0-9a-f]{64}")
SESSION_SECONDS = 8 * 3600
LAUNCH_SECONDS = 60
REUSE_MIN_SECONDS = 15 * 60
PROBE_SECONDS = 2
PROBE_LIMIT = 8192  # One identity, proof or launch-code response, headers included.
BIND_ATTEMPTS = 16
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; object-src 'none'"


class WebVault(Vault):
    def _password(self):
        if not self.password:
            raise RouterError("needs_unlock", "Supply this vault's passphrase in the local form for this request, or use the private terminal.")
        return self.password


def fields(body: dict, required=(), optional=()):
    if set(body) - set(required) - set(optional) or any(k not in body for k in required):
        raise RouterError("invalid_request", "Unexpected or missing request fields.")


def text(body, key, *, default=None, limit=16384):
    value = body.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit or any(c in value for c in "\r\n\x00"):
        raise RouterError("invalid_request", "Expected a bounded, single-line string.")
    return value


def flag(body, key, default=False):
    value = body.get(key, default)
    if type(value) is not bool:
        raise RouterError("invalid_request", "Expected a boolean field.")
    return value


def selections(body, key, allowed=None):
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 80 or any(not isinstance(v, str) or len(v) > 100 for v in value):
        raise RouterError("invalid_request", "Expected a bounded list of names.")
    if allowed is not None and any(v not in allowed for v in value):
        raise RouterError("invalid_request", "Unsupported selection.")
    return value


def probe_proof(token, challenge):
    return hmac.new(token.encode(), ("atm-console-probe|" + challenge).encode(), hashlib.sha256).hexdigest()


class Console(ThreadingHTTPServer):
    daemon_threads = True
    # POSIX SO_REUSEADDR lets `atm ui --port P` restart while P's closed connections sit in TIME_WAIT,
    # but never binds beside a live listener on the same address. On Windows it would let a second
    # socket share the port, so it stays off there.
    allow_reuse_address = os.name == "posix"
    # The shell bootstraps ten metadata requests concurrently. Python 3.13's
    # default backlog of five resets a queued browser burst before accept runs.
    request_queue_size = 32

    def __init__(self, home, *, port=0, executable=None, user_home=None, router_factory=None, localhost=False):
        if type(port) is not int or not 0 <= port <= 65535:
            raise RouterError("invalid_port", "Port must be between 0 and 65535.")
        self.home = State(Path(home)).home
        self.executable, self.user_home = executable, user_home
        self.router_factory = router_factory
        self.secret_session = None
        self.secret_session_thread = None
        self.token = secrets.token_urlsafe(32)
        self.expires_at = time.monotonic() + SESSION_SECONDS
        self.launch_codes = {}
        self.lock = threading.RLock()
        self.loopback6 = None
        super().__init__(("127.0.0.1", port), Handler, bind_and_activate=False)
        try:
            self.bind_loopback(port, localhost)
        except BaseException:
            self.socket.close()
            raise
        self.authority = f"{'localhost' if localhost else '127.0.0.1'}:{self.server_port}"
        self.origin = "http://" + self.authority
        from .passkeys import Passkeys
        self.passkeys = Passkeys(State(self.home), self.origin)
        self.token_path = self.home / (f"ui-session-{self.server_port}.token")
        atomic_write(self.token_path, self.token.encode())

    def bind_loopback(self, port, localhost):
        """127.0.0.1:port and, for a localhost authority, [::1]:port too: browsers try ::1 first for
        localhost, so no other local program may answer there with this page or its launch fragment."""
        for _ in range(BIND_ATTEMPTS):
            self.server_address = ("127.0.0.1", port)
            try:
                self.server_bind()
            except OSError as error:
                if port and error.errno == errno.EADDRINUSE:
                    raise RouterError("port_in_use", f"127.0.0.1:{port} is already in use. Choose another --port.") from None
                raise
            self.server_activate()
            if not localhost:
                return
            try:
                self.loopback6 = Loopback6(self)
                return
            except OSError as error:
                if error.errno in (errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT):
                    return  # No IPv6 loopback here: the browser cannot reach [::1] either.
                if error.errno != errno.EADDRINUSE:
                    raise
            if port:
                raise RouterError("port_in_use", f"Another program holds [::1]:{port}, which the browser tries first "
                                  f"for localhost:{port}. Choose another --port.")
            self.socket.close()  # Both families on one fresh port, or no console.
            self.socket = socket.socket(self.address_family, self.socket_type)
        raise RouterError("port_in_use", "No local port was free on both 127.0.0.1 and [::1]. No console was started.")

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address

    def serve_forever(self, poll_interval=0.5):
        twin = self.loopback6 and threading.Thread(target=self.loopback6.serve_forever, args=(poll_interval,), daemon=True)
        if twin:
            twin.start()
        try:
            super().serve_forever(poll_interval)
        finally:
            if twin:
                self.loopback6.shutdown()
                twin.join()

    def shutdown(self):
        super().shutdown()
        if self.loopback6:
            self.loopback6.shutdown()

    def launch_code(self, seconds=LAUNCH_SECONDS):
        """One-time code that lets `atm ui` open this console without putting the bearer in a URL."""
        now = time.monotonic()
        code = secrets.token_urlsafe(32)
        with self.lock:
            self.launch_codes = {c: t for c, t in self.launch_codes.items() if t > now}
            while len(self.launch_codes) >= 8:
                self.launch_codes.pop(next(iter(self.launch_codes)))
            self.launch_codes[code] = now + seconds
        return code

    def redeem(self, code):
        """The bearer, once per launch code and only within its lifetime."""
        with self.lock:
            match = next((c for c in self.launch_codes if LAUNCH_CODE.fullmatch(code or "") and hmac.compare_digest(c, code)), None)
            expires = self.launch_codes.pop(match, 0)
        now = time.monotonic()
        if now >= expires:
            raise RouterError("launch_expired", "This launch link was already used or has expired. Run atm ui again in the terminal.")
        if now >= self.expires_at:
            raise RouterError("session_expired", "This console session expired. Run atm ui again in the terminal.")
        return self.token

    def open_router(self, password=None):
        if self.router_factory:
            return self.router_factory(password)
        router = Router(self.home)
        router.vault = WebVault(router.state, password=password)
        return router

    def server_close(self):
        if hasattr(self, "passkeys"):
            self.passkeys.clear()
        if self.secret_session is not None:
            self.secret_session.closing.set()
            if self.secret_session_thread:
                self.secret_session_thread.join(320)
        super().server_close()
        if self.loopback6:
            self.loopback6.server_close()
        self.launch_codes.clear()
        if hasattr(self, "token_path"):
            try:
                if self.token_path.read_text() == self.token:
                    self.token_path.unlink()
            except OSError:
                pass
        self.token = ""


class Loopback6(socketserver.ThreadingTCPServer):
    """[::1] twin of a localhost console. Requests are handled by, and with the state of, the IPv4 server."""
    address_family = socket.AF_INET6
    daemon_threads = True
    allow_reuse_address = Console.allow_reuse_address
    request_queue_size = Console.request_queue_size

    def __init__(self, primary):
        self.primary = primary
        super().__init__(("::1", primary.server_port), None, bind_and_activate=False)
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            self.server_bind()
            self.server_activate()
        except BaseException:
            self.server_close()
            raise

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address

    def finish_request(self, request, client_address):
        self.primary.finish_request(request, client_address)


class Handler(BaseHTTPRequestHandler):
    server_version = "ATM"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass  # Never log URLs, headers, tokens, request bodies or credentials.

    def respond(self, status, payload, *, mime="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        try:
            self.send_response(status)
            for key, value in {"Content-Type": mime, "Content-Length": str(len(raw)),
                               "Cache-Control": "no-store", "Content-Security-Policy": CSP,
                               "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
                               "X-Frame-Options": "DENY", "Cross-Origin-Resource-Policy": "same-origin",
                               "Connection": "close"}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            # Client navigation/close is not a second application failure to write.
            pass
        finally:
            self.close_connection = True

    def check_request(self, *, authenticated):
        for header in ("Host", "Origin", "Authorization", "Content-Type", "Content-Length", "X-ATM-Challenge"):
            if len(self.headers.get_all(header, [])) > 1:
                raise RouterError("forbidden_request", "Duplicate security-sensitive header.")
        if self.headers.get("Host") != self.server.authority:
            raise RouterError("forbidden_request", "Invalid local Host.")
        if self.headers.get("Origin") not in (None, self.server.origin):
            raise RouterError("forbidden_request", "Cross-origin request rejected.")
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            raise RouterError("forbidden_request", "Cross-site request rejected.")
        if "?" in self.path or "#" in self.path:
            raise RouterError("forbidden_request", "Query-string tokens and parameters are not accepted.")
        if authenticated:
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, "Bearer " + self.server.token):
                raise RouterError("unauthorized", "Open this running console from its private terminal session.")
            if time.monotonic() >= self.server.expires_at:
                # Only a holder of this bearer learns that it expired.
                raise RouterError("session_expired", "This console session expired. Run atm ui again in the terminal.")

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def do_OPTIONS(self):
        self.respond(403, {"error": {"code": "forbidden_request", "message": "Cross-origin access is disabled."}})

    def handle_request(self, write):
        router = None
        try:
            static = self.path in STATIC and not write
            challenge = self.path == "/api/console" and not write and "Authorization" not in self.headers \
                and "X-ATM-Challenge" in self.headers
            redeem = self.path == "/api/console/redeem" and write
            self.check_request(authenticated=not (static or challenge or redeem))
            if static:
                name, mime = STATIC[self.path]
                self.respond(200, files("agent_tool_maker.data").joinpath("web").joinpath(name).read_bytes(), mime=mime)
                return
            if challenge:
                # Proof of token possession without the bearer: `atm ui` sends it only to a listener that can answer.
                value = self.headers["X-ATM-Challenge"]
                if not CHALLENGE.fullmatch(value):
                    raise RouterError("invalid_request", "Expected a 64-hex challenge.")
                self.respond(200, {"service": "atm-console", "proof": probe_proof(self.server.token, value)})
                return
            if self.path == "/api/console" and not write:
                # Non-secret identity: `atm ui` reopens this console, never a foreign listener or another home.
                self.respond(200, {"service": "atm-console", "version": __version__, "home": str(self.server.home),
                                   "expires_in_seconds": max(0, int(self.server.expires_at - time.monotonic()))})
                return
            body = {}
            if write:
                if self.headers.get("Origin") != self.server.origin:
                    raise RouterError("forbidden_request", "Writes require the exact local Origin.")
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json" or self.headers.get("Transfer-Encoding"):
                    raise RouterError("invalid_request", "Only bounded JSON requests are accepted.")
                length = self.headers.get("Content-Length", "")
                limit = 8 * 1024 * 1024 + MAX_BODY if self.path == "/api/sync/import" else MAX_BODY
                if not length.isdecimal() or not 1 <= int(length) <= limit:
                    raise RouterError("invalid_request", "Request body exceeds limit or has no valid length.")
                raw = self.rfile.read(int(length))
                if len(raw) != int(length):
                    raise RouterError("invalid_request", "Incomplete request.")
                from .sync import strict_json
                body = strict_json(raw, limit=limit)
                if not isinstance(body, dict):
                    raise RouterError("invalid_request", "Expected a JSON object.")
            if redeem:
                # Exact Origin and Host, no bearer: the page trades the one-time launch fragment for the bearer.
                fields(body, ("code",))
                self.respond(200, {"token": self.server.redeem(text(body, "code", limit=64))})
                return
            # A credits refresh waits on an account tool; it must not block the console.
            unlocked = write and self.path == "/api/credits/refresh"
            with contextlib.nullcontext() if unlocked else self.server.lock:
                router = self.server.open_router(text(body, "passphrase"))
                result = self.mutate(router, body) if write else self.read(router)
            self.respond(200, result)
        except RouterError as error:
            status = 401 if error.code in {"unauthorized", "session_expired", "launch_expired"} else 403 if error.code == "forbidden_request" else 404 if error.code == "not_found" else 409 if error.code in {"setup_changed", "state_changed", "setup_conflict", "registration_changed", "refresh_in_progress"} else 400
            self.respond(status, {"error": error.as_dict()})
        except (ValueError, TypeError, KeyError, OSError, RecursionError):
            self.respond(400, {"error": {"code": "invalid_request", "message": "Invalid local input or state. No provider execution was requested."}})
        finally:
            if router:
                router.close()
                router.vault.password = None
                router.vault._key = None
                router.vault._used_secrets.clear()

    def read(self, router):
        if self.path == "/api/passkeys":
            return self.server.passkeys.status()
        if self.path == "/api/session":
            from .session import status
            return status(router.state.home)
        if self.path == "/api/extensions":
            from .extensions_web import inventory
            return inventory(router)
        if self.path == "/api/credits":
            from .credits import payload
            return payload(router)  # Cached state only; no tool runs on GET.
        if self.path in {"/api/sync", "/api/access"}:
            from .multidevice_web import read
            return read(router,self.path)
        routes = {"/api/overview": lambda: mg.overview(router, user_home=self.server.user_home),
                  "/api/agents": lambda: mg.agents(router, user_home=self.server.user_home),
                  "/api/tools": lambda: mg.tools(router), "/api/connections": lambda: mg.connections(router),
                  "/api/clis": lambda: mg.cli_inventory(router), "/api/jobs": lambda: mg.recent_jobs(router)}
        if self.path in routes:
            return routes[self.path]()
        if self.path.startswith("/api/tools/"):
            tool = router.catalog.get(self.path.removeprefix("/api/tools/"))
            # Public schemas only; arbitrary custom headers and example values are not exposed.
            keys = ("id", "title", "provider", "adapter", "capabilities", "schema", "permissions", "paid", "implementation", "notes")
            return {**{key: tool.get(key) for key in keys}, **mg.tool_references(router.state, tool),
                    "enabled": mg.enabled(router.state, tool["id"])}
        raise RouterError("not_found", "Unknown console endpoint.")

    def mutate(self, router, body):
        path = self.path
        if path == "/api/console/launch-code":
            fields(body)
            return {"code": self.server.launch_code()}
        if path.startswith("/api/passkeys/"):
            passkeys = self.server.passkeys
            if path == "/api/passkeys/register/begin":
                fields(body, ("label",), ("passphrase",))
                return passkeys.register_begin(router.vault, text(body, "label", limit=80))
            if path in {"/api/passkeys/register/verify", "/api/passkeys/register/finish"}:
                fields(body, ("ceremony_id", "credential"), ("prf_first",) if path.endswith("finish") else ())
                return passkeys.register_finish(body) if path.endswith("finish") else passkeys.register_verify(body)
            if path == "/api/passkeys/auth/begin":
                fields(body, ("credential_id",))
                from .session import status
                if status(router.state.home)["unlocked"]:
                    raise RouterError("session_already_unlocked", "Existing lease was preserved; no authentication is needed.")
                return passkeys.auth_begin(text(body, "credential_id"), "console.unlock")
            if path == "/api/passkeys/cancel":
                fields(body)
                passkeys.clear()
                return {"status": "cancelled"}
            if path == "/api/passkeys/disable":
                fields(body, ("credential_id", "confirm"), ("passphrase",))
                identifier = text(body, "credential_id")
                if text(body, "confirm") != identifier:
                    raise RouterError("approval_required", "Confirm the selected local Passkey.")
                result = passkeys.disable(router.vault, identifier)
                passkeys.clear()
                return result
            raise RouterError("not_found", "Unknown Passkey operation.")
        if path == "/api/oauth/login":
            fields(body, ("provider",), ("keep_login", "replace", "passphrase"))
            from .oauth_web import login
            return login(router, provider=text(body, "provider"), keep_login=flag(body, "keep_login"),
                         replace=flag(body, "replace"), executable=self.server.executable)
        if path == "/api/oauth/cancel":
            # Owner-only, like every console write (bearer, exact Origin and Host). No CLI command cancels a login:
            # Agents hand the login to the owner and only read its status. Metadata only, so no password is taken.
            fields(body, ("provider",))
            from .oauth import OAuth
            return OAuth(router.state, router.vault, router.net).cancel_login(text(body, "provider"))
        if path == "/api/oauth/keep-login":
            fields(body, ("provider", "enabled"))
            from .oauth import OAuth
            result = OAuth(router.state, router.vault, router.net).keep_login(text(body, "provider"), enabled=flag(body, "enabled"))
            if flag(body, "enabled"):
                from .oauth_service import install_service
                result["service"] = install_service(router.state, executable=self.server.executable, apply=True)
            return result
        if path == "/api/settings/network":
            # Owner-only, like every console write (bearer, exact Origin and Host). No CLI command writes it:
            # Agents drive the CLI and must not be able to widen the address check.
            fields(body, ("fake_ip_tunnel",), ("expected",))
            from .network import set_fake_ip_tunnel
            return set_fake_ip_tunnel(router.state, flag(body, "fake_ip_tunnel"),
                                      expected=flag(body, "expected") if "expected" in body else None)
        if path == "/api/session/unlock":
            fields(body, optional=("ttl", "passphrase", "passkey"))
            from .session import status, ttl_seconds, SecretSession, run_service
            seconds = ttl_seconds(text(body, "ttl", default="30m"))
            if "passkey" in body and ("passphrase" in body or seconds != 1800):
                self.server.passkeys.clear()
                raise RouterError("invalid_request", "Passkey unlock uses the fixed 30-minute lease and no password field.")
            current = status(router.state.home)
            if current["unlocked"]:
                self.server.passkeys.clear()
                return {**current, "action": "unchanged"}
            if "passkey" in body:
                self.server.passkeys.auth_finish(router.vault, body["passkey"], "console.unlock")
            service = SecretSession(router.state.home, seconds=seconds, vault=router.vault)
            self.server.secret_session = service
            self.server.secret_session_thread = threading.Thread(target=run_service, args=(service,), daemon=True)
            self.server.secret_session_thread.start()
            return service.metadata_status()
        if path == "/api/session/lock":
            fields(body)
            self.server.passkeys.clear()
            from .session import owner_call, status
            if not status(router.state.home)["unlocked"]:
                return status(router.state.home)
            result = owner_call(router.state.home, "session.lock")
            # Our listener must finish closing before another local unlock can bind it.
            # This waits for closure, not for already-admitted subprocesses to finish.
            if self.server.secret_session_thread:
                self.server.secret_session_thread.join(2)
            return result
        if path == "/api/credits/refresh":
            fields(body, ("provider",))
            from .credits import refresh
            return refresh(router, text(body, "provider", limit=64))
        if path == "/api/credits/cycle":
            fields(body, ("provider", "day"))
            from .credits import set_cycle
            return set_cycle(router, text(body, "provider", limit=64), body["day"])
        if path.startswith(("/api/extensions/", "/api/credentials/")):
            from .extensions_web import mutate
            return mutate(router,path,body)
        if path.startswith(("/api/sync/", "/api/access/")):
            from .multidevice_web import mutate
            return mutate(router,path,body,user_home=self.server.user_home)
        if path in {"/api/setup/preview", "/api/setup/apply"}:
            fields(body, optional=("agents", "clis", "replace_skills", "approved_sha256"))
            kwargs = dict(agent_names=selections(body, "agents", mg.DEFAULT_AGENTS), cli_names=selections(body, "clis") or [],
                          replace_skills=flag(body, "replace_skills"), executable=self.server.executable, user_home=self.server.user_home)
            if path.endswith("preview"):
                return mg.setup_plan(router, **kwargs)
            return mg.apply_setup(router, approved_sha256=text(body, "approved_sha256"), **kwargs)
        if path == "/api/agents/unregister":
            fields(body, ("agent", "confirm"))
            name = text(body, "agent")
            if text(body, "confirm") != name:
                raise RouterError("approval_required", "Confirm the selected agent name.")
            return mg.unregister(router, name, apply=True)
        if path == "/api/tools/toggle":
            fields(body, ("tool", "enabled", "expected_enabled"))
            return mg.set_enabled(router, text(body, "tool"), flag(body, "enabled"), apply=True, expected=flag(body, "expected_enabled"))
        if path == "/api/vault/init":
            fields(body, ("backend",), ("passphrase",))
            backend = text(body, "backend")
            if backend not in {"keyring", "passphrase"}:
                raise RouterError("invalid_request", "Unsupported vault backend.")
            return router.vault.init(backend)
        if path == "/api/connections/save":
            fields(body, ("provider", "value"), ("replace", "expires_at", "passphrase"))
            from .session import exists, shared_put
            if exists(router.state.home):
                return shared_put(router.state.home, text(body, "provider"), text(body, "value"), replace=flag(body, "replace"), expires_at=text(body, "expires_at"))
            return mg.connect_value(router, text(body, "provider"), text(body, "value"),
                                    replace=flag(body, "replace"), expires_at=text(body, "expires_at"))
        if path == "/api/connections/remove":
            fields(body, ("provider", "confirm"), ("passphrase",))
            name = text(body, "provider")
            if name not in router.state.secret_names() or text(body, "confirm") != name:
                raise RouterError("approval_required", "Confirm the exact configured connection to remove locally.")
            from .session import exists, owner_call
            if exists(router.state.home):
                return owner_call(router.state.home, "session.remove", {"provider": name, "confirm": name})
            return router.vault.delete(name)
        if path == "/api/verify":
            fields(body, ("provider",), ("allow_network", "passphrase"))
            from .verification import verify
            return verify(router, text(body, "provider"), allow_network=flag(body, "allow_network"))
        raise RouterError("not_found", "No execution or arbitrary configuration endpoint is exposed.")


def read_token_file(path):
    """(token, lstat) of an owner-only, single-link regular token file, else None. Never follows a link."""
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 \
                or info.st_nlink != 1 or not 0 < info.st_size <= 256:
            return None
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            opened = os.fstat(fd)
            value = os.read(fd, 257).decode("ascii") if (opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino) else ""
        finally:
            os.close(fd)
    except (OSError, UnicodeDecodeError):
        return None
    return (value, info) if TOKEN_VALUE.fullmatch(value) else None


def exchange(port, method, path, headers, deadline, body=None):
    """JSON object of one 200 application/json answer from 127.0.0.1:port, else None.

    The whole exchange (connect, status line, headers, body) shares one monotonic deadline and a
    small size cap, so a trickling or flooding listener cannot hold `atm ui`. Redirects are not
    followed. ConnectionRefusedError: nothing listens.
    """
    def left():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Console probe deadline passed.")
        return remaining
    lines = [f"{method} {path} HTTP/1.0", f"Host: localhost:{port}", *(f"{k}: {v}" for k, v in headers.items())]
    if body is not None:
        lines += ["Content-Type: application/json", f"Content-Length: {len(body)}"]
    raw = b""
    with socket.create_connection(("127.0.0.1", port), timeout=left()) as connection:
        connection.sendall(("\r\n".join(lines) + "\r\n\r\n").encode() + (body or b""))
        while len(raw) <= PROBE_LIMIT:
            connection.settimeout(left())
            chunk = connection.recv(512)
            if not chunk:
                break
            raw += chunk
    head, separator, content = raw.partition(b"\r\n\r\n")
    status, *header_lines = head.decode("latin-1").split("\r\n")
    found = {}
    for line in header_lines:
        name, _, value = line.partition(":")
        found.setdefault(name.strip().lower(), []).append(value.strip())
    if len(raw) > PROBE_LIMIT or not separator or not re.fullmatch(r"HTTP/1\.[01] 200( .*)?", status) \
            or [v.split(";")[0].strip() for v in found.get("content-type", [])] != ["application/json"] \
            or found.get("content-length", [str(len(content))]) != [str(len(content))]:
        return None
    value = json.loads(content)
    return value if isinstance(value, dict) else None


def probe(port, token, home):
    """Identity of this home's console on port, else None. ConnectionRefusedError: nothing listens.

    The listener first proves it holds the token (HMAC of a fresh challenge); a listener that
    cannot never receives the bearer. Only then is the authenticated identity read.
    """
    deadline = time.monotonic() + PROBE_SECONDS
    try:
        challenge = secrets.token_hex(32)
        answer = exchange(port, "GET", "/api/console", {"X-ATM-Challenge": challenge}, deadline)
        if not answer or set(answer) != {"service", "proof"} or answer["service"] != "atm-console" \
                or not isinstance(answer["proof"], str) or not CHALLENGE.fullmatch(answer["proof"]) \
                or not hmac.compare_digest(answer["proof"], probe_proof(token, challenge)):
            return None
        body = exchange(port, "GET", "/api/console", {"Authorization": "Bearer " + token}, deadline)
        if not body or body.get("service") != "atm-console" or body.get("version") != __version__ \
                or type(body.get("expires_in_seconds")) is not int or not 0 < body["expires_in_seconds"] <= SESSION_SECONDS \
                or not isinstance(body.get("home"), str) or not os.path.samefile(body["home"], home):
            return None
        return body
    except ConnectionRefusedError:
        raise
    except (OSError, ValueError, RecursionError):
        return None


def request_launch_code(port, token):
    """A fresh one-time launch code from the verified console on port, else None."""
    try:
        body = exchange(port, "POST", "/api/console/launch-code", {"Origin": f"http://localhost:{port}",
                        "Authorization": "Bearer " + token}, time.monotonic() + PROBE_SECONDS, b"{}")
    except (OSError, ValueError, RecursionError):
        return None
    code = body.get("code") if body else None
    return code if isinstance(code, str) and LAUNCH_CODE.fullmatch(code) else None


def running_console(home, port=0):
    """(port, token, token file, identity) of this home's live console; removes files nothing listens on."""
    home = Path(home).expanduser().absolute()
    if os.name != "posix":
        return None
    try:  # Only an owner-only home: another account must not plant or swap token files in it.
        info = os.lstat(home)
    except OSError:
        return None
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        return None
    found = []
    try:
        for path in home.glob("ui-session-*.token"):
            match = TOKEN_FILE.fullmatch(path.name)
            number = int(match[1]) if match else 0
            if 1024 <= number <= 65535 and port in (0, number) and (entry := read_token_file(path)):
                found.append((entry[1].st_mtime, number, path, *entry))
    except OSError:
        return None
    for _, number, path, token, info in sorted(found, key=lambda row: row[0], reverse=True):
        try:
            identity = probe(number, token, home)
        except ConnectionRefusedError:
            try:  # Stale: remove exactly the validated file, not one a new console wrote since.
                now = os.lstat(path)
                if (now.st_dev, now.st_ino, now.st_mtime_ns) == (info.st_dev, info.st_ino, info.st_mtime_ns):
                    path.unlink()
            except OSError:
                pass
            continue
        if identity:
            return number, token, path, identity
    return None


def announce(origin, token_path, hours, *, reused, note=""):
    note += "Reused the console already running for this ATM home; its own terminal stops it. " if reused else "Ctrl-C stops the server. "
    print(json.dumps({"url": origin, "session_token_file": str(token_path), "scope": "loopback_only",
                      "expires_after_hours": hours, "reused": reused,
                      "note": "Keep the session token private. " + note + "No secret is printed here."}), flush=True)


def serve(home, *, port=0, open_browser=True, executable=None):
    running, note = running_console(home, port), ""
    if running:
        number, token, token_path, identity = running
        origin = f"http://localhost:{number}"
        if identity["expires_in_seconds"] < REUSE_MIN_SECONDS:
            why = "expires within 15 minutes"
        else:
            code = request_launch_code(number, token) if open_browser else None
            if code or not open_browser:
                announce(origin, token_path, round(identity["expires_in_seconds"] / 3600, 2), reused=True)
                if code:  # A one-time code, never the bearer, goes into the browser's URL and history.
                    webbrowser.open(origin + "/#launch=" + code)
                return 0
            why = "did not issue a launch code"
        if port:  # It holds the requested port, so a new console cannot bind there.
            raise RouterError("port_in_use", f"{origin} is this ATM home's running console, which {why}. "
                              "Stop it with Ctrl-C in its terminal, or choose another --port.")
        note = f"The running console {why}, so a new one was started. "
    from .onboarding import executable_path
    server = Console(home, port=port, executable=str(executable_path(executable)), localhost=True)
    try:
        announce(server.origin, server.token_path, SESSION_SECONDS // 3600, reused=False, note=note)
        if open_browser:
            webbrowser.open(server.origin + "/#launch=" + server.launch_code())
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
