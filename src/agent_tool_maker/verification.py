"""Explicit, fixed read-only account probes. Never use generation as a health check."""
from __future__ import annotations

import re
import time
from urllib.parse import urlsplit

from .errors import RouterError
from .health import credential_revision, vault_health

PROBES = {
    "elevenlabs": {"url": "https://api.elevenlabs.io/v1/user", "header": "xi-api-key", "prefix": "",
                   "source": "https://elevenlabs.io/docs/api-reference/user/get"},
    "tripo": {"url": "https://openapi.tripo3d.ai/v3/account/balance", "header": "Authorization", "prefix": "Bearer ",
              "source": "https://developers.tripo3d.ai/en/docs/account"},
    "cloudflare": {"url": "https://api.cloudflare.com/client/v4/user/tokens/verify", "header": "Authorization", "prefix": "Bearer ",
                   "source": "https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/verify/"},
    "github": {"url": "https://api.github.com/user", "header": "Authorization", "prefix": "Bearer ",
               "source": "https://docs.github.com/en/rest/users/users#get-the-authenticated-user"},
}


def accepted(provider: str, payload: dict) -> bool:
    if provider == "elevenlabs":
        return isinstance(payload.get("user_id"), str) and bool(payload["user_id"])
    if provider == "github":
        return isinstance(payload.get("login"), str) and bool(payload["login"])
    if provider == "cloudflare":
        return payload.get("success") is True and isinstance(payload.get("result"), dict) and payload["result"].get("status") == "active"
    data = payload.get("data")
    return payload.get("code") == 0 and isinstance(data, dict) and type(data.get("balance")) in (int, float)


def verify(router, provider: str, *, allow_network=False) -> dict:
    if provider not in PROBES:
        return {"provider": provider, "status": "unsupported_probe", "network_calls": 0, "secrets_read": False,
                "next_action": "No reviewed account probe is available. Use the vendor's status flow or a separately approved small task; never silently generate, post or deploy."}
    probe = PROBES[provider]
    result = {"provider": provider, "status": "planned", "method": "GET", "url": probe["url"],
              "source": probe["source"], "network_calls": 0, "secrets_read": False,
              "scope": "This exact account/token endpoint only; not generation, deployment, project access or a price guarantee.",
              "note": "Cloudflare probe supports user-owned API tokens, not every account-token type. Provider quota/rate limits may apply."}
    if not allow_network:
        return result
    revision = credential_revision(router.state, provider)
    if revision is None:
        return {**result, "status": "missing_credential", "next_action": f"Human: connect {provider} privately once."}
    expiry = router.state.setting("credential_meta:" + provider, {}).get("expires_at")
    if expiry is not None and expiry <= time.time():
        return {**result, "status": "credential_expired", "next_action": "Renew this credential only. Automatic refresh is not implemented."}
    access = vault_health(router.vault)
    if access["state"] not in {"unlocked_in_this_process", "unlock_not_checked"}:
        return {**result, "status": access["state"], "next_action": access.get("next_action")}
    try:
        secret = router.vault.get(provider)
        result["secrets_read"] = True
        headers = {probe["header"]: probe["prefix"] + secret, "Accept": "application/json"}
        if provider == "github":
            headers["X-GitHub-Api-Version"] = "2022-11-28"
        result["network_calls"] = 1
        response = router.net.request("GET", probe["url"], host=urlsplit(probe["url"]).hostname, headers=headers)
        payload = router.net.json(response)
        result.update(status="probe_passed" if accepted(provider, payload) else "unexpected_or_rejected_response", http_status=response.status_code)
    except RouterError as error:
        result.update(status="auth_or_scope_rejected" if error.code == "upstream_auth" else error.code)
        status = re.search(r"HTTP (\d{3})", str(error))
        if status:
            result["http_status"] = int(status.group(1))
            if result["http_status"] == 429:
                result["status"] = "rate_limited"
            elif result["http_status"] >= 500:
                result["status"] = "service_unavailable"
        result["next_action"] = "Inspect this connection's key, scopes and service status. A 403 is not proof that every operation is unauthorized; do not reset other connections."
    # Persist only the probe result, never the HTTP body, headers, identity or balance.
    result["checked_at"] = time.time()
    if result["network_calls"]:
        router.state.set_setting("verification:" + provider, {
            "provider": provider, "status": result["status"], "checked_at": result["checked_at"],
            "http_status": result.get("http_status"), "credential_revision": revision,
            "scope": "account_probe_only"})
    return result
