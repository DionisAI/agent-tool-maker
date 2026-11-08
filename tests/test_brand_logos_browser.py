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
            page.get_by_role('heading',name='你的工具箱').wait_for()
            def loaded():
                page.wait_for_function("() => [...document.querySelectorAll('.provider-mark img')].every(x=>x.complete&&x.naturalWidth>0)")
            def screenshot(name):
                path=os.environ.get('ATM_SCREENSHOT_DIR')
                if path:
                    Path(path).mkdir(parents=True,exist_ok=True)
                    page.locator('footer').evaluate("e=>e.textContent='隔离测试状态 · 假凭证 · 没有供应商请求'")
                    page.screenshot(path=str(Path(path)/f'brand-{width}-{name}.png'),full_page=True)
            loaded()
            assert page.locator('.brand-tile').count()==12
            assert page.locator('.brand-tile [data-brand=tripo] img').count()==1
            assert page.locator('.brand-tile [data-brand=higgsfield] img').count()==1
            assert page.locator('[data-brand=claude] img').count()==1
            assert page.locator('[data-brand=openai] img').count()==1
            assert page.evaluate('document.documentElement.scrollWidth')<=width
            screenshot('overview')
            page.locator('.brand-tile').filter(has=page.locator('[data-brand=tripo]')).click()
            expect(page.get_by_label('搜索工具')).to_have_value('tripo.')
            assert 'tripo.' in page.locator('tbody tr').first.inner_text()
            loaded();screenshot('tripo')
            page.get_by_label('搜索工具').fill('acme.fixture')
            expect(page.locator('tbody tr')).to_have_count(1)
            assert page.locator('[data-brand=acme]').inner_text()=='AC'
            assert page.locator('tbody img').count()==0
            assert '<img src=x onerror=alert(1)>' in page.locator('tbody').inner_text()
            page.get_by_role('button',name='查看',exact=True).click()
            expect(page.locator('#modal-body')).to_contain_text('acme.fixture')
            page.get_by_role('button',name='关闭',exact=True).click()
            page.get_by_label('搜索工具').fill('Higgsfield')
            assert page.locator('tbody tr').count()>0
            assert page.locator('tbody [data-brand=higgsfield] img').count()==page.locator('tbody tr').count()
            loaded();screenshot('tools')
            page.get_by_role('button',name='连接与凭证',exact=True).click()
            page.get_by_label('搜索连接').fill('fal.ai')
            expect(page.locator('.connection-grid .card')).to_have_count(1)
            expect(page.locator('.connection-grid')).to_contain_text('已保存')
            assert page.locator('#passkeys-panel [data-brand="1password"] img').count()==1
            loaded();screenshot('connections')
            assert not [r for r in requests if r[0]=='POST'] # Logos/navigation are read-only.
            assert all(urlsplit(url).netloc==urlsplit(server.origin).netloc or url.startswith('data:') for _,url in requests)
            page.get_by_role('button',name='工具目录',exact=True).click()
            page.get_by_label('搜索工具').fill('fal.generate')
            page.on('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='已启用 · 停用',exact=True).click()
            expect(page.get_by_role('button',name='已停用 · 启用',exact=True)).to_be_visible()
            router=Router(state.home)
            try:assert router.readiness(router.catalog.get('fal.generate'))=='disabled'
            finally:router.close()
            page.get_by_role('button',name='Agent 客户端',exact=True).click()
            assert page.locator('tbody [data-brand=ffmpeg] img').count()>0
            loaded()
            page.get_by_role('button',name='锁定界面',exact=True).click()
            assert page.locator('#gate').is_visible() and not page.locator('#main').inner_text()
            assert not errors,errors
            assert not failures,failures
            browser.close()
        with state.db() as db:assert db.execute('SELECT * FROM secrets').fetchall()==secrets_before
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
