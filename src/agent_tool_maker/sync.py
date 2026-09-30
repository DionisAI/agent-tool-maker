"""Opt-in credential replication over untrusted file transport.

Protocol: recipient-specific X25519/HKDF-SHA256/AES-256-GCM envelopes, signed by
an explicitly pinned Ed25519 peer. This is a versioned application protocol, not
an independently audited standard or Byzantine-consensus implementation. See
MULTI_DEVICE.md. Multi-value registers retain concurrent writes; wall clocks are
metadata only. Policies, CLI paths, browser cookies and private keys NEVER sync.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import stat
import time
import tempfile
import uuid
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import RouterError
from .storage import atomic_write, canonical

FORMAT = "atm-sync-v1"
MAX_PACKET = 8 * 1024 * 1024
MAX_RECORDS = 256
MAX_SIBLINGS = 32
MAX_ACTORS = 64
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PROVIDER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\Z")


def fail(code: str = "invalid_sync") -> None:
    raise RouterError(code, "Invalid or unauthorized sync data. No plaintext or upstream response is included.")


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(value: Any, size: int | None = None) -> bytes:
    if not isinstance(value, str) or len(value) > MAX_PACKET * 2:
        fail()
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        fail()
    if size is not None and len(raw) != size:
        fail()
    return raw


def strict_json(raw: str | bytes, *, limit: int = MAX_PACKET) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail("duplicate_json_key")
            result[key] = value
        return result
    if len(raw) > limit:
        fail("sync_too_large")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: fail())
    except (ValueError, UnicodeError, RecursionError):
        fail()


def provider_name(name: Any) -> str:
    if not isinstance(name, str) or not PROVIDER.fullmatch(name):
        fail()
    return name


def fingerprint(card: dict) -> str:
    return hashlib.sha256(canonical({k: card[k] for k in ("format", "encryption_key", "signing_key")}).encode()).hexdigest()


def validate_card(card: Any) -> dict:
    if not isinstance(card, dict) or set(card) != {"format", "name", "encryption_key", "signing_key", "id"}:
        fail()
    if card["format"] != "atm-device-v1" or not isinstance(card["name"], str) or not 1 <= len(card["name"]) <= 80 or any(ord(c) < 32 for c in card["name"]):
        fail()
    unb64(card["encryption_key"], 32)
    unb64(card["signing_key"], 32)
    if card["id"] != fingerprint(card):
        fail("fingerprint_mismatch")
    return card


def _get(db, name, default=None):
    row = db.execute("SELECT value FROM settings WHERE name=?", (name,)).fetchone()
    return json.loads(row[0]) if row else default


def _set(db, name, value):
    db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (name, canonical(value)))


def _seal(key: bytes, value: Any, aad: str) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    return nonce, AESGCM(key).encrypt(nonce, canonical(value).encode(), aad.encode())


def _open(key: bytes, nonce: bytes, ciphertext: bytes, aad: str) -> Any:
    try:
        return strict_json(AESGCM(key).decrypt(nonce, ciphertext, aad.encode()))
    except (InvalidTag, ValueError):
        fail("sync_store_corrupt")


def _load(db, key, provider) -> list[dict]:
    row = db.execute("SELECT nonce,ciphertext FROM sync_registers WHERE provider=?", (provider,)).fetchone()
    return _open(key, row[0], row[1], "atm-register-v1:" + provider) if row else []


def _assert_consistent(db, key, provider, versions):
    """Detect edits by pre-sync clients instead of exporting a stale register."""
    row = db.execute("SELECT nonce,ciphertext FROM secrets WHERE name=?", (provider,)).fetchone()
    summary = _summary(versions)
    if not versions:
        if row:
            fail("sync_state_drift")
        return
    active = summary["state"] == "active"
    if bool(row) != active:
        fail("sync_state_drift")
    if row:
        try:
            value = AESGCM(key).decrypt(row[0], row[1], provider.encode()).decode()
        except (InvalidTag, UnicodeError):
            fail("sync_store_corrupt")
        meta = _get(db, "credential_meta:" + provider, {})
        if value != versions[0]["value"] or meta.get("expires_at") != versions[0]["expires_at"]:
            fail("sync_state_drift")


def _content(version: dict) -> str:
    return canonical({k: version[k] for k in ("value", "deleted", "expires_at")})


def _summary(versions: list[dict]) -> dict:
    conflict = len({_content(v) for v in versions}) > 1
    return {"state": "conflict" if conflict else "deleted" if versions and versions[0]["deleted"] else "active",
            "heads": [{k: v[k] for k in ("revision", "clock", "author", "deleted", "expires_at", "created_at")} for v in versions],
            "expected": hashlib.sha256(canonical(sorted(v["revision"] for v in versions)).encode()).hexdigest()}


def _store(db, key: bytes, provider: str, versions: list[dict]) -> None:
    """Atomically keep causal state and the v0.4-compatible active credential view."""
    versions = sorted(versions, key=lambda x: x["revision"])
    summary = _summary(versions)
    nonce, ciphertext = _seal(key, versions, "atm-register-v1:" + provider)
    db.execute("INSERT OR REPLACE INTO sync_registers VALUES (?,?,?,?)", (provider, canonical(summary), nonce, ciphertext))
    _set(db, "sync_conflict:" + provider, summary["state"] == "conflict")
    db.execute("DELETE FROM secrets WHERE name=?", (provider,))
    expiry = None
    if summary["state"] == "active" and versions:
        value = versions[0]
        nonce = os.urandom(12)
        cipher = AESGCM(key).encrypt(nonce, value["value"].encode(), provider.encode())
        db.execute("INSERT INTO secrets VALUES (?,?,?)", (provider, nonce, cipher))
        expiry = value["expires_at"]
    _set(db, "credential_meta:" + provider, {"configured_at": time.time(), "expires_at": expiry,
                                            "sync_state": summary["state"]})


def dominates(left: dict, right: dict) -> bool:
    return all(left.get(a, 0) >= n for a, n in right.items()) and any(left.get(a, 0) > right.get(a, 0) for a in left)


def validate_versions(values: Any) -> list[dict]:
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_SIBLINGS:
        fail()
    fields = {"revision", "clock", "author", "deleted", "value", "expires_at", "created_at", "nonce"}
    for v in values:
        if not isinstance(v, dict) or set(v) != fields or not isinstance(v["clock"], dict) or not 1 <= len(v["clock"]) <= MAX_ACTORS:
            fail()
        if any(not isinstance(a, str) or not HEX64.fullmatch(a) or type(n) is not int or not 1 <= n < 2**53 for a, n in v["clock"].items()):
            fail()
        if v["author"] not in v["clock"] or type(v["deleted"]) is not bool:
            fail()
        if v["deleted"]:
            if v["value"] is not None:
                fail()
        elif not isinstance(v["value"], str) or not 1 <= len(v["value"]) <= 16384 or any(c in v["value"] for c in "\r\n\x00"):
            fail()
        for k in ("created_at", "expires_at"):
            if v[k] is None and k == "expires_at":
                continue
            if type(v[k]) not in (int, float) or not math.isfinite(v[k]) or v[k] < 0:
                fail()
        if not isinstance(v["nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", v["nonce"]):
            fail()
        body = {k: value for k, value in v.items() if k != "revision"}
        if v["revision"] != hashlib.sha256(canonical(body).encode()).hexdigest():
            fail("invalid_revision")
    return values


def merge(left: list[dict], right: list[dict]) -> list[dict]:
    """Multi-value register join: commutative, associative, idempotent."""
    by_clock = {}
    all_versions = {v["revision"]: v for v in left + right}
    for v in all_versions.values():
        ck = canonical(v["clock"])
        if ck in by_clock and by_clock[ck] != v["revision"]:
            fail("causal_collision")
        by_clock[ck] = v["revision"]
    result = [v for v in all_versions.values() if not any(dominates(w["clock"], v["clock"]) for w in all_versions.values())]
    if len(result) > MAX_SIBLINGS:
        fail("too_many_conflicts")
    return sorted(result, key=lambda x: x["revision"])


def _new_version(versions, actor, value, expiry):
    clock = {}
    for v in versions:
        for a, n in v["clock"].items():
            clock[a] = max(n, clock.get(a, 0))
    clock[actor] = clock.get(actor, 0) + 1
    body = {"clock": clock, "author": actor, "value": value, "deleted": value is None,
            "expires_at": expiry, "created_at": time.time(), "nonce": uuid.uuid4().hex}
    result = {**body, "revision": hashlib.sha256(canonical(body).encode()).hexdigest()}
    validate_versions([result])
    return result


def local_write(db, key: bytes, provider: str, value: str | None, expiry=None, *, bootstrap=False) -> bool:
    """Called inside Vault's transaction. False means replication not enabled."""
    identity = _get(db, "sync:identity")
    if not identity:
        return False
    versions = _load(db, key, provider)
    if not bootstrap:
        _assert_consistent(db, key, provider, versions)
    if _summary(versions)["state"] == "conflict":
        raise RouterError("sync_conflict", "Resolve this credential's concurrent versions first; no overwrite was made.")
    _store(db, key, provider, [_new_version(versions, identity["public"]["id"], value, expiry)])
    return True


