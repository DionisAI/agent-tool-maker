"""Chromium component verification with synthetic data; no localhost networking."""
import json
import os
from pathlib import Path
import shutil
from importlib.resources import files
import pytest
from agent_tool_maker import management as mg
from agent_tool_maker.engine import Router
from agent_tool_maker.vault import Vault
from agent_tool_maker.sync import Sync
from agent_tool_maker.broker import list_grants


@pytest.mark.browser
def test_sync_and_access_components_no_plaintext(tmp_path):
    from playwright.sync_api import sync_playwright,expect
    executable=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not executable:pytest.skip('Chromium unavailable')
    r=Router(tmp_path/'state');r.vault=Vault(r.state,password='FAKE-component-passphrase');r.vault.init('passphrase')
    sync=Sync(r.vault);sync.initialize('测试 Laptop');r.vault.put('fal','NEVER-SHOW-FAKE-KEY')
    try:
        responses={'/api/overview':mg.overview(r,user_home=tmp_path/'user'),'/api/tools':mg.tools(r),'/api/connections':mg.connections(r),
                   '/api/jobs':mg.recent_jobs(r),'/api/clis':mg.cli_inventory(r),'/api/sync':sync.status(),'/api/access':{**list_grants(r.state),'broker':None}}
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1080});page.set_default_timeout(7000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            asset=files('agent_tool_maker.data').joinpath('web')
            html=asset.joinpath('index.html').read_text().replace('<link rel="stylesheet" href="/assets/app.css">','')
            for name in ('brand-data.js','brands.js','passkeys.js','model.js','app.js'):
                html=html.replace('<script src="/assets/'+name+'" defer></script>','')
            page.set_content(html)
            page.add_style_tag(content=asset.joinpath('app.css').read_text())
            page.evaluate('(data)=>{window.fetch=async(path)=>({ok:true,status:200,json:async()=>data[path]});}',responses)
            for name in ('brand-data.js','brands.js','passkeys.js','model.js','app.js'):
                page.add_script_tag(content=asset.joinpath(name).read_text())
            page.locator('#session-token').fill('SYNTHETIC-NOT-A-REAL-TOKEN');page.get_by_role('button',name='打开管理台').click()
            page.get_by_role('heading',name='开始使用 ATM').wait_for()  # extensions, session and passkeys are not mocked.
            page.locator('[data-nav=settings]').click()
            page.locator('nav.subnav').get_by_role('button',name='设备同步',exact=True).click()
            expect(page.locator('#main')).to_contain_text('测试 Laptop')
            assert 'NEVER-SHOW' not in page.content()
            if os.environ.get('ATM_SCREENSHOT_DIR'):
                out=Path(os.environ['ATM_SCREENSHOT_DIR']);out.mkdir(parents=True,exist_ok=True)
                page.locator('footer').evaluate("e=>e.textContent+=' · 合成测试状态 / 不是真实账户'")
                page.screenshot(path=str(out/'atm-v0.5-sync.png'),full_page=True)
            page.get_by_role('button',name='配对另一台设备',exact=True).click()
            expect(page.locator('#modal-body')).to_contain_text('独立核对指纹')
            page.get_by_role('button',name='关闭',exact=True).click()
            page.locator('nav.subnav').get_by_role('button',name='高级',exact=True).click()
            expect(page.locator('#main')).to_contain_text('atm broker serve')
            page.locator('[data-nav=agents]').click()
            if os.environ.get('ATM_SCREENSHOT_DIR'):page.screenshot(path=str(out/'atm-v0.5-access.png'),full_page=True)
            page.get_by_role('button',name='新建受限授权',exact=True).click()
            expect(page.locator('#modal-body')).to_contain_text('精确工具 ID')
            assert not errors,errors
            browser.close()
    finally:r.close()
