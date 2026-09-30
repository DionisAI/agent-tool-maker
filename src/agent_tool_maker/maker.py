"""Create, validate and explicitly install local declarative tools and workflows."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator
from .actions import PERMISSIONS, render
from .errors import RouterError
from .mcp_bridge import check_schema_local
from .network import checked_url
from .storage import canonical,atomic_write

MAX_MANIFEST=256*1024

def digest(tool):return hashlib.sha256(canonical(tool).encode()).hexdigest()

def read_manifest(path):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>MAX_MANIFEST:raise RouterError('bad_manifest','Manifest must be an existing JSON file under 256 KiB.')
    try:
        from .sync import strict_json
        return strict_json(p.read_bytes(),limit=MAX_MANIFEST)
    except (ValueError,UnicodeError,RouterError):raise RouterError('bad_manifest','Invalid manifest JSON.') from None

def _validate_manifest(tool,catalog=None):
    if not isinstance(tool,dict):raise RouterError('bad_manifest','Tool definition must be an object.')
    allowed={'id','provider','title','capabilities','schema','example','adapter','implementation','paid','permissions','sources','checked_on','verification','notes','command','executable','request','credential','url','instructions','extensions','steps','server','mcp_operation','completion','user_defined','recipe'}
    if set(tool)-allowed:raise RouterError('bad_manifest','Unknown manifest fields.')
    for field in ['id','provider','title','capabilities','schema','adapter']:
        if field not in tool:raise RouterError('bad_manifest','Missing manifest field: '+field)
    if not isinstance(tool['id'],str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{2,79}',tool['id']):raise RouterError('bad_tool_id','Invalid tool ID.')
    if not isinstance(tool['title'],str) or len(tool['title'])>200:raise RouterError('bad_manifest','Invalid title.')
    if not isinstance(tool['capabilities'],list) or not tool['capabilities'] or any(not isinstance(c,str) for c in tool['capabilities']):raise RouterError('bad_manifest','Capabilities must be strings.')
    if not isinstance(tool['provider'],str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{1,79}',tool['provider']):raise RouterError('bad_manifest','Invalid provider.')
    if not isinstance(tool['schema'],dict):raise RouterError('bad_manifest','An object input schema is required.')
    check_schema_local(tool['schema'])
    if tool['schema'].get('type')!='object':raise RouterError('bad_manifest','Top-level tool input must be an object.')
    if 'example' in tool and next(Draft202012Validator(tool['schema']).iter_errors(tool['example']),None):raise RouterError('bad_manifest','Example does not satisfy input schema.')
    if not isinstance(tool.get('paid',False),bool):raise RouterError('bad_manifest','paid must be boolean.')
    if not isinstance(tool.get('permissions',[]),list) or any(not isinstance(x,str) for x in tool.get('permissions',[])):raise RouterError('bad_manifest','Permissions must be a list of strings.')
    permissions=set(tool.get('permissions',[]))
    if permissions-PERMISSIONS:raise RouterError('bad_manifest','Unknown permission.')
    adapter=tool['adapter']
    if adapter=='command':
        permissions.add('execute_code') # Generated commands never self-certify as harmless.
        spec=tool.get('command',{})
        if not isinstance(spec,dict):raise RouterError('bad_manifest','Command must be an object.')
        if set(spec)-{'argv','output','outputs','timeout','cwd_input','credential_env','credential_required'}:raise RouterError('bad_manifest','Unknown command fields.')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}',tool.get('executable','')):raise RouterError('bad_manifest','Invalid executable alias.')
        if not isinstance(spec.get('argv'),list) or len(spec['argv'])>80:raise RouterError('bad_manifest','argv must be a bounded array.')
        for item in spec['argv']:
            if isinstance(item,str):
                if '\x00' in item or len(item)>4096:raise RouterError('bad_manifest','Invalid static argument.')
            elif isinstance(item,dict) and len(item)==1:
                kind,value=next(iter(item.items()))
                if kind not in {'input','json','file','dir','output','workspace'} or not isinstance(value,str):raise RouterError('bad_manifest','Unsupported argv token; custom tools cannot select bundled scripts.')
                if kind in {'input','json','file','dir'} and value.split('.')[0] not in tool['schema'].get('properties',{}):raise RouterError('bad_manifest','Argument references undefined input.')
                if kind=='output' and (not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',value) or value in {'.','..'}):raise RouterError('bad_manifest','Invalid output path.')
            else:raise RouterError('bad_manifest','Invalid argv token.')
        if spec.get('output','text') not in {'text','json'}:raise RouterError('bad_manifest','Unsupported CLI output format.')
        if not isinstance(spec.get('timeout',120),int) or not 1<=spec.get('timeout',120)<=900:raise RouterError('bad_manifest','Timeout out of bounds.')
        if type(spec.get('credential_required', False)) is not bool:raise RouterError('bad_manifest','credential_required must be boolean.')
        env=spec.get('credential_env',{})
        if not isinstance(env,dict) or any(k in {'PATH','HOME','NODE_OPTIONS','PYTHONPATH','LD_PRELOAD'} or not re.fullmatch(r'[A-Z][A-Z0-9_]+',k) or not re.fullmatch(r'[a-z][a-z0-9_.-]{1,79}',v) for k,v in env.items()):raise RouterError('bad_manifest','Invalid secret-reference mapping.')
        for name in spec.get('outputs',[]):
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',name) or name in {'.','..'}:raise RouterError('bad_manifest','Invalid expected output name.')
    elif adapter=='rest':
        spec=tool.get('request',{})
        if not isinstance(spec,dict):raise RouterError('bad_manifest','Request must be an object.')
        if set(spec)-{'origin','path','method','auth','body','query','headers','idempotency_header','form','optional_query'}:raise RouterError('bad_manifest','Custom API tools require a fixed approved HTTPS origin and supported fields.')
        checked_url(spec.get('origin',''))
        from urllib.parse import urlsplit
        p=urlsplit(spec['origin'])
        if p.path not in {'','/'} or p.query:raise RouterError('bad_manifest','API origin cannot contain a path or query.')
        method=spec.get('method','GET')
        if method not in {'GET','POST','PUT','PATCH','DELETE'}:raise RouterError('bad_manifest','Unsupported method.')
        if method!='GET':permissions.add('external_write')
        path=spec.get('path','')
        if not path.startswith('/') or path.startswith('//') or '?' in path or '#' in path or '..' in path.split('/'):raise RouterError('bad_manifest','Invalid endpoint path.')
        for param in re.findall(r'\{([^}]+)\}',path):
            if param.split('.')[0] not in tool['schema'].get('properties',{}):raise RouterError('bad_manifest','Path references undefined input.')
        auth=spec.get('auth','bearer')
        if auth not in {'bearer','none','basic'} and not re.fullmatch(r'header:[A-Za-z0-9-]+',auth):raise RouterError('bad_manifest','Unsupported custom authentication mode.')
        if auth.startswith('header:') and auth.split(':',1)[1].lower() in {'host','content-length','transfer-encoding','connection','cookie','proxy-authorization'}:raise RouterError('bad_manifest','Authentication may not override routing/protocol headers.')
        optional=spec.get('optional_query',[])
        if not isinstance(optional,list) or any(not isinstance(k,str) or k not in spec.get('query',{}) for k in optional):raise RouterError('bad_manifest','optional_query must reference declared query keys.')
        headers=spec.get('headers',{})
        if not isinstance(headers,dict):raise RouterError('bad_manifest','Headers must be an object.')
        for k,v in headers.items():
            if k.lower() not in {'accept','content-type','user-agent'} or not isinstance(v,str) or any(c in v for c in '\r\n\x00'):
                raise RouterError('bad_manifest','Custom static headers are restricted; authentication uses vault references.')
        if auth!='none' and not re.fullmatch(r'[a-z][a-z0-9_.-]{1,79}',tool.get('credential','')):raise RouterError('bad_manifest','A vault credential name is required.')
    elif adapter=='web_recipe':
        from .web_recipe import validate_recipe
        validate_recipe(tool.get('recipe'),tool['schema'])
        permissions.add('external_write')  # DOM operations may have side effects, even on GET pages.
        if tool.get('credential'):raise RouterError('bad_manifest','Browser sessions are not API credential slots.')
    elif adapter in {'browser','desktop','human'}:
        checked_url(tool.get('url',''))
    elif adapter=='workflow':
        steps=tool.get('steps')
        if not isinstance(steps,list) or not 1<=len(steps)<=20:raise RouterError('bad_workflow','Workflow needs 1–20 sequential steps.')
        names=set()
        for step in steps:
            if not isinstance(step,dict) or set(step)!={'name','tool','inputs'} or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',step['name']) or step['name'] in names:raise RouterError('bad_workflow','Invalid or duplicate workflow step.')
            if not isinstance(step['inputs'], dict):raise RouterError('bad_workflow','Step inputs must be an object.')
            refs=re.findall(r'\$steps\.([a-z0-9_]+)',canonical(step['inputs']))
            if any(name not in names for name in refs):raise RouterError('bad_workflow','Workflow references a future or nonexistent step.')
            if catalog:
                child=catalog.get(step['tool'])
                if child['adapter']=='workflow':raise RouterError('bad_workflow','Nested workflows are not supported in v0.2.')
                permissions.update(child.get('permissions',[]))
            names.add(step['name'])
    else:raise RouterError('bad_manifest','Only declarative API, CLI, workflow and handoff templates may be installed.')
    result=copy.deepcopy(tool);result['permissions']=sorted(permissions);result['paid']=tool.get('paid',False)
    if adapter=='workflow' and catalog:result['paid']=result['paid'] or any(catalog.get(s['tool']).get('paid',False) for s in result['steps'])
    result.update(user_defined=True,implementation='workflow' if adapter=='workflow' else 'handoff' if adapter in {'browser','desktop','human'} else 'native',verification='user_installed_not_live_verified')
    return result

def validate_manifest(tool,catalog=None):
    try:
        return _validate_manifest(tool,catalog)
    except RouterError:
        raise
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError):
        raise RouterError('bad_manifest','Malformed extension data; no code was loaded or executed.') from None


def scaffold(catalog,name,source,out):
    tool=copy.deepcopy(catalog.get(source))
    tool.pop('relevance',None);tool.pop('readiness',None)
    tool['id']=name;tool['title']='Custom '+tool['title'];tool['user_defined']=True
    # Bundled script actions cannot be cloned into unrestricted script loaders.
    tool=validate_manifest(tool,catalog)
    p=Path(out)
    if p.exists():raise RouterError('file_exists','Refusing to overwrite the tool definition.')
    atomic_write(p,(json.dumps(tool,ensure_ascii=False,indent=2)+'\n').encode())
    return {'path':str(p.resolve()),'sha256':digest(tool),'installed':False,'next':'Review, validate, then make install --approve <sha256>.'}

def install(state,catalog,path,approval):
    tool=validate_manifest(read_manifest(path),catalog);sha=digest(tool)
    if approval!=sha:raise RouterError('approval_mismatch','Approval must match the normalized manifest SHA-256 from make validate.')
    if tool['id'] in catalog.tools:raise RouterError('duplicate_tool','Tool ID already exists; remove the reviewed custom version explicitly first.')
    with state.db() as c:
        c.execute("BEGIN IMMEDIATE")
        old=c.execute("SELECT value FROM settings WHERE name='custom_tools'").fetchone();tools=json.loads(old[0]) if old else []
        if any(t['id']==tool['id'] for t in tools):raise RouterError('duplicate_tool','Custom tool already installed.')
        tools.append(tool);c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('custom_tools',canonical(tools)))
    return {'installed':tool['id'],'sha256':sha,'permissions':tool['permissions'],'paid':tool['paid'],'live_tested':False}

def remove(state,tool_id):
    with state.db() as c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT value FROM settings WHERE name='custom_tools'").fetchone();tools=json.loads(row[0]) if row else []
        if not any(t['id']==tool_id for t in tools):raise RouterError('not_custom_tool','Only installed custom tools can be removed.')
        tools=[t for t in tools if t['id']!=tool_id]
        c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('custom_tools',canonical(tools)))
    return {'removed':tool_id,'existing_jobs_preserved':True}

def execute_workflow(router,tool,job):
    """Resume deterministic child jobs. Stop on pending, failure, or ambiguous submission."""
    validate_manifest(tool,router.catalog)
    if job['data'].get('definition_sha256')!=digest(tool):raise RouterError('definition_changed','Workflow definition changed; existing run is not resumed against new code.')
    done={}; children=[]
    grant=job['data'].get('permissions_granted',[]);paid=job['data'].get('paid_granted',False)
    for step in tool['steps']:
        inputs=render(step['inputs'],{'input':job['data']['inputs'],'steps':done})
        result=router.run(step['tool'],inputs,job['workspace'],request_key=f"{job['id']}:{step['name']}",allow_paid=paid,grants=grant)
        if result['status'] in {'queued','running','awaiting_download','download_failed'}:result=router.refresh(result['id'])
        children.append({'name':step['name'],'job_id':result['id'],'status':result['status']})
        if result['status']!='completed':
            failed=result['status'] in {'failed','submission_unknown','delivery_failed'}
            return router.state.update_job(job['id'],'blocked' if failed else 'waiting',children=children,blocked_on=result['id'],verification='workflow_incomplete')
        done[step['name']]=result
    artifacts=[a for child in done.values() for a in child['data'].get('artifacts',[])]
    return router.state.update_job(job['id'],'completed',children=children,artifacts=artifacts,verification='all_declared_child_jobs_completed',completion='Each child acceptance level still applies; no implicit business acceptance or rollback.')
