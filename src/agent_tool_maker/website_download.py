"""Single existing XYQ image download, then secure import and complete decoding.

Browser-owned auth; fixed reviewed bridge; no prompt, key, profile or URL export.
Local resume may finish an observed original download, never start another click.
"""
from contextlib import contextmanager,ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile

from .errors import RouterError
from . import media

MAX_IMAGE_BYTES=64*1024*1024
MAX_JSON=32000
SETTINGS=('thread_id','result_id','expected_result_sha256','quote_sha256','request_key','human_confirmed')
UUID=r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}'
KEY=r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}'
SHA=r'[a-f0-9]{64}'
SAFE_ENV={'PATH','HOME','USER','LOGNAME','LANG','LC_ALL','LC_CTYPE','TMPDIR','TEMP','TMP','DISPLAY','XDG_RUNTIME_DIR'}

def fail(code,message):raise RouterError(code,message,uncertain=code in {'delivery_unknown','download_unknown','receipt_write_failed'})
def _sha(value):return hashlib.sha256(value).hexdigest()
def _json(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def source_digest():
    h=hashlib.sha256()
    for name in ('website_download.py','media.py','errors.py'):
        p=Path(__file__).with_name(name)
        if p.is_symlink() or not p.is_file():fail('definition_changed','Review regular download-pipeline source files.')
        h.update((name+'\0').encode());h.update(p.read_bytes());h.update(b'\0')
    return h.hexdigest()

def settings(raw):
    try:v=json.loads(raw) if isinstance(raw,str) else raw
    except (ValueError,TypeError):fail('invalid_argument','Use exact existing-image download settings.')
    if (not isinstance(v,dict) or set(v)!=set(SETTINGS) or
        not isinstance(v['thread_id'],str) or not re.fullmatch(UUID,v['thread_id']) or
        not isinstance(v['result_id'],str) or not re.fullmatch(r'[a-f0-9]{32}',v['result_id']) or
        any(not isinstance(v[k],str) or not re.fullmatch(SHA,v[k]) for k in ('expected_result_sha256','quote_sha256')) or
        not isinstance(v['request_key'],str) or not re.fullmatch(KEY,v['request_key'])):
        fail('invalid_argument','Bind one image download to its exact thread, resource, digests and original key.')
    if v['human_confirmed'] is not True:fail('confirmation_required','Confirm one download of this existing image.')
    return {k:v[k] for k in SETTINGS}

def _canonical(path):
    return isinstance(path,str) and path.startswith('/') and path!='/' and os.path.normpath(path)==path and not any(ord(c)<32 for c in path)

def _check_directory(path):
    with ExitStack() as stack:
        try:
            fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);stack.callback(os.close,fd)
            for part in Path(path).parts[1:]:
                fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);stack.callback(os.close,fd)
        except OSError:fail('unsafe_path','Reviewed download directory must exist with no linked ancestors.')

@contextmanager
def _ledger(workspace,create=True):
    if not _canonical(workspace):fail('unsafe_path','Use an exact regular project directory.')
    with ExitStack() as stack:
        try:
            flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_DIRECTORY
            fd=os.open('/',flags);stack.callback(os.close,fd)
            for part in Path(workspace).parts[1:]:
                fd=os.open(part,flags,dir_fd=fd);stack.callback(os.close,fd)
            for part in ('.atm','xyq-result-downloads'):
                if create:
                    try:os.mkdir(part,0o700,dir_fd=fd)
                    except FileExistsError:pass
                fd=os.open(part,flags,dir_fd=fd);stack.callback(os.close,fd)
            lock=os.open('finalize.lock',(os.O_RDWR|os.O_CREAT if create else os.O_RDONLY)|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=fd);stack.callback(os.close,lock)
            s=os.fstat(lock)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:fail('unsafe_path','Finalization lock must be a regular single-link file.')
            try:fcntl.flock(lock,(fcntl.LOCK_EX if create else fcntl.LOCK_SH)|fcntl.LOCK_NB)
            except BlockingIOError:fail('workspace_busy','Another download finalizer is active; inspect its original request.')
        except FileNotFoundError:fail('request_missing','No original download ledger exists.')
        except OSError:fail('unsafe_path','Download directories and lock must not be linked or inaccessible.')
        yield fd

