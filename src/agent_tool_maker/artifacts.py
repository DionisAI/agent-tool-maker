from __future__ import annotations
import hashlib
import io
import json
import os
import re
import struct
import wave
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from .errors import RouterError
from .storage import atomic_write

MAX_BYTES = 128*1024*1024
SUFFIXES = {"image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/gif":".gif",
            "audio/mpeg":".mp3","audio/wav":".wav","audio/x-wav":".wav","video/mp4":".mp4",
            "video/webm":".webm","model/gltf-binary":".glb","application/json":".json","image/svg+xml":".svg"}


def confined_file(workspace: Path, value: str | Path) -> Path:
    root = workspace.resolve()
    p = Path(value).expanduser()
    p = p if p.is_absolute() else root / p
    if p.is_symlink():
        raise RouterError("unsafe_path","Symbolic-link inputs are not accepted.")
    p = p.resolve()
    if not p.is_relative_to(root) or not p.is_file():
        raise RouterError("unsafe_path","Input must be an existing regular file inside this job's workspace.")
    if p.stat().st_size > MAX_BYTES:
        raise RouterError("artifact_too_large","File exceeds 128 MiB limit.")
    return p


def managed_dir(workspace: Path, job_id: str, name="artifacts") -> Path:
    if not re.fullmatch(r"[a-f0-9-]{36}",job_id):
        raise RouterError("unsafe_path","Invalid managed job ID.")
    root = workspace.resolve()
    root.mkdir(parents=True,exist_ok=True)
    p = root
    for part in [".atm", name, job_id]:
        p = p / part
        if p.is_symlink():
            raise RouterError("unsafe_path","Managed directories must not contain symbolic links.")
        p.mkdir(exist_ok=True, mode=0o700)
    return p


def infer_suffix(data: bytes, mime="", hint=""):
    if data[:4]==b"glTF": return ".glb"
    if data[:8]==b"\x89PNG\r\n\x1a\n": return ".png"
    if data[:3]==b"\xff\xd8\xff": return ".jpg"
    if data[:6] in [b"GIF87a",b"GIF89a"]: return ".gif"
    if data[:4]==b"RIFF" and data[8:12]==b"WAVE": return ".wav"
    if data[:4]==b"RIFF" and data[8:12]==b"WEBP": return ".webp"
    if data[:3]==b"ID3" or (len(data)>2 and data[0]==255 and data[1]&224==224): return ".mp3"
    if data[4:8]==b"ftyp": return ".mp4"
    if data[:4]==b"\x1aE\xdf\xa3": return ".webm"
    suffix = Path(hint).suffix.lower()
    if suffix in {".json",".txt",".md",".svg"}: return suffix
    return SUFFIXES.get(mime,suffix or ".bin")


def validate_bytes(data: bytes, suffix: str) -> dict:
    if not data or len(data)>MAX_BYTES:
        raise RouterError("invalid_artifact","Empty or oversized artifact.")
    lead = data[:512].lstrip().lower()
    if lead.startswith((b"<!doctype html",b"<html")):
        raise RouterError("invalid_artifact","Received an HTML page rather than a media artifact.")
    detail = {}
    try:
        if suffix in [".png",".jpg",".jpeg",".webp",".gif"]:
            with Image.open(io.BytesIO(data)) as im:
                if im.width*im.height>50_000_000:
                    raise ValueError()
                im.verify()
            with Image.open(io.BytesIO(data)) as im:
                im.load()
                detail = {"width":im.width,"height":im.height,"format":im.format}
            level="decoded"
        elif suffix==".glb":
            if len(data)<20 or data[:4]!=b"glTF": raise ValueError()
            version,total=struct.unpack_from("<II",data,4)
            if version!=2 or total!=len(data): raise ValueError()
            pos,document=12,None
            while pos<len(data):
                if pos+8>len(data): raise ValueError()
                length,kind=struct.unpack_from("<II",data,pos)
                pos+=8
                if length%4 or pos+length>len(data): raise ValueError()
                if document is None:
                    if kind!=0x4E4F534A: raise ValueError()
                    document=json.loads(data[pos:pos+length].decode().rstrip("\x00 "))
                pos+=length
            if not isinstance(document,dict) or document.get("asset",{}).get("version")!="2.0": raise ValueError()
            for item in document.get("buffers",[])+document.get("images",[]):
                uri=item.get("uri","")
                if uri and not uri.startswith("data:"):
                    raise RouterError("external_dependencies","GLB has external buffer/texture dependencies; export a self-contained file.")
            detail={"meshes":len(document.get("meshes",[])),"nodes":len(document.get("nodes",[]))}
            if not detail["meshes"]:
                raise RouterError("invalid_artifact","GLB has no meshes; an empty scene is not accepted as a 3D model.")
            level="container_and_json"  # Not a complete glTF semantic or GPU-render validation.
        elif suffix==".wav":
            with wave.open(io.BytesIO(data),"rb") as w:
                n,c,r,s=w.getnframes(),w.getnchannels(),w.getframerate(),w.getsampwidth()
                if n<=0 or c<=0 or r<=0 or len(w.readframes(n)) != n*c*s: raise ValueError()
                detail={"duration_seconds":n/r,"channels":c,"sample_rate":r}
            level="decoded_pcm"
        elif suffix==".mp3":
            if len(data)<16 or not (data[:3]==b"ID3" or data[0]==255 and data[1]&224==224): raise ValueError()
            level="signature_only"
        elif suffix==".mp4":
            if len(data)<16 or data[4:8]!=b"ftyp": raise ValueError()
            level="signature_only"
        elif suffix==".webm":
            if len(data)<16 or data[:4]!=b"\x1aE\xdf\xa3": raise ValueError()
            level="signature_only"
        elif suffix==".json":
            json.loads(data)
            level="parsed_json"
        elif suffix==".svg":
            if b"<!doctype" in data.lower() or b"<!entity" in data.lower(): raise ValueError()
            doc=ET.fromstring(data)
            if doc.tag.split("}")[-1]!="svg": raise ValueError()
            for node in doc.iter():
                if node.tag.split("}")[-1].lower() in ["script","foreignobject","iframe"]: raise ValueError()
                for k,v in node.attrib.items():
                    k=k.split("}")[-1].lower()
                    if k.startswith("on") or (k in ["href","src"] and not v.startswith("#")) or "url(" in v.lower():
                        raise ValueError()
            level="restricted_xml"  # Do not render/inline untrusted SVG without a sandbox.
        elif suffix in [".txt",".md"]:
            data.decode("utf-8")
            level="utf8_only"
        else:
            raise RouterError("unsupported_artifact",f"Unsupported artifact extension: {suffix}")
    except RouterError:
        raise
    except Exception:
        raise RouterError("invalid_artifact",f"File failed basic validation for {suffix}.") from None
    return {"level":level,"details":detail,"semantic_quality_checked":False}


def save_artifact(workspace,job_id,data,*,mime="",hint="",expected=None):
    suffix=infer_suffix(data,mime,hint)
    if expected and suffix not in expected:
        raise RouterError("unexpected_artifact",f"Expected {', '.join(expected)}, not {suffix}.")
    validation=validate_bytes(data,suffix)
    digest=hashlib.sha256(data).hexdigest()
    target=managed_dir(Path(workspace),job_id)/f"{digest[:20]}{suffix}"
    atomic_write(target,data)
    return {"path":str(target),"sha256":digest,"bytes":len(data),"extension":suffix,"validation":validation}
