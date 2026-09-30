"""Real local Chromium, in-memory fixture page. NOT production-site computer-use validation."""
import base64
import functools
import http.server
import json
import os
from pathlib import Path
import shutil
import threading
import pytest
from agent_tool_maker.demo import run_demo

@pytest.fixture
def chromium():
    playwright=pytest.importorskip('playwright.sync_api')
    path=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium') or shutil.which('chromium-browser')
    if not path: pytest.skip('Chromium is not installed')
    with playwright.sync_playwright() as p:
        browser=p.chromium.launch(executable_path=path,headless=True,args=['--no-sandbox'])
        yield browser
        browser.close()

@pytest.mark.browser
@pytest.mark.integration
def test_real_browser_download_handoff(router,workspace,assets,tmp_path,chromium):
    webroot=tmp_path/'fixture-site';webroot.mkdir()
    data=base64.b64encode(assets['model.glb']).decode()
    (webroot/'index.html').write_text('''<!doctype html><title>Local browser contract fixture</title>
<textarea aria-label="Task"></textarea><button id="generate">Generate fixture</button><span id="state">idle</span>
<script>window.submissions=0;document.getElementById('generate').onclick=()=>{window.submissions++;document.getElementById('state').textContent='completed';
let a=document.createElement('a');a.textContent='Download GLB';a.download='model.glb';a.href='data:model/gltf-binary;base64,'''+data+''' ';a.id='download';document.body.appendChild(a);};</script>''')
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(webroot)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        # Test-only in-memory fixture origin. Production registry/add-browser requires HTTPS.
        url='about:blank'  # In-memory fixture: no navigation/network or enterprise-policy changes.
        router.catalog.tools['tripo.web']={**router.catalog.get('tripo.web'),'url':url}
        job=router.run('tripo.web',{'task':'A simple 3D fixture'},workspace,request_key='real-browser-fixture')
        plan=job['data']['handoff'];assert job['status']=='requires_browser'
        page=chromium.new_page(accept_downloads=True)
        page.set_content((webroot/'index.html').read_text())
        page.get_by_label('Task').fill(plan['task_data'])
        page.get_by_role('button',name='Generate fixture').click()
        with page.expect_download() as download:
            page.get_by_role('link',name='Download GLB').click()
        file=Path(plan['download_directory'])/'downloaded.glb';download.value.save_as(file)
        assert file.read_bytes()==assets['model.glb']
        complete=router.complete_browser(job['id'],[str(file)],page.url)
        assert complete['status']=='completed'
        assert complete['data']['artifacts'][0]['validation']['level']=='container_and_json'
        assert router.run('tripo.web',{'task':'A simple 3D fixture'},workspace,request_key='real-browser-fixture')['id']==job['id']
        assert page.evaluate('window.submissions')==1
        page.close()
    finally:
        server.shutdown();server.server_close();thread.join()

@pytest.mark.browser
@pytest.mark.integration
def test_offline_demo_page_renders(tmp_path,chromium):
    result=run_demo(tmp_path/'demo')
    page=chromium.new_page()
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    html=Path(result['index']).read_text()
    import re
    for rel in re.findall(r'(?:src)="([^"]+)"',html):
        f=Path(result['index']).parent/rel
        if f.is_file():
            mime='image/png' if f.suffix=='.png' else 'audio/mpeg'
            html=html.replace(rel,'data:'+mime+';base64,'+base64.b64encode(f.read_bytes()).decode())
    page.set_content(html)
    page.wait_for_function("document.querySelector('#model').dataset.loaded === 'true'")
    assert page.locator('h1').inner_text()=='One task. Three tool adapters.'
    assert page.locator('img').evaluate('(e)=>e.complete && e.naturalWidth>0')
    assert not errors,errors
    page.close()
