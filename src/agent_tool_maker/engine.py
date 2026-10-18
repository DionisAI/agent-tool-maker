from __future__ import annotations
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from .artifacts import confined_file, managed_dir, save_artifact
from .browser import handoff, check_receipt_source
from .catalog import Catalog
from .cli_adapter import execute_cli
from .errors import RouterError
from .network import Network, checked_url
from .storage import State, canonical
from .vault import Vault

HOSTS={"fal":"queue.fal.run","higgsfield":"api.higgsfield.ai","tripo":"openapi.tripo3d.ai",
       "elevenlabs":"api.elevenlabs.io","exa":"api.exa.ai","firecrawl":"api.firecrawl.dev"}
TERMINAL={"completed","failed","submission_unknown"}


def safe_endpoint(value):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*",value) or any(p in [".",".."] for p in value.split("/")):
        raise RouterError("unsafe_endpoint","Endpoint must be a relative model ID, not a URL, query or traversal path.")
    return value


def safe_id(value):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}",value):
        raise RouterError("upstream_schema","Missing or malformed task identifier.",uncertain=True)
    return value


def media_urls(value):
    found=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k in {"url","image_url","audio_url","video_url","model_url","download_url"} and isinstance(v,str) and v.startswith("https://"):
                    found.append(v)
                elif isinstance(v,(dict,list)):
                    walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(value)
    return list(dict.fromkeys(found))


