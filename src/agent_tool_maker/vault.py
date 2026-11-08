from __future__ import annotations
import base64
import getpass
import hashlib
import os
import sys
import time
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from .errors import RouterError
from .storage import State

SERVICE = "agent-tool-maker-local"


def prompt_secret(label: str) -> str:
    if not sys.stdin.isatty():
        raise RouterError("interactive_required", "Run the credential setup directly in a human terminal, not an agent transcript.")
    return getpass.getpass(label)


class Vault:
    """AES-256-GCM at rest, with OS-keyring or passphrase-derived master key.

    No get-secret CLI; this Python method is for trusted in-process adapters.
    This is not a security boundary against arbitrary code under the same OS user.
    """
    def __init__(self, state: State, password: str | None = None, keyring_backend=None):
        self.state, self.password = state, password
        self.keyring_backend = keyring_backend
        self._key: bytes | None = None
        self._used_secrets: list[str] = []

    def _keyring(self):
        if self.keyring_backend:
            return self.keyring_backend
        try:
            import keyring
        except ImportError:
            raise RouterError("keyring_unavailable", "Install the [secure] extra and enable the OS keyring, or initialize passphrase mode.") from None
        # Reject fail/plaintext/third-party fallback keyrings rather than silently weakening storage.
        module = type(keyring.get_keyring()).__module__
        if not module.startswith(("keyring.backends.macOS", "keyring.backends.Windows", "keyring.backends.SecretService", "keyring.backends.kwallet")):
            raise RouterError("keyring_unavailable", "A supported native secure keyring was not found; no plaintext fallback is used.")
        return keyring

    @property
    def keyring_account(self):
        return hashlib.sha256(str(self.state.home.resolve()).encode()).hexdigest()

    def _password(self):
        # Explicit opt-in for headless use. Never passed to child CLI processes.
        value = self.password or os.environ.get("ATM_VAULT_PASSWORD")
        return value if value else prompt_secret("Vault passphrase: ")

    def init(self, backend="keyring"):
        with self.state.db() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM settings WHERE name='vault' ").fetchone():
                raise RouterError("vault_exists", "Vault already initialized; existing secrets are not replaced.")
            salt = os.urandom(16)
            if backend == "keyring":
                key = AESGCM.generate_key(bit_length=256)
                try:
                    self._keyring().set_password(SERVICE, self.keyring_account, base64.b64encode(key).decode())
                except RouterError:
                    raise
                except Exception:
                    raise RouterError("keyring_unavailable", "Native keyring write failed.") from None
            elif backend == "passphrase":
                password = self._password()
                if len(password) < 12:
                    raise RouterError("weak_passphrase", "Use a vault passphrase of at least 12 characters.")
                key = self._derive(password, salt)
            else:
                raise RouterError("bad_backend", "Expected keyring or passphrase.")
            nonce = os.urandom(12)
            config = {"service": SERVICE, "backend": backend, "salt": base64.b64encode(salt).decode(),
                      "check_nonce": base64.b64encode(nonce).decode(),
                      "check": base64.b64encode(AESGCM(key).encrypt(nonce, b"ATM-v1", b"vault-check")).decode()}
            from .storage import canonical
            c.execute("INSERT INTO settings VALUES ('vault',?)", (canonical(config),))
            self._key = key
        return {"initialized": True, "backend": backend}

    @staticmethod
    def _derive(password, salt):
        return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())

    def unlock_with_key(self, key: bytes):
        """Accept a locally unwrapped key only after authenticating the existing vault.

        Used by the human-window Passkey route; no raw-key HTTP/CLI/RPC endpoint.
        The original password/keyring backend and every ciphertext stay unchanged.
        """
        cfg = self.state.setting('vault')
        try:
            if not cfg or not isinstance(key, bytes) or len(key) != 32:
                raise ValueError()
            check = AESGCM(key).decrypt(base64.b64decode(cfg['check_nonce']),
                base64.b64decode(cfg['check']), b'vault-check')
            if check not in (b'ATM-v1', b'ATR-v1'):
                raise ValueError()
        except (InvalidTag, ValueError, KeyError, TypeError):
            raise RouterError('passkey_vault_mismatch', 'Passkey did not unlock this existing vault; use the recovery password.') from None
        self._key = key
        return key

    def unlock(self):
        if self._key:
            return self._key
        cfg = self.state.setting("vault")
        if not cfg:
            raise RouterError("vault_not_initialized", "Run atm vault init in a human terminal first.")
        try:
            if cfg["backend"] == "keyring":
                value = self._keyring().get_password(cfg.get("service", "agent-tool-router-local"), self.keyring_account)
                if not value:
                    raise RouterError("keyring_key_missing", "OS keyring master key is missing; do not reset the vault blindly.")
                key = base64.b64decode(value, validate=True)
            else:
                key = self._derive(self._password(), base64.b64decode(cfg["salt"]))
            check = AESGCM(key).decrypt(base64.b64decode(cfg["check_nonce"]), base64.b64decode(cfg["check"]), b"vault-check")
            # Retain only the encrypted legacy-format marker, not a CLI/env alias.
            # Removing this reader would lock existing users out of their Keys.
            if check not in (b"ATM-v1", b"ATR-v1"):
                raise ValueError()
        except RouterError:
            raise
        except (InvalidTag, ValueError, KeyError):
            raise RouterError("vault_locked", "Incorrect passphrase or damaged vault metadata.") from None
        except Exception:
            raise RouterError("keyring_unavailable", "Native keyring could not unlock the vault.") from None
        self._key = key
        return key

    def put(self, name: str, value: str, *, expires_at: float | None = None):
        if not value or len(value) > 16384 or any(x in value for x in ["\r", "\n", "\x00"]):
            raise RouterError("bad_credential", "Credential must be nonempty, bounded and contain no control-line characters.")
        nonce = os.urandom(12)
        cipher = AESGCM(self.unlock()).encrypt(nonce, value.encode(), name.encode())
        with self.state.db() as c:
            c.execute("BEGIN IMMEDIATE")
            from .sync import local_write
            if local_write(c, self.unlock(), name, value, expires_at):
                self._used_secrets.append(value)
                return
            c.execute("INSERT OR REPLACE INTO secrets VALUES (?,?,?)", (name, nonce, cipher))
            from .storage import canonical
            c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ("credential_meta:" + name, canonical({"configured_at": time.time(), "expires_at": expires_at})))
        self._used_secrets.append(value)

    def get(self, name: str) -> str:
        with self.state.db() as c:
            c.execute("BEGIN")  # Metadata/conflict/value belong to one read snapshot.
            from .sync import _get
            if _get(c, "sync_conflict:" + name, False):
                raise RouterError("sync_conflict", "Concurrent credential edits require explicit resolution; no key was selected.")
            meta = _get(c, "credential_meta:" + name, {})
            if meta.get("expires_at") is not None and meta["expires_at"] <= time.time():
                raise RouterError("credential_expired", "The selected credential has expired; renew that connection rather than resetting the vault.")
            row = c.execute("SELECT nonce,ciphertext FROM secrets WHERE name=?", (name,)).fetchone()
        if not row:
            raise RouterError("missing_credential", f"Connect {name} in a human terminal first.")
        try:
            value = AESGCM(self.unlock()).decrypt(row[0], row[1], name.encode()).decode()
        except (InvalidTag, UnicodeDecodeError):
            raise RouterError("vault_corrupt", "Credential authentication failed; ciphertext may be damaged.") from None
        self._used_secrets.append(value)
        return value

    def delete(self, name):
        self.unlock()
        with self.state.db() as c:
            c.execute("BEGIN IMMEDIATE")
            from .sync import local_write
            if not local_write(c, self.unlock(), name, None):
                c.execute("DELETE FROM secrets WHERE name=?", (name,))
        return {"removed": name, "note": "Provider-side key is not revoked. SQLite backups may retain ciphertext."}

    def redact(self, obj):
        if isinstance(obj, str):
            for secret in self._used_secrets:
                if secret:
                    obj = obj.replace(secret, "[REDACTED]")
            return obj
        if isinstance(obj, dict):
            return {k: ("[REDACTED]" if k.lower() in {"authorization", "api_key", "access_token", "refresh_token", "client_secret", "id_token", "code_verifier", "secret", "password"} else self.redact(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.redact(x) for x in obj]
        return obj
