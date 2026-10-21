from __future__ import annotations
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit, urljoin
import httpx
from .errors import RouterError
from .storage import canonical

MAX_RESPONSE = 128 * 1024 * 1024
# RFC 2544 benchmarking range. Fake-IP proxy tunnels (Shadowrocket, Clash, Surge) answer every name from it.
FAKE_IP = ipaddress.ip_network("198.18.0.0/15")
# IPv6 forms that carry an IPv4 address (Python's is_global judges the IPv6 form, not the address inside).
IPV4_TRANSLATED = ipaddress.ip_network("::ffff:0:0:0/96")
NAT64 = ipaddress.ip_network("64:ff9b::/96")  # 64:ff9b:1::/48 (local-use NAT64) is already non-global.
NETWORK_SETTING = "network"


def network_settings(state) -> dict:
    """Owner network options. Read at every address check, so a change reaches the console, the CLI,
    the broker and the background OAuth worker without a restart. Anything but an exact true is off."""
    try:
        value = state.setting(NETWORK_SETTING, {})
    except ValueError:  # A row that is not JSON reads as off; the owner's next change overwrites it.
        value = {}
    value = value if isinstance(value, dict) else {}
    changed = value.get("changed_at")
    return {"fake_ip_tunnel": value.get("fake_ip_tunnel") is True,
            "changed_at": changed if type(changed) in (int, float) else None}


def fake_ip_tunnel(state) -> bool:
    return network_settings(state)["fake_ip_tunnel"]


def set_fake_ip_tunnel(state, enabled, *, expected=None) -> dict:
    """Owner-only: the console calls this; no CLI command does. Compared and written in one SQLite transaction."""
    if type(enabled) is not bool or expected is not None and type(expected) is not bool:
        raise RouterError("invalid_request", "Expected a boolean field.")
    with state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT value FROM settings WHERE name=?", (NETWORK_SETTING,)).fetchone()
        try:
            current = json.loads(row[0]) if row else {}
        except ValueError:
            current = {}
        current = current if isinstance(current, dict) else {}
        previous = current.get("fake_ip_tunnel") is True
        if expected is not None and previous is not expected:
            raise RouterError("state_changed", "Network setting changed; refresh before applying.")
        if previous != enabled:
            now = time.time()
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)",
                       (NETWORK_SETTING, canonical({**current, "fake_ip_tunnel": enabled, "changed_at": now})))
    return {**network_settings(state), "previous": previous,
            "action": "unchanged" if previous == enabled else "enable" if enabled else "disable"}


def numeric_host(host: str) -> bool:
    """An address written in the URL, in any notation the system resolver reads without DNS
    (198.18.0.1, 3323068417, 0xc6120001, 198.18.1, a trailing dot). Never sends a query."""
    for name in dict.fromkeys((host, host.rstrip("."))):
        try:
            socket.getaddrinfo(name, 443, flags=socket.AI_NUMERICHOST, type=socket.SOCK_STREAM)
            return True
        except (OSError, UnicodeError, ValueError):
            pass
        try:
            socket.inet_aton(name)
            return True
        except (OSError, ValueError):
            pass
    return False


def fake_ip_answer(address) -> bool:
    """Plain IPv4 only: mapped, compatible or translated IPv6 forms of the range are not Fake-IP answers."""
    return address.version == 4 and address in FAKE_IP


