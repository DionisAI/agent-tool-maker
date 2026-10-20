"""Native browser HTTP/CSP, isolated fake vault/catalog; no supplier/account requests."""
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import urlsplit
import pytest
from agent_tool_maker.catalog import add_browser_tool
from agent_tool_maker.engine import Router
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault
from agent_tool_maker.webapp import Console

@pytest.mark.browser
@pytest.mark.parametrize('width',[1440,390],ids=['desktop','mobile'])
def test_native_local_logos_filters_unknown_and_controls(tmp_path,width):
    from playwright.sync_api import sync_playwright,expect
    chrome=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not chrome:pytest.skip('Native Chromium path not supplied')
    state=State(tmp_path/'state');vault=Vault(state,password='fake-brand-test-only');vault.init('passphrase')
    vault.put('fal','fake-brand-key-only')
    add_browser_tool(state,'tripo.studio.fixture','Tripo Studio · 隔离显示测试','https://example.test/tripo','3d')
    add_browser_tool(state,'acme.fixture','<img src=x onerror=alert(1)>','https://example.test/acme','image')
    rows=state.setting('custom_browser_tools');rows[0]['provider']='studio';state.set_setting('custom_browser_tools',rows)
    with state.db() as db:secrets_before=db.execute('SELECT * FROM secrets').fetchall()
    server=Console(state.home,localhost=True,user_home=tmp_path/'user')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=chrome,headless=True)
            page=browser.new_page(viewport={'width':width,'height':1050 if width>780 else 844})
            page.set_default_timeout(15000);expect.set_options(timeout=15000)
            errors=[];failures=[];requests=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('requestfailed',lambda request:failures.append(request.failure))
            page.on('request',lambda request:requests.append((request.method,request.url)))
            page.goto(server.origin+'/#token='+server.token)
            page.get_by_role('heading',name='我在用的服务').wait_for()
            def loaded():
                page.wait_for_function("() => [...document.querySelectorAll('.provider-mark img')].every(x=>x.complete&&x.naturalWidth>0)")
            def screenshot(name):
                path=os.environ.get('ATM_SCREENSHOT_DIR')
                if path:
                    Path(path).mkdir(parents=True,exist_ok=True)
                    page.locator('footer').evaluate("e=>e.textContent='隔离测试状态 · 假凭证 · 没有供应商请求'")
                    page.screenshot(path=str(Path(path)/f'brand-{width}-{name}.png'),full_page=True)
            loaded()
            # 首页: the in-use service rows, the credits cards and both Agents carry bundled marks.
            assert page.locator('#home-services .service-row').count()>=1
            assert page.locator('#home-services .service-row [data-brand=fal] img').count()==1
            assert page.locator('#credits-panel [data-brand=tripo] img').count()==1
            assert page.locator('#credits-panel [data-brand=higgsfield] img').count()==1
            assert page.locator('[data-brand=claude] img').count()==1
            assert page.locator('[data-brand=openai] img').count()==1
            assert page.evaluate('document.documentElement.scrollWidth')<=width
            screenshot('overview')
            # 服务: every service is one click away; Tripo collects the studio-namespace tool.
            page.get_by_role('button',name='服务',exact=True).click()
            assert page.locator('.service-index [data-brand=tripo] img').count()==1
            assert page.locator('.service-index [data-brand=higgsfield] img').count()==1
            assert page.locator('.service-index [data-brand=acme]').count()==1
            page.locator('.service-index button').filter(has=page.locator('[data-brand=tripo]')).click()
            expect(page.locator('#main .page-title h1')).to_have_text('Tripo3D')
            expect(page.locator('#tools')).to_contain_text('tripo.studio.fixture')
            loaded();screenshot('tripo')
            page.get_by_role('button',name='服务',exact=True).click()
            page.get_by_role('button',name='按工具',exact=True).click()
            page.locator('#services-q').fill('acme.fixture')
            rows=page.locator('#services-results [data-tool-id]')
            expect(rows).to_have_count(1)
            assert page.locator('#services-results [data-brand=acme]').inner_text()=='AC'
            assert page.locator('#services-results img').count()==0
            assert '<img src=x onerror=alert(1)>' in rows.inner_text()
            page.locator('[data-key="tool:acme.fixture"]').click()
            expect(page.locator('#modal-body')).to_contain_text('acme.fixture')
            page.get_by_role('button',name='关闭',exact=True).click()
            page.locator('#services-q').fill('Higgsfield')
            assert rows.count()>0
            assert page.locator('#services-results [data-tool-id] [data-brand=higgsfield] img').count()==rows.count()
            loaded();screenshot('tools')
            # 设置 › Key 保管: the saved Key and the Passkey mark.
            page.get_by_role('button',name='设置',exact=True).click()
            page.get_by_label('搜索 Key').fill('fal')
            saved=page.locator('#all-keys .rows').first.locator('li.key-row')
            expect(saved).to_have_count(1)
            expect(saved).to_contain_text('可以使用')
            assert page.locator('#passkeys-panel [data-brand="1password"] img').count()==1
            loaded();screenshot('connections')
            assert not [r for r in requests if r[0]=='POST'] # Logos/navigation are read-only.
            assert all(urlsplit(url).netloc==urlsplit(server.origin).netloc or url.startswith('data:') for _,url in requests)
            page.get_by_role('button',name='服务',exact=True).click()
            page.locator('#services-q').fill('fal.generate')
            switch=page.get_by_role('switch',name='允许 Agent 使用 fal.generate',exact=True)
            expect(switch).to_have_attribute('aria-checked','true')
            page.on('dialog',lambda dialog:pytest.fail('no native confirm for a single switch'))
            switch.click()
            expect(page.get_by_role('switch',name='允许 Agent 使用 fal.generate',exact=True)).to_have_attribute('aria-checked','false')
            router=Router(state.home)
            try:assert router.readiness(router.catalog.get('fal.generate'))=='disabled'
            finally:router.close()
            page.evaluate("go('settings/programs')")
            assert page.locator('[data-program=ffmpeg] [data-brand=ffmpeg] img').count()==1
            loaded()
            page.get_by_role('button',name='退出管理台',exact=True).click()
            assert page.locator('#gate').is_visible() and not page.locator('#main').inner_text()
            assert not errors,errors
            assert not failures,failures
            browser.close()
        with state.db() as db:assert db.execute('SELECT * FROM secrets').fetchall()==secrets_before
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
