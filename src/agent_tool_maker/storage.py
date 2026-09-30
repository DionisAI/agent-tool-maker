from __future__ import annotations
import contextlib
import hashlib
import json
import os
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from .errors import RouterError


def private_dir(path: Path) -> Path:
    path = path.expanduser().absolute()
    if path.is_symlink():
        raise RouterError("unsafe_path", "State directory must not be a symbolic link.")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        path.chmod(0o700)
    return path


def atomic_write(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise RouterError("unsafe_path", "Refusing to overwrite a symbolic link.")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".atm-")
    try:
        if os.name == "posix":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class State:
    """SQLite is the local source of truth. No prompts or credentials in audit events."""
    def __init__(self, home: Path):
        self.home = private_dir(home)
        self.path = self.home / "state.sqlite3"
        if self.path.is_symlink():
            raise RouterError("unsafe_path", "State database must not be a symbolic link.")
        if not self.path.exists():
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                if self.path.is_symlink():
                    raise RouterError("unsafe_path", "State database must not be a symbolic link.")
        with self.db() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS secrets (name TEXT PRIMARY KEY, nonce BLOB, ciphertext BLOB);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                    fingerprint TEXT NOT NULL, tool TEXT NOT NULL, workspace TEXT NOT NULL,
                    status TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY, job_id TEXT, kind TEXT NOT NULL, at REAL NOT NULL);
            ''')
        if os.name == "posix":
            self.path.chmod(0o600)

    @contextlib.contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def setting(self, name: str, default=None):
        with self.db() as c:
            row = c.execute("SELECT value FROM settings WHERE name=?", (name,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_setting(self, name: str, value: Any):
        with self.db() as c:
            c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (name, canonical(value)))

    def secret_names(self) -> list[str]:
        with self.db() as c:
            return [r[0] for r in c.execute("SELECT name FROM secrets ORDER BY name")]

    def create_job(self, tool: str, inputs: dict, workspace: Path, request_key: str | None, context=None):
        key = request_key or str(uuid.uuid4())
        if not 1 <= len(key) <= 200:
            raise RouterError("bad_request_key", "Request key must contain 1-200 characters.")
        payload=[tool, inputs, str(workspace)]
        if context is not None: payload.append(context)
        fingerprint = hashlib.sha256(canonical(payload).encode()).hexdigest()
        now, job_id = time.time(), str(uuid.uuid4())
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM jobs WHERE request_key=?", (key,)).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise RouterError("idempotency_conflict", "Request key already belongs to different inputs, tool or workspace.")
                return self._decode(row), False
            data = {"inputs": inputs, "artifacts": [], "cost_usd": None,
                    "cost_status": "unknown", "verification": "not_started"}
            c.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                      (job_id, key, fingerprint, tool, str(workspace), "submitting", canonical(data), now, now))
            c.execute("INSERT INTO events(job_id,kind,at) VALUES (?,?,?)", (job_id, "created", now))
        return self.job(job_id), True

    @staticmethod
    def _decode(row):
        result = dict(row)
        result["data"] = json.loads(result["data"])
        result.pop("fingerprint", None)
        return result

    def job(self, job_id: str):
        with self.db() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise RouterError("job_not_found", "No local job with that ID.")
        return self._decode(row)

    def jobs(self, limit: int = 50):
        with self.db() as c:
            return [self._decode(r) for r in c.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,))]

    def update_job(self, job_id: str, status: str, **patch):
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise RouterError("job_not_found", "No local job with that ID.")
            data = json.loads(row[0])
            data.update(patch)
            c.execute("UPDATE jobs SET status=?,data=?,updated=? WHERE id=?",
                      (status, canonical(data), time.time(), job_id))
            c.execute("INSERT INTO events(job_id,kind,at) VALUES (?,?,?)", (job_id, status, time.time()))
        return self.job(job_id)
