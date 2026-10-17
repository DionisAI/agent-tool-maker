from __future__ import annotations
import argparse
import json
import os
import sys
from importlib.resources import files
from pathlib import Path
from . import __version__
from .catalog import add_browser_tool
from .cli_adapter import bind_cli
from .engine import Router
from .errors import RouterError
from .storage import atomic_write
from .vault import prompt_secret


def parser():
    p=argparse.ArgumentParser(prog="atm",description="ATM: unlock once locally; let your Agent use saved API Keys. JSON output by default.")
    p.add_argument("--version",action="version",version=__version__)
    p.add_argument("--home",type=Path,default=Path(os.environ.get("ATM_HOME","~/.local/share/agent-tool-maker")).expanduser())
    sub=p.add_subparsers(dest="command",required=True)
    from .quickstart import add_commands as quick_commands
    quick_commands(sub)
    sub.add_parser("init",help="Create local state without network calls")
    doc=sub.add_parser("doctor",help="Local preflight; no vendor calls or implicit secret prompts")
    doc.add_argument("--tool", action="append", default=[])
    doc.add_argument("--check-unlock", action="store_true")
    doc.add_argument("--strict", action="store_true")
    setup=sub.add_parser("setup", help="Preview reusable user-level configuration; --apply writes reviewed changes")
    agent_choice=setup.add_mutually_exclusive_group()
    agent_choice.add_argument("--agent", action="append", choices=["codex", "claude"], default=None)
    agent_choice.add_argument("--no-agents", action="store_true", help="Only configure selected CLIs; skip default Claude/Codex registration")
    setup.add_argument("--cli", action="append", default=[])
    setup.add_argument("--atm-executable")
    setup.add_argument("--apply", action="store_true")
    setup.add_argument("--replace-skills", action="store_true")
    verify=sub.add_parser("verify", help="Preview a fixed account probe; --allow-network performs it")
    verify.add_argument("provider")
    verify.add_argument("--allow-network", action="store_true")
    v=sub.add_parser("vault"); vs=v.add_subparsers(dest="operation",required=True)
    vi=vs.add_parser("init"); vi.add_argument("--backend",choices=["keyring","passphrase"],default="keyring")
    vs.add_parser("status")
    vr=vs.add_parser("remove"); vr.add_argument("provider")
    c=sub.add_parser("connect",help="Human credential setup; never paste keys into an agent transcript")
    c.add_argument("--replace", action="store_true", help="Explicitly replace an already saved credential")
    c.add_argument("--expires-at", help="Optional ISO-8601 credential expiry with timezone; no automatic refresh")
    c.add_argument("provider"); c.add_argument("--env",help="Explicit one-time import from this environment variable")
    cl=sub.add_parser("cli"); cls=cl.add_subparsers(dest="operation",required=True)
    cls.add_parser("list", help="Inspect registered/detected CLI entries without executing them")
    cb=cls.add_parser("bind"); cb.add_argument("name",); cb.add_argument("path")
    for name in ["list","search"]:
        s=sub.add_parser(name)
        s.add_argument("query",nargs="?",default="")
        s.add_argument("--capability")
    d=sub.add_parser("describe"); d.add_argument("tool")
    r=sub.add_parser("route"); r.add_argument("task"); r.add_argument("--capability")
    r.add_argument("--allow-browser",action="store_true"); r.add_argument("--prefer",choices=["auto","api","cli","browser","mcp","workflow","desktop","human"],default="auto")
    run=sub.add_parser("run"); run.add_argument("tool"); run.add_argument("--input",required=True,help="JSON file or - for stdin")
    run.add_argument("--workspace",type=Path,default=Path.cwd()); run.add_argument("--request-key")
    run.add_argument("--expect-definition", help="Fail if installed manifest differs from this digest")
    run.add_argument("--allow-paid",action="store_true"); run.add_argument("--dry-run",action="store_true")
    for name in ['write','production','code']:
        run.add_argument('--allow-'+name,action='store_true')
    j=sub.add_parser("jobs"); js=j.add_subparsers(dest="operation",required=True)
    js.add_parser("list")
    get=js.add_parser("get"); get.add_argument("id"); get.add_argument("--refresh",action="store_true")
    done=js.add_parser("complete"); done.add_argument("id"); done.add_argument("--file",action="append",required=True)
    done.add_argument("--source-url",required=True)
    block=js.add_parser("block"); block.add_argument("id"); block.add_argument("--reason",required=True,choices=["login_required","awaiting_confirmation","requires_browser","requires_desktop","requires_human"])
    skill=sub.add_parser("skill"); ss=skill.add_subparsers(dest="operation",required=True)
    exp=ss.add_parser("export"); exp.add_argument("--destination",type=Path,required=True); exp.add_argument("--replace-skills",action="store_true")
    custom=sub.add_parser("add-browser"); custom.add_argument("id"); custom.add_argument("--title",required=True)
    custom.add_argument("--url",required=True); custom.add_argument("--capability",required=True)
    demo=sub.add_parser("demo",help="Offline synthetic fixture demo; no provider credentials or billing")
    demo.add_argument("--out",type=Path,default=Path("demo-output"))
    origin=sub.add_parser('origin');o=origin.add_subparsers(dest='operation',required=True)
    osub=o.add_parser('set');osub.add_argument('provider');osub.add_argument('url');osub.add_argument('--approve-origin',action='store_true')
    m=sub.add_parser('mcp');ms=m.add_subparsers(dest='operation',required=True)
    b=ms.add_parser('bind');b.add_argument('server');b.add_argument('--config',required=True);b.add_argument('--approve-config',action='store_true')
    make=sub.add_parser('make');mk=make.add_subparsers(dest='operation',required=True)
    sc=mk.add_parser('scaffold');sc.add_argument('id');sc.add_argument('--from',dest='from_tool',required=True);sc.add_argument('--out',required=True)
    va=mk.add_parser('validate');va.add_argument('path')
    ins=mk.add_parser('install');ins.add_argument('path');ins.add_argument('--approve',required=True)
    rm=mk.add_parser('remove');rm.add_argument('id');rm.add_argument('--yes',action='store_true')
    sub.add_parser('roadmap');sub.add_parser('stats')
    agents=sub.add_parser('agents'); ag=agents.add_subparsers(dest='operation',required=True)
    ag.add_parser('list')
    reg=ag.add_parser('register'); reg.add_argument('--agent',action='append',choices=['claude','codex'])
    reg.add_argument('--apply',action='store_true'); reg.add_argument('--replace-skills',action='store_true'); reg.add_argument('--atm-executable')
    unreg=ag.add_parser('unregister'); unreg.add_argument('agent',choices=['claude','codex']); unreg.add_argument('--apply',action='store_true')
    tools=sub.add_parser('tools'); ts=tools.add_subparsers(dest='operation',required=True)
    tl=ts.add_parser('list'); tl.add_argument('query',nargs='?',default=''); tl.add_argument('--capability')
    for verb in ['enable','disable']:
        op=ts.add_parser(verb); op.add_argument('tool'); op.add_argument('--apply',action='store_true')
    connections=sub.add_parser('connections'); cs=connections.add_subparsers(dest='operation',required=True); cs.add_parser('list')
    ui=sub.add_parser('ui',help='Start the loopback-only local management console; Ctrl-C stops it')
    ui.add_argument('--port',type=int,default=0); ui.add_argument('--no-browser',action='store_true'); ui.add_argument('--atm-executable')
    from .multidevice_cli import add_commands
    add_commands(p, sub)
    setup.add_argument("--broker", action="store_true", help="Register scoped broker runtime for Claude/Codex; profiles are granted separately")
    from .extensions_cli import add_commands
    add_commands(sub,mk)
    from .secrets_cli import add_commands as secrets_commands
    secrets_commands(sub)
    from .oauth_cli import add_commands as oauth_commands
    oauth_commands(sub)
    from .studio_cli import add_commands as studio_commands
    studio_commands(sub)
    from .media import add_commands as media_commands
    media_commands(sub)
    from .website_download import add_commands as delivery_commands
    delivery_commands(sub)
    return p