class Sync:
    def __init__(self, vault):
        self.vault, self.state = vault, vault.state

    def initialize(self, name: str) -> dict:
        existing = self.state.setting("sync:identity")
        if existing:
            return {"status": "already_initialized", "device": existing["public"], "secrets_returned": False}
        key = self.vault.unlock()
        encryption, signing = X25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        card = {"format": "atm-device-v1", "name": name,
                "encryption_key": b64(encryption.public_key().public_bytes_raw()),
                "signing_key": b64(signing.public_key().public_bytes_raw())}
        card["id"] = fingerprint(card)
        validate_card(card)
        nonce, ciphertext = _seal(key, {"encryption": b64(encryption.private_bytes_raw()), "signing": b64(signing.private_bytes_raw())}, "atm-device-private-v1")
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if _get(db, "sync:identity"):
                raise RouterError("state_changed", "Device initialization raced; inspect the existing identity.")
            _set(db, "sync:identity", {"public": card, "nonce": b64(nonce), "ciphertext": b64(ciphertext)})
            for row in db.execute("SELECT name,nonce,ciphertext FROM secrets").fetchall():
                value = AESGCM(key).decrypt(row["nonce"], row["ciphertext"], row["name"].encode()).decode()
                expiry = _get(db, "credential_meta:" + row["name"], {}).get("expires_at")
                local_write(db, key, row["name"], value, expiry, bootstrap=True)
        return {"status": "initialized", "device": card, "secrets_returned": False}

    def identity(self) -> dict:
        value = self.state.setting("sync:identity")
        if not value:
            raise RouterError("sync_not_initialized", "Initialize a distinct device identity on this machine first.")
        return validate_card(value["public"])

    def _private(self):
        config = self.state.setting("sync:identity")
        self.identity()
        value = _open(self.vault.unlock(), unb64(config["nonce"], 12), unb64(config["ciphertext"]), "atm-device-private-v1")
        enc = X25519PrivateKey.from_private_bytes(unb64(value["encryption"], 32))
        sig = Ed25519PrivateKey.from_private_bytes(unb64(value["signing"], 32))
        if b64(enc.public_key().public_bytes_raw()) != config["public"]["encryption_key"] or b64(sig.public_key().public_bytes_raw()) != config["public"]["signing_key"]:
            fail("sync_store_corrupt")
        return enc, sig

    def trust(self, card: dict, expected: str, *, send=(), receive=(), apply=False, replace=False) -> dict:
        card = validate_card(card)
        if expected != card["id"] or card["id"] == self.identity()["id"]:
            fail("fingerprint_mismatch")
        for names in (send, receive):
            if not isinstance(names, (list, tuple)) or len(names) > MAX_RECORDS:
                fail()
            for name in names:
                provider_name(name)
        policy = {"card": card, "send": sorted(set(send)), "receive": sorted(set(receive)), "revoked": False}
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = _get(db, "sync:peer:" + card["id"])
            if old and old != policy and not replace:
                raise RouterError("peer_policy_changed", "Review changed device scopes; explicit replacement is required.")
            if apply:
                _set(db, "sync:peer:" + card["id"], policy)
                # Scope changes must force the next exchange snapshot.
                if old != policy:
                    db.execute("DELETE FROM settings WHERE name=?", ("sync:sent:" + card["id"],))
        return {"status": "unchanged" if old == policy else "trusted" if apply else "planned", "peer": policy, "applied": apply}

    def peer(self, device: str, db=None) -> dict:
        if not isinstance(device, str) or not HEX64.fullmatch(device):
            fail("unknown_device")
        value = _get(db, "sync:peer:" + device) if db is not None else self.state.setting("sync:peer:" + device)
        if not value or value["revoked"]:
            fail("untrusted_device")
        validate_card(value["card"])
        return value

    def revoke(self, device: str, *, apply=False) -> dict:
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            peer = self.peer(device, db)
            if apply:
                _set(db, "sync:peer:" + device, {**peer, "revoked": True})
        return {"device": device, "revoked": apply,
                "warning": "Local trust revocation cannot erase previously delivered secrets. Rotate upstream keys and revoke this device on other peers."}

    def status(self) -> dict:
        with self.state.db() as db:
            peers = [json.loads(r[0]) for r in db.execute("SELECT value FROM settings WHERE name LIKE 'sync:peer:%' ORDER BY name")]
            registers = [{"provider": r[0], **json.loads(r[1])} for r in db.execute("SELECT provider,summary FROM sync_registers ORDER BY provider")]
        return {"device": self.state.setting("sync:identity", {}).get("public"), "peers": peers,
                "records": registers, "conflicts": sum(r["state"] == "conflict" for r in registers),
                "secrets_returned": False, "transport": "encrypted_files", "automatic_network": False}

    def _snapshot(self, peer_id: str) -> dict:
        key = self.vault.unlock()
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            policy = self.peer(peer_id, db)
            records = {}
            for provider in policy["send"]:
                versions = _load(db, key, provider)
                _assert_consistent(db, key, provider, versions)
                if versions:
                    records[provider] = versions
            return {"records": records}

    def export_packet(self, peer_id: str) -> dict:
        own = self.identity()
        peer = self.peer(peer_id)
        payload = self._snapshot(peer_id)
        ephemeral = X25519PrivateKey.generate()
        header = {"format": FORMAT, "sender": own["id"], "recipient": peer_id,
                  "packet": uuid.uuid4().hex, "ephemeral": b64(ephemeral.public_key().public_bytes_raw()),
                  "salt": b64(os.urandom(32)), "nonce": b64(os.urandom(12))}
        aad = canonical(header).encode()
        shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(unb64(peer["card"]["encryption_key"], 32)))
        derived = HKDF(hashes.SHA256(), 32, unb64(header["salt"], 32), b"ATM-SYNC-v1\x00" + aad).derive(shared)
        ciphertext = b64(AESGCM(derived).encrypt(unb64(header["nonce"], 12), canonical(payload).encode(), aad))
        message = {"header": header, "ciphertext": ciphertext}
        _, signing = self._private()
        packet = {**message, "signature": b64(signing.sign(canonical(message).encode()))}
        if len(canonical(packet).encode()) > MAX_PACKET:
            fail("sync_too_large")
        # A changed/revoked policy during encryption must not deliver the old scope.
        if self.peer(peer_id) != peer:
            fail("peer_policy_changed")
        return packet

    def _decrypt_packet(self, packet: dict) -> tuple[dict, dict]:
        if not isinstance(packet, dict) or set(packet) != {"header", "ciphertext", "signature"} or len(canonical(packet).encode()) > MAX_PACKET:
            fail()
        h = packet["header"]
        if not isinstance(h, dict) or set(h) != {"format", "sender", "recipient", "packet", "ephemeral", "salt", "nonce"} or h["format"] != FORMAT:
            fail()
        if h["recipient"] != self.identity()["id"]:
            fail("wrong_recipient")
        if not isinstance(h["packet"], str) or not re.fullmatch(r"[0-9a-f]{32}", h["packet"]):
            fail()
        peer = self.peer(h["sender"])
        try:
            Ed25519PublicKey.from_public_bytes(unb64(peer["card"]["signing_key"], 32)).verify(
                unb64(packet["signature"], 64), canonical({"header": h, "ciphertext": packet["ciphertext"]}).encode())
            enc, _ = self._private()
            shared = enc.exchange(X25519PublicKey.from_public_bytes(unb64(h["ephemeral"], 32)))
            aad = canonical(h).encode()
            key = HKDF(hashes.SHA256(), 32, unb64(h["salt"], 32), b"ATM-SYNC-v1\x00" + aad).derive(shared)
            value = strict_json(AESGCM(key).decrypt(unb64(h["nonce"], 12), unb64(packet["ciphertext"]), aad))
        except (InvalidSignature, InvalidTag, ValueError):
            fail("sync_authentication_failed")
        if not isinstance(value, dict) or set(value) != {"records"} or not isinstance(value["records"], dict) or len(value["records"]) > MAX_RECORDS:
            fail()
        for name, versions in value["records"].items():
            provider_name(name)
            if name not in peer["receive"]:
                fail("sync_scope_denied")
            validate_versions(versions)
        return value["records"], peer

    def import_packet(self, packet: dict, *, apply=False) -> dict:
        incoming, policy = self._decrypt_packet(packet)
        key, changes = self.vault.unlock(), []
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if self.peer(packet["header"]["sender"], db) != policy:
                fail("peer_policy_changed")
            for provider, versions in sorted(incoming.items()):
                old = _load(db, key, provider)
                _assert_consistent(db, key, provider, old)
                merged = merge(old, versions)
                changed = canonical(merged) != canonical(old)
                summary = _summary(merged)
                changes.append({"provider": provider, "changed": changed, **summary})
                if apply and changed:
                    _store(db, key, provider, merged)
        return {"applied": apply, "sender": packet["header"]["sender"], "changes": changes,
                "conflicts": sum(c["state"] == "conflict" for c in changes), "secrets_returned": False}

    def resolve(self, provider: str, choose: str, expected: str, *, apply=False) -> dict:
        provider_name(provider)
        actor, key = self.identity()["id"], self.vault.unlock()
        with self.state.db() as db:
            db.execute("BEGIN IMMEDIATE")
            versions = _load(db, key, provider)
            _assert_consistent(db, key, provider, versions)
            summary = _summary(versions)
            if summary["state"] != "conflict" or expected != summary["expected"]:
                raise RouterError("conflict_changed", "Conflict changed or is already resolved. Review current heads again.")
            chosen = next((v for v in versions if v["revision"] == choose), None)
            if not chosen:
                fail("invalid_resolution")
            if apply:
                _store(db, key, provider, [_new_version(versions, actor, chosen["value"], chosen["expires_at"])])
        return {"provider": provider, "chosen_revision": choose, "applied": apply, "secrets_returned": False}

    def exchange(self, directory: Path, *, apply=False) -> dict:
        """One bounded import/export cycle. No daemon, network client or shared master key."""
        root = Path(directory).expanduser().absolute()
        for part in (root, *root.parents):
            if part.is_symlink():
                fail("unsafe_sync_directory")
        own = self.identity()["id"]
        inbox = root / own
        changes = []
        paths = sorted(inbox.glob("*.atmsync")) if inbox.exists() else []
        if len(paths) > 512:
            fail("sync_inbox_limit")
        for path in paths:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PACKET:
                fail("unsafe_sync_file")
            raw = read_sync_file(path)
            packet_hash = hashlib.sha256(raw).hexdigest()
            if self.state.setting("sync:received:" + packet_hash):
                continue
            try:
                result = self.import_packet(strict_json(raw), apply=apply)
                changes.append({"file": path.name, **result})
                if apply:
                    self.state.set_setting("sync:received:" + packet_hash, True)
            except RouterError as error:
                changes.append({"file": path.name, "rejected": error.code})
        outgoing = []
        for peer in self.status()["peers"]:
            if peer["revoked"] or not peer["send"]:
                continue
            pid = peer["card"]["id"]
            snapshot = self._snapshot(pid)
            # This digest stays in the local owner-only database, never transport metadata.
            revision = hashlib.sha256(canonical(snapshot).encode()).hexdigest()
            sent = self.state.setting("sync:sent:" + pid, {})
            if isinstance(sent, dict) and sent.get("revision") == revision:
                old_target = root / pid / sent.get("file", "missing")
                if old_target.is_file() and not old_target.is_symlink() and hashlib.sha256(read_sync_file(old_target)).hexdigest() == sent.get("sha256"):
                    continue
            target = root / pid / (own + "-" + uuid.uuid4().hex + ".atmsync")
            if apply:
                packet = self.export_packet(pid)
                raw = canonical(packet).encode()
                write_sync_file(target, raw)
                self.state.set_setting("sync:sent:" + pid, {"revision": revision, "file": target.name, "sha256": hashlib.sha256(raw).hexdigest()})
            outgoing.append({"device": pid, "file": str(target), "written": apply})
        return {"applied": apply, "incoming": changes, "outgoing": outgoing,
                "status": "partial_rejection" if any("rejected" in c for c in changes) else "completed" if apply else "planned",
                "network_calls": 0, "secrets_returned": False}


