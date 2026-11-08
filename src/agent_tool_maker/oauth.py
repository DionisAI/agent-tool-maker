"""Owner-managed, pinned Higgsfield PKCE connection; tokens never leave adapters.

Separate from Key slots, synchronization and bounded project authorization. Refresh
claims commit before dispatch: a crashed/uncertain rotation is never blindly retried.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .errors import RouterError
from .network import checked_url, public_address
from .storage import canonical

NAME = "higgsfield"
RESOURCE = "https://mcp.higgsfield.ai/mcp"
ISSUER = "https://clerk.higgsfield.ai"
PROTECTED_METADATA = "https://mcp.higgsfield.ai/.well-known/oauth-protected-resource"
SERVER_METADATA = ISSUER + "/.well-known/oauth-authorization-server"
SCOPES = {"openid", "email", "offline_access"}
ENDPOINTS = {"authorization_endpoint": ISSUER + "/oauth/authorize",
             "token_endpoint": ISSUER + "/oauth/token",
             "registration_endpoint": ISSUER + "/oauth/register"}
LOGIN_SECONDS = 300
REFRESH_MARGIN = 90
CLAIM_SECONDS = 120
MAX_JSON = 65536


def provider(name):
    if name != NAME:
        raise RouterError("oauth_provider", "This OAuth connection supports Higgsfield only.")


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def includes(value, required):
    return isinstance(value, list) and all(isinstance(item, str) for item in value) and set(required).issubset(value)


def secret_string(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 16384 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise RouterError("oauth_response", "OAuth returned an invalid token or client identifier.")
    return value


class OAuth:
    def __init__(self, state, vault, network, *, clock=time.time):
        self.state, self.vault, self.net, self.clock = state, vault, network, clock

    def _row(self, db):
        row = db.execute("SELECT * FROM oauth_connections WHERE name=?", (NAME,)).fetchone()
        if not row:
            return None, None
        return dict(row), json.loads(row["metadata"])

    def _seal(self, payload):
        nonce = os.urandom(12)
        aad = canonical(["atm-oauth-v1", NAME, ISSUER, RESOURCE]).encode()
        return nonce, AESGCM(self.vault.unlock()).encrypt(nonce, canonical(payload).encode(), aad)

    def _open(self, row):
        aad = canonical(["atm-oauth-v1", NAME, ISSUER, RESOURCE]).encode()
        try:
            value = json.loads(AESGCM(self.vault.unlock()).decrypt(row["nonce"], row["ciphertext"], aad), object_pairs_hook=pairs)
            if not isinstance(value, dict):
                raise ValueError()
        except (InvalidTag, ValueError, UnicodeDecodeError):
            raise RouterError("oauth_corrupt", "OAuth ciphertext authentication failed; existing vault is preserved.") from None
        for key in ("access_token", "refresh_token", "verifier", "state"):
            if value.get(key):
                self.vault._used_secrets.append(value[key])
        return value

    def _write(self, db, meta, payload=None):
        if payload is None:
            db.execute("UPDATE oauth_connections SET metadata=? WHERE name=?", (canonical(meta), NAME))
        else:
            nonce, cipher = self._seal(payload)
            db.execute("INSERT OR REPLACE INTO oauth_connections VALUES (?,?,?,?)", (NAME, canonical(meta), nonce, cipher))

    def status(self, name=NAME):
        provider(name)
        with self.state.db() as db:
            _, meta = self._row(db)
        if not meta:
            return {"provider": NAME, "status": "missing", "resource": RESOURCE, "keep_login": False, "secrets_returned": False}
        result = {k: meta.get(k) for k in ("expires_at", "refreshable", "keep_login", "last_refresh_at", "last_error", "login_deadline")}
        status = meta["status"]
        if status == "pending" and meta["login_deadline"] <= self.clock():
            status = "refresh_unknown" if meta.get("phase") == "exchanging" else "needs_login"
        if status == "refreshing" and meta["claim_deadline"] <= self.clock():
            status = "refresh_unknown"
        if status == "ready" and meta["expires_at"] <= self.clock():
            status = "expired"
        return {"provider": NAME, "status": status, "resource": RESOURCE, "issuer": ISSUER,
                **result, "background_supported": self.state.setting("vault", {}).get("backend") == "keyring",
                "secrets_returned": False}

    def _request(self, method, url, *, body=None, form=False):
        if url not in {PROTECTED_METADATA, SERVER_METADATA, *ENDPOINTS.values()}:
            raise RouterError("oauth_origin", "OAuth endpoint differs from the reviewed provider pin.")
        checked_url(url)
        try:
            public_address(url, self.net.resolver)
        except RouterError as error:
            if error.code == "unsafe_download":
                raise RouterError("oauth_dns_policy", "Official OAuth host resolves to a private or reserved address. No OAuth request was sent; review the local DNS/proxy route.") from None
            raise
        self.net.client.cookies.clear()
        kwargs = {} if body is None else ({"data": body} if form else {"json": body})
        dispatched = False
        try:
            dispatched = True
            with self.net.client.stream(method, url, headers={"Accept": "application/json"}, follow_redirects=False, **kwargs) as response:
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_JSON:
                        raise RouterError("oauth_response", "OAuth response exceeded its bound.", uncertain=method == "POST")
                try:
                    data = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    if not isinstance(data, dict):
                        raise ValueError()
                except (ValueError, UnicodeDecodeError):
                    raise RouterError("oauth_response", "OAuth response was not a bounded JSON object.", uncertain=method == "POST") from None
                if not 200 <= response.status_code < 300:
                    # Only standardized, fixed error names survive; bodies/descriptions are secret-bearing.
                    err = data.get("error")
                    known = {"invalid_grant", "invalid_client", "invalid_scope", "access_denied", "invalid_request", "unauthorized_client"}
                    code = "oauth_" + err if isinstance(err, str) and err in known else "oauth_http"
                    raise RouterError(code, f"OAuth returned HTTP {response.status_code}; provider body suppressed.",
                                      uncertain=method == "POST" and (response.status_code >= 500 or not isinstance(err, str) or err not in known))
                return data
        except (httpx.HTTPError, OSError):
            raise RouterError("oauth_network", "OAuth transport interrupted; no automatic token-exchange retry.", uncertain=dispatched and method == "POST") from None
        finally:
            self.net.client.cookies.clear()

    def discovery(self):
        protected = self._request("GET", PROTECTED_METADATA)
        if protected.get("resource") != RESOURCE or not includes(protected.get("authorization_servers"), {ISSUER}) or not includes(protected.get("scopes_supported"), SCOPES):
            raise RouterError("oauth_metadata", "Protected-resource metadata differs from reviewed resource, issuer or scopes.")
        server = self._request("GET", SERVER_METADATA)
        if server.get("issuer") != ISSUER or any(server.get(k) != v for k, v in ENDPOINTS.items()):
            raise RouterError("oauth_metadata", "Authorization-server issuer or endpoint pin changed.")
        required = {"grant_types_supported": {"authorization_code", "refresh_token"}, "code_challenge_methods_supported": {"S256"},
                    "token_endpoint_auth_methods_supported": {"none"}, "scopes_supported": SCOPES}
        if any(not includes(server.get(key), values) for key, values in required.items()):
            raise RouterError("oauth_metadata", "Provider does not advertise the required public PKCE refresh flow.")
        return server

    def _tokens(self, data, previous=None):
        previous = previous or {}
        if str(data.get("token_type", "")).lower() != "bearer":
            raise RouterError("oauth_response", "Expected a Bearer OAuth token.", uncertain=True)
        expiry = data.get("expires_in")
        if type(expiry) not in (int, float) or not math.isfinite(expiry) or not 0 < expiry <= 366 * 86400:
            raise RouterError("oauth_response", "OAuth response has no valid bounded token expiry.", uncertain=True)
        granted = data.get("scope", " ".join(previous.get("scopes", sorted(SCOPES))))
        allowed = set(previous.get("scopes", SCOPES))
        if not isinstance(granted, str) or not set(granted.split()).issubset(allowed) or "openid" not in granted.split():
            raise RouterError("oauth_scope", "OAuth granted unexpected or missing scopes.", uncertain=True)
        try:
            access = secret_string(data.get("access_token"))
            refresh = data.get("refresh_token", previous.get("refresh_token"))
            if refresh is not None:
                refresh = secret_string(refresh)
        except RouterError:
            raise RouterError("oauth_response", "OAuth returned invalid token fields after exchange.", uncertain=True) from None
        self.vault._used_secrets.extend(v for v in (access, refresh) if v)
        return {"access_token": access, "refresh_token": refresh, "expires_at": self.clock() + expiry,
                "scopes": sorted(set(granted.split()))}

    def _finish(self, claim, payload, *, refresh=False):
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            _, meta = self._row(db)
            if not meta or meta.get("claim") != claim:
                raise RouterError("oauth_conflict", "Connection changed while OAuth was in flight; no automatic retry.", uncertain=True)
            meta.update(status="ready", expires_at=payload["expires_at"], refreshable=bool(payload.get("refresh_token")),
                        last_error=None if payload.get("refresh_token") else "oauth_refresh_token_missing")
            for key in ("claim", "claim_deadline", "phase", "login_deadline"):
                meta.pop(key, None)
            if refresh:
                meta["last_refresh_at"] = self.clock()
            self._write(db, meta, payload)
            db.execute("INSERT INTO events(job_id,kind,at) VALUES (NULL,?,?)", ("oauth.refreshed" if refresh else "oauth.connected", self.clock()))

    def _failed(self, claim, error):
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            _, meta = self._row(db)
            if meta and meta.get("claim") == claim:
                meta.update(status="refresh_unknown" if error.uncertain else "needs_login", last_error=error.code)
                self._write(db, meta)
                db.execute("INSERT INTO events(job_id,kind,at) VALUES (NULL,?,?)", ("oauth." + meta["status"], self.clock()))

    def keep_login(self, name=NAME, *, enabled):
        provider(name)
        if enabled and self.state.setting("vault", {}).get("backend") != "keyring":
            raise RouterError("oauth_needs_keyring", "Background refresh requires the existing native-keyring vault; passphrase connections refresh during an explicit unlock.")
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            _, meta = self._row(db)
            if not meta:
                raise RouterError("oauth_missing", "Complete the local OAuth login first.")
            meta["keep_login"] = enabled
            self._write(db, meta)
        return self.status()

    def refresh(self, name=NAME, *, force=False, background=False):
        provider(name)
        status = self.status()
        if background and not status.get("keep_login"):
            return {**status, "action": "disabled"}
        if background and self.state.setting("vault", {}).get("backend") != "keyring":
            return {**status, "action": "needs_unlock"}
        if status["status"] not in {"ready", "expired"}:
            raise RouterError("oauth_" + status["status"], "Connection needs human login or an in-flight refresh to finish; no retry was dispatched.")
        if not force and status["expires_at"] - self.clock() > REFRESH_MARGIN:
            return {**status, "action": "not_due"}
        # Unlock/decrypt BEFORE claiming so a local keyring failure never looks like dispatched rotation.
        self.vault.unlock()
        claim = secrets.token_hex(16)
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row, meta = self._row(db)
            if meta["status"] != "ready":
                raise RouterError("oauth_busy", "Another OAuth operation owns this connection.")
            if background and not meta.get("keep_login"):
                return {**self.status(), "action": "disabled"}
            if not force and meta["expires_at"] - self.clock() > REFRESH_MARGIN:
                return {**self.status(), "action": "not_due"}
            payload = self._open(row)
            if not payload.get("refresh_token"):
                raise RouterError("oauth_needs_login", "Provider did not issue an offline refresh token; repeat human login.")
            meta.update(status="refreshing", claim=claim, claim_deadline=self.clock() + CLAIM_SECONDS)
            self._write(db, meta)
        try:
            data = self._request("POST", ENDPOINTS["token_endpoint"], form=True,
                                 body={"grant_type": "refresh_token", "refresh_token": payload["refresh_token"],
                                       "client_id": payload["client_id"], "resource": RESOURCE})
            tokens = self._tokens(data, payload)
            self._finish(claim, {"client_id": payload["client_id"], **tokens}, refresh=True)
        except RouterError as error:
            self._failed(claim, error)
            raise
        # Persistence exceptions deliberately leave the committed claim: restart reports uncertainty.
        return {**self.status(), "action": "refreshed"}

    def access_token(self, name, resource):
        provider(name)
        if resource != RESOURCE:
            raise RouterError("oauth_resource", "OAuth token is bound to the exact reviewed MCP resource.")
        self.refresh(name)
        with self.state.db() as db:
            row, meta = self._row(db)
            if not row or meta["status"] != "ready" or meta["expires_at"] <= self.clock():
                raise RouterError("oauth_needs_login", "A current OAuth access token is required.")
            return self._open(row)["access_token"]

    def begin_login(self, name=NAME, *, keep_login=False, replace=False, opener=None, timeout=LOGIN_SECONDS):
        provider(name)
        if keep_login and self.state.setting("vault", {}).get("backend") != "keyring":
            raise RouterError("oauth_needs_keyring", "Keep-login requires native keyring; no vault migration was performed.")
        current = self.status()
        if current["status"] == "pending":
            return None, {**current, "action": "reused", "browser_opened": False}
        if current["status"] in {"ready", "expired", "refreshing"} and not replace:
            return None, {**current, "action": "preserved", "browser_opened": False}
        self.vault.unlock()
        server = LoginServer(self, timeout=timeout)
        claim = secrets.token_hex(16)
        payload = {"state": secrets.token_urlsafe(32), "verifier": secrets.token_urlsafe(48), "redirect_uri": server.redirect_uri}
        try:
            with self.state.db() as db:
                db.execute("BEGIN IMMEDIATE")
                _, old = self._row(db)
                if old and old["status"] == "ready" and not replace:
                    raise RouterError("oauth_conflict", "Another process connected this provider; explicit replacement is required.")
                if old and (old["status"] == "refreshing" and old["claim_deadline"] > self.clock() or old["status"] == "pending" and old["login_deadline"] > self.clock()):
                    raise RouterError("oauth_busy", "A pending OAuth request already owns this connection.")
                meta = {"status": "pending", "claim": claim, "phase": "registering", "login_deadline": self.clock() + timeout,
                        "keep_login": keep_login, "last_error": None}
                self._write(db, meta, payload)
            discovered = self.discovery()
            client = self._request("POST", ENDPOINTS["registration_endpoint"], body={"client_name": "ATM local OAuth",
                                   "redirect_uris": [server.redirect_uri], "token_endpoint_auth_method": "none",
                                   "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]})
            if client.get("token_endpoint_auth_method", "none") != "none" or client.get("redirect_uris") != [server.redirect_uri]:
                raise RouterError("oauth_registration", "Registration changed the public client or exact redirect URI.")
            payload.update(client_id=secret_string(client.get("client_id")), require_iss=discovered.get("authorization_response_iss_parameter_supported") is True)
            with self.state.db() as db:
                db.execute("BEGIN IMMEDIATE")
                _, meta = self._row(db)
                if meta.get("claim") != claim:
                    raise RouterError("oauth_conflict", "OAuth login ownership changed.")
                meta["phase"] = "waiting"
                self._write(db, meta, payload)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(payload["verifier"].encode()).digest()).rstrip(b"=").decode()
            url = ENDPOINTS["authorization_endpoint"] + "?" + urlencode({"response_type": "code", "client_id": payload["client_id"],
                     "redirect_uri": server.redirect_uri, "scope": " ".join(sorted(SCOPES)), "state": payload["state"],
                     "code_challenge": challenge, "code_challenge_method": "S256", "resource": RESOURCE})
            server.claim = claim
            try:
                opened = bool((opener or webbrowser.open)(url))
            except (OSError, webbrowser.Error):
                opened = False
            # Never return the authorization URL, state, verifier or callback code to the Agent.
            return server, {**self.status(), "action": "started", "browser_opened": opened}
        except RouterError as error:
            self._failed(claim, error)
            server.server_close()
            raise
        except BaseException:
            server.server_close()
            raise

    def callback(self, claim, query):
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row, meta = self._row(db)
            if not meta or meta.get("claim") != claim or meta["status"] != "pending" or meta.get("phase") != "waiting" or meta["login_deadline"] <= self.clock():
                raise RouterError("oauth_callback", "This local login request is no longer accepting callbacks.")
            pending = self._open(row)
            state = query.get("state", "")
            if not isinstance(state, str) or not state.isascii() or not hmac.compare_digest(state, pending["state"]):
                raise RouterError("oauth_state", "OAuth callback state did not match.")
            if (pending["require_iss"] or "iss" in query) and query.get("iss") != ISSUER:
                raise RouterError("oauth_issuer", "OAuth callback issuer did not match.")
            if "error" in query:
                meta.update(status="denied", last_error="oauth_access_denied")
                self._write(db, meta)
                return {**self.status(), "status": "denied", "last_error": "oauth_access_denied"}
            code = query.get("code", "")
            if not isinstance(code, str) or not 1 <= len(code) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in code):
                raise RouterError("oauth_callback", "OAuth callback has no valid code.")
            meta.update(phase="exchanging")
            self._write(db, meta)
        try:
            result = self._request("POST", ENDPOINTS["token_endpoint"], form=True, body={"grant_type": "authorization_code",
                     "client_id": pending["client_id"], "code": code, "redirect_uri": pending["redirect_uri"],
                     "code_verifier": pending["verifier"], "resource": RESOURCE})
            tokens = self._tokens(result)
            self._finish(claim, {"client_id": pending["client_id"], **tokens})
        except RouterError as error:
            self._failed(claim, error)
            raise
        return self.status()


class LoginServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, oauth, *, timeout):
        self.oauth, self.claim, self.done = oauth, None, threading.Event()
        self.deadline = time.monotonic() + timeout
        self.result = None
        super().__init__(("127.0.0.1", 0), Callback)
        self.timeout = .25
        self.authority = f"127.0.0.1:{self.server_port}"
        self.redirect_uri = "http://" + self.authority + "/oauth/callback"

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(3)
        return connection, address

    def run(self):
        try:
            while not self.done.is_set() and time.monotonic() < self.deadline:
                self.handle_request()
            if not self.done.is_set():
                self.oauth._failed(self.claim, RouterError("oauth_login_timeout", "Local OAuth login timed out."))
            return self.oauth.status()
        finally:
            self.server_close()


class Callback(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Callback query contains a secret code/state; never log it.

    def do_GET(self):
        try:
            if self.headers.get_all("Host") != [self.server.authority] or len(self.path) > 16384:
                raise RouterError("oauth_callback", "Invalid local callback authority or size.")
            parts = urlsplit(self.path)
            if parts.path != "/oauth/callback" or parts.scheme or parts.netloc or parts.fragment:
                raise RouterError("oauth_callback", "Invalid local callback path.")
            query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=12, strict_parsing=True)
            if any(len(v) != 1 for v in query.values()) or set(query) - {"state", "code", "iss", "error", "error_description", "session_state"} or "code" in query and "error" in query:
                raise RouterError("oauth_callback", "Duplicate or unexpected OAuth callback fields.")
            self.server.result = self.server.oauth.callback(self.server.claim, {k: v[0] for k, v in query.items()})
            self.server.done.set()
            status, message = 200, "ATM login finished. You may close this window."
        except (RouterError, ValueError) as error:
            status, message = 400, "ATM login was not completed. Check the local connection status."
            if isinstance(error, RouterError) and error.code not in {"oauth_state", "oauth_issuer", "oauth_callback"}:
                self.server.done.set()
        raw = message.encode()
        self.send_response(status)
        for key, value in {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(raw)), "Cache-Control": "no-store",
                           "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'none'", "Connection": "close"}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)