def load_input(value):
    try:
        if value!="-" and Path(value).stat().st_size>1_000_000:raise ValueError()
        raw=sys.stdin.read(1_000_001) if value=="-" else Path(value).read_text()
        if len(raw)>1_000_000: raise ValueError()
        data=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError()))
        if not isinstance(data,dict): raise ValueError()
        return data
    except (OSError,ValueError,UnicodeDecodeError):
        raise RouterError("invalid_input_file","Input must be a readable JSON object, at most 1 MB.") from None


def dispatch(args,router):
    cmd=args.command
    if cmd == "studio":
        from .studio_cli import dispatch as studio_dispatch
        return studio_dispatch(args, router)
    if cmd == "oauth":
        from .oauth_cli import dispatch as oauth_dispatch
        return oauth_dispatch(args, router)
    if cmd in {"keys", "exec", "lock", "session"} or cmd == "access" and args.operation == "permit-exec":
        from .secrets_cli import dispatch as secrets_dispatch
        return secrets_dispatch(args, router)
    if cmd in {"credentials","web"} or cmd=="make" and args.operation in {"new","from-openapi","pack","check-bundle","update","draft"}:
        from .extensions_cli import dispatch as extension_dispatch
        return extension_dispatch(args,router)
    if cmd in {"sync", "access", "broker"}:
        from .multidevice_cli import dispatch as multidispatch
        return multidispatch(args,router)
    if cmd=="init":
        return {"home":str(router.state.home),"tools":len(router.catalog.tools),"network_calls":0,"version":__version__}
    if cmd=="doctor":
        from .health import doctor
        result=doctor(router,tool_ids=args.tool,check_unlock=args.check_unlock)
        if args.strict and result["local_blockers"]:
            result["status"]="blocked"
        return result
    if cmd=="setup":
        from .onboarding import setup
        from .management import DEFAULT_AGENTS
        selected=() if args.no_agents else DEFAULT_AGENTS if args.agent is None else args.agent
        return setup(router,agents=selected,cli_names=args.cli,executable=args.atm_executable,
                     apply=args.apply,replace_skills=args.replace_skills,broker=args.broker)
    if cmd=="verify":
        from .verification import verify
        return verify(router,args.provider,allow_network=args.allow_network)
    if cmd=="vault":
        if args.operation=="init": return router.vault.init(args.backend)
        if args.operation=="status": return {"backend":router.state.setting("vault",{}).get("backend"),"credential_names":router.state.secret_names(),"secrets_returned":False}
        from .session import exists, owner_call
        if exists(router.state.home):
            return owner_call(router.state.home, "session.remove", {"provider": args.provider, "confirm": args.provider})
        return router.vault.delete(args.provider)
    if cmd=="connect":
        from .management import known_credentials, connect_value
        providers = known_credentials(router)
        if args.provider not in providers:
            raise RouterError("unknown_provider","Unknown credential slot. Declare it with atm credentials declare NAME --apply, then connect; browser sessions are separate.")
        if args.provider in router.state.secret_names() and not args.replace:
            return {"provider": args.provider, "status": "already_configured", "secrets_read": False, "next_action": "Existing credential preserved. Use --replace only to rotate this connection."}
        from .session import exists as session_exists, status as session_status
        if session_exists(router.state.home) and not session_status(router.state.home)["unlocked"]:
            raise RouterError("session_locked", "Unlock the existing session before entering a new value. Stored Keys do not need to be re-entered.")
        from .health import parse_expiry
        expiry = parse_expiry(args.expires_at)
        if args.env:
            value=os.environ.get(args.env,"")
            if not value: raise RouterError("missing_environment","Named environment variable is empty or unset.")
        elif args.provider=="higgsfield":
            value=prompt_secret("Higgsfield API key ID: ")+":"+prompt_secret("Higgsfield API key secret: ")
        else: value=prompt_secret(f"{args.provider} API key: ")
        from .session import exists, shared_put
        if exists(router.state.home):
            saved = shared_put(router.state.home, args.provider, value, replace=args.replace, expires_at=args.expires_at)
        else:
            saved = connect_value(router,args.provider,value,replace=args.replace,expires_at=args.expires_at)
        return {**saved,"one_time_env_import":bool(args.env)}
    if cmd=="cli":
        if args.operation=="list":
            from .management import cli_inventory
            return cli_inventory(router)
        return bind_cli(router.state,args.name,args.path)
    if cmd=="agents":
        from . import management as mg
        if args.operation=="list": return mg.agents(router)
        if args.operation=="unregister": return mg.unregister(router,args.agent,apply=args.apply)
        from .onboarding import setup
        return setup(router,agents=mg.DEFAULT_AGENTS if args.agent is None else args.agent,
                     apply=args.apply,replace_skills=args.replace_skills,executable=args.atm_executable)
    if cmd=="tools":
        from . import management as mg
        if args.operation=="list": return mg.tools(router,query=args.query,capability=args.capability)
        return mg.set_enabled(router,args.tool,args.operation=="enable",apply=args.apply)
    if cmd=="connections":
        from .management import connections
        return connections(router)
    if cmd in ["list","search"]:
        return {"tools":[{k:t[k] for k in ["id","title","capabilities","implementation","readiness"]} for t in router.search(args.query,args.capability)]}
    if cmd=="describe":
        t=router.catalog.get(args.tool)
        return {**t,"readiness":router.readiness(t)}
    if cmd=="route": return router.route(args.task,capability=args.capability,allow_browser=args.allow_browser,prefer=args.prefer)
    if cmd=='stats':
        from collections import Counter
        tools=list(router.catalog.tools.values())
        return {'version':__version__,'actions':len(tools),'providers':len({t['provider'] for t in tools}),
                'adapters':dict(Counter(t['adapter'] for t in tools)),
                'implementation':dict(Counter(t['implementation'] for t in tools)),
                'note':'Action count is not a claim that all vendors were live-tested.'}
    if cmd=='roadmap':
        return json.loads(files('agent_tool_maker.data').joinpath('roadmap.json').read_text())
    if cmd=='origin':
        from .actions import set_origin
        if not args.approve_origin:raise RouterError('approval_required','Review the destination then use --approve-origin.')
        return set_origin(router.state,args.provider,args.url)
    if cmd=='mcp':
        from .mcp_bridge import bind_server
        if not args.approve_config:raise RouterError('approval_required','Review server command, credentials and tool allowlist, then --approve-config.')
        return bind_server(router.state,args.server,load_input(args.config))
    if cmd=='make':
        from .maker import scaffold,validate_manifest,read_manifest,digest,install,remove
        if args.operation=='scaffold':return scaffold(router.catalog,args.id,args.from_tool,args.out)
        if args.operation=='validate':
            tool=validate_manifest(read_manifest(args.path),router.catalog)
            return {'valid':True,'id':tool['id'],'sha256':digest(tool),'permissions':tool['permissions'],'paid':tool['paid'],'execution_started':False}
        if args.operation=='install':return install(router.state,router.catalog,args.path,args.approve)
        if not args.yes:raise RouterError('approval_required','Confirm removal with --yes.')
        return remove(router.state,args.id)
    if cmd=="run":
        inputs=load_input(args.input)
        if args.expect_definition is not None:
            from .maker import digest
            if digest(router.catalog.get(args.tool))!=args.expect_definition:raise RouterError("definition_changed","Generated CLI expects another definition.")
        if args.dry_run:
            tool=router.catalog.validate(args.tool,inputs)
            from .actions import preflight
            plan=preflight(router,tool,inputs,args.workspace)
            return {"plan":plan,"permissions_required":tool.get('permissions',[]),"dry_run":True,"tool":tool["id"],"schema_valid":True,"readiness":router.readiness(tool),
                    "paid":tool["paid"],"cost_usd":None,"credentials_read":False,"network_calls":0}
        return router.public_job(router.run(args.tool,inputs,args.workspace,request_key=args.request_key,allow_paid=args.allow_paid,expect_definition=args.expect_definition,grants=[p for p,flag in [('external_write',args.allow_write),('production',args.allow_production),('execute_code',args.allow_code)] if flag]))
    if cmd=="jobs":
        if args.operation=="list": return {"jobs":[router.public_job(j) for j in router.state.jobs()]}
        if args.operation=="get": return router.public_job(router.refresh(args.id) if args.refresh else router.state.job(args.id))
        if args.operation=="complete": return router.public_job(router.complete_browser(args.id,args.file,args.source_url))
        return router.public_job(router.block_browser(args.id,args.reason))
    if cmd=="skill":
        from .onboarding import export_skill
        return export_skill(args.destination,replace=args.replace_skills)
    if cmd=="add-browser": return add_browser_tool(router.state,args.id,args.title,args.url,args.capability)
    raise RouterError("unknown_command","Unknown command.")