def read_sync_file(path: Path) -> bytes:
    path = Path(path).expanduser().absolute()
    for p in (path, *path.parents):
        if p.is_symlink():
            fail("unsafe_sync_file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_PACKET:
            fail("unsafe_sync_file")
        raw = f.read(MAX_PACKET + 1)
    if len(raw) > MAX_PACKET:
        fail("sync_too_large")
    return raw


def write_sync_file(path: Path, raw: bytes) -> None:
    path = Path(path).expanduser().absolute()
    for p in (path, *path.parents):
        if p.is_symlink():
            fail("unsafe_sync_file")
    if len(raw) > MAX_PACKET:
        fail("sync_too_large")
    if path.exists():
        raise RouterError("file_exists", "Choose a new sync export path; existing packets are not overwritten.")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".atm-sync-", dir=path.parent)
    try:
        if os.name == "posix":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        # Atomic visibility and O_EXCL-equivalent publication. File transports that
        # cannot create hard links are reported unsupported, never downgraded to
        # a partially written visible packet.
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise RouterError("file_exists", "Existing packet preserved; choose a new path.") from None
    finally:
        Path(temporary).unlink(missing_ok=True)


def watch(vault, directory: Path, *, interval=30, ttl_hours=8):
    """Owner-started foreground loop; unlock once, stop on rejection or lease end."""
    import threading
    if type(interval) not in (int, float) or not math.isfinite(interval) or not 5 <= interval <= 3600:
        raise RouterError("invalid_interval", "Sync interval must be between 5 and 3600 seconds.")
    if type(ttl_hours) not in (int, float) or not math.isfinite(ttl_hours) or not 0 < ttl_hours <= 720:
        raise RouterError("invalid_ttl", "Sync lease must be positive and no more than 720 hours.")
    vault.unlock()
    sync = Sync(vault)
    sync.identity()
    deadline = time.monotonic() + ttl_hours * 3600
    cycles = 0
    try:
        while time.monotonic() < deadline:
            result = sync.exchange(directory, apply=True)
            cycles += 1
            print(canonical({"event":"sync_cycle", "cycle":cycles, "status":result["status"],
                             "received":len(result["incoming"]), "sent":len(result["outgoing"])}), flush=True)
            if result["status"] == "partial_rejection":
                return {"status":"partial_rejection", "cycles":cycles, "note":"Stopped for owner review; no silently ignored invalid packet."}
            threading.Event().wait(min(interval, max(0, deadline-time.monotonic())))
    except KeyboardInterrupt:
        pass
    finally:
        vault._key = None
        vault.password = None
        vault._used_secrets.clear()
    return {"status":"stopped", "cycles":cycles, "secrets_returned":False}
