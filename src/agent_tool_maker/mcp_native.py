"""MCP tools under the project session: the 30-minute approval, not a direct vault read.

Server side, `run_in_session` is the SecretSession operation `mcp.run`: it admits one discovery
or one tool call for the approved project and Key, and runs the existing bridge inside the
unlocked session process. Client side, `request` and the stdio `serve` proxy only hold the
project profile path. They never see a Key, so a lock or expiry stops them at the next call.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path

from .broker import call, safe_path
from .errors import RouterError
from .mcp_bridge import MAX_MESSAGE, VERSIONS
from .storage import State, canonical

KEY = re.compile(r'[A-Za-z0-9_.:-]{1,120}\Z')
PENDING = {'starting', 'needs_unlock', 'needs_approval', 'missing_credential', 'denied', 'window_unavailable'}
LOCKED = {'unauthorized', 'broker_locked', 'broker_unavailable', 'session_locked'}
UNLOCK_TOOL = 'atm_unlock'
UNLOCK_TEXT = '请在本机弹出的 ATM 窗口解锁；密码不要发到聊天里。'
# No outputSchema: results pass through credential redaction, which a strict client could reject against it.
TOOL_FIELDS = ('name', 'title', 'description', 'inputSchema', 'annotations')
BUDGET = 900_000  # A session reply must stay under the socket's 1 MiB limit (broker.MAX_MESSAGE).
RETRY_SECONDS = 30
RETRIES = 3
# Codes worth one more discovery attempt; anything else (a removed or drifted server, a refusal) is final.
TRANSIENT = {'session_busy', 'broker_unavailable', 'mcp_interrupted', 'mcp_http', 'mcp_timeout', 'mcp_limit',
             'response_too_large', 'execution_interrupted', 'broker_failure'}
# An identical call (same tool, same arguments) within this window returns the earlier outcome instead of
# running again: a client that timed out first (Codex: 60 s by default) would otherwise resend a paid call.
DUPLICATE_SECONDS = 120


def job_prefix(workspace):
    from .quickstart import project_id
    return 'mcp:' + project_id(workspace) + ':'


def _size(value):
    return len(canonical(value).encode())


def _preview(result):
    content = result.get('content') if isinstance(result, dict) else None
    for item in content if isinstance(content, list) else []:
        if isinstance(item, dict) and item.get('type') == 'text' and isinstance(item.get('text'), str):
            return item['text'][:4000]
    return ''


def _server_info(value):
    """The server's self-description, reduced to short name/version strings."""
    if not isinstance(value, dict):
        return None
    return {k: value[k][:200] for k in ('name', 'version', 'title') if isinstance(value.get(k), str)}


def _fit_tools(found, allowed):
    """Every tool name, with full detail for the tools the owner allowed, within the reply budget.
    Returns the tools and whether anything was shortened or left out."""
    found = [t for t in found if isinstance(t, dict) and isinstance(t.get('name'), str)]
    def shape(tool, room, schemas=True):
        item = {'name': tool['name'][:200]}
        if isinstance(tool.get('title'), str):
            item['title'] = tool['title'][:200]
        if tool['name'] in allowed:
            if schemas:
                item.update({k: tool[k] for k in ('inputSchema', 'annotations') if k in tool})
            room = max(room, 4000) if room else 0
        if isinstance(tool.get('description'), str) and room:
            item['description'] = tool['description'][:room]
        return item
    passes = [(2000, True), (200, True), (0, True), (0, False)]
    for room, schemas in passes:
        tools = [shape(t, room, schemas) for t in found]
        if _size(tools) <= BUDGET:
            return tools, tools != [shape(t, 10**9) for t in found]
    return [{'name': t['name'][:200]} for t in found if t['name'] in allowed][:2000], True