def _read(fd,name):
    try:file=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
    except FileNotFoundError:return None
    except OSError:fail('receipt_invalid','Selected download receipt is inaccessible or linked.')
    try:
        s=os.fstat(file)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or not 2<=s.st_size<=MAX_JSON:fail('receipt_invalid','Expected one bounded regular download receipt.')
        data=os.read(file,MAX_JSON+1)
        def pairs(values):
            d={}
            for k,v in values:
                if k in d:raise ValueError('duplicate field')
                d[k]=v
            return d
        try:r=json.loads(data,object_pairs_hook=pairs)
        except (ValueError,UnicodeError):fail('receipt_invalid','Download receipt is malformed.')
        if not isinstance(r,dict):fail('receipt_invalid','Expected a download receipt object.')
        return r
    finally:os.close(file)

def _write(fd,name,value,exclusive=False):
    try:
        file=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK|(os.O_EXCL if exclusive else 0),0o600,dir_fd=fd)
        try:
            s=os.fstat(file)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:fail('unsafe_path','Receipt writes require a regular single-link file.')
            if not exclusive:os.ftruncate(file,0)
            data=_json(value)
            if len(data)>MAX_JSON:fail('receipt_invalid','Download receipt exceeds its bound.')
            with os.fdopen(os.dup(file),'wb') as out:out.write(data);out.flush()
            os.fsync(file)
        finally:os.close(file)
        os.fsync(fd)
    except OSError:fail('receipt_write_failed','Download receipt write failed; keep original intent and locks.')

def _bridge(path,expected):
    if not _canonical(path) or not isinstance(expected,str) or not re.fullmatch(SHA,expected):fail('invalid_argument','Use a reviewed absolute bridge executable and hash.')
    p=Path(path)
    try:
        if p.is_symlink() or not p.is_file() or not os.access(p,os.X_OK):fail('bridge_missing','The reviewed bridge executable is missing or linked.')
        for parent in p.parents:
            if parent.is_symlink():fail('unsafe_path','Bridge executable parents must not be linked.')
        if _sha(p.read_bytes())!=expected:fail('executable_changed','Review the changed bridge before any download.')
    except OSError:fail('bridge_missing','The reviewed bridge executable is inaccessible.')

