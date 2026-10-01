"""Portable extension data and code generation. Drafts never install or execute themselves."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .errors import RouterError
from .maker import digest, read_manifest, validate_manifest
from .storage import canonical, atomic_write
from .sync import strict_json, write_sync_file

NAME = re.compile(r"[a-z][a-z0-9_.-]{1,79}\Z")
FORMAT = "atm-extension-v1"


def credential_name(name: str) -> str:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise RouterError("invalid_credential_name", "Use a lowercase namespace, 2–80 letters/digits/dots/dashes/underscores; no secret values.")
    return name


def declare_credential(router, name: str, *, label: str | None = None, apply=False) -> dict:
    """Declare a vault slot without having to install an adapter or storing a value."""
    credential_name(name)
    label = label or name
    if not isinstance(label, str) or not 1 <= len(label) <= 120 or any(ord(c) < 32 for c in label):
        raise RouterError("invalid_label", "Use a short non-secret label.")
    from .management import known_credentials
    with router.state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT value FROM settings WHERE name='credential_registry'").fetchone()
        registry = json.loads(row[0]) if row else {}
        action = "unchanged" if name in registry or name in known_credentials(router) else "declare"
        if apply and action == "declare":
            registry[name] = {"label": label}
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ("credential_registry", canonical(registry)))
    return {"provider": name, "label": label, "action": action, "applied": bool(apply),
            "credential_saved": name in router.state.secret_names(), "secrets_returned": False,
            "next": "Human: atm connect NAME. Declaring a slot does not authorize a destination or validate an account."}


def write_draft(tool: dict, out: Path, catalog=None) -> dict:
    tool = validate_manifest(tool, catalog)
    write_sync_file(Path(out), (json.dumps(tool, ensure_ascii=False, indent=2) + "\n").encode())
    return {"path": str(Path(out).absolute()), "id": tool["id"], "sha256": digest(tool),
            "installed": False, "execution_started": False, "verification": "schema_only"}


def new_template(tool_id: str, kind: str, *, url=None, executable=None) -> dict:
    base = {"id": tool_id, "provider": tool_id.split(".")[0], "title": "Custom " + tool_id,
            "capabilities": ["custom"], "schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "paid": True, "permissions": [], "notes": "Draft template. Replace placeholders using observed documentation; not live verified."}
    if kind == "api":
        base.update(adapter="rest", credential=base["provider"], request={"origin": url or "https://api.example.com",
                    "path": "/v1/status", "method": "GET", "auth": "bearer"})
    elif kind == "cli":
        base.update(adapter="command", executable=executable or "mycli",
                    command={"argv": ["--version"], "output": "text", "timeout": 30})
    elif kind == "web":
        base.update(adapter="web_recipe", recipe={"version": 1, "start_url": url or "https://example.com/",
                    "allowed_origins": [], "steps": [
                        {"op": "wait", "target": {"css": "body"}},
                        {"op": "extract", "target": {"css": "h1"}, "name": "heading"}], "timeout_ms": 15000})
        p = urlsplit(base["recipe"]["start_url"])
        base["recipe"]["allowed_origins"] = [f"{p.scheme}://{p.netloc}"]
    else:
        raise RouterError("unsupported_template", "Choose api, cli or web.")
    return validate_manifest(base)


def update_manifest(state, catalog, path, *, approval: str, expected: str) -> dict:
    """Compare-and-swap a custom definition; preserve history, switches and jobs."""
    tool = validate_manifest(read_manifest(path), catalog)
    new_sha = digest(tool)
    if new_sha != approval:
        raise RouterError("approval_mismatch", "Approve the normalized candidate digest.")
    with state.db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT value FROM settings WHERE name='custom_tools'").fetchone()
        tools = json.loads(row[0]) if row else []
        old = next((t for t in tools if t["id"] == tool["id"]), None)
        if old is None:
            raise RouterError("not_custom_tool", "Only an installed custom tool can be updated.")
        if digest(old) != expected:
            raise RouterError("definition_changed", "Installed definition changed; inspect it and review again.")
        if new_sha != expected:
            db.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", ("tool_history:" + tool["id"] + ":" + expected, canonical(old)))
            tools = [tool if t["id"] == tool["id"] else t for t in tools]
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ("custom_tools", canonical(tools)))
    return {"updated": tool["id"], "previous_sha256": expected, "sha256": new_sha,
            "unchanged": new_sha == expected, "old_grants": "stale_until_owner_review", "live_tested": False}


def _import_openapi(document: dict, operation_id: str, tool_id: str, *, credential: str | None = None) -> dict:
    """Deliberately narrow OpenAPI3 JSON importer. No fetch, YAML objects or external refs."""
    def unsupported(message):
        raise RouterError("openapi_unsupported", message)
    if not isinstance(document, dict) or not str(document.get("openapi", "")).startswith("3."):
        unsupported("Only OpenAPI 3.x JSON documents are supported.")
    # Resolve local refs with explicit cycle/depth rejection, not network retrieval.
    def resolve(value, chain=(), depth=0):
        if depth > 32:
            unsupported("Reference/schema depth exceeds 32.")
        if isinstance(value, list):
            return [resolve(v, chain, depth + 1) for v in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            ref = value["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/") or ref in chain or len(value) != 1:
                unsupported("Use acyclic local $ref without siblings; external refs are never fetched.")
            result = document
            try:
                for item in ref[2:].split("/"):
                    result = result[item.replace("~1", "/").replace("~0", "~")]
            except (KeyError, TypeError):
                unsupported("Local reference is missing.")
            return resolve(result, (*chain, ref), depth + 1)
        # OpenAPI3.0 nullable is converted explicitly.
        result = {k: resolve(v, chain, depth + 1) for k, v in value.items() if k not in {"nullable", "example", "examples"}}
        if value.get("nullable"):
            if isinstance(result.get("type"), str):
                result["type"] = [result["type"], "null"]
            else:
                unsupported("Nullable schemas without a simple type require a manual adapter.")
        return result
    candidates = []
    for path, item in document.get("paths", {}).items():
        item = resolve(item)
        for method in ("get", "post", "put", "patch", "delete"):
            op = item.get(method, {})
            if op.get("operationId") == operation_id:
                candidates.append((path, item, method, op))
    if len(candidates) != 1:
        unsupported("Select exactly one unique operationId.")
    path, item, method, op = candidates[0]
    servers = op.get("servers", item.get("servers", document.get("servers", [])))
    if len(servers) != 1 or not isinstance(servers[0].get("url"), str) or servers[0].get("variables"):
        unsupported("Select one fixed HTTPS server; variables or multiple servers need manual review.")
    from .network import checked_url
    server = servers[0]["url"].rstrip("/")
    checked_url(server)
    p = urlsplit(server)
    if p.query or p.fragment:
        unsupported("Server URLs cannot contain queries or fragments.")
    origin = f"{p.scheme}://{p.netloc}"
    spec = {"origin": origin, "path": p.path + path, "method": method.upper(), "auth": "none"}
    properties, required, query, optional = {}, [], {}, []
    params = {}
    for param in [*item.get("parameters", []), *op.get("parameters", [])]:
        params[(param.get("in"), param.get("name"))] = param
    for (location, name), param in params.items():
        if location not in {"path", "query"} or not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            unsupported("Only named scalar path/query parameters are supported; headers/cookies need manual review.")
        schema = param.get("schema", {})
        if schema.get("type") not in ({"string", "integer"} if location == "path" else {"string", "number", "integer", "boolean"}) or name in properties or name == "body":
            unsupported("Complex/duplicate parameters require a manual adapter.")
        if param.get("style", "simple" if location == "path" else "form") != ("simple" if location == "path" else "form"):
            unsupported("Non-default parameter serialization is unsupported.")
        properties[name] = schema
        if param.get("required") or location == "path":
            required.append(name)
        if location == "query":
            query[name] = "$" + name
            if not param.get("required"):
                optional.append(name)
    if query:
        spec.update(query=query, optional_query=optional)
    if "requestBody" in op:
        body = op["requestBody"]
        if not body.get("required") or set(body.get("content", {})) != {"application/json"}:
            unsupported("Only required application/json request bodies are imported.")
        properties["body"] = body["content"]["application/json"].get("schema", {})
        required.append("body")
        spec["body"] = "$body"
    security = op.get("security", document.get("security", []))
    credential_field = {}
    if security:
        if len(security) != 1 or len(security[0]) != 1:
            unsupported("Multiple/alternative authentication schemes need manual review.")
        scheme_name = next(iter(security[0]))
        scheme = resolve(document.get("components", {}).get("securitySchemes", {}).get(scheme_name, {}))
        if scheme.get("type") == "http" and scheme.get("scheme") in {"bearer", "basic"}:
            spec["auth"] = scheme["scheme"]
        elif scheme.get("type") == "apiKey" and scheme.get("in") == "header":
            spec["auth"] = "header:" + scheme["name"]
        else:
            unsupported("Only bearer, basic or header API keys; OAuth/cookie/query-key auth is not imported.")
        if not credential:
            unsupported("Provide the vault slot name using --credential (never the key value).")
        credential_field["credential"] = credential_name(credential)
    tool = {"id": tool_id, "provider": tool_id.split(".")[0], "title": (op.get("summary") or operation_id)[:200],
            "adapter": "rest", "capabilities": ["custom"], "paid": True,
            "schema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
            "request": spec, **credential_field, "notes": "Imported draft; request/response and pricing require independent live acceptance."}
    return validate_manifest(tool)


def import_openapi(document, operation_id, tool_id, *, credential=None):
    try:
        return _import_openapi(document,operation_id,tool_id,credential=credential)
    except RouterError:
        raise
    except (TypeError,KeyError,ValueError,AttributeError,RecursionError):
        raise RouterError('openapi_unsupported','Malformed or unsupported OpenAPI structure; no network lookup or heuristic fallback was made.') from None


def pack(tool: dict, directory: Path, catalog=None) -> dict:
    """Compile a manifest into a portable Python CLI; no LLM or credentials needed."""
    tool = validate_manifest(tool, catalog)
    dest = Path(directory).expanduser().absolute()
    for p in (dest, *dest.parents):
        if p.is_symlink():
            raise RouterError("unsafe_bundle_path", "Bundle path cannot traverse symlinks.")
    if dest.exists():
        raise RouterError("file_exists", "Choose a new bundle directory; existing work is preserved.")
    sha = digest(tool)
    from importlib.resources import files
    script = files('agent_tool_maker.data').joinpath('EXTENSION_CLI_TEMPLATE.py').read_text().replace(
        '__TOOL_LITERAL__',repr(tool['id'])).replace('__DIGEST_LITERAL__',repr(sha))
    readme = (f"# {tool['id']}\n\nGenerated stdlib-only Python CLI. Requires an installed ATM >=0.6.0 command and the reviewed manifest. Use --atm /absolute/path/to/atm when PATH differs (including pipx).\n"
              "No credential, browser session, binary, account, permission or dependency is embedded.\n\n"
              "```sh\natm make validate manifest.json\n"
              f"atm make install manifest.json --approve {sha}\n"
              "python tool.py --input inputs.example.json --workspace /your/project --dry-run\n```\n\n"
              "For scoped execution add `--client claude` or `--client codex` and a stable `--request-key`; never bypass Broker refusal.\n"
              "Review paid/write/code grants separately. Pass actual schema-valid inputs; examples may be empty.\n"
              "Manifest or runtime changes need review; a hash proves consistency, not safety or publisher identity.\n")
    data = {"manifest.json": json.dumps(tool, ensure_ascii=False, indent=2) + "\n", "tool.py": script,
            "README.md": readme, "inputs.example.json": json.dumps(tool.get("example", {}), ensure_ascii=False, indent=2) + "\n"}
    hashes = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in data.items()}
    data["bundle-lock.json"] = canonical({"format": FORMAT, "tool": tool["id"], "definition_sha256": sha, "files": hashes})
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".atm-build-", dir=dest.parent))
    try:
        for name, text in data.items():
            atomic_write(temp / name, text.encode())
        # mkdir reserves the target without replacing another writer's directory.
        dest.mkdir()
        for file in temp.iterdir():
            file.rename(dest / file.name)
    finally:
        shutil.rmtree(temp)
    return {"directory": str(dest), "tool": tool["id"], "sha256": sha,
            "files": sorted(data), "installed": False, "generated_python_cli": True}


def validate_bundle(directory: Path) -> dict:
    directory = Path(directory)
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise RouterError("unsafe_bundle_path", "No symlink bundle paths.")
    lock_path = directory / "bundle-lock.json"
    if lock_path.is_symlink() or not lock_path.is_file() or lock_path.stat().st_size > 16384:
        raise RouterError("invalid_bundle", "Missing regular bundle lock.")
    lock = strict_json(lock_path.read_bytes(), limit=16384)
    if not isinstance(lock,dict) or lock.get("format") != FORMAT or set(lock.get("files", {})) != {"manifest.json", "tool.py", "README.md", "inputs.example.json"}:
        raise RouterError("invalid_bundle", "Unknown bundle format or file set.")
    for name, expected in lock["files"].items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512*1024 or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RouterError("bundle_modified", "A bundle file differs from its lock; review/rebuild before use.")
    tool = validate_manifest(read_manifest(directory / "manifest.json"))
    if digest(tool) != lock.get("definition_sha256") or tool["id"] != lock.get("tool"):
        raise RouterError("bundle_modified", "Manifest digest differs from the bundle lock.")
    return {"valid": True, "sha256": digest(tool), "tool": tool["id"], "executed": False,
            "security_audit": False}
