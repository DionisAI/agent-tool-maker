"""CLI surface for arbitrary credentials, extension drafts and browser-backed tools."""
from pathlib import Path
from .errors import RouterError


def add_commands(sub, make):
    creds = sub.add_parser('credentials', help='Manage independent credential slots without needing an adapter')
    ops = creds.add_subparsers(dest='operation', required=True)
    ops.add_parser('list')
    declare = ops.add_parser('declare'); declare.add_argument('name'); declare.add_argument('--label'); declare.add_argument('--apply', action='store_true')
    new = make.add_parser('new'); new.add_argument('id'); new.add_argument('--kind', choices=['api','cli','web'], required=True)
    new.add_argument('--url'); new.add_argument('--executable'); new.add_argument('--out', type=Path, required=True)
    oa = make.add_parser('from-openapi'); oa.add_argument('path', type=Path); oa.add_argument('--operation-id', required=True)
    oa.add_argument('--id', required=True); oa.add_argument('--credential'); oa.add_argument('--out', type=Path, required=True)
    pack = make.add_parser('pack'); pack.add_argument('path'); pack.add_argument('--out', type=Path, required=True)
    check = make.add_parser('check-bundle'); check.add_argument('directory', type=Path)
    update = make.add_parser('update'); update.add_argument('path'); update.add_argument('--approve', required=True); update.add_argument('--expected', required=True)
    draft = make.add_parser('draft'); draft.add_argument('--agent', choices=['claude','codex'], required=True)
    draft.add_argument('--seed', type=Path, required=True); draft.add_argument('--brief', type=Path, required=True)
    draft.add_argument('--out', type=Path, required=True); draft.add_argument('--allow-agent', action='store_true'); draft.add_argument('--timeout', type=int, default=180)
    web = sub.add_parser('web', help='Encrypted, device-local official browser login; not cookie extraction')
    w = web.add_subparsers(dest='operation', required=True)
    w.add_parser('sessions')
    login = w.add_parser('login'); login.add_argument('tool'); login.add_argument('--replace', action='store_true'); login.add_argument('--expires-at')
    remove = w.add_parser('remove-session'); remove.add_argument('name'); remove.add_argument('--apply', action='store_true')


def dispatch(args, router):
    from . import extensions as ex
    from .maker import read_manifest
    if args.command == 'credentials':
        if args.operation == 'list':
            from .management import connections
            return connections(router)
        return ex.declare_credential(router,args.name,label=args.label,apply=args.apply)
    if args.command == 'web':
        from . import web_recipe as wr
        if args.operation == 'sessions': return wr.sessions(router.state)
        if args.operation == 'login':
            from .health import parse_expiry
            return wr.login(router,args.tool,replace=args.replace,expires_at=parse_expiry(args.expires_at))
        if not args.apply: return {'session':args.name,'action':'remove','applied':False,'provider_session_revoked':False}
        return wr.remove_session(router.state,args.name)
    if args.operation == 'new': return ex.write_draft(ex.new_template(args.id,args.kind,url=args.url,executable=args.executable),args.out,router.catalog)
    if args.operation == 'from-openapi':
        from .sync import strict_json
        if not args.path.is_file() or args.path.stat().st_size>2*1024*1024:
            raise RouterError('openapi_limit','Use a local OpenAPI JSON document under 2 MiB.')
        tool=ex.import_openapi(strict_json(args.path.read_bytes(),limit=2*1024*1024),args.operation_id,args.id,credential=args.credential)
        return ex.write_draft(tool,args.out,router.catalog)
    if args.operation == 'pack': return ex.pack(read_manifest(args.path),args.out,router.catalog)
    if args.operation == 'check-bundle': return ex.validate_bundle(args.directory)
    if args.operation == 'update': return ex.update_manifest(router.state,router.catalog,args.path,approval=args.approve,expected=args.expected)
    if args.operation == 'draft':
        from .factory import draft
        return draft(router,args.agent,args.seed,args.brief,args.out,allow_agent=args.allow_agent,timeout=args.timeout)
    raise RouterError('unknown_command','Unknown extension operation.')
