"""Explicit per-user macOS launchd worker; no credentials in its plist or logs.

Disable means no new refresh admissions. Keep the plist recoverable instead of
uninstalling/deleting files. Other platforms expose the foreground watch worker.
"""
from __future__ import annotations

import hashlib
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

from .errors import RouterError
from .storage import atomic_write


def service_status(state):
    value = state.setting("oauth_service", {})
    return {"status": value.get("status", "not_installed"), "platform": sys.platform,
            "label": value.get("label"), "verification": "last_install_only", "secrets_returned": False}


def install_service(state, *, executable, apply=False, user_home=None, platform=None, runner=subprocess.run):
    if not apply or (platform or sys.platform) != "darwin":
        return _install_service(state, executable=executable, apply=apply, user_home=user_home, platform=platform, runner=runner)
    import fcntl
    lock = state.home / "oauth-service.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        raise RouterError("unsafe_path", "A private regular OAuth service lock is required.") from None
    with os.fdopen(fd, "a+b") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        return _install_service(state, executable=executable, apply=apply, user_home=user_home, platform=platform, runner=runner)


def loaded_arguments(output):
    text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output
    if not isinstance(text, str):
        return None
    block = re.search(r"(?ms)^\s*arguments = \{\s*\n(.*?)^\s*\}", text)
    return [line.strip() for line in block.group(1).splitlines() if line.strip()] if block else None


def _install_service(state, *, executable, apply=False, user_home=None, platform=None, runner=subprocess.run):
    system = platform or sys.platform
    if system != "darwin":
        return {"status": "foreground_only", "command": "atm oauth watch", "applied": False}
    if not isinstance(executable, (str, Path)):
        raise RouterError("oauth_service_executable", "An installed ATM executable is required for the user service.")
    path = Path(executable).expanduser().resolve()
    if path.name != "atm" or not path.is_file() or not os.access(path, os.X_OK):
        raise RouterError("oauth_service_executable", "Select the reviewed installed ATM executable for the user service.")
    label = "local.atm.oauth." + hashlib.sha256(str(state.home).encode()).hexdigest()[:16]
    target = (Path(user_home) if user_home else Path.home()) / "Library/LaunchAgents" / (label + ".plist")
    logs = state.home / "oauth-worker.log"
    config = {"Label": label, "ProgramArguments": [str(path), "--home", str(state.home), "oauth", "watch"],
              "RunAtLoad": True, "StartInterval": 60, "ProcessType": "Background",
              "StandardOutPath": str(logs), "StandardErrorPath": str(logs), "Umask": 0o077}
    # One finite tick per launch avoids an unbounded log-producing KeepAlive process.
    config["ProgramArguments"].append("--once")
    raw = plistlib.dumps(config, sort_keys=True)
    if target.is_symlink() or target.exists() and target.read_bytes() != raw:
        raise RouterError("oauth_service_conflict", "Existing user service differs; preserve it for explicit review.")
    result = {"status": "planned", "label": label, "path": str(target), "interval_seconds": 60, "applied": False}
    if not apply:
        return result
    if target.parent.is_symlink():
        raise RouterError("unsafe_path", "LaunchAgents directory must not be a symbolic link.")
    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not target.exists():
        atomic_write(target, raw)
    if target.is_symlink() or not target.is_file() or target.read_bytes() != raw:
        raise RouterError("oauth_service_conflict", "User service changed during installation; it was preserved.")
    # launchd-managed log is created private, with no secrets; cap it by recoverable rename.
    if logs.is_symlink():
        raise RouterError("unsafe_path", "OAuth log must not be a symbolic link.")
    if logs.exists() and logs.stat().st_size > 1024 * 1024:
        logs.rename(logs.with_name("oauth-worker-" + __import__("uuid").uuid4().hex + ".log"))
    if not logs.exists():
        atomic_write(logs, b"")
    domain = "gui/" + str(os.getuid())
    try:
        check = runner(["/bin/launchctl", "print", domain + "/" + label], capture_output=True, timeout=10)
        if check.returncode != 0:
            loaded = runner(["/bin/launchctl", "bootstrap", domain, str(target)], capture_output=True, timeout=10)
            if loaded.returncode != 0:
                state.set_setting("oauth_service", {"status": "load_failed", "label": label})
                raise RouterError("oauth_service_failed", "User service was written but launchd did not load it; no provider-body output returned.")
            check = runner(["/bin/launchctl", "print", domain + "/" + label], capture_output=True, timeout=10)
        if check.returncode != 0 or loaded_arguments(check.stdout) != config["ProgramArguments"] or target.is_symlink() or target.read_bytes() != raw:
            state.set_setting("oauth_service", {"status": "load_conflict", "label": label})
            raise RouterError("oauth_service_conflict", "Loaded user service differs from the reviewed arguments; no success was recorded.")
    except (OSError, subprocess.TimeoutExpired):
        state.set_setting("oauth_service", {"status": "load_failed", "label": label})
        raise RouterError("oauth_service_failed", "User service load check failed.") from None
    state.set_setting("oauth_service", {"status": "loaded", "label": label, "executable_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {**result, "status": "loaded", "applied": True}
