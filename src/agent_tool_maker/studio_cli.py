"""Independent Tripo server commands; fixed tool manifests remain the permission gate."""
from __future__ import annotations

import argparse
import asyncio
import copy
import os
import shutil
from pathlib import Path

from .errors import RouterError
from .storage import atomic_write, canonical
from .studio_runtime import DATA, TICKET_ENV, bundle_digest, index, private_path, request, serve, studio_dir


def add_commands(sub):
    root = sub.add_parser("studio", help="Server-owned Tripo browser; no local computer or Cookie synchronization")
    commands = root.add_subparsers(dest="operation", required=True)
    daemon = commands.add_parser("serve", help="Foreground persistent browser service; supervise it on the server")
    daemon.add_argument("--node", type=Path)
    daemon.add_argument("--chromium", type=Path)
    daemon.add_argument("--headed", action="store_true")
    daemon.add_argument("--virtual-display", help="Linux Xvfb display, e.g. :99; keeps the browser headed after login closes")
    commands.add_parser("status")
    login = commands.add_parser("login", help="Temporary loopback VNC entry into the SERVER browser; human login only")
    login.add_argument("--ttl", type=int, default=600)
    login.add_argument("--port", type=int, default=5900)
    commands.add_parser("login-close")
    install = commands.add_parser("install", help="Preview reviewed tripo.server.* definitions; never replace local adapters")
    install.add_argument("--apply", action="store_true")
    install.add_argument("--approve", help="Exact preview bundle SHA256")
    install.add_argument("--atm-executable", type=Path)
    runner = commands.add_parser("run", help="Run an installed server tool through existing ATM permission and job gates")
    runner.add_argument("tool", help="Reviewed operation name, such as account or assets")
    runner.add_argument("--input", required=True)
    runner.add_argument("--workspace", type=Path, default=Path.cwd())
    runner.add_argument("--request-key", required=True)
    for flag in ("code", "write", "paid"):
        runner.add_argument("--allow-" + flag, action="store_true")
    # Router-only entry. help=SUPPRESS would print "==SUPPRESS==", so list public operations instead.
    adapter = commands.add_parser("adapter")
    adapter.add_argument("--bundle", required=True)
    adapter.add_argument("tool")
    adapter.add_argument("argv", nargs=argparse.REMAINDER)
    commands.metavar = "{" + ",".join(name for name in commands.choices if name != "adapter") + "}"


def manifests(home):
    from .maker import validate_manifest
    pin = bundle_digest()
    tools = []
    for operation, original in index().items():
        tool = copy.deepcopy(original)
        tool["id"] = "tripo.server." + operation
        tool["title"] = "Tripo server " + operation
        tool["executable"] = "atm"
        tool["command"]["argv"] = ["--home", str(home), "studio", "adapter", "--bundle", pin, operation,
                                    *original["command"]["argv"][3:]]
        tool["notes"] += " Server-owned persistent Chromium via private Unix socket; no OpenCLIApp or local computer dependency."
        tools.append(validate_manifest(tool))
    return tools


def dispatch(args, router):
    operation = args.operation
    home = router.state.home
    if operation == "serve":
        node = str(args.node or shutil.which("node") or "")
        if not node or not Path(node).is_file():
            raise RouterError("dependency_missing", "A reviewed Node.js executable is required on this machine.")
        if args.chromium and not args.chromium.is_file():
            raise RouterError("dependency_missing", "The selected Chromium executable does not exist.")
        try:
            asyncio.run(serve(home, node=node, executable=str(args.chromium) if args.chromium else None,
                              headed=args.headed, virtual_display=args.virtual_display))
        except RouterError:
            raise
        except Exception:
            raise RouterError("browser_start_failed", "Server browser startup failed; check Chromium, sandbox and display dependencies locally.") from None
        return {"status": "stopped", "profile_preserved": True}
    if operation in {"status", "login", "login-close"}:
        packet = {"method": "login_close" if operation == "login-close" else operation}
        if operation == "login":
            packet.update(ttl=args.ttl, port=args.port)
        return asyncio.run(request(home, packet, timeout=60))
    if operation == "install":
        from .catalog import Catalog
        from .cli_adapter import bind_cli
        from .maker import digest, install
        pin = bundle_digest()
        tools = manifests(home)
        plan = {"status": "preview", "bundle_sha256": pin, "tools": [{"id": t["id"], "sha256": digest(t)} for t in tools],
                "tool_count": len(tools), "credentials_copied": False, "existing_local_tools_preserved": True}
        if not args.apply:
            return plan
        if args.approve != pin:
            raise RouterError("approval_required", "Apply requires the exact reviewed server bundle SHA256.")
        executable = args.atm_executable or Path(shutil.which("atm") or "")
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RouterError("bad_executable", "Bind an existing reviewed ATM executable on this machine.")
        # Preflight every collision BEFORE any installation or binary binding.
        stored = {t["id"]: t for t in router.state.setting("custom_tools", [])}
        for tool in tools:
            existing = router.catalog.tools.get(tool["id"])
            if existing and (tool["id"] not in stored or digest(stored[tool["id"]]) != digest(tool)):
                raise RouterError("definition_conflict", "An existing server definition differs; review a CAS update instead of replacing it.")
        directory = private_path(studio_dir(home) / "manifests", directory=True)
        for tool in tools:
            if tool["id"] in stored:
                continue
            path = directory / (tool["id"] + ".json")
            atomic_write(path, canonical(tool).encode())
            install(router.state, router.catalog, path, digest(tool))
            router.catalog = Catalog(router.state)
        bind_cli(router.state, "atm", str(executable))
        return {**plan, "status": "installed", "authentication": "not_verified"}
    if operation == "run":
        from .cli import load_input
        grants = (["execute_code"] if args.allow_code else []) + (["external_write"] if args.allow_write else [])
        return router.run("tripo.server." + args.tool, load_input(args.input), args.workspace,
                          request_key=args.request_key, allow_paid=args.allow_paid, grants=grants)
    if operation == "adapter":
        if args.bundle != bundle_digest():
            raise RouterError("definition_changed", "Review and reinstall the changed server runtime bundle.")
        # Write/paid/confirmed operations need the single-use ticket only the Router's execution sets.
        return asyncio.run(request(home, {"method": "run", "operation": args.tool, "argv": args.argv,
                               "workspace": str(Path.cwd()), "bundle": args.bundle, "ticket": os.environ.get(TICKET_ENV)}))
    raise RouterError("invalid_argument", "Unknown server operation.")