def plain_global(address) -> bool:
    """Stricter than is_global, for the answers the owner's Fake-IP setting lets through beside 198.18.0.0/15:
    unicast and not reserved, IPv6 site-local, or an IPv4-mapped, -compatible or -translated IPv6 form. A NAT64
    address counts only when the IPv4 address inside it would. With the setting off, is_global is used unchanged."""
    if not address.is_global or address.is_multicast:
        return False
    if address.version == 4:
        return not address.is_reserved
    if address in NAT64:
        return plain_global(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
    return not (address.is_reserved or address.is_site_local or address.ipv4_mapped is not None
                or int(address) >> 32 == 0 or address in IPV4_TRANSLATED)


def checked_url(url: str, hosts: set[str] | None = None) -> str:
    try:
        p = urlsplit(url)
        port = p.port
    except (ValueError, TypeError):
        raise RouterError("unsafe_url", "Malformed URL.") from None
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.fragment or port not in (None,443):
        raise RouterError("unsafe_url", "Only HTTPS URLs without credentials, fragments or nonstandard ports are accepted.")
    if hosts and p.hostname not in hosts:
        raise RouterError("unsafe_origin", "Provider authentication is never forwarded to a different origin.")
    return url


def public_address(url, resolver=socket.getaddrinfo, *, fake_ip=False):
    """Every resolved address must be global. With the owner's Fake-IP setting (`fake_ip`), a DNS name may
    also resolve to plain IPv4 198.18.0.0/15: such an answer names no destination, so the local proxy, not
    this check, decides where the connection goes. Address literals never use that exemption, and every
    other answer in the set must then be plain global unicast (`plain_global`), or the whole set is refused.
    HTTPS certificate checks are unchanged."""
    host = urlsplit(checked_url(url)).hostname
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise RouterError("unsafe_download", "Private or special-purpose address literals are not permitted.")
    try:
        addresses = resolver(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise RouterError("dns_error", "Could not resolve artifact host.") from None
    answers = [ipaddress.ip_address(item[4][0]) for item in addresses]
    # What the owner's setting admits: a DNS name's plain Fake-IP answers, every other answer plain global unicast.
    named = any(fake_ip_answer(a) for a in answers) and not numeric_host(host)
    admitted = bool(answers) and all(named and fake_ip_answer(a) or plain_global(a) for a in answers)
    if not (admitted if fake_ip else answers and all(a.is_global for a in answers)):
        # The hint offers the setting only when turning it on would admit this exact set.
        raise RouterError("unsafe_download", "Artifact host resolves to a private, local or special-purpose address.",
                          hint="fake_ip_tunnel" if admitted and not fake_ip else None)


class Network:
    """No automatic paid retries, no environment proxies, no auth-bearing redirects."""
    def __init__(self, transport=None, resolver=socket.getaddrinfo):
        self.client = httpx.Client(transport=transport, timeout=httpx.Timeout(45,connect=15),
                                   follow_redirects=False,trust_env=False)
        self.resolver = resolver
        self.artifact_client = httpx.Client(transport=transport, timeout=45, follow_redirects=False, trust_env=False)

    def close(self):
        self.client.close()
        self.artifact_client.close()

    def request(self, method, url, *, host, headers=None, body=None, allow_local=False, form=False):
        if allow_local:
            p=urlsplit(url)
            if p.scheme!="http" or p.hostname not in {"127.0.0.1","localhost","::1"} or p.hostname!=host or p.username or p.password or p.fragment:
                raise RouterError("unsafe_origin","Local API requests must use an explicitly configured loopback origin.")
        else: checked_url(url, {host})
        self.client.cookies.clear()
        kwargs={"data":body} if form else {"json":body}
        try:
            with self.client.stream(method, url, headers=headers, **kwargs) as r:
                if not 200 <= r.status_code < 300:
                    code = "upstream_auth" if r.status_code in [401,403] else "upstream_http"
                    if r.status_code == 402:
                        code = "upstream_payment_required"
                    raise RouterError(code, f"Provider returned HTTP {r.status_code}; response body suppressed.",
                                      uncertain=method not in {"GET","HEAD"} and r.status_code >= 500)
                chunks, size = [], 0
                for chunk in r.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE:
                        raise RouterError("response_too_large", "Provider response exceeds the local limit.",uncertain=method not in {"GET","HEAD"})
                    chunks.append(chunk)
                return httpx.Response(r.status_code,headers=r.headers,content=b"".join(chunks))
        except (httpx.HTTPError, OSError):
            raise RouterError("network_error", "Request interrupted; paid submissions are not automatically repeated.",uncertain=method not in {"GET","HEAD"}) from None

    @staticmethod
    def json(response, *, submission=False):
        try:
            value = response.json()
            if not isinstance(value,dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeDecodeError):
            raise RouterError("upstream_schema", "Provider did not return a JSON object.",uncertain=submission) from None

    def download(self, url, max_bytes=MAX_RESPONSE, *, fake_ip=lambda: False):
        """Public HTTPS only; no API headers/cookies. DNS check is defense-in-depth, not a sandbox.
        Every redirect hop is checked again and reads the owner's Fake-IP setting again (`fake_ip()`)."""
        for _ in range(4):
            public_address(url,self.resolver,fake_ip=fake_ip())
            try:
                # A separate client prevents provider Set-Cookie state reaching artifact hosts.
                self.artifact_client.cookies.clear()
                with self.artifact_client.stream("GET",url,headers={"Accept":"*/*"}) as r:
                    if r.status_code in [301,302,303,307,308]:
                        next_url = urljoin(url,r.headers.get("location",""))
                        if next_url == url:
                            raise RouterError("download_redirect", "Invalid artifact redirect.")
                        url = checked_url(next_url)
                        continue
                    if r.status_code != 200:
                        raise RouterError("download_http", f"Artifact returned HTTP {r.status_code}.")
                    chunks,size=[],0
                    for chunk in r.iter_bytes():
                        size+=len(chunk)
                        if size>max_bytes:
                            raise RouterError("artifact_too_large","Artifact exceeds 128 MiB limit.")
                        chunks.append(chunk)
                    return b"".join(chunks),r.headers.get("content-type","").split(";")[0]
            except (httpx.HTTPError,OSError):
                raise RouterError("download_network", "Artifact download interrupted; generation was not repeated.") from None
        raise RouterError("download_redirect", "Too many artifact redirects.")