class Router:
    def __init__(self,home: Path,*,network=None,vault=None):
        self.state=State(home)
        self.vault=vault or Vault(self.state)
        self.net=network or Network()
        self.catalog=Catalog(self.state)

    def close(self):
        self.net.close()

    def readiness(self,tool):
        names=([tool["credential"]] if tool.get("credential") else [])+list(tool.get("command",{}).get("credential_env",{}).values())
        if any(self.state.setting("sync_conflict:"+n,False) for n in names): return "sync_conflict"
        from .management import enabled
        if not enabled(self.state,tool["id"]): return "disabled"
        if tool["adapter"]=="web_recipe":
            from .web_recipe import health
            return health(self,tool)["state"]
        if tool["adapter"] in {"desktop","human"}: return "host_"+tool["adapter"]+"_required"
        if tool["adapter"]=="workflow": return "workflow_dependencies_not_verified"
        if tool["adapter"]=="mcp": return "configured_not_verified" if self.state.setting("mcp:"+tool["server"]) else "mcp_not_configured"
        if tool["adapter"]=="rest":
            if tool.get("credential") and tool["credential"] not in self.state.secret_names():return "missing_credential"
            if tool["request"].get("origin_setting") and not self.state.setting("origin:"+tool['provider']):return "missing_origin"
            return "configured_not_verified"
        if tool["adapter"]=="catalog_only": return "catalog_only"
        if tool["adapter"]=="browser": return "browser_login_unknown"
        if tool.get("credential"):
            return "configured_not_verified" if tool["credential"] in self.state.secret_names() else "missing_credential"
        path=self.state.setting(f"cli:{tool.get('executable')}")
        return "configured_not_verified" if path and Path(path).is_file() else "cli_not_configured"

    def search(self,query="",capability=None):
        return [{**t,"readiness":self.readiness(t)} for t in self.catalog.search(query,capability)]

    def route(self,task,*,capability=None,allow_browser=False,prefer="auto"):
        candidates=[]
        for t in self.search(task,capability):
            if t["readiness"] == "disabled": continue
            mode="browser" if t["adapter"]=="web_recipe" else t["adapter"] if t["adapter"] in {"browser","desktop","human","mcp","workflow"} else "cli" if t.get("executable") else "api"
            if t["adapter"]=="catalog_only" or (mode in {"browser","desktop","human"} and not allow_browser): continue
            ready=t["readiness"]=="configured_not_verified" or t["adapter"] in {"browser","desktop","human"} and allow_browser
            rank=t["relevance"]+(70 if ready else 0)+(30 if prefer==mode else 0)
            candidates.append({"tool":t["id"],"mode":mode,"readiness":t["readiness"],"eligible":ready,
                               "rank":rank,"reason":"configured route" if ready and mode!="browser" else "host browser and login required" if mode=="browser" else "connect credentials or CLI first",
                               "cost_usd":None,"cost_status":"unknown"})
        candidates.sort(key=lambda x:(not x["eligible"],-x["rank"],x["tool"]))
        return {"recommended":next((x["tool"] for x in candidates if x["eligible"]),None),
                "candidates":candidates[:10],"strategy":"deterministic capability/readiness ranking, not a quality or price benchmark",
                "execution_started":False,"automatic_billing_fallback":False}

    def _credential(self,provider):
        key=self.vault.get(provider)
        if provider=="higgsfield" and (":" not in key or not all(key.split(":",1))):
            raise RouterError("bad_credential","Higgsfield requires KEY_ID:KEY_SECRET.")
        if provider=="elevenlabs": return {"xi-api-key":key}
        if provider=="exa": return {"x-api-key":key}
        return {"Authorization":("Key " if provider in ["fal","higgsfield"] else "Bearer ")+key}

    def _json(self,provider,method,path,body=None,*,url=None):
        target=url or f"https://{HOSTS[provider]}{path}"
        response=self.net.request(method,target,host=HOSTS[provider],headers=self._credential(provider),body=body)
        return self.net.json(response,submission=method=="POST")

    def run(self,tool_id,inputs,workspace,*,request_key=None,allow_paid=False,grants=(),expect_definition=None):
        tool=self.catalog.validate(tool_id,inputs)
        from .maker import digest
        if expect_definition is not None and digest(tool)!=expect_definition:
            raise RouterError("definition_changed","Generated CLI expects a different installed definition; review/rebuild, do not execute silently.")
        if self.readiness(tool)=="sync_conflict":
            raise RouterError("sync_conflict","Resolve the credential conflict first; no alternative login or account was selected.")
        from .management import enabled
        if not enabled(self.state,tool_id):
            raise RouterError("tool_disabled","This action is disabled for all local agents. Enable it explicitly before new execution.")
        if tool["adapter"]=="catalog_only":
            raise RouterError("not_implemented","This item is catalog-only, not an executable adapter.")
        if tool.get("paid") and tool["adapter"]!="browser" and not allow_paid:
            raise RouterError("paid_confirmation_required","This call can spend your provider credits. Review inputs, then pass --allow-paid only with user authorization. This is not a dollar budget guarantee.")
        from .actions import check_permissions, preflight
        from .maker import digest
        check_permissions({**tool,"paid": tool.get("paid",False) and tool["adapter"] not in {"browser","desktop","human"}},allow_paid=allow_paid,grants=grants)
        workspace=Path(workspace).expanduser().resolve()
        workspace.mkdir(parents=True,exist_ok=True)
        # Validate path-like arguments before claiming a job or making a paid call.
        if "endpoint" in inputs: safe_endpoint(inputs["endpoint"])
        if tool["adapter"]=="elevenlabs": safe_id(inputs["voice_id"])
        if tool["adapter"] in ["ffprobe","ffmpeg"]: confined_file(workspace,inputs["path"])
        if tool["adapter"]=="firecrawl": checked_url(inputs["url"])
        preflight(self,tool,inputs,workspace)
        newer=tool["adapter"] in {"rest","command","workflow","mcp","desktop","human","web_recipe"}
        job,created=self.state.create_job(tool_id,inputs,workspace,request_key,context=digest(tool) if newer else None)
        if not created:
            return job  # Includes failed/ambiguous calls: never recreate a generation automatically.
        if newer:
            job=self.state.update_job(job["id"],"submitting",definition_sha256=digest(tool),permissions_granted=list(grants),paid_granted=bool(allow_paid))
        try:
            return self._submit(tool,job)
        except RouterError as e:
            status="submission_unknown" if e.uncertain else "failed"
            return self.state.update_job(job["id"],status,error=e.as_dict())
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, RecursionError):
            error=RouterError("execution_interrupted", "Unexpected provider shape or local execution failure; reconcile the existing task before any new submission.", uncertain=True)
            return self.state.update_job(job["id"],"submission_unknown",error=error.as_dict())

    def _submit(self,tool,job):
        adapter,inputs,job_id=tool["adapter"],job["data"]["inputs"],job["id"]
        if adapter=="web_recipe":
            from .web_recipe import execute_web
            return execute_web(self,tool,job)
        if adapter=="rest":
            from .actions import execute_rest
            return execute_rest(self,tool,job)
        if adapter=="command":
            from .actions import execute_command
            return execute_command(self,tool,job)
        if adapter=="mcp":
            from .mcp_bridge import execute_mcp
            return execute_mcp(self,tool,job)
        if adapter=="workflow":
            from .maker import execute_workflow
            return execute_workflow(self,tool,job)
        if adapter in {"desktop","human"}:
            from .actions import execute_handoff
            return execute_handoff(self,tool,job)
        if adapter=="browser":
            return self.state.update_job(job_id,"requires_browser",handoff=handoff(tool,job),verification="waiting_for_files")
        if adapter=="elevenlabs":
            payload={"text":inputs["text"],"model_id":inputs.get("model_id","eleven_multilingual_v2")}
            r=self.net.request("POST",f"https://{HOSTS[adapter]}/v1/text-to-speech/{inputs['voice_id']}?output_format=mp3_44100_128",
                               host=HOSTS[adapter],headers=self._credential(adapter),body=payload)
            # A successful generation may still produce a malformed local asset. Never resubmit it.
            try:
                artifact=save_artifact(job["workspace"],job_id,r.content,mime="audio/mpeg",expected=[".mp3"])
            except RouterError as e:
                return self.state.update_job(job_id,"delivery_failed",error=e.as_dict(),upstream_may_have_charged=True)
            return self.state.update_job(job_id,"completed",artifacts=[artifact],verification="basic_file_validation",
                                         usage={"character_cost":r.headers.get("character-cost"),"request_id":r.headers.get("request-id")})
        if adapter=="fal":
            j=self._json(adapter,"POST","/"+safe_endpoint(inputs["endpoint"]),inputs["arguments"])
            request_id=safe_id(j.get("request_id"))
            if not isinstance(j.get("status_url"),str) or not isinstance(j.get("response_url"),str):
                raise RouterError("upstream_schema","fal response did not include lifecycle URLs; reconcile the task in provider history.",uncertain=True)
            for key in ["status_url","response_url"]: checked_url(j[key],{HOSTS[adapter]})
            return self.state.update_job(job_id,"queued",upstream_id=request_id,status_url=j["status_url"],response_url=j["response_url"])
        if adapter=="higgsfield":
            j=self._json(adapter,"POST","/"+safe_endpoint(inputs["endpoint"]),inputs["arguments"])
            request_id=safe_id(j.get("request_id"))
            url=j.get("status_url",f"https://{HOSTS[adapter]}/requests/{request_id}/status")
            checked_url(url,{HOSTS[adapter]})
            return self.state.update_job(job_id,"queued",upstream_id=request_id,status_url=url)
        if adapter=="tripo":
            j=self._json(adapter,"POST","/v3/generation/text-to-model",{"model":"v3.1-20260211",**inputs})
            if j.get("code",0)!=0: raise RouterError("upstream_rejected","Tripo rejected the request; inspect provider account.")
            request_id=safe_id(j.get("data",j).get("task_id"))
            return self.state.update_job(job_id,"queued",upstream_id=request_id,status_url=f"https://{HOSTS[adapter]}/v3/tasks/{request_id}")
        if adapter in ["exa","firecrawl"]:
            if adapter=="exa": j=self._json(adapter,"POST","/search",{"numResults":5,**inputs})
            else: j=self._json(adapter,"POST","/v2/scrape",{"url":inputs["url"],"formats":["markdown"]})
            if j.get("success") is False: raise RouterError("upstream_rejected","Provider reported unsuccessful processing.")
            j=self.vault.redact(j)
            artifact=save_artifact(job["workspace"],job_id,canonical(j).encode(),hint="result.json")
            return self.state.update_job(job_id,"completed",artifacts=[artifact],verification="parsed_json")
        if adapter=="xyq":
            kind=tool["id"].split(".")[1]
            args=[f"generate-{kind}","--prompt",inputs["prompt"],"--model",inputs["model"]]
            for key,flag in {"ratio":"--ratio","duration":"--duration","count":"--generate-image-count","resolution":"--resolution"}.items():
                if key in inputs: args.extend([flag,str(inputs[key])])
            result=execute_cli(self.state,"xyq",args,Path(job["workspace"]))
            thread,run=safe_id(result.get("thread_id")),safe_id(result.get("run_id"))
            return self.state.update_job(job_id,"queued",thread_id=thread,upstream_id=run)
        if adapter=="ffprobe":
            file=confined_file(Path(job["workspace"]),inputs["path"])
            result=execute_cli(self.state,"ffprobe",["-v","error","-protocol_whitelist","file,pipe","-show_format","-show_streams","-of","json","-i",str(file)],Path(job["workspace"]))
            artifact=save_artifact(job["workspace"],job_id,canonical(result).encode(),hint="probe.json")
            return self.state.update_job(job_id,"completed",artifacts=[artifact],verification="ffprobe",result=result,cost_usd=0,cost_status="local_no_provider_charge")
        if adapter=="ffmpeg":
            file=confined_file(Path(job["workspace"]),inputs["path"])
            target=managed_dir(Path(job["workspace"]),job_id)/"converted.mp3"
            if target.is_symlink(): raise RouterError("unsafe_path","Unsafe transcode output.")
            execute_cli(self.state,"ffmpeg",["-nostdin","-v","error","-protocol_whitelist","file,pipe","-i",str(file),"-vn","-codec:a","libmp3lame","-q:a","4","-y",str(target)],Path(job["workspace"]),parse_json=False)
            artifact=save_artifact(job["workspace"],job_id,confined_file(Path(job["workspace"]),target).read_bytes(),hint="audio.mp3")
            return self.state.update_job(job_id,"completed",artifacts=[artifact],verification="basic_file_validation",cost_usd=0,cost_status="local_no_provider_charge")
        raise RouterError("not_implemented","No executor for this adapter.")

    def refresh(self,job_id):
        job=self.state.job(job_id)
        if job["status"] in TERMINAL or job["status"] in ["requires_browser","login_required","awaiting_confirmation","delivery_failed","submitting","requires_desktop","requires_human"]:
            return job
        tool=self.catalog.get(job["tool"])
        try:
            if job["data"].get("media_urls"):
                return self._collect(job,tool,job["data"]["media_urls"])
            return self._refresh(job,tool)
        except RouterError as e:
            # Polling errors never turn into a new paid submission.
            return self.state.update_job(job_id,job["status"],last_error=e.as_dict())
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, RecursionError):
            e=RouterError("upstream_schema", "Unexpected status/output shape; existing task retained without resubmission.")
            return self.state.update_job(job_id,job["status"],last_error=e.as_dict())

    def _refresh(self,job,tool):
        adapter,d,jid=tool["adapter"],job["data"],job["id"]
        if adapter=="workflow":
            from .management import enabled
            if not enabled(self.state, tool["id"]):
                raise RouterError("tool_disabled", "Workflow is disabled; no further steps will start.")
            from .maker import execute_workflow
            return execute_workflow(self,tool,job)
        if adapter=="xyq":
            directory=managed_dir(Path(job["workspace"]),jid,"downloads")
            result=execute_cli(self.state,"xyq",["query-result","--thread-id",d["thread_id"],"--run-id",d["upstream_id"],"--download-dir",str(directory)],Path(job["workspace"]))
            if result.get("error_message"):
                return self.state.update_job(jid,"failed",error={"code":"upstream_failed","message":"小云雀 reported failure; message suppressed."})
            if result.get("completed") is not True:
                return self.state.update_job(jid,"running")
            paths=[item.get("output_path") for key in ["images","videos"] for item in result.get(key,[]) if item.get("output_path")]
            if not paths: raise RouterError("missing_artifacts","CLI completed but returned no downloaded files.")
            return self._import(job,paths,expected=[".png",".jpg",".webp",".gif"] if tool["id"].endswith("image") else [".mp4",".webm"])
        j=self._json(adapter,"GET","",url=d["status_url"])
        if adapter=="tripo":
            if j.get("code",0)!=0: raise RouterError("upstream_rejected","Tripo status lookup failed.")
            j=j.get("data",j)
        status=str(j.get("status","")).lower()
        if status in ["failed","error","banned","expired","cancelled","canceled","nsfw"] or j.get("error"):
            return self.state.update_job(jid,"failed",error={"code":"upstream_failed","message":f"Provider task terminal state: {status}."})
        if status not in ["completed","success"]:
            if status not in ["queued","in_queue","running","in_progress","processing"]:
                raise RouterError("upstream_schema","Unrecognized provider state; existing task retained, no resubmission.")
            return self.state.update_job(jid,"running" if status not in ["queued","in_queue"] else "queued")
        if adapter=="fal":
            j=self._json(adapter,"GET","",url=d["response_url"])
            if j.get("error"):
                return self.state.update_job(jid,"failed",error={"code":"upstream_failed","message":"fal completed with an error result."})
        if adapter=="tripo":
            output=j.get("output",{})
            url=output.get("model_url") or output.get("model")
            urls=[url] if isinstance(url,str) else []
        else: urls=media_urls(j)
        if not urls:
            raise RouterError("missing_artifacts","Provider finished but output has no supported media URLs. Check the current endpoint schema.")
        job=self.state.update_job(jid,"awaiting_download",media_urls=urls,provider_completed=True)
        return self._collect(job,tool,urls)

    def _collect(self,job,tool,urls):
        if len(urls)>16: raise RouterError("too_many_artifacts","Result has more than 16 files; manual selection is required.")
        artifacts=[]
        try:
            for url in urls:
                data,mime=self.net.download(url)
                artifact=save_artifact(job["workspace"],job["id"],data,mime=mime,hint=urlsplit(url).path,
                                       expected=[".glb"] if tool["adapter"]=="tripo" else None)
                artifacts.append(artifact)
        except RouterError as e:
            return self.state.update_job(job["id"],"download_failed",artifacts=artifacts,error=e.as_dict(),provider_completed=True)
        return self.state.update_job(job["id"],"completed",artifacts=artifacts,verification="basic_file_validation",error=None,last_error=None)

    def _import(self,job,paths,expected=None,**patch):
        artifacts=[]
        if not paths or len(paths)>16:
            raise RouterError("missing_artifacts","Supply 1-16 actual downloaded files.")
        for value in paths:
            p=confined_file(Path(job["workspace"]),value)
            artifacts.append(save_artifact(job["workspace"],job["id"],p.read_bytes(),hint=p.name,expected=expected))
        return self.state.update_job(job["id"],"completed",artifacts=artifacts,verification="basic_file_validation",**patch)

    def complete_browser(self,job_id,paths,source_url):
        job=self.state.job(job_id)
        tool=self.catalog.get(job["tool"])
        if tool["adapter"] not in {"browser","desktop","human"}: raise RouterError("wrong_job_type","Manual completion is only for external handoffs.")
        if job["status"]=="completed": return job
        check_receipt_source(tool,source_url)
        if tool["adapter"]=="web_recipe":
            from .web_recipe import health
            return health(self,tool)["state"]
        if tool["adapter"] in {"desktop","human"}:
            from .actions import output_record
            if not paths or len(paths)>16: raise RouterError("missing_artifacts","Supply 1–16 actual files.")
            records=[output_record(job['workspace'],p) for p in paths]
            return self.state.update_job(job_id,"completed",artifacts=records,provenance={"source_url":source_url,"attestation":"host_reported_not_provider_verified"},verification="file_exists_and_hash",completion="External deliverable reported; physical fit, commercial acceptance and payment remain separate.")
        return self._import(job,paths,expected=tool["extensions"],provenance={"source_url":source_url,"attestation":"reported_by_host_not_provider_verified"})

    def block_browser(self,job_id,reason):
        job=self.state.job(job_id)
        if self.catalog.get(job["tool"])["adapter"] not in {"browser","desktop","human"} or job["status"]=="completed":
            raise RouterError("wrong_job_type","Only an unfinished browser handoff can be blocked.")
        if reason not in ["login_required","awaiting_confirmation","requires_browser","requires_desktop","requires_human"]:
            raise RouterError("invalid_state","Invalid browser state.")
        return self.state.update_job(job_id,reason)

    def public_job(self,job):
        # No raw API credentials; temporary signed media URLs are private state, not chat output.
        result=json.loads(canonical(job))
        result["data"].pop("media_urls",None)
        return self.vault.redact(result)


ToolMaker = Router