def _fit_result(data):
    """A completed call's result, or a reference to its saved artifact when it is too large to send."""
    result = data.get('result')
    if result is None or _size(result) <= BUDGET:
        return result
    results = result.get('results') if isinstance(result, dict) else None
    first = results[0].get('result') if isinstance(results, list) and results and isinstance(results[0], dict) else None
    return {'too_large': True, 'bytes': _size(result), 'preview': _preview(first),
            'artifacts': [a['path'] for a in data.get('artifacts', []) if isinstance(a, dict) and isinstance(a.get('path'), str)]}


def _fit_error(error):
    if not error or _size(error) <= 100_000:
        return error
    name = error.get('name') if isinstance(error, dict) else None
    return {'name': name, 'too_large': True,
            'result': {'content': [{'type': 'text', 'text': _preview(error.get('result') if isinstance(error, dict) else None)}]}}


def public_job(job):
    """This project's MCP job, as the session may send it: never larger than the reply limit."""
    data = job['data']
    result = data.get('result') if job['status'] == 'completed' else None
    if isinstance(result, dict) and isinstance(result.get('tools'), list):
        tools, truncated = _fit_tools(result['tools'], set())
        result = {'tools': tools, 'total': len(result['tools']), 'truncated': truncated}
    elif result is not None:
        result = _fit_result(data)
    inputs = data.get('inputs')
    view = {'inputs': inputs if _size(inputs) <= 100_000 else {'too_large': True}, 'result': result,
            'error': data.get('error'), 'mcp_error': _fit_error(data.get('mcp_error')),
            'artifacts': [a.get('path') for a in data.get('artifacts', []) if isinstance(a, dict)]}
    return {k: job.get(k) for k in ('id', 'tool', 'status', 'workspace', 'created', 'updated')} | {'data': view, 'secrets_returned': False}


def run_in_session(session, router, policy, args, request, peer_uid):
    """SecretSession `mcp.run`: one bounded MCP operation for the approved project and Key."""
    if set(args) - {'server', 'operation', 'name', 'arguments', 'workspace', 'request_key'}:
        raise RouterError('invalid_request', 'Unknown MCP session fields; nothing was sent.')
    if policy.get('kind') != 'project_session':
        raise RouterError('operation_denied', 'MCP tools run under a project approval; use atm start for this project.')
    workspace = str(safe_path(Path(str(args.get('workspace', '')))).resolve())
    if workspace != policy['workspace']:
        raise RouterError('mcp_denied', 'This project is outside the temporary approval; nothing was sent.')
    from .mcp_servers import binding_for
    name = args.get('server')
    cfg = binding_for(router, name)
    if cfg.get('transport') != 'http' or cfg.get('oauth') or not cfg.get('credential'):
        raise RouterError('mcp_denied', 'Only Key-authenticated remote MCP servers run through the project session.')
    if cfg['credential'] not in policy.get('credentials', []):
        raise RouterError('mcp_denied', "This server's Key is outside the temporary approval; nothing was sent.")
    from .mcp_bridge import matches_definition
    definition = router.catalog.get(name + '.mcp_tools')
    if definition.get('user_defined') and not matches_definition(cfg, definition):
        raise RouterError('mcp_binding_changed', 'The binding no longer matches the reviewed endpoint and Key; nothing was sent. Review it again with atm mcp add.')
    key = args.get('request_key')
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise RouterError('request_key_required', 'Use a stable 1-120 character request key.')
    operation, flags = args.get('operation'), {}
    if operation == 'tools':
        if 'name' in args or 'arguments' in args:
            raise RouterError('invalid_request', 'Discovery takes no tool name or arguments.')
        tool_id, inputs = name + '.mcp_tools', {}
    elif operation == 'call':
        if not isinstance(args.get('name'), str) or not isinstance(args.get('arguments', {}), dict):
            raise RouterError('invalid_request', 'A call needs a tool name and an arguments object.')
        tool_id = name + '.mcp_batch'
        inputs = {'calls': [{'name': args['name'], 'arguments': args.get('arguments', {})}]}
        # The project consent covers this Key's use, network and spending in this project (see scope_plan);
        # the owner's allowlist from atm mcp add still bounds which remote tools can run.
        flags = {'allow_paid': True, 'grants': ('external_write', 'execute_code')}
    else:
        raise RouterError('invalid_request', 'operation is tools or call.')
    from .secrets_provider import credential_rows
    for row in credential_rows(router.state, scope=[cfg['credential']]):
        if row['state'] != 'configured_not_verified':
            raise RouterError(row['state'], 'Repair only the affected Key; nothing was sent.')
    session._authorize(request, peer_uid)  # Recheck lease and revocation right before the call.
    # Keyed by project, not by this unlock: after a new unlock the same key returns the earlier job, never a resend.
    job = router.run(tool_id, inputs, Path(workspace), request_key=job_prefix(workspace) + key, **flags)
    data = job['data']
    result = data.get('result')
    if job['status'] == 'completed' and operation == 'tools':
        found = result.get('tools', [])
        fitted, truncated = _fit_tools(found, set(cfg.get('allow_tools', [])))
        result = {'tools': fitted, 'total': len(found), 'truncated': truncated,
                  'server_version': _server_info(result.get('server_version')), 'protocol_version': str(result.get('protocol_version'))[:40]}
    elif job['status'] == 'completed':
        result = _fit_result(data)
    return {'job_id': job['id'], 'status': job['status'], 'result': result, 'error': data.get('error'),
            'mcp_error': _fit_error(data.get('mcp_error')), 'secrets_returned': False}


