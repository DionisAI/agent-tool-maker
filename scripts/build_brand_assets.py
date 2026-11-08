"""Build local image-only brand assets from reviewed, downloaded SVGs (no network).

python scripts/build_brand_assets.py /absolute/reviewed/inventory.json
Each inventory entry binds its input file to an upstream SHA-256 and source URL.
See docs/BRAND_LOGOS.md. This is a maintenance step, never a console request.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'src/agent_tool_maker/data/web'
NAMESPACE='http://www.w3.org/2000/svg'

def image_svg(raw:bytes,color:str) -> bytes:
    """Fail closed on active/external content; emit only the vector shapes we use."""
    if not raw or len(raw)>120_000 or not re.fullmatch(r'[0-9a-fA-F]{6}',color):
        raise ValueError('Invalid bounded SVG input or brand color')
    if b'<!' in raw:
        raise ValueError('SVG declarations/entities are not supported')
    original=ET.fromstring(raw)
    if original.tag not in ['svg','{'+NAMESPACE+'}svg']:
        raise ValueError('Expected SVG root')
    allowed={'svg':{'viewBox','width','height','fill','fill-rule','clip-rule'},'path':{'d','fill','fill-rule','clip-rule'},'title':set()}
    def clean(node):
        tag=node.tag.removeprefix('{'+NAMESPACE+'}')
        if tag not in allowed:raise ValueError('Unsupported SVG element: '+tag)
        attributes={}
        for key,value in node.attrib.items():
            if key=='xmlns' and value==NAMESPACE:continue
            if key=='role' and value=='img':continue
            if key=='style' and value=='flex:none;line-height:1':continue
            if key not in allowed[tag]:raise ValueError('Unsupported SVG attribute: '+key)
            if re.search(r'url\s*\(|https?:|//|javascript:|data:',value,re.I):
                raise ValueError('External or active SVG value')
            attributes[key]='#'+color if value=='currentColor' else value
        result=ET.Element(tag,attributes)
        if tag=='title':result.text=node.text
        for child in node:result.append(clean(child))
        return result
    root=clean(original)
    if not root.get('viewBox'):raise ValueError('SVG viewBox required')
    root.set('xmlns',NAMESPACE);root.set('fill','#'+color)
    root.attrib.pop('width',None);root.attrib.pop('height',None)
    return ET.tostring(root,encoding='utf-8')

def build(inventory:Path):
    entries=json.loads(inventory.read_text())
    images={};sources={}
    for key,entry in sorted(entries.items()):
        if not re.fullmatch(r'[a-z0-9_]+',key) or key in {'__proto__','constructor','prototype'}:
            raise ValueError('Invalid brand key')
        path=inventory.parent/entry['file']
        if path.parent.resolve()!=inventory.parent.resolve():raise ValueError('Asset must be in reviewed directory')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['upstream_sha256']:raise ValueError('Upstream digest changed: '+key)
        svg=image_svg(raw,entry['hex'])
        images[key]={'name':entry['name'],'src':'data:image/svg+xml;base64,'+base64.b64encode(svg).decode()}
        sources[key]={**{k:v for k,v in entry.items() if k!='file'},'bundled_svg_sha256':hashlib.sha256(svg).hexdigest()}
    code="'use strict';\n// Generated offline by scripts/build_brand_assets.py. See brand-sources.json.\nwindow.ATM_BRAND_DATA="+json.dumps(images,ensure_ascii=False,separators=(',',':'))+';\n'
    if len(code.encode())>500_000:raise ValueError('Brand bundle exceeds budget')
    (WEB/'brand-data.js').write_text(code)
    (WEB/'brand-sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
    licenses=(inventory.parent/'simple-license.txt').read_text()+'\n\nLobe Icons\n'+(inventory.parent/'lobe-license.txt').read_text()
    (WEB/'brand-licenses.txt').write_text(licenses+'\n\nBrand marks belong to their respective owners. Display identifies tools, not affiliation or account availability.\n')
    print(json.dumps({'logos':len(images),'bundle_bytes':len(code.encode())}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory',type=Path)
    build(parser.parse_args().inventory)