def _run_bridge(path,expected,adapter_pin,args,workspace):
    _bridge(path,expected)
    argv=[path,'__opencli_shim','xyq-web','result-download-bound','--pin',adapter_pin,'-f','json','--workspace',workspace,'--settings',_json(args).decode()]
    env={k:v for k,v in os.environ.items() if k in SAFE_ENV}
    env.update({'NO_COLOR':'1','CI':'1','PIPPIT_CLI_DISABLE_TELEMETRY':'1'})
    with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        try:proc=subprocess.Popen(argv,cwd=workspace,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
        except OSError:fail('bridge_start_failed','Reviewed bridge did not start; inspect the original intent.')
        try:proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait();fail('download_unknown','Bridge observation timed out; no automatic second download.')
        _bridge(path,expected)
        if proc.returncode:fail('download_unknown','Bridge did not confirm this download; inspect its original native receipt.')
        out.seek(0);data=out.read(128*1024+1)
        if len(data)>128*1024:fail('bridge_protocol','Download bridge response exceeded its bound.')
        try:v=json.loads(data)
        except (ValueError,UnicodeError):fail('bridge_protocol','Download bridge response was not JSON.')
        if not isinstance(v,list) or len(v)!=1 or not isinstance(v[0],dict) or not isinstance(v[0].get('result'),dict) or v[0]['result'].get('status')!='download_observed':
            fail('bridge_protocol','Download bridge did not return an observed original download.')
    # The durable source receipt, not stdout, is authoritative for file identity.

def _native(fd,key,args):
    r=_read(fd,key+'.json')
    if r is None:return None
    expected=_sha(_json(['xyq-existing-image-download-v1',args]))
    if (r.get('version')!=1 or r.get('request_key')!=args['request_key'] or r.get('fingerprint')!=expected or
        r.get('thread_id')!=args['thread_id'] or r.get('result_id')!=args['result_id'] or
        r.get('result_sha256')!=args['expected_result_sha256'] or r.get('quote_sha256')!=args['quote_sha256'] or
        r.get('status') not in {'download_dispatch_claimed','download_unknown','download_observed','delivered'}):
        fail('receipt_invalid','Original native receipt differs from this exact download.')
    if r['status'] not in {'download_observed','delivered'}:return None
    v=r.get('download')
    if (not isinstance(v,dict) or set(v)!={'filename','state','source_result_id','source_association_verified','download_freshness_verified'} or
        v['state']!='complete' or v['source_result_id']!=args['result_id'] or v['source_association_verified'] is not True or
        v['download_freshness_verified'] is not False or not _canonical(v['filename']) or
        not isinstance(r.get('filename'),str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,159}\.png',r['filename']) or
        Path(v['filename']).name!=r['filename'] or
        any(type(r.get(k)) is not int or not 1<=r[k]<=16384 for k in ('width','height')) or r['width']*r['height']>media.MAX_PIXELS):
        fail('receipt_invalid','Observed native download lacks exact file/source identity.')
    return r

def _import(fd,workspace,root,key,native):
    source=native['download']['filename']
    if not _canonical(root) or str(Path(source).parent)!=root:fail('download_path_invalid','Observed file is outside the reviewed download directory.')
    name=Path(source).name;target=key+'.png'
    if _read_exists(fd,target):fail('artifact_present_unverified','Existing unverified output is preserved; inspect this original request.')
    with media._open_project_file(root,name) as (input_fd,_,_):
        before=media._snapshot(input_fd)
        if before[2]>MAX_IMAGE_BYTES:fail('download_size_limit','Downloaded image exceeds the declared byte limit.')
        digest=media._hash(input_fd);os.lseek(input_fd,0,os.SEEK_SET)
        output=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
        try:
            copied=0
            with os.fdopen(os.dup(output),'wb') as out:
                while block:=os.read(input_fd,1024*1024):
                    copied+=len(block)
                    if copied>MAX_IMAGE_BYTES:fail('download_size_limit','Downloaded image grew beyond its byte limit.')
                    out.write(block)
                out.flush()
            os.fsync(output)
        finally:os.close(output)
        if copied!=before[2] or media._snapshot(input_fd)!=before or media._hash(input_fd)!=digest:fail('download_changed','Source download changed during import.')
        with media._open_project_file(root,name) as (check,_,_):
            if media._snapshot(check)!=before:fail('download_changed','Source download path changed during import.')
    os.fsync(fd)
    artifact=media.inspect_media(workspace,'.atm/xyq-result-downloads/'+target,'image',digest)
    return artifact

def _read_exists(fd,name):
    try:os.stat(name,dir_fd=fd,follow_symlinks=False);return True
    except FileNotFoundError:return False

def _external_unknowns(fd):
    value=_read(fd,'external-unknown.json')
    if value is None:return []
    if value.get('version')!=1 or set(value)!={'version','records'} or not isinstance(value['records'],list) or len(value['records'])>100:
        fail('receipt_invalid','External original-download markers have an unknown contract.')
    for r in value['records']:
        if (not isinstance(r,dict) or set(r)!={'thread_id','result_id','request_key','status'} or r['status']!='download_unknown' or
            not isinstance(r['thread_id'],str) or not re.fullmatch(UUID,r['thread_id']) or
            not isinstance(r['result_id'],str) or not re.fullmatch(r'[a-f0-9]{32}',r['result_id']) or
            not isinstance(r['request_key'],str) or not re.fullmatch(KEY,r['request_key'])):
            fail('receipt_invalid','External original-download marker is malformed.')
    return value['records']

def record_unknown(workspace,thread_id,result_id,request_key):
    # Import a known pre-existing manual/bridge uncertainty, without pretending it
    # had this adapter's original quote or native receipt. Never clears a marker.
    if (not isinstance(thread_id,str) or not re.fullmatch(UUID,thread_id) or not isinstance(result_id,str) or
        not re.fullmatch(r'[a-f0-9]{32}',result_id) or not isinstance(request_key,str) or not re.fullmatch(KEY,request_key)):
        fail('invalid_argument','Use exact metadata from the original unknown download.')
    r={'thread_id':thread_id,'result_id':result_id,'request_key':request_key,'status':'download_unknown'}
    with _ledger(workspace) as fd:
        records=_external_unknowns(fd)
        if r in records:return {**r,'recorded':True,'reused':True,'browser_input':False}
        if len(records)>=100:fail('receipt_limit','Existing uncertainty markers are preserved at their bound.')
        if any(v['request_key']==request_key for v in records):fail('request_conflict','Original imported key names a different resource.')
        records.append(r);_write(fd,'external-unknown.json',{'version':1,'records':records})
    return {**r,'recorded':True,'reused':False,'browser_input':False}

def _release(fd,name,key,fingerprint):
    lock=_read(fd,name)
    completed=_sha(key.encode())+'.'+name+'.completed'
    if lock is None:
        old=_read(fd,completed)
        if old and old.get('request_key')==key and old.get('fingerprint')==fingerprint:return
        fail('receipt_invalid','Original active/completed lock changed; it is preserved.')
    if lock.get('request_key')!=key or lock.get('fingerprint')!=fingerprint:fail('receipt_invalid','Original active lock changed; it is preserved.')
    if _read_exists(fd,completed):fail('receipt_invalid','Completed lock already exists; active lock is preserved.')
    os.rename(name,completed,src_dir_fd=fd,dst_dir_fd=fd);os.fsync(fd)

def _public(r,artifact=None,reused=False):
    return {'status':('delivered' if r['status']=='delivered' else 'file_verified') if artifact else 'download_unknown','request_key':r['settings']['request_key'],
        'thread_id':r['settings']['thread_id'],'result_id':r['settings']['result_id'],'result_id_kind':'visible_media_resource',
        'artifact':artifact,'source_association_verified':bool(artifact),'download_verified':bool(artifact),'complete_decode_verified':bool(artifact),
        'download_freshness_verified':False,'provider_task_id':None,'provider_generation_verified':False,'task_association_verified':False,
        'generation_submitted':False,'upload_started':False,'paid_submitted':False,'credentials_read':False,'secrets_returned':False,
        'submission_repeated':False,'reused':reused,'provider_checked':False,'locks_finalized':r['status']=='delivered','failure_code':r.get('failure_code'),'failure_phase':r.get('failure_phase'),
        'previous_failure':r.get('previous_failure')}

def download(workspace,raw,bridge,bridge_sha256,adapter_pin,download_root):
    args=settings(raw)
    if not isinstance(adapter_pin,str) or not re.fullmatch(SHA,adapter_pin) or not _canonical(download_root):fail('invalid_argument','Use reviewed adapter pin and canonical download directory.')
    _bridge(bridge,bridge_sha256)
    _check_directory(download_root)
    key=_sha(args['request_key'].encode());fp=_sha(_json(['xyq-image-delivery-v1',args,bridge,bridge_sha256,adapter_pin,download_root]))
    with _ledger(workspace) as fd:
        name=key+'.delivery.json';r=_read(fd,name);resume=bool(r)
        if r:
            if r.get('version')!=1 or r.get('fingerprint')!=fp or r.get('settings')!=args or r.get('status') not in {'dispatch_claimed','delivery_unknown','file_verified','delivered'}:fail('request_conflict','Retained delivery uses a different original contract.')
            if r['status']=='delivered':
                a=r.get('artifact')
                if not isinstance(a,dict) or a.get('file')!='.atm/xyq-result-downloads/'+key+'.png':fail('receipt_invalid','Retained artifact has a different path contract.')
                if _native(fd,key,args) is None:fail('receipt_invalid','Original native source association is missing.')
                verified=media.inspect_media(workspace,a['file'],'image',a.get('sha256'))
                return _public(r,verified,True)
            if _native(fd,key,args) is None:fail('download_unknown','Original download has no verified source event; do not start another click.')
        else:
            if any(v['thread_id']==args['thread_id'] and v['result_id']==args['result_id'] for v in _external_unknowns(fd)):
                fail('download_unknown','This selected resource has a pre-existing unknown native download; no new key starts a second click.')
            if _read_exists(fd,'delivery-active.lock') or _read_exists(fd,'active.lock'):fail('workspace_busy','An original result download is unresolved in this project.')
            if _read_exists(fd,key+'.png'):fail('artifact_present_unverified','Existing unverified output is preserved before browser dispatch.')
            r={'version':1,'status':'dispatch_claimed','settings':args,'fingerprint':fp,'download_root':download_root}
            _write(fd,'delivery-active.lock',{'version':1,'request_key':args['request_key'],'fingerprint':fp},True)
            _write(fd,name,r,True)
        phase='bridge_dispatch'
        try:
            if not resume:_run_bridge(bridge,bridge_sha256,adapter_pin,args,workspace)
            phase='native_source_receipt'
            native=_native(fd,key,args)
            if native is None:fail('download_unknown','No authoritative native source receipt was observed.')
            phase='file_import_and_decode'
            if r['status']=='file_verified':
                a=r.get('artifact')
                if not isinstance(a,dict) or a.get('file')!='.atm/xyq-result-downloads/'+key+'.png':fail('receipt_invalid','Retained verified file has a different path.')
                artifact=media.inspect_media(workspace,a['file'],'image',a.get('sha256'))
            else:artifact=_import(fd,workspace,download_root,key,native)
            r.update(status='file_verified',artifact=artifact);_write(fd,name,r)
            phase='lock_finalization'
            _release(fd,'active.lock',args['request_key'],native['fingerprint'])
            _release(fd,'delivery-active.lock',args['request_key'],fp)
            if 'failure_code' in r:
                r['previous_failure']={'code':r.pop('failure_code'),'phase':r.pop('failure_phase')}
            r['status']='delivered';_write(fd,name,r)
            return _public(r,artifact,resume)
        except (RouterError,OSError) as error:
            # Preserve any bytes, all native intent and both active locks on uncertainty.
            r['status']='file_verified' if r['status'] in {'file_verified','delivered'} else 'delivery_unknown'
            r['failure_code']=error.code if isinstance(error,RouterError) else 'file_io_failed';r['failure_phase']=phase;_write(fd,name,r)
            fail('delivery_unknown','Original download/file delivery is unverified; preserve receipts, bytes and locks.')

def status(workspace,request_key):
    if not isinstance(request_key,str) or not re.fullmatch(KEY,request_key):fail('invalid_argument','Use the original download key.')
    key=_sha(request_key.encode())
    with _ledger(workspace,create=False) as fd:
        r=_read(fd,key+'.delivery.json')
        if not r:
            old=next((v for v in _external_unknowns(fd) if v['request_key']==request_key),None)
            if old:return {**old,'query_scope':'external_original_native_download_marker','external_unknown':True,'provider_checked':False,
                'download_verified':False,'complete_decode_verified':False,'submission_repeated':False,'browser_input':False}
        if not r or r.get('version')!=1 or not isinstance(r.get('settings'),dict):fail('request_missing','No original download-pipeline receipt exists.')
        args=settings(r['settings'])
        if args['request_key']!=request_key or r.get('status') not in {'dispatch_claimed','delivery_unknown','file_verified','delivered'}:fail('receipt_invalid','Retained delivery state has a different contract.')
        if r['status'] in {'file_verified','delivered'}:
            a=r.get('artifact')
            if not isinstance(a,dict) or a.get('file')!='.atm/xyq-result-downloads/'+key+'.png':fail('receipt_invalid','Retained artifact path differs.')
            if _native(fd,key,args) is None:fail('receipt_invalid','Original native source receipt is missing.')
            return _public(r,media.inspect_media(workspace,a['file'],'image',a.get('sha256')),True)
        native=_native(fd,key,args)
        result=_public(r);result['native_source_observed']=native is not None;result['local_finalization_available']=native is not None and not _read_exists(fd,key+'.png')
        result['query_scope']='original_local_receipts_and_selected_artifact';return result

def add_commands(sub):
    p=sub.add_parser('delivery',help='Existing website output delivery; no generation or authentication export')
    commands=p.add_subparsers(dest='operation',required=True)
    d=commands.add_parser('xyq-image',help='One confirmed existing image download and complete local decoding')
    d.add_argument('--workspace',required=True);d.add_argument('--settings',required=True)
    for name in ('bridge','bridge-sha256','adapter-pin','download-root','pin'):d.add_argument('--'+name,required=True)
    s=commands.add_parser('status',help='Read the original delivery receipt and verify its selected completed local artifact')
    s.add_argument('--workspace',required=True);s.add_argument('--request-key',required=True);s.add_argument('--pin',required=True)
    u=commands.add_parser('record-unknown',help='Record exact metadata of a pre-existing unknown native download; never permits another click')
    for name in ('workspace','thread-id','result-id','request-key','pin'):u.add_argument('--'+name,required=True)

def dispatch(args):
    if args.pin!=source_digest():fail('definition_changed','Review changed website download pipeline source.')
    if args.operation=='status':return [{'result':status(args.workspace,args.request_key)}]
    if args.operation=='record-unknown':return [{'result':record_unknown(args.workspace,args.thread_id,args.result_id,args.request_key)}]
    return [{'result':download(args.workspace,args.settings,args.bridge,args.bridge_sha256,args.adapter_pin,args.download_root)}]
