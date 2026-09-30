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
    p=argparse.ArgumentParser(prog="atm",description="Agent Tool Maker: discover, run, create and compose local tools. JSON output by default.")
    p.add_argument("--version",action="version",version=__version__)
    p.add_argument("--home",type=Path,default=Path(os.environ.get("ATM_HOME",os.environ.get("ATR_HOME","~/.local/share/agent-tool-maker"))).expanduser())
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("init",help="Create local state without network calls")
    sub.add_parser("doctor",help="Report setup state; does not claim logins are valid")
    v=sub.add_parser("vault"); vs=v.add_subparsers(dest="operation",required=True)
    vi=vs.add_parser("init"); vi.add_argument("--backend",choices=["keyring","passphrase"],default="keyring")
    vs.add_parser("status")
    vr=vs.add_parser("remove"); vr.add_argument("provider")
    c=sub.add_parser("connect",help="Human credential setup; never paste keys into an agent transcript")
    c.add_argument("provider"); c.add_argument("--env",help="Explicit one-time import from this environment variable")
    cl=sub.add_parser("cli"); cls=cl.add_subparsers(dest="operation",required=True)
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
    exp=ss.add_parser("export"); exp.add_argument("--destination",type=Path,required=True)
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
    if cmd=="init":
        return {"home":str(router.state.home),"tools":len(router.catalog.tools),"network_calls":0,"version":__version__}
    if cmd=="doctor":
        return {"home":str(router.state.home),"vault":router.state.setting("vault",{}).get("backend","not_initialized"),
                "tools":[{"id":t["id"],"state":router.readiness(t)} for t in router.catalog.tools.values()],
                "notes":["Configuration is not authentication verification.","Browser handoffs require a host browser tool and user login.","No provider calls were made."]}
    if cmd=="vault":
        if args.operation=="init": return router.vault.init(args.backend)
        if args.operation=="status": return {"backend":router.state.setting("vault",{}).get("backend"),"credential_names":router.state.secret_names(),"secrets_returned":False}
        return router.vault.delete(args.provider)
    if cmd=="connect":
        providers={t.get("credential") for t in router.catalog.tools.values()}-{None}
        for t in router.catalog.tools.values():providers.update(t.get('command',{}).get('credential_env',{}).values())
        providers.update({'google_oauth','cloudflare','supabase','expo'})
        for key in ['figma','notion','linear','playwright','chrome_devtools','posthog','sentry']:
            cfg=router.state.setting('mcp:'+key,{})
            if cfg.get('credential'):providers.add(cfg['credential'])
            providers.update(cfg.get('env_credentials',{}).values())
        if args.provider not in providers:
            raise RouterError("unknown_provider","No native API credential adapter for this provider; browser logins and CLI logins are separate.")
        if args.env:
            value=os.environ.get(args.env,"")
            if not value: raise RouterError("missing_environment","Named environment variable is empty or unset.")
        elif args.provider=="higgsfield":
            value=prompt_secret("Higgsfield API key ID: ")+":"+prompt_secret("Higgsfield API key secret: ")
        else: value=prompt_secret(f"{args.provider} API key: ")
        router.vault.put(args.provider,value)
        return {"provider":args.provider,"saved_encrypted":True,"authentication":"not_verified","one_time_env_import":bool(args.env)}
    if cmd=="cli": return bind_cli(router.state,args.name,args.path)
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
        if args.dry_run:
            tool=router.catalog.validate(args.tool,inputs)
            from .actions import preflight
            plan=preflight(router,tool,inputs,args.workspace)
            return {"plan":plan,"permissions_required":tool.get('permissions',[]),"dry_run":True,"tool":tool["id"],"schema_valid":True,"readiness":router.readiness(tool),
                    "paid":tool["paid"],"cost_usd":None,"credentials_read":False,"network_calls":0}
        return router.public_job(router.run(args.tool,inputs,args.workspace,request_key=args.request_key,allow_paid=args.allow_paid,grants=[p for p,flag in [('external_write',args.allow_write),('production',args.allow_production),('execute_code',args.allow_code)] if flag]))
    if cmd=="jobs":
        if args.operation=="list": return {"jobs":[router.public_job(j) for j in router.state.jobs()]}
        if args.operation=="get": return router.public_job(router.refresh(args.id) if args.refresh else router.state.job(args.id))
        if args.operation=="complete": return router.public_job(router.complete_browser(args.id,args.file,args.source_url))
        return router.public_job(router.block_browser(args.id,args.reason))
    if cmd=="skill":
        target=args.destination.expanduser().resolve()/"agent-tool-maker"/"SKILL.md"
        if target.exists(): raise RouterError("file_exists","Skill already exists; inspect it rather than overwriting silently.")
        atomic_write(target,files("agent_tool_maker.data").joinpath("SKILL.md").read_bytes())
        return {"skill_path":str(target),"host_registration":"Load this directory through your agent's supported skill mechanism."}
    if cmd=="add-browser": return add_browser_tool(router.state,args.id,args.title,args.url,args.capability)
    raise RouterError("unknown_command","Unknown command.")


def main(argv=None):
    args=parser().parse_args(argv)
    router=None
    try:
        if args.command=="demo":
            from .demo import run_demo
            value=run_demo(args.out)
        else:
            router=Router(args.home)
            value=dispatch(args,router)
        print(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
        return 2 if isinstance(value,dict) and value.get("status") in ["failed","submission_unknown","download_failed","delivery_failed","blocked"] else 0
    except RouterError as e:
        print(json.dumps({"error":e.as_dict()},ensure_ascii=False,indent=2))
        return 2
    except (OSError,ValueError,KeyError,TypeError):
        # No traceback or upstream body in normal agent-facing output.
        print(json.dumps({"error":{"code":"local_failure","message":"Local state, input or provider shape was invalid. Check configuration and the test report; no automatic paid retry was made."}}))
        return 2
    finally:
        if router: router.close()
