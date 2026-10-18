"""Small MCP client subset: stdio and Streamable HTTP JSON/SSE.

Initialize -> discover -> validate -> call in one bounded session. Pinned owner-managed
Higgsfield OAuth is optional. No sampling, elicitation, legacy SSE or paid retry.
"""
from __future__ import annotations
import hashlib
import json
import os
import queue
import re
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator
import httpx
from .cli_adapter import SAFE_ENV
from .errors import RouterError
from .network import checked_url, public_address
from .storage import canonical

MAX_MESSAGE=2*1024*1024
VERSIONS={'2025-06-18','2025-03-26','2024-11-05'}

def check_schema_local(schema):
    def walk(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in {'$ref','$dynamicRef'} and (not isinstance(v,str) or not v.startswith('#')):
                    raise RouterError('external_schema_reference','Schema may not load remote or local-file references.')
                walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(schema)
    try:Draft202012Validator.check_schema(schema)
    except Exception: raise RouterError('invalid_schema','Invalid local JSON schema.') from None

def bind_server(state,name,config):
    if not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}',name):raise RouterError('bad_server','Invalid server name.')
    if not isinstance(config,dict) or set(config)-{'transport','command','args','url','credential','oauth','env_credentials','allow_tools','allow_local','timeout'}:
        raise RouterError('bad_server','Unknown MCP configuration fields. Secrets belong in the vault.')
    cfg=dict(config);mode=cfg.get('transport')
    if 'oauth' in cfg:
        from .oauth import NAME, RESOURCE
        if mode != 'http' or cfg.get('oauth') != NAME or cfg.get('url') != RESOURCE or cfg.get('credential') or cfg.get('env_credentials') or cfg.get('allow_local'):
            raise RouterError('oauth_resource','OAuth binding requires the exact Higgsfield HTTP resource and no other credentials.')
    if mode=='stdio':
        p=Path(cfg.get('command','')).expanduser().resolve()
        if not p.is_file() or not os.access(p,os.X_OK): raise RouterError('bad_executable','MCP command must be an installed absolute executable.')
        args=cfg.get('args',[])
        if not isinstance(args,list) or any(not isinstance(x,str) or '\x00' in x for x in args):raise RouterError('bad_server','MCP args must be a string array.')
        cfg.update(command=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        env=cfg.get('env_credentials',{})
        if not isinstance(env,dict) or any(not re.fullmatch(r'[A-Z][A-Z0-9_]+',k) or not isinstance(v,str) or k in {'PATH','HOME','NODE_OPTIONS','PYTHONPATH','LD_PRELOAD'} for k,v in env.items()):
            raise RouterError('unsafe_environment','Invalid credential environment mapping.')
    elif mode=='http':
        url=cfg.get('url','');parts=urlsplit(url)
        if cfg.get('allow_local'):
            if parts.scheme!='http' or parts.hostname not in {'127.0.0.1','localhost','::1'} or parts.username or parts.password or parts.fragment:
                raise RouterError('unsafe_origin','Local MCP endpoints must be explicit loopback HTTP URLs.')
        else:checked_url(url)
        if parts.query:raise RouterError('unsafe_origin','Do not place tokens in MCP endpoint query strings.')
    else:raise RouterError('bad_server','MCP transport must be stdio or http.')
    allow=cfg.get('allow_tools',[])
    if not isinstance(allow,list) or any(not isinstance(x,str) or not x for x in allow):raise RouterError('bad_server','allow_tools must be a list of exact discovered names.')
    if not isinstance(cfg.get('timeout',120),int) or not 1<=cfg.get('timeout',120)<=900:raise RouterError('bad_server','Invalid timeout.')
    cfg['allow_tools']=allow
    state.set_setting('mcp:'+name,cfg)
    return {'server':name,'transport':mode,'allowed_tools':allow,'credentials_returned':False,'authentication':'not_verified'}

class Stdio:
    def __init__(self,cfg,vault,workspace):
        path=Path(cfg['command'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=cfg['sha256']:
            raise RouterError('executable_changed','MCP executable changed; explicitly rebind after review.')
        env={k:v for k,v in os.environ.items() if k in SAFE_ENV};env['NO_COLOR']='1'
        for k,cred in cfg.get('env_credentials',{}).items():env[k]=vault.get(cred)
        self.err=tempfile.TemporaryFile();self.queue=queue.Queue(maxsize=128);self.stop=threading.Event()
        self.proc=subprocess.Popen([str(path),*cfg.get('args',[])],cwd=workspace,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   stderr=self.err,shell=False,start_new_session=os.name=='posix')
        self.timeout=cfg.get('timeout',120)
        def reader():
            try:
                while not self.stop.is_set():
                    line=self.proc.stdout.readline(MAX_MESSAGE+1)
                    if not line:break
                    if len(line)>MAX_MESSAGE: self.queue.put(RouterError('mcp_limit','MCP message too large.'));break
                    try:self.queue.put(json.loads(line),timeout=1)
                    except (ValueError,RecursionError,queue.Full):break
            finally:
                try:self.queue.put(None,timeout=1)
                except queue.Full:pass
        self.reader=threading.Thread(target=reader,daemon=True);self.reader.start()
    def send(self,msg):
        try:self.proc.stdin.write((canonical(msg)+'\n').encode());self.proc.stdin.flush()
        except (OSError,BrokenPipeError):raise RouterError('mcp_interrupted','MCP process disconnected.',uncertain=True) from None
    def exchange(self,msg,notify=False):
        self.send(msg)
        if notify:return None
        deadline=time.monotonic()+self.timeout
        while True:
            try:item=self.queue.get(timeout=max(.01,deadline-time.monotonic()))
            except queue.Empty:raise RouterError('mcp_timeout','MCP request timed out; do not repeat a tool call blindly.',uncertain=True) from None
            if isinstance(item,RouterError):raise item
            if item is None:raise RouterError('mcp_interrupted','MCP process ended before its response.',uncertain=True)
            if not isinstance(item,dict):raise RouterError('mcp_protocol','MCP message must be an object.')
            if item.get('method'):
                if 'id' in item:
                    self.send({'jsonrpc':'2.0','id':item['id'],'error':{'code':-32601,'message':'Client callbacks, sampling and elicitation are not supported.'}})
                continue
            if item.get('id')==msg['id']:return item
    def close(self):
        self.stop.set()
        if self.proc.poll() is None:
            if os.name=='posix':os.killpg(self.proc.pid,signal.SIGTERM)
            else:self.proc.terminate()
            try:self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                if os.name=='posix':os.killpg(self.proc.pid,signal.SIGKILL)
                else:self.proc.kill()
                self.proc.wait()
        for f in [self.proc.stdin,self.proc.stdout,self.err]:
            try:f.close()
            except OSError:pass
        self.reader.join(timeout=2)

class HTTP:
    def __init__(self,cfg,vault,network):
        self.cfg=cfg;self.net=network;self.session=None;self.version=None
        self.oauth = None
        if cfg.get('oauth'):
            from .oauth import OAuth
            self.oauth = OAuth(vault.state, vault, network)
        self.headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json'}
        if cfg.get('credential'):self.headers['Authorization']='Bearer '+vault.get(cfg['credential'])
    def exchange(self,msg,notify=False):
        url=self.cfg['url']
        if not self.cfg.get('allow_local'):public_address(url,self.net.resolver)
        headers=dict(self.headers)
        if self.oauth:
            headers['Authorization'] = 'Bearer ' + self.oauth.access_token(self.cfg['oauth'], url)
            self.headers['Authorization'] = headers['Authorization']  # Same pinned resource for session DELETE, without refresh/replay.
        if self.session:headers['Mcp-Session-Id']=self.session
        if self.version:headers['MCP-Protocol-Version']=self.version
        self.net.client.cookies.clear()
        try:
            with self.net.client.stream('POST',url,headers=headers,json=msg,timeout=self.cfg.get('timeout',120)) as r:
                if not 200<=r.status_code<300:raise RouterError('mcp_http',f'MCP returned HTTP {r.status_code}; no automatic retry.',uncertain=msg.get('method')=='tools/call')
                if r.headers.get('Mcp-Session-Id'):
                    sid=r.headers['Mcp-Session-Id']
                    if len(sid)>1024 or any(ord(c)<33 or ord(c)>126 for c in sid):raise RouterError('mcp_protocol','Invalid session ID.')
                    self.session=sid
                if notify:return None
                content=r.headers.get('content-type','').split(';')[0]
                if content=='text/event-stream':
                    lines=[];size=0
                    for line in r.iter_lines():
                        size+=len(line)
                        if size>MAX_MESSAGE:raise RouterError('mcp_limit','MCP SSE response exceeded limit.')
                        if line=='':
                            if lines:
                                item=json.loads('\n'.join(lines));lines=[]
                                if item.get('method') and 'id' in item:raise RouterError('mcp_callback_unsupported','Server requires an unsupported client callback.',uncertain=True)
                                if item.get('id')==msg['id']:return item
                        elif line.startswith('data:'):lines.append(line[5:].lstrip(' '))
                    raise RouterError('mcp_interrupted','SSE ended before the response.',uncertain=True)
                if content!='application/json':raise RouterError('mcp_protocol','Unsupported MCP content type.')
                chunks=[];size=0
                for c in r.iter_bytes():
                    size+=len(c)
                    if size>MAX_MESSAGE:raise RouterError('mcp_limit','MCP response exceeded limit.')
                    chunks.append(c)
                return json.loads(b''.join(chunks))
        except (httpx.HTTPError,OSError,ValueError,RecursionError):raise RouterError('mcp_interrupted','MCP response was interrupted or invalid.',uncertain=msg.get('method')=='tools/call') from None
    def close(self):
        # Stateless invocation; no reconnect or automatic replay. Explicit DELETE is best effort.
        if self.session:
            headers=dict(self.headers);headers['Mcp-Session-Id']=self.session
            if self.version:headers['MCP-Protocol-Version']=self.version
            try:
                with self.net.client.stream('DELETE',self.cfg['url'],headers=headers,timeout=5) as r:pass
            except (httpx.HTTPError,OSError):pass

def execute_mcp(router,tool,job):
    from .artifacts import save_artifact
    cfg=router.state.setting('mcp:'+tool['server'])
    if not cfg:raise RouterError('mcp_not_configured','Bind this MCP server in a human terminal first.')
    conn=None;counter=0;partial=[]
    try:
        conn=Stdio(cfg,router.vault,job['workspace']) if cfg['transport']=='stdio' else HTTP(cfg,router.vault,router.net)
        def call(method,params):
            nonlocal counter
            counter+=1;msg={'jsonrpc':'2.0','id':counter,'method':method,'params':params}
            answer=conn.exchange(msg)
            if not isinstance(answer,dict) or answer.get('id')!=counter or 'error' in answer or not isinstance(answer.get('result'),dict):
                raise RouterError('mcp_protocol','MCP response was rejected or malformed.',uncertain=method=='tools/call')
            return answer['result']
        init=call('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'agent-tool-maker','version':'0.2.0'}})
        version=init.get('protocolVersion')
        if version not in VERSIONS:raise RouterError('mcp_version','Server selected an unsupported protocol version.')
        if isinstance(conn,HTTP):conn.version=version
        conn.exchange({'jsonrpc':'2.0','method':'notifications/initialized'},notify=True)
        tools={};cursor=None
        for _ in range(20):
            page=call('tools/list',{'cursor':cursor} if cursor else {})
            for t in page.get('tools',[]):
                if not isinstance(t,dict) or not isinstance(t.get('name'),str) or t['name'] in tools:raise RouterError('mcp_protocol','Invalid or duplicate tool name.')
                check_schema_local(t.get('inputSchema',{}));tools[t['name']]=t
            cursor=page.get('nextCursor')
            if not cursor:break
        else:raise RouterError('mcp_limit','MCP registry pagination exceeded 20 pages.')
        if tool['mcp_operation']=='tools':result={'tools':list(tools.values()),'server_version':init.get('serverInfo'),'protocol_version':version}
        else:
            calls=job['data']['inputs']['calls']
            # Validate the ENTIRE batch and allowlist before the first side-effecting call.
            for item in calls:
                name=item['name']
                if name not in cfg['allow_tools']:raise RouterError('mcp_tool_not_approved','A tool is not in the human-approved server allowlist.')
                if name not in tools:raise RouterError('mcp_tool_missing','Selected tool is not in the live server registry.')
                if next(Draft202012Validator(tools[name]['inputSchema']).iter_errors(item['arguments']),None):raise RouterError('invalid_input','MCP tool arguments fail the discovered schema.')
            for item in calls:
                # Record started status BEFORE transmission. Unknown calls are never replayed.
                router.state.update_job(job['id'],'running',mcp_completed=partial,mcp_started=item['name'])
                result=call('tools/call',item)
                if result.get('isError'):raise RouterError('mcp_tool_error','Server tool reported failure; previous results are retained.',uncertain=True)
                partial.append({'name':item['name'],'result':router.vault.redact(result)})
            result={'results':partial,'protocol_version':version,'session_scope':'one ATM job; batch calls share the same session'}
        result=router.vault.redact(result)
        artifact=save_artifact(job['workspace'],job['id'],canonical(result).encode(),hint='mcp.json')
        return router.state.update_job(job['id'],'completed',result=result,artifacts=[artifact],verification='mcp_response_not_business_acceptance')
    finally:
        if conn:conn.close()
