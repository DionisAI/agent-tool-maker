"""CLI entry points for sync and owner-created broker grants."""
from pathlib import Path
from .errors import RouterError
from .storage import canonical


def add_commands(parser, sub):
    selected = parser.add_mutually_exclusive_group()
    selected.add_argument('--client', choices=['claude', 'codex'], help='Use this scoped broker profile; never fall back to direct vault access')
    selected.add_argument('--client-profile', type=Path, help='Explicit owner-only broker client file; do not read it into model context')
    sync = sub.add_parser('sync', help='Encrypted multi-device replication; credentials only, no private identity or local paths')
    ss = sync.add_subparsers(dest='operation', required=True)
    init = ss.add_parser('init'); init.add_argument('--name', required=True)
    ident = ss.add_parser('identity'); ident.add_argument('--out', type=Path)
    ss.add_parser('status'); ss.add_parser('conflicts')
    trust = ss.add_parser('trust'); trust.add_argument('card', type=Path); trust.add_argument('--fingerprint', required=True)
    trust.add_argument('--send', action='append', default=[]); trust.add_argument('--receive', action='append', default=[])
    trust.add_argument('--apply', action='store_true'); trust.add_argument('--replace', action='store_true')
    rev = ss.add_parser('revoke'); rev.add_argument('device'); rev.add_argument('--apply', action='store_true')
    exp = ss.add_parser('export'); exp.add_argument('--to', required=True); exp.add_argument('--out', type=Path, required=True)
    imp = ss.add_parser('import'); imp.add_argument('path', type=Path); imp.add_argument('--apply', action='store_true')
    ex = ss.add_parser('exchange'); ex.add_argument('--directory', required=True, type=Path); ex.add_argument('--apply', action='store_true')
    watcher=ss.add_parser('watch');watcher.add_argument('--directory',required=True,type=Path);watcher.add_argument('--interval',type=float,default=30);watcher.add_argument('--ttl-hours',type=float,default=8)
    rs = ss.add_parser('resolve'); rs.add_argument('provider'); rs.add_argument('--choose', required=True)
    rs.add_argument('--expected', required=True); rs.add_argument('--apply', action='store_true')
    access = sub.add_parser('access', help='Owner-managed scoped agent grants; not a substitute for OS isolation')
    aa = access.add_subparsers(dest='operation', required=True)
    aa.add_parser('list')
    from .secrets_cli import add_permit
    add_permit(aa)
    grant = aa.add_parser('grant'); grant.add_argument('--agent', required=True); grant.add_argument('--tool', action='append', required=True)
    grant.add_argument('--workspace', type=Path, required=True); grant.add_argument('--out', type=Path)
    grant.add_argument('--socket', type=Path); grant.add_argument('--ttl-hours', type=float, default=168)
    grant.add_argument('--apply', action='store_true')
    grant.add_argument('--client-uid',type=int); grant.add_argument('--socket-group')
    for flag in ('write', 'production', 'code', 'paid'):
        grant.add_argument('--allow-'+flag, action='store_true')
    revoke = aa.add_parser('revoke'); revoke.add_argument('id'); revoke.add_argument('--apply', action='store_true')
    broker = sub.add_parser('broker', help='Unlock once for a bounded foreground local execution session')
    bb = broker.add_subparsers(dest='operation', required=True)
    serve = bb.add_parser('serve'); serve.add_argument('--socket', type=Path); serve.add_argument('--ttl-hours', type=float, default=8)
    serve.add_argument('--socket-group')
    bb.add_parser('status')


def dispatch(args, router):
    if args.command == 'sync':
        from .sync import Sync, strict_json, read_sync_file, write_sync_file
        s = Sync(router.vault)
        if args.operation == 'init': return s.initialize(args.name)
        if args.operation == 'identity':
            card = s.identity()
            if args.out:
                write_sync_file(args.out, canonical(card).encode())
                return {'public_card_file': str(args.out), 'fingerprint': card['id'], 'contains_private_keys': False}
            return card
        if args.operation == 'status': return s.status()
        if args.operation == 'conflicts': return {'conflicts': [r for r in s.status()['records'] if r['state'] == 'conflict'], 'secrets_returned': False}
        if args.operation == 'trust': return s.trust(strict_json(read_sync_file(args.card)), args.fingerprint, send=args.send, receive=args.receive, apply=args.apply, replace=args.replace)
        if args.operation == 'revoke': return s.revoke(args.device, apply=args.apply)
        if args.operation == 'export':
            packet = s.export_packet(args.to)
            write_sync_file(args.out, canonical(packet).encode())
            return {'exported_to': args.to, 'file': str(args.out), 'encrypted': True, 'secrets_returned': False}
        if args.operation == 'import': return s.import_packet(strict_json(read_sync_file(args.path)), apply=args.apply)
        if args.operation == 'exchange': return s.exchange(args.directory, apply=args.apply)
        if args.operation == 'watch':
            from .sync import watch
            return watch(router.vault,args.directory,interval=args.interval,ttl_hours=args.ttl_hours)
        if args.operation == 'resolve': return s.resolve(args.provider, args.choose, args.expected, apply=args.apply)
    if args.command == 'access':
        from .broker import grant, list_grants, revoke
        if args.operation == 'list': return list_grants(router.state)
        if args.operation == 'revoke': return revoke(router.state, args.id, apply=args.apply)
        grants = [p for p,f in [('external_write',args.allow_write),('production',args.allow_production),('execute_code',args.allow_code)] if f]
        return grant(router, args.agent, tools=args.tool, workspace=args.workspace, output=args.out,
                     socket_file=args.socket, ttl_hours=args.ttl_hours, grants=grants, allow_paid=args.allow_paid, apply=args.apply, client_uid=args.client_uid, socket_group=args.socket_group)
    if args.command == 'broker' and args.operation == 'status':
        from .broker import socket_path
        path = socket_path(router.state)
        return {'last_report': router.state.setting('broker_status'), 'default_socket_exists': path.is_socket(),
                'note': 'Historical owner metadata, not authenticated liveness. Use --client NAME broker status for a live check.'}
    raise RouterError('unsupported_command', 'Unknown multi-device command.')


def client_dispatch(args):
    from .broker import call, client_path
    from .cli import load_input
    profile = args.client_profile or client_path(args.client)
    command = args.command
    if command in {"keys", "exec", "credentials", "session", "unlock", "lock"}:
        from .secrets_cli import client_dispatch as secrets_client
        return secrets_client(args, profile)
    if command in {'doctor', 'broker'}:
        if command == 'doctor' and args.check_unlock or command == 'broker' and args.operation != 'status':
            raise RouterError('operation_denied', 'Clients cannot unlock or manage the broker.')
        return call(profile, 'status', {})
    if command in {'list', 'search'}:
        return call(profile, 'search', {'query': args.query, 'capability': args.capability})
    if command == 'describe': return call(profile, 'describe', {'tool': args.tool})
    if command == 'run':
        if any((args.allow_paid, args.allow_code, args.allow_write, args.allow_production)):
            raise RouterError('grant_escalation_denied', 'Broker permissions come from the owner grant, not runtime allow flags.')
        return call(profile, 'run', {'tool': args.tool, 'inputs': load_input(args.input),
                                    'workspace': str(args.workspace.expanduser().absolute()), 'request_key': args.request_key, 'dry_run': args.dry_run, 'expect_definition': args.expect_definition})
    if command == 'jobs' and args.operation == 'get': return call(profile, 'job', {'id': args.id, 'refresh': args.refresh})
    raise RouterError('operation_denied', 'Scoped clients cannot manage credentials, peers, grants or unowned tasks. No direct fallback occurred.')
