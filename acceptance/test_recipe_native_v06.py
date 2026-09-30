"""Mandatory native-navigation tier in CI, separate from in-memory DOM tests.
Requires an environment that allows the test browser to navigate a routed fixture
origin. Do not weaken managed browser policy to run this test.
"""
import os
from contextlib import contextmanager
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright
from agent_tool_maker.engine import Router
from agent_tool_maker.extensions import new_template
from agent_tool_maker.network import Network
from agent_tool_maker.web_recipe import save_session
from agent_tool_maker.vault import Vault
from agent_tool_maker.storage import State
import httpx


def test_native_website_recipe_and_local_storage(tmp_path,monkeypatch):
    import agent_tool_maker.web_recipe as wr
    state=State(tmp_path/'owner');vault=Vault(state,password='native-fixture-password');vault.init('passphrase')
    net=Network(httpx.MockTransport(lambda r:httpx.Response(500)),resolver=lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    router=Router(state.home,vault=vault,network=net)
    tool=new_template('fixture.native','web',url='https://fixture.example/');tool['paid']=False
    tool['recipe'].update(session='native',steps=[{'op':'expect_text','target':{'css':'#state'},'value':'authenticated'},
          {'op':'download','target':{'role':'link','name':'Download'},'filename':'out.txt'}])
    save_session(vault,'native',['https://fixture.example'],{'cookies':[],'origins':[{'origin':'https://fixture.example','localStorage':[{'name':'logged','value':'fixture-login-yes'}]}]})
    html='''<div id="state"></div><a download="out.txt" href="data:text/plain,native-output">Download</a>
<script>document.querySelector('#state').textContent=localStorage.getItem('logged')==='fixture-login-yes'?'authenticated':'missing';</script>'''
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('ATM_CHROMIUM') or None)
        @contextmanager
        def context(storage=None):
            ctx=browser.new_context(storage_state=storage,accept_downloads=True,service_workers='block')
            ctx.route('https://fixture.example/**',lambda r:r.fulfill(status=200,content_type='text/html',body=html))
            try:yield ctx
            finally:ctx.close()
        monkeypatch.setattr(wr,'open_context',context)
        try:
            router.catalog.tools[tool['id']]=tool
            job=router.run(tool['id'],{},tmp_path/'workspace',grants=['external_write'],request_key='native')
            assert job['status']=='completed',job
            assert Path(job['data']['artifacts'][0]['path']).read_text()=='native-output'
        finally:browser.close();router.close()