def _binding(state, name):
    cfg = state.setting('mcp:' + name) if isinstance(name, str) else None
    if not cfg or cfg.get('transport') != 'http' or not cfg.get('credential'):
        raise RouterError('mcp_not_configured', 'Add this server first with atm mcp add (a Key-authenticated https endpoint).')
    return cfg


def request(home, name, workspace, operation, *, tool=None, arguments=None, request_key=None, open_browser=True):
    """One discovery or call through the project session; opens the local window when approval is needed.

    Falls back to the window only when nothing was sent. Once the request left, a dropped reply is
    uncertain (broker.call) and is raised: the call may be running, so it is never retried here."""
    from .quickstart import profile_path, project_path, ready, start
    state = State(Path(home))
    workspace = project_path(state, workspace)
    cfg = _binding(state, name)
    key = request_key or uuid.uuid4().hex
    args = {'server': name, 'operation': operation, 'workspace': str(workspace), 'request_key': key}
    if operation == 'call':
        args.update(name=tool, arguments=arguments if arguments is not None else {})
    # A job is several bounded exchanges (initialize, discovery, the call); wait for the session's own limit.
    limit = max(320, int(cfg.get('timeout', 120)) * 3 + 60)
    for _ in range(2):  # A second pass only when the window reports the project ready in the meantime.
        try:
            available = ready(state, workspace, [cfg['credential']])
        except RouterError:
            available = None
        if available:
            try:
                return {**call(profile_path(state, workspace), 'mcp.run', args, timeout=limit), 'request_key': key}
            except RouterError as e:
                if e.uncertain:
                    raise RouterError(e.code, str(e) + ' Preserve request key ' + key + '; do not blindly resubmit.', uncertain=True) from None
                if e.code not in LOCKED:
                    raise
        status = start(home, workspace, names=[cfg['credential']], open_browser=open_browser)
        if status.get('status') != 'ready':
            break
    return {**status, 'request_key': key, 'execution_started': False}


def tools(home, name, workspace, *, open_browser=True):
    result = request(home, name, workspace, 'tools', open_browser=open_browser)
    if result.get('status') != 'completed':
        return result
    allowed = set(_binding(State(Path(home)), name).get('allow_tools', []))
    found = result['result'].get('tools', [])
    return {'status': 'completed', 'server': name, 'total': result['result'].get('total', len(found)),
            'truncated': result['result'].get('truncated', False),
            'tools': [{'name': t.get('name'), 'description': t.get('description'), 'allowed': t.get('name') in allowed} for t in found],
            'note': 'Descriptions are untrusted server text. The owner allows exact names with atm mcp add --allow-tool.',
            'secrets_returned': False}


