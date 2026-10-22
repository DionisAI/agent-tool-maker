"""Reviewed declarative HTTP and argv adapters. No shell/eval or plugin code loader."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from .artifacts import confined_file, managed_dir, save_artifact
from .cli_adapter import execute_cli
from .errors import RouterError
from .network import checked_url, fake_ip_tunnel, public_address
from .storage import canonical, atomic_write

PERMISSIONS = {"external_write", "production", "execute_code"}

def get_path(obj, path):
    value = obj
    for part in path.split('.'):
        try:
            value = value[int(part)] if isinstance(value, list) else value[part]
        except (KeyError, IndexError, ValueError, TypeError):
            raise RouterError("missing_reference", "A declared input or workflow reference is missing.") from None
    return value

def render(value, inputs):
    """Whole-value substitution retains types; no string eval or Jinja."""
    if isinstance(value, str) and value.startswith('$'):
        return get_path(inputs, value[1:])
    if isinstance(value, dict):
        return {k: render(v, inputs) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, inputs) for v in value]
    return value

def check_permissions(tool, *, allow_paid=False, grants=()):
    required = set(tool.get('permissions', []))
    missing = required - set(grants)
    if missing:
        raise RouterError('permission_required', 'Explicit authorization required: ' + ', '.join(sorted(missing)))
    if tool.get('paid') and not allow_paid:
        raise RouterError('paid_confirmation_required', 'This operation may consume credits or billable resources. Review it and authorize with --allow-paid; this is not a dollar cap.')

def directory(workspace, value):
    p = Path(value)
    if not p.is_absolute(): p = workspace / p
    if p.is_symlink(): raise RouterError('unsafe_path', 'Symlink directories are not accepted.')
    p = p.resolve()
    if not p.is_relative_to(workspace.resolve()) or not p.is_dir():
        raise RouterError('unsafe_path', 'Project directory must be inside the workspace.')
    return p

def resolve_origin(state, tool):
    req = tool['request']
    origin = req.get('origin') or state.setting('origin:' + tool['provider'])
    if not origin:
        raise RouterError('missing_origin', 'Set the provider origin in a human terminal with atm origin set.')
    p = urlsplit(origin)
    if p.query or p.fragment or p.username or p.password or p.path not in ('', '/'):
        raise RouterError('unsafe_origin', 'Provider origin must contain only scheme, host and optional approved local port.')
    if req.get('local'):
        if p.hostname not in {'127.0.0.1', 'localhost', '::1'} or p.scheme != 'http':
            raise RouterError('unsafe_origin', 'This local service only permits explicitly configured loopback HTTP origins.')
    else:
        checked_url(origin)
    if req.get('host_suffix') and not p.hostname.endswith(req['host_suffix']):
        raise RouterError('unsafe_origin', 'Provider origin has the wrong approved hostname suffix.')
    return origin.rstrip('/')

def set_origin(state, provider, origin):
    from .catalog import Catalog
    tools = [t for t in Catalog(state).tools.values() if t['provider'] == provider and t.get('request', {}).get('origin_setting')]
    if not tools: raise RouterError('unknown_provider', 'This provider does not support a configurable origin.')
    # Validate without altering state on failure.
    class Preview:
        def setting(self, key): return origin
    for tool in tools: resolve_origin(Preview(), tool)
    state.set_setting('origin:' + provider, origin.rstrip('/'))
    return {'provider': provider, 'origin': origin, 'authentication': 'not_verified'}

def compile_request(state, tool, inputs):
    spec = tool['request']; origin = resolve_origin(state, tool)
    def part(match):
        v = get_path(inputs, match.group(1))
        if not isinstance(v, (str, int)) or str(v) in {'.', '..'} or any(c in str(v) for c in '/\\\x00\r\n'):
            raise RouterError('unsafe_path_parameter', 'Path parameters must be single non-traversing segments.')
        return quote(str(v), safe='')
    path = re.sub(r'\{([A-Za-z0-9_.]+)\}', part, spec['path'])
    if not path.startswith('/') or path.startswith('//') or '..' in path.split('/'):
        raise RouterError('unsafe_endpoint', 'Invalid API path.')
    query = {}
    for key,value in spec.get('query',{}).items():
        try:query[key]=render(value,inputs)
        except RouterError as error:
            if key not in spec.get('optional_query',[]) or error.code!='missing_reference':raise
    query = {k: ('true' if v else 'false') if isinstance(v,bool) else v for k,v in query.items()}
    url = origin + path + (('?' + urlencode(query, doseq=True)) if query else '')
    body = render(spec['body'], inputs) if 'body' in spec else None
    return {'method': spec.get('method', 'GET'), 'url': url, 'body': body, 'auth': spec.get('auth', 'bearer'),
            'credential': tool.get('credential'), 'headers': spec.get('headers', {}), 'local': spec.get('local', False)}

def compile_command(state, tool, inputs, workspace, outdir):
    spec = tool['command']; workspace = Path(workspace).resolve(); args=[]
    if tool['provider']=='imagemagick':
        p=confined_file(workspace,inputs['path'])
        if p.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.gif'}:raise RouterError('unsupported_artifact','ImageMagick actions accept raster input only, not document/script formats.')
    for item in spec['argv']:
        if isinstance(item, str): args.append(item); continue
        if not isinstance(item, dict) or len(item) != 1: raise RouterError('bad_manifest', 'Invalid argv token.')
        kind, value = next(iter(item.items()))
        if kind == 'input':
            v = get_path(inputs, value)
            if not isinstance(v, (str, int, float)) or isinstance(v, bool): raise RouterError('invalid_argument', 'CLI argument must be a scalar.')
            v = str(v)
            if v.startswith('-') or '\x00' in v or '\r' in v or '\n' in v:
                raise RouterError('unsafe_argument', 'Positional/flag values cannot start with a dash or contain control lines.')
            args.append(v)
        elif kind == 'json': args.append(canonical(get_path(inputs, value)))
        elif kind == 'file': args.append(str(confined_file(workspace, get_path(inputs, value))))
        elif kind == 'dir': args.append(str(directory(workspace, get_path(inputs, value))))
        elif kind == 'output':
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', value) or value in {'.', '..'}:
                raise RouterError('unsafe_path', 'Output name must be a simple filename.')
            dest=outdir/value
            if dest.is_symlink(): raise RouterError('unsafe_path', 'Output target cannot be a symlink.')
            args.append(str(dest))
        elif kind == 'workspace': args.append(str(workspace))
        elif kind == 'script':
            from importlib.resources import files
            args.append(str(files('agent_tool_maker.data').joinpath(value)))
        else: raise RouterError('bad_manifest', 'Unknown argv token type.')
    cwd = directory(workspace, inputs[spec['cwd_input']]) if spec.get('cwd_input') else workspace
    return {'executable': tool['executable'], 'argv': args, 'cwd': str(cwd), 'output': spec.get('output', 'text'),
            'timeout': spec.get('timeout', 120)}

def output_record(workspace, path):
    """Hash opaque engineering files; only claim media validation where actually performed."""
    p=confined_file(Path(workspace),path); size=p.stat().st_size
    if not size: raise RouterError('invalid_artifact','Expected output file is empty.')
    if size>1024*1024*1024:raise RouterError('artifact_limit','Individual engineering output exceeds 1 GiB.')
    sha=hashlib.sha256()
    with p.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):sha.update(chunk)
    return {'path': str(p), 'sha256': sha.hexdigest(), 'bytes':size, 'extension':p.suffix,
            'validation':{'level':'file_exists_and_hash','semantic_quality_checked':False}}

def preflight(router, tool, inputs, workspace):
    """Validates inputs/paths without credentials, subprocesses, network, or output directories."""
    workspace=Path(workspace).resolve()
    if tool['adapter']=='web_recipe':
        from .web_recipe import recipe_plan
        return recipe_plan(tool,inputs)
    if tool['adapter']=='rest': return compile_request(router.state,tool,inputs)
    if tool['adapter']=='command': return compile_command(router.state,tool,inputs,workspace,workspace/'.atm'/'dry-run')
    return {'adapter':tool['adapter'], 'execution_started':False}

def _headers(router, tool, req, job):
    headers=dict(req['headers']); key = router.vault.get(req['credential']) if req['credential'] else None
    auth=req['auth']
    if key:
        if auth=='bearer': headers['Authorization']='Bearer '+key
        elif auth=='basic': headers['Authorization']='Basic '+base64.b64encode(key.encode()).decode()
        elif auth.startswith('header:'): headers[auth.split(':',1)[1]]=key
        elif auth=='ghost':
            try:
                kid, secret=key.split(':',1)
                enc=lambda x:base64.urlsafe_b64encode(canonical(x).encode()).rstrip(b'=')
                now=int(time.time()); token=enc({'alg':'HS256','typ':'JWT','kid':kid})+b'.'+enc({'iat':now,'exp':now+300,'aud':'/admin/'})
                token+=b'.'+base64.urlsafe_b64encode(hmac.new(bytes.fromhex(secret),token,hashlib.sha256).digest()).rstrip(b'=')
                headers['Authorization']='Ghost '+token.decode()
            except ValueError: raise RouterError('bad_credential','Ghost requires id:hexsecret.') from None
        elif auth=='telegram': pass  # Token belongs in path; never included in plans or logs.
        elif auth!='none': raise RouterError('bad_manifest','Unsupported authentication mode.')
    if tool['request'].get('idempotency_header'):
        headers[tool['request']['idempotency_header']]=job['id']
    return headers,key

def _semantic_error(value):
    if not isinstance(value,dict): return False
    if value.get('ok') is False or value.get('success') is False or value.get('status') == 'error' or value.get('errors') or value.get('error'):
        return True
    if isinstance(value.get('status_code'),int) and value['status_code']>=40000: return True
    def walk(v):
        if isinstance(v,dict):
            if v.get('userErrors') or (isinstance(v.get('status_code'), int) and v['status_code'] >= 40000): return True
            return any(walk(x) for x in v.values())
        if isinstance(v,list): return any(walk(x) for x in v)
        return False
    return walk(value.get('data',{})) or walk(value.get('tasks', []))

def execute_rest(router, tool, job):
    req=compile_request(router.state,tool,job['data']['inputs'])
    url=req['url']
    # Dynamic remote origins are a human configuration boundary, not arbitrary agent URLs.
    if (tool['request'].get('origin_setting') or tool.get('user_defined')) and not req['local']:
        public_address(url, router.net.resolver, fake_ip=fake_ip_tunnel(router.state))
    headers,key=_headers(router,tool,req,job)
    if req['auth']=='telegram': url=url.replace('/bot__TOKEN__/','/bot'+quote(key,safe=':')+'/')
    if tool['request'].get('test_key_only') and not key.startswith(('sk_test_','rk_test_')):
        raise RouterError('test_key_required','This action only accepts Stripe test-mode keys. Live charging is not implemented.')
    response=router.net.request(req['method'],url,host=urlsplit(url).hostname,headers=headers,body=req['body'],
                                allow_local=req['local'], form=tool['request'].get('form',False))
    try: result=response.json()
    except ValueError: raise RouterError('upstream_schema','Expected JSON response.',uncertain=req['method']!='GET') from None
    if _semantic_error(result):
        raise RouterError('upstream_rejected','Provider returned an application-level error; result body suppressed.',uncertain=req['method']!='GET')
    result=router.vault.redact(result)
    artifact=save_artifact(job['workspace'],job['id'],canonical(result).encode(),hint='result.json')
    return router.state.update_job(job['id'],'completed',result=result,artifacts=[artifact],
        verification='http_and_json_only', completion=tool.get('completion','Request returned successfully; business outcome is not automatically verified.'))

def execute_command(router,tool,job):
    root=Path(job['workspace']); out=managed_dir(root,job['id'])
    plan=compile_command(router.state,tool,job['data']['inputs'],root,out)
    env={}
    for name,credential in tool['command'].get('credential_env',{}).items():
        if credential in router.state.secret_names(): env[name]=router.vault.get(credential)
        elif tool['command'].get('credential_required'):raise RouterError('missing_credential','A required CLI credential slot is not configured; no process was started.')
    result=execute_cli(router.state,plan['executable'],plan['argv'],Path(plan['cwd']),timeout=plan['timeout'],
                       parse_json=plan['output']=='json',output_mode=plan['output'],extra_env=env)
    result=router.vault.redact(result)
    expected=tool['command'].get('outputs',[]); artifacts=[]
    for name in expected: artifacts.append(output_record(root,out/name))
    candidates=[p for p in out.rglob('*') if p.is_file()]
    if len(candidates)>256:raise RouterError('artifact_limit','More than 256 outputs; inspect the managed directory manually.')
    for p in candidates:
        if p.parent!=out or p.name not in expected:artifacts.append(output_record(root,p))
    record=save_artifact(root,job['id'],canonical(result).encode(),hint='command-result.json');artifacts.append(record)
    return router.state.update_job(job['id'],'completed',result=result,artifacts=artifacts,
        verification='cli_exit_and_declared_outputs',completion=tool.get('completion','CLI completed; verify remote state or production output separately.'))

def execute_handoff(router,tool,job):
    root=Path(job['workspace']); out=managed_dir(root,job['id'],'handoffs')
    kind=tool['adapter']; task=job['data']['inputs']
    receipt={'kind':kind,'tool':tool['id'],'task':task,'instructions':tool.get('instructions',[]),
             'output_directory':str(out),'source':tool.get('url'),'completion':'Return actual files and a source/attestation; preparing this task is NOT completion.',
             'approval':'No external purchase, hire, publication or desktop execution has occurred.'}
    path=out/'handoff.json';atomic_write(path,canonical(receipt).encode())
    return router.state.update_job(job['id'],'requires_'+kind,handoff=receipt,artifacts=[output_record(root,path)],verification='waiting_for_external_execution')
