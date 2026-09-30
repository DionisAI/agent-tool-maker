from __future__ import annotations
import hashlib
import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from .errors import RouterError
from .storage import State

SAFE_ENV={"PATH","HOME","USER","LOGNAME","LANG","LC_ALL","LC_CTYPE","TMPDIR","TEMP","TMP",
          "SYSTEMROOT","WINDIR","COMSPEC","APPDATA","LOCALAPPDATA","USERPROFILE",
          "DBUS_SESSION_BUS_ADDRESS","XDG_RUNTIME_DIR","XDG_CONFIG_HOME","DISPLAY"}


def bind_cli(state: State, name: str, path: str):
    from .catalog import Catalog
    allowed={t.get("executable") for t in Catalog(state).tools.values()}-{None}
    allowed |= set(state.setting("custom_cli_names", []))
    if name not in allowed:
        raise RouterError("unsupported_cli","Only reviewed CLI adapters can be bound.")
    p=Path(path).expanduser().resolve()
    if not p.is_absolute() or not p.is_file() or not os.access(p,os.X_OK):
        raise RouterError("bad_executable","Bind an existing executable by absolute path.")
    state.set_setting(f"cli:{name}",str(p))
    state.set_setting(f"cli_hash:{name}", hashlib.sha256(p.read_bytes()).hexdigest())
    return {"bound":name,"path":str(p),"authentication":"not_verified"}


def execute_cli(state: State,name: str,args: list[str],workspace: Path,timeout=60,parse_json=True,output_mode=None,extra_env=None):
    path=state.setting(f"cli:{name}")
    if not path or not Path(path).is_file():
        raise RouterError("cli_not_configured",f"Bind {name} using atm cli bind in a human terminal.")
    expected=state.setting(f"cli_hash:{name}")
    if expected and hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected:
        raise RouterError("executable_changed","Bound executable changed; review the update and explicitly bind it again.")
    env={k:v for k,v in os.environ.items() if k in SAFE_ENV}
    if extra_env:
        for key,value in extra_env.items():
            if key in {"PATH","HOME","LD_PRELOAD","PYTHONPATH","NODE_OPTIONS"}:
                raise RouterError("unsafe_environment","Refusing execution-control environment override.")
            env[key]=value
    env.update({"PIPPIT_CLI_DISABLE_TELEMETRY":"1","NO_COLOR":"1","CI":"1","GH_PROMPT_DISABLED":"1","CLOUDFLARE_SEND_METRICS":"false"})
    # Capture output in temporary files; returned JSON is bounded. Raw stderr and API env are not returned.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            proc=subprocess.Popen([path,*args],cwd=workspace,env=env,stdin=subprocess.DEVNULL,
                                  stdout=out,stderr=err,shell=False,start_new_session=os.name=="posix")
        except OSError:
            raise RouterError("cli_start_failed","Could not start the configured CLI.") from None
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name=="posix": os.killpg(proc.pid,signal.SIGKILL)
            else: proc.kill()
            proc.wait()
            raise RouterError("cli_timeout","CLI timed out; upstream completion is unknown. Do not resubmit blindly.",uncertain=True) from None
        if proc.returncode:
            raise RouterError("cli_failed",f"CLI exited with code {proc.returncode}; stderr suppressed. Check its login/status directly.",uncertain=True)
        out.seek(0)
        data=out.read(2*1024*1024+1)
        if len(data)>2*1024*1024:
            raise RouterError("cli_output_limit","CLI output exceeded the JSON limit.",uncertain=True)
        if output_mode=="text":
            return {"returncode":0,"stdout":data.decode("utf-8",errors="replace")}
        if not parse_json:
            return {"returncode": 0}
        try:
            parsed=json.loads(data)
            if not isinstance(parsed,(dict,list)): raise ValueError()
            return parsed
        except (ValueError,UnicodeDecodeError):
            raise RouterError("cli_protocol","CLI did not return a JSON object; upstream outcome may be unknown.",uncertain=True) from None