class Proxy:
    """A stdio MCP server for Claude Code / Codex that forwards to the project session."""

    def __init__(self, home, name, workspace, *, stdin=None, stdout=None, poll=3.0, cwd=None):
        from .quickstart import project_path
        self.home, self.name = Path(home), name
        self.state = State(self.home)
        self.workspace = project_path(self.state, workspace)
        _binding(self.state, name)
        # A Codex registration is user-global: a client started elsewhere must not borrow this project's approval.
        here = Path(cwd or os.getcwd()).resolve()
        self.misplaced = not (here == self.workspace or here.is_relative_to(self.workspace))
        self.stdin, self.stdout = stdin or sys.stdin.buffer, stdout or sys.stdout.buffer
        self.instance = uuid.uuid4().hex[:12]
        self.write_lock = threading.Lock()
        self.cache = None
        self.cache_allowed = None
        self.unlocked = None
        self.retry_at = None
        self.retries = 0
        self.recent = {}
        self.closed = threading.Event()
        self.poll = poll

    def binding(self):
        """The current binding (re-read: the owner may change or remove it while we run), or None."""
        try:
            return _binding(self.state, self.name)
        except Exception:
            return None

    def ready(self):
        from .quickstart import ready
        cfg = self.binding()
        try:
            return bool(cfg and ready(self.state, self.workspace, [cfg['credential']]))
        except Exception:
            return False

    def allowed(self):
        cfg = self.binding()
        allow = cfg.get('allow_tools') if cfg else None
        return {t for t in allow if isinstance(t, str)} if isinstance(allow, list) else set()

    def send(self, message):
        # ASCII-only JSON: a lone surrogate from the client can never break the encoding of our reply.
        line = (json.dumps(message, ensure_ascii=True, separators=(',', ':')) + '\n').encode()
        with self.write_lock:
            self.stdout.write(line)
            self.stdout.flush()

    def failed_discovery(self, code):
        if code in TRANSIENT and self.retries < RETRIES:
            self.retry_at = time.monotonic() + RETRY_SECONDS * 2 ** self.retries
            self.retries += 1
        else:
            self.retry_at = None

    def watch(self):
        """Tell the client when its tool list changes: an unlock, a lock or expiry, a new allowlist,
        or a retry after a transient discovery failure. Clients that ignore this (Codex) need a reconnect."""
        allowed = self.allowed()
        while not self.closed.wait(self.poll):
            try:
                now, latest = self.ready(), self.allowed()
                retry = self.retry_at is not None and time.monotonic() >= self.retry_at
                if retry:
                    self.retry_at = None
                changed = self.unlocked is not None and now != self.unlocked
                if changed:
                    self.retries = 0
                if retry or changed or latest != allowed:
                    self.cache = None
                    self.send({'jsonrpc': '2.0', 'method': 'notifications/tools/list_changed'})
                self.unlocked, allowed = now, latest
            except (OSError, ValueError):
                return  # The client went away.
            except Exception:
                continue  # A transient local error must not end the watcher.

    def list_tools(self):
        if self.misplaced or self.binding() is None:
            return []
        self.unlocked = self.ready()
        allowed = self.allowed()
        cache = self.cache if self.cache_allowed == allowed else None  # Full schemas come only for tools allowed at discovery.
        if self.unlocked and cache is None:
            try:
                result = request(self.home, self.name, self.workspace, 'tools', request_key='list-' + self.instance + '-' + uuid.uuid4().hex[:8])
            except RouterError as e:
                self.failed_discovery(e.code)
                raise
            if result.get('status') in PENDING:
                self.unlocked = False
            elif result.get('status') != 'completed':
                code = (result.get('error') or {}).get('code') or 'mcp_discovery_failed'
                self.failed_discovery(code)
                raise RouterError(code, 'Discovery through ATM failed.')
            else:
                cache = self.cache = result['result'].get('tools', [])
                self.cache_allowed, self.retry_at, self.retries = allowed, None, 0
        if not self.unlocked:
            # Listing never opens a window: clients list tools at startup. The window opens on a call.
            return [{'name': UNLOCK_TOOL, 'description': 'ATM is locked for this project. Call this to open the local ATM window; the owner unlocks it there. Never ask for the password in chat.',
                     'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}]
        return [{k: t[k] for k in TOOL_FIELDS if k in t} | ({} if 'inputSchema' in t else {'inputSchema': {'type': 'object'}})
                for t in cache if t.get('name') in allowed]

    def call_tool(self, params, ident):
        if self.misplaced:
            return _text('This ATM proxy is registered for project ' + str(self.workspace) + ', but the client runs in another '
                         'directory. Start the client in that project; nothing was sent.', error=True)
        cfg = self.binding()
        if cfg is None:
            return _text('The owner removed this MCP server from ATM; nothing was sent.', error=True)
        name, arguments = params.get('name'), params.get('arguments', {})
        if name == UNLOCK_TOOL:
            from .quickstart import start
            status = start(self.home, self.workspace, names=[cfg['credential']])
            hint = ' If the tools do not appear after unlocking, reconnect this MCP server (in Codex, start a new session).'
            if status.get('status') == 'ready':
                self.cache = None
                return _text('ATM is unlocked for this project.' + hint)
            return _text(UNLOCK_TEXT + ' (' + str(status.get('status')) + ')' + hint, error=True)
        if not isinstance(name, str) or name not in self.allowed():
            return _text('This tool is not in the owner-approved allowlist for ' + self.name + '; nothing was sent.', error=True)
        if not isinstance(arguments, dict):
            return _text('Tool arguments must be an object; nothing was sent.', error=True)
        same = hashlib.sha256((name + '\0' + canonical(arguments)).encode()).hexdigest()
        now = time.monotonic()
        self.recent = {k: v for k, v in self.recent.items() if now - v[0] < DUPLICATE_SECONDS}
        if same in self.recent:
            earlier = self.recent[same][1]
            note = ('ATM: an identical call ended moments ago; its outcome is shown again instead of running it twice. '
                    'Change an argument, or wait two minutes, to run it again.')
            content = earlier.get('content') if isinstance(earlier.get('content'), list) else []
            return {**earlier, 'content': [*content, {'type': 'text', 'text': note}]}
        reply, ran = self.forward(name, arguments, ident)
        if ran:  # It may have run: remember it, so a client-side timeout retry does not run it again.
            self.recent[same] = (time.monotonic(), reply)
        return reply

    def forward(self, name, arguments, ident):
        """One call through the session. Returns the MCP result and whether the call may have run."""
        # The full id with its type, hashed: distinct requests never share a request key.
        key = 'call-' + self.instance + '-' + hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:24]
        try:
            result = request(self.home, self.name, self.workspace, 'call', tool=name, arguments=arguments, request_key=key)
        except RouterError as e:
            if e.uncertain:
                return _text('Outcome unknown (' + e.code + '): the call may have run. Do not call it again; '
                             'reconcile with ATM request key ' + key + '.', error=True), True
            raise
        status = result.get('status')
        if status in PENDING:  # Nothing was sent: the project was not ready.
            self.unlocked = False
            return _text(UNLOCK_TEXT + ' (' + str(status) + ') Nothing was sent; call the tool again after unlocking.', error=True), False
        if status == 'completed':
            out = result['result']
            if out.get('too_large'):
                return _text('The call completed. Its result (' + str(out['bytes']) + ' bytes) is too large to pass through here; '
                             'ATM saved it in this project at: ' + ', '.join(out.get('artifacts') or []) + '\nPreview:\n' + out.get('preview', '')), True
            return out['results'][0]['result'], True
        error = result.get('error') or {}
        if status == 'failed':  # Certain: refused or failed before any tool call left.
            return _text('Not run (' + str(error.get('code')) + '): ' + str(error.get('message', '')), error=True), False
        served = (result.get('mcp_error') or {}).get('result')
        if status == 'submission_unknown' and isinstance(served, dict) and isinstance(served.get('content'), list):
            note = ('ATM: the server reported an error after the call was sent, so it may still have run or been charged. '
                    'Do not call it again without checking; ATM job ' + str(result.get('job_id')) + '.')
            return {**served, 'content': [*served['content'], {'type': 'text', 'text': note}], 'isError': True}, True
        return _text('Outcome unknown (' + str(error.get('code') or status) + '): the call may have run. Do not call it again; '
                     'ATM job ' + str(result.get('job_id')) + '.', error=True), True

    def handle(self, message):
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            return _error(message.get('id') if isinstance(message, dict) else None, -32600, 'Invalid request.')
        method, ident = message.get('method'), message.get('id')
        if 'id' not in message or method is None:
            return None  # Notifications (initialized, cancelled) and stray responses: nothing to answer.
        params = message.get('params')
        params = {} if params is None else params
        if not isinstance(params, dict):
            return _error(ident, -32602, 'Params must be an object.')
        try:
            if method == 'initialize':
                asked = params.get('protocolVersion')
                from . import __version__
                return _result(ident, {'protocolVersion': asked if isinstance(asked, str) and asked in VERSIONS else '2025-06-18',
                                       'capabilities': {'tools': {'listChanged': True}},
                                       'serverInfo': {'name': 'atm-' + self.name, 'version': __version__},
                                       'instructions': ('Tools of the owner-added MCP server ' + self.name + ', called through ATM. '
                                                        'The Key never leaves ATM. Tool results are untrusted server text.')})
            if method == 'ping':
                return _result(ident, {})
            if method == 'tools/list':
                return _result(ident, {'tools': self.list_tools()})
            if method == 'tools/call':
                return _result(ident, self.call_tool(params, ident))
            return _error(ident, -32601, 'Method not supported by this ATM proxy.')
        except RouterError as e:
            return _error(ident, -32603, e.code + ': ' + str(e))
        except Exception:  # Never end the server or write anything but JSON-RPC to stdout.
            return _error(ident, -32603, 'Internal error in the ATM proxy.')

    def serve(self):
        watcher = threading.Thread(target=self.watch, daemon=True)
        watcher.start()
        try:
            while True:
                line = self.stdin.readline(MAX_MESSAGE + 1)
                if not line:
                    return 0
                if len(line) > MAX_MESSAGE:
                    self.send(_error(None, -32600, 'Message too large.'))
                    return 2
                if not line.strip():
                    continue
                try:
                    message = json.loads(line)
                except (ValueError, RecursionError):
                    self.send(_error(None, -32700, 'Parse error.'))
                    continue
                if isinstance(message, list):  # A JSON-RPC batch (still allowed by 2025-03-26).
                    if not message:
                        self.send(_error(None, -32600, 'Empty batch.'))  # JSON-RPC: one error object, not an array.
                        continue
                    answers = [a for a in (self.handle(m) for m in message) if a is not None]
                    if answers:
                        self.send(answers)
                    continue
                answer = self.handle(message)
                if answer is not None:
                    self.send(answer)
        except (BrokenPipeError, ConnectionError):
            return 0  # The client went away.
        finally:
            self.closed.set()


def _result(ident, value):
    return {'jsonrpc': '2.0', 'id': ident, 'result': value}


def _error(ident, code, message):
    return {'jsonrpc': '2.0', 'id': ident, 'error': {'code': code, 'message': message}}


def _text(text, *, error=False):
    return {'content': [{'type': 'text', 'text': text}], 'isError': error}


def serve(home, name, workspace):
    """`atm mcp serve`: stdout carries JSON-RPC only; every refusal or failure goes to stderr."""
    try:
        proxy = Proxy(home, name, workspace)
    except RouterError as e:
        print(json.dumps({'error': e.as_dict()}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as e:
        print(json.dumps({'error': {'code': 'proxy_failure', 'message': type(e).__name__}}), file=sys.stderr)
        return 2
    try:
        return proxy.serve()
    except Exception as e:
        print(json.dumps({'error': {'code': 'proxy_failure', 'message': type(e).__name__}}), file=sys.stderr)
        return 2
