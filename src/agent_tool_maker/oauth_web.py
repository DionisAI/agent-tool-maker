"""Local owner UI starts one bounded listener; consent remains in the provider UI."""
import threading

from .engine import Router
from .oauth import OAuth


def login(router, *, provider, keep_login, replace, executable):
    connection = OAuth(router.state, router.vault, router.net)
    current = connection.status(provider)
    if current["status"] == "pending" or current["status"] in {"ready", "expired", "refreshing"} and not replace:
        return {**current, "action": "preserved", "browser_opened": False}
    # Request-scoped WebVault is wiped when the HTTP handler finishes. Give the
    # bounded callback worker its own key snapshot; never retain the passphrase.
    worker = Router(router.state.home)
    try:
        worker.vault._key = router.vault.unlock()
        manager = OAuth(worker.state, worker.vault, worker.net)
        server, result = manager.begin_login(provider, keep_login=keep_login, replace=replace)
    except BaseException:
        worker.close()
        worker.vault._key = None
        raise
    if server is None:
        worker.close()
        worker.vault._key = None
        return result

    def run():
        try:
            final = server.run()
            if final["status"] == "ready" and final.get("refreshable") and keep_login:
                from .oauth_service import install_service
                from .errors import RouterError
                try:
                    install_service(worker.state, executable=executable, apply=True)
                except RouterError as error:
                    worker.state.set_setting("oauth_service", {"status": "load_failed", "error": error.code})
        finally:
            worker.close()
            worker.vault._key = None
            worker.vault._used_secrets.clear()
    threading.Thread(target=run, name="atm-oauth-login", daemon=True).start()
    return result
