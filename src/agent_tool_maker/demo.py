"""Deterministic offline contract demo. All provider replies are synthetic fixtures."""
from __future__ import annotations
import base64
import json
import socket
from importlib.resources import files
from pathlib import Path
import httpx
from .engine import Router
from .network import Network
from .storage import State, atomic_write
from .vault import Vault
from .errors import RouterError


def fixture_assets():
    return {k:base64.b64decode(v) for k,v in json.loads(files("agent_tool_maker.data").joinpath("demo_assets.json").read_text()).items()}


def fixture_resolver(*args,**kwargs):
    return [(socket.AF_INET,socket.SOCK_STREAM,6,"",("93.184.216.34",443))]


class FixtureProvider:
    def __init__(self):
        self.calls=[]
        self.assets=fixture_assets()

    def __call__(self,r):
        self.calls.append((r.method,str(r.url)))
        host,path=r.url.host,r.url.path
        if host=="assets.example.test":
            name=path.lstrip("/")
            return httpx.Response(200,content=self.assets[name],headers={"content-type":{"image.png":"image/png","tone.mp3":"audio/mpeg","model.glb":"model/gltf-binary"}[name]})
        if host=="api.elevenlabs.io":
            return httpx.Response(200,content=self.assets["tone.mp3"],headers={"character-cost":"42","request-id":"fixture-tts"})
        if host=="queue.fal.run":
            if r.method=="POST":
                return httpx.Response(200,json={"request_id":"fixture-fal","status_url":"https://queue.fal.run/fal-ai/flux/requests/fixture-fal/status","response_url":"https://queue.fal.run/fal-ai/flux/requests/fixture-fal"})
            if path.endswith("/status"): return httpx.Response(200,json={"status":"COMPLETED"})
            return httpx.Response(200,json={"images":[{"url":"https://assets.example.test/image.png"}]})
        if host=="openapi.tripo3d.ai":
            if r.method=="POST": return httpx.Response(200,json={"code":0,"data":{"task_id":"fixture-tripo"}})
            return httpx.Response(200,json={"code":0,"data":{"status":"success","output":{"model_url":"https://assets.example.test/model.glb"}}})
        if host=="api.higgsfield.ai":
            if r.method=="POST": return httpx.Response(200,json={"request_id":"fixture-higgs","status":"queued","status_url":"https://api.higgsfield.ai/requests/fixture-higgs/status"})
            return httpx.Response(200,json={"request_id":"fixture-higgs","status":"completed","images":[{"url":"https://assets.example.test/image.png"}]})
        if host=="api.exa.ai": return httpx.Response(200,json={"results":[{"title":"Fixture search result","url":"https://example.com"}]})
        if host=="api.firecrawl.dev": return httpx.Response(200,json={"success":True,"data":{"markdown":"# Synthetic scrape fixture"}})
        raise AssertionError(f"Unexpected MOCK request: {r.method} {r.url}")


def run_demo(out: Path):
    out=out.expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        raise RouterError("demo_directory_not_empty","Use an empty output directory so a demo cannot overwrite real data.")
    out.mkdir(parents=True,exist_ok=True)
    state=State(out/".demo-state")
    vault=Vault(state,password="demo-only-not-a-real-secret")
    vault.init("passphrase")
    for provider in ["elevenlabs","fal","tripo"]: vault.put(provider,"FAKE-DEMO-CREDENTIAL-"+provider)
    fake=FixtureProvider()
    router=Router(state.home,network=Network(httpx.MockTransport(fake),fixture_resolver),vault=vault)
    jobs=[]
    try:
        for tool,payload in [
            ("fal.generate",{"endpoint":"fal-ai/flux/schnell","arguments":{"prompt":"A wooden robot"}}),
            ("elevenlabs.tts",{"text":"Synthetic demo: output is a test tone, not real narration.","voice_id":"fixture-voice"}),
            ("tripo.text_to_3d",{"prompt":"A low-poly robot"})]:
            job=router.run(tool,payload,out,request_key="demo-"+tool,allow_paid=True)
            if job["status"]=="queued": job=router.refresh(job["id"])
            if job["status"]!="completed": raise RouterError("demo_failed","Fixture pipeline did not complete.")
            jobs.append(job)
        browser=router.run("tripo.web",{"task":"Create a model using my web membership."},out,request_key="demo-browser")
        atomic_write(out/"browser-handoff.json",json.dumps(router.public_job(browser),indent=2,ensure_ascii=False).encode())
        report={"demo":"synthetic offline fixtures, not vendor-generated work","live_provider_calls":0,
                "real_money_spent":0,"mock_requests":len(fake.calls),
                "completed_native_jobs":len(jobs),"browser_status":browser["status"],
                "jobs":[router.public_job(j) for j in jobs]}
        atomic_write(out/"receipt.json",json.dumps(report,indent=2,ensure_ascii=False).encode())
        paths=[Path(j["data"]["artifacts"][0]["path"]).relative_to(out).as_posix() for j in jobs]
        glb=base64.b64encode(Path(jobs[2]["data"]["artifacts"][0]["path"]).read_bytes()).decode()
        html=TEMPLATE.replace("__IMAGE__",paths[0]).replace("__AUDIO__",paths[1]).replace("__MODEL__",paths[2]).replace("__GLB__",glb)
        atomic_write(out/"index.html",html.encode())
        return {"demo":report["demo"],"index":str(out/"index.html"),"receipt":str(out/"receipt.json"),
                "completed_jobs":3,"browser_handoff":str(out/"browser-handoff.json"),"live_provider_calls":0}
    finally: router.close()


