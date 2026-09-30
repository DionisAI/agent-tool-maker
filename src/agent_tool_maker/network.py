from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlsplit, urljoin
import httpx
from .errors import RouterError

MAX_RESPONSE = 128 * 1024 * 1024


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


def public_address(url, resolver=socket.getaddrinfo):
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
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise RouterError("unsafe_download", "Artifact host resolves to a private, local or special-purpose address.")


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

    def download(self, url, max_bytes=MAX_RESPONSE):
        """Public HTTPS only; no API headers/cookies. DNS check is defense-in-depth, not a sandbox."""
        for _ in range(4):
            public_address(url,self.resolver)
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
