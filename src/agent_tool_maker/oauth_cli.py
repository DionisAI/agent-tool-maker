"""Human consent entry point and metadata-only refresh supervision."""
from __future__ import annotations

import sys
import time

from .errors import RouterError
from .oauth import NAME, OAuth


def add_commands(sub):
    oauth = sub.add_parser("oauth", help="Owner-managed browser login and encrypted OAuth refresh; no token export")
    ops = oauth.add_subparsers(dest="operation", required=True)
    for verb in ("status", "refresh"):
        op = ops.add_parser(verb)
        op.add_argument("provider", nargs="?", default=NAME, choices=[NAME])
    login = ops.add_parser("login")
    login.add_argument("provider", nargs="?", default=NAME, choices=[NAME])
    login.add_argument("--replace", action="store_true", help="Explicitly replace an existing OAuth connection")
    login.add_argument("--keep-login", action="store_true", help="After consent, enable native-keyring refresh and a macOS user service")
    keep = ops.add_parser("keep-login")
    keep.add_argument("provider", nargs="?", default=NAME, choices=[NAME])
    keep.add_argument("--disable", action="store_true")
    keep.add_argument("--apply", action="store_true")
    watch = ops.add_parser("watch", help="Metadata-only refresh worker; native keyring and explicit keep-login required")
    watch.add_argument("--once", action="store_true")
    watch.add_argument("--interval", type=int, default=60)


def tick(router):
    connection = OAuth(router.state, router.vault, router.net)
    try:
        return connection.refresh(background=True)
    except RouterError as error:
        return {**connection.status(), "action": "paused", "error": error.as_dict()}
    finally:
        router.vault._key = None
        router.vault.password = None
        router.vault._used_secrets.clear()


def dispatch(args, router):
    connection = OAuth(router.state, router.vault, router.net)
    if args.operation == "status":
        from .oauth_service import service_status
        return {**connection.status(args.provider), "service": service_status(router.state)}
    if args.operation == "refresh":
        return connection.refresh(args.provider, force=True)
    if args.operation == "login":
        server, result = connection.begin_login(args.provider, keep_login=args.keep_login, replace=args.replace)
        if server is None:
            return result
        print(__import__("json").dumps(result), flush=True)
        try:
            final = server.run()
            if final["status"] == "ready" and final.get("refreshable") and args.keep_login:
                from .oauth_service import install_service
                final["service"] = install_service(router.state, executable=sys.argv[0], apply=True)
            return final
        finally:
            router.vault._key = None
            router.vault.password = None
            router.vault._used_secrets.clear()
    if args.operation == "keep-login":
        from .oauth_service import install_service
        if not args.apply:
            return {"provider": args.provider, "keep_login": not args.disable, "applied": False,
                    "service": install_service(router.state, executable=sys.argv[0], apply=False) if not args.disable else None}
        result = connection.keep_login(args.provider, enabled=not args.disable)
        if not args.disable:
            result["service"] = install_service(router.state, executable=sys.argv[0], apply=True)
        return result
    if args.operation == "watch":
        if not 15 <= args.interval <= 3600:
            raise RouterError("oauth_interval", "Refresh polling interval must be 15-3600 seconds.")
        while True:
            result = tick(router)
            if args.once:
                return result
            # Fixed metadata diagnostics only; no raw provider errors or tokens.
            print(__import__("json").dumps(result), flush=True)
            time.sleep(args.interval)
    raise RouterError("oauth_command", "Unknown OAuth operation.")