TEMPLATE='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Tool Maker — Offline Demo</title>
<style>body{margin:0;background:#f4f6f7;color:#142b36;font:16px system-ui}main{max-width:1100px;margin:48px auto;padding:24px}h1{font-size:42px;margin:12px 0}.eyebrow{letter-spacing:.18em;font-size:12px;font-weight:700}header p{max-width:760px;line-height:1.7;color:#4a6270}.note{padding:16px;background:#fff1cb;border-left:4px solid #d9a524;margin:26px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:20px}article{background:white;border:1px solid #dbe3e8;border-radius:12px;padding:22px}article p{color:#526675;line-height:1.6}img,canvas{width:100%;height:230px;object-fit:contain;background:#ebf0f4;border-radius:8px}audio{width:100%}.status{font:12px monospace;color:#216455;background:#e8f5ef;padding:6px 9px;border-radius:5px;display:inline-block}a{color:#235d8a}footer{margin-top:28px;line-height:1.8}code{font-size:13px}</style>
<main><header><div class="eyebrow">AGENT TOOL MAKER · V0.2</div><h1>One task. Three tool adapters.</h1><p>A local, inspectable pipeline for API calls, media files and browser handoffs. This page uses artifacts actually saved by the router, not placeholder download links.</p></header>
<div class="note"><strong>Offline contract demo.</strong> All provider responses are synthetic. The image is a test drawing, the audio is a test tone, and the GLB is a tetrahedron. No vendor generated these assets. No money was spent.</div>
<section class="grid"><article><span class="status">FAL ADAPTER · COMPLETED</span><h2>Image asset</h2><img src="__IMAGE__" alt="Synthetic cube fixture"><p>Downloaded through the fixture transport, decoded, hashed and saved.</p></article>
<article><span class="status">TRIPO ADAPTER · COMPLETED</span><h2>3D asset</h2><canvas id="model" width="480" height="360"></canvas><p>The preview reads vertex data from the actual saved GLB fixture. <a href="__MODEL__">Open GLB file</a>.</p></article>
<article><span class="status">ELEVENLABS ADAPTER · COMPLETED</span><h2>Audio asset</h2><audio controls src="__AUDIO__"></audio><p>This is a 440 Hz test tone, not AI narration. The adapter recorded the returned usage header without inventing a dollar price.</p><h3>Browser route</h3><p>Status: <code>requires_browser</code>. A handoff is not a completed generation.</p><a href="browser-handoff.json">Inspect browser handoff</a></article></section>
<footer><a href="receipt.json">Inspect full receipt</a> · All files local · No account required · No analytics<br>Production adapters require your own credentials; browser routes require the host agent's real browser tool.</footer></main>
<script>const bytes=Uint8Array.from(atob('__GLB__'),c=>c.charCodeAt(0));const dv=new DataView(bytes.buffer),jl=dv.getUint32(12,true),doc=JSON.parse(new TextDecoder().decode(bytes.slice(20,20+jl))),bin=28+jl;const acc=doc.accessors[0],view=doc.bufferViews[acc.bufferView],verts=new Float32Array(bytes.buffer,bin+(view.byteOffset||0),acc.count*3);const canvas=document.getElementById('model'),ctx=canvas.getContext('2d');canvas.dataset.loaded='true';function draw(t){ctx.clearRect(0,0,480,360);const a=t*.0004,points=[];for(let i=0;i<verts.length;i+=3){let x=verts[i]*Math.cos(a)+verts[i+2]*Math.sin(a),z=-verts[i]*Math.sin(a)+verts[i+2]*Math.cos(a);points.push([240+x*130,180-verts[i+1]*130+z*22]);}ctx.strokeStyle='#276b69';ctx.lineWidth=4;for(let i=0;i<4;i++)for(let j=i+1;j<4;j++){ctx.beginPath();ctx.moveTo(...points[i]);ctx.lineTo(...points[j]);ctx.stroke();}requestAnimationFrame(draw)}requestAnimationFrame(draw);</script></html>'''
