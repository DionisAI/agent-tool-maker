"""Credential-first CLI. No raw-secret retrieval and no per-program tool manifest."""
import argparse
from pathlib import Path
import uuid
from .errors import RouterError


def add_commands(sub):
    unlock = sub.add_parser('unlock', help='Owner unlocks one fixed foreground session; default 30m')
    unlock.add_argument('--ttl', default='30m')
    sub.add_parser('lock', help='Stop admitting new secret operations; does not retract already delivered keys')
    sess = sub.add_parser('session'); ss = sess.add_subparsers(dest='operation', required=True); ss.add_parser('status')
    keys = sub.add_parser('keys', help='Secret-free credential metadata, independent of tool catalog')
    ks = keys.add_subparsers(dest='operation', required=True)
    ks.add_parser('list')
    find = ks.add_parser('find'); find.add_argument('query')
    alias = ks.add_parser('alias'); alias.add_argument('name'); alias.add_argument('--credential', action='append', required=True)
    alias.add_argument('--expected'); alias.add_argument('--apply', action='store_true')
    run = sub.add_parser('exec', help='Inject approved ATM references into an existing program; no tool manifest')
    run.add_argument('--env', action='append', required=True)
    run.add_argument('--workspace', type=Path, default=Path.cwd())
    run.add_argument('--request-key'); run.add_argument('--dry-run', action='store_true')
    run.add_argument('argv', nargs=argparse.REMAINDER)
    return run


def add_permit(access_sub):
    import argparse
    p = access_sub.add_parser('permit-exec', help='Owner reviews an exact command/key/project permit, not a tool plugin')
    p.add_argument('--agent', choices=['claude', 'codex', 'local'], required=True)
    p.add_argument('--env', action='append', required=True)
    p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path)
    p.add_argument('--ttl-hours', type=float, default=168); p.add_argument('--timeout', type=int, default=60)
    p.add_argument('--pin-file', action='append', default=[])
    p.add_argument('--apply', action='store_true'); p.add_argument('--approve')
    p.add_argument('argv', nargs=argparse.REMAINDER)


def command_args(args):
    argv = args.argv[1:] if args.argv and args.argv[0] == '--' else args.argv
    if not argv:
        raise RouterError('invalid_command', 'Put the exact program and arguments after --.')
    return argv


def dispatch(args, router):
    from . import secrets_provider as sp
    from . import session
    if args.command == 'session':
        return session.status(router.state.home)
    if args.command == 'lock':
        if not session.status(router.state.home)['unlocked']:
            return {'status': 'locked', 'unlocked': False, 'action': 'unchanged'}
        return session.owner_call(router.state.home, 'session.lock')
    if args.command == 'keys':
        if args.operation == 'alias':
            return sp.alias(router.state, args.name, args.credential, apply=args.apply, expected=args.expected)
        return {**sp.find_keys(router.state, getattr(args, 'query', '')), 'session': session.status(router.state.home)}
    if args.command == 'access':
        return sp.permit_exec(router, args.agent, mappings=args.env, argv=command_args(args), workspace=args.workspace,
                              output=args.out, ttl_hours=args.ttl_hours, pin_files=args.pin_file,
                              timeout=args.timeout, apply=args.apply, approve=args.approve)
    if args.command == 'exec':
        # No client selection means the separately approved local profile, NOT Owner authority.
        return execute_client(args, router.state.home / 'local-exec.client.json')
    raise RouterError('operation_denied', 'Unsupported credential operation.')


def execute_client(args, profile):
    from .broker import call
    from .secrets_provider import normalized_argv, parse_mapping
    key = args.request_key or uuid.uuid4().hex
    try:
        return call(profile, 'exec', {'argv': normalized_argv(command_args(args)), 'environment': parse_mapping(args.env),
                    'workspace': str(args.workspace.expanduser().absolute()), 'request_key': key, 'dry_run': args.dry_run}, timeout=320)
    except RouterError as e:
        # A lost response must include its stable request key, never instruct blind retry.
        if e.uncertain:
            raise RouterError(e.code, str(e) + ' Preserve request key ' + key + '; do not start a new task.', uncertain=True) from None
        raise


def client_dispatch(args, profile):
    from .broker import call
    if args.command in {'keys', 'credentials'}:
        if args.operation not in {'find', 'list'}:
            raise RouterError('operation_denied', 'A credential-use grant cannot change metadata or keys.')
        return call(profile, 'keys.find', {'query': getattr(args, 'query', '')})
    if args.command == 'exec':
        return execute_client(args, profile)
    if args.command == 'session' and args.operation == 'status':
        return call(profile, 'status', {})
    raise RouterError('operation_denied', 'Agent clients cannot unlock, lock or manage the Owner session.')