def main(argv=None):
    args=parser().parse_args(argv)
    router=None
    try:
        if args.command in {"start", "use", "_desktop"}:
            if args.client or args.client_profile:
                raise RouterError("operation_denied", "Use the project-session entry without a strict client profile; no profile was changed.")
            from .quickstart import dispatch as quick_dispatch
            value = quick_dispatch(args)
        elif args.client or args.client_profile:
            from .multidevice_cli import client_dispatch
            value=client_dispatch(args)
        elif args.command=="unlock":
            from .session import serve
            return serve(args.home, ttl=args.ttl)
        elif args.command=="broker" and args.operation=="serve":
            from .broker import serve
            return serve(args.home,socket_file=args.socket,ttl_hours=args.ttl_hours,socket_group=args.socket_group)
        elif args.command=="ui":
            from .webapp import serve
            return serve(args.home,port=args.port,open_browser=not args.no_browser,executable=args.atm_executable)
        elif args.command=="demo":
            from .demo import run_demo
            value=run_demo(args.out)
        elif args.command == "media":
            from .media import dispatch as media_dispatch
            value = media_dispatch(args)
        elif args.command == "delivery":
            from .website_download import dispatch as delivery_dispatch
            value = delivery_dispatch(args)
        else:
            router=Router(args.home)
            value=dispatch(args,router)
        print(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
        if args.command in {"start", "use"} and isinstance(value, dict):
            if value.get("status") in {"denied", "window_unavailable"}:
                return 2
            if value.get("status") in {"starting", "needs_unlock", "needs_approval", "missing_credential"}:
                return 3  # Human action pending, not a successfully executed program.
        if args.command=="verify" and args.allow_network and value.get("status")!="probe_passed":
            return 2
        if args.command=="setup" and args.apply and value.get("status") in {"needs_review", "needs_dependencies"}:
            return 2
        if args.command == "oauth" and isinstance(value, dict):
            if value.get("status") in {"pending", "refreshing"}:
                return 3
            if value.get("status") in {"missing", "needs_login", "refresh_unknown", "denied", "expired"} or value.get("action") in {"paused", "denied", "login_failed"}:
                return 2
        return 2 if isinstance(value,dict) and value.get("status") in ["failed","submission_unknown","download_failed","delivery_failed","blocked","partial_rejection","login_required"] else 0
    except RouterError as e:
        print(json.dumps({"error":e.as_dict()},ensure_ascii=False,indent=2))
        return 2
    except (OSError,ValueError,KeyError,TypeError):
        # No traceback or upstream body in normal agent-facing output.
        print(json.dumps({"error":{"code":"local_failure","message":"Local state, input or provider shape was invalid. Check configuration and the test report; no automatic paid retry was made."}}))
        return 2
    finally:
        if router: router.close()
