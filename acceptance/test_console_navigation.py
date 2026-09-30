"""Native browser acceptance. Requires localhost navigation permitted by host policy.

Run separately in CI; never disable enterprise policy to make this test pass.
"""
import os
from pathlib import Path
import shutil
import threading
import pytest
from agent_tool_maker.webapp import Console


def test_real_browser_localhost_navigation_and_security_headers(tmp_path):
    from playwright.sync_api import sync_playwright
    executable=shutil.which('atm')
    assert executable, 'Install the ATM package before acceptance.'
    server=Console(tmp_path/'state',executable=executable,user_home=tmp_path/'user')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=os.environ.get('ATM_CHROMIUM') or pw.chromium.executable_path,headless=True)
            page=browser.new_page(viewport={'width':1365,'height':1000})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            response=page.goto(server.origin)
            assert response.status==200
            assert "script-src 'self'" in response.headers['content-security-policy']
            page.locator('#session-token').fill(server.token)
            page.get_by_role('button',name='连接工作台 →').click()
            page.get_by_role('heading',name='连接一次，持续使用。').wait_for()
            page.get_by_role('button',name='配置默认客户端 →').click()
            page.get_by_role('button',name='预览变更',exact=True).click()
            page.wait_for_function("!Array.from(document.querySelectorAll('button')).find(x=>x.textContent==='批准并应用').disabled")
            page.get_by_role('button',name='批准并应用',exact=True).click()
            page.wait_for_function("document.querySelectorAll('.card .badge.good').length === 2")
            page.get_by_role('button',name='工具目录').click()
            page.get_by_label('搜索工具').fill('fal.generate')
            page.on('dialog',lambda d:d.accept())
            page.get_by_role('button',name='已启用 · 停用').click()
            page.get_by_label('搜索工具').fill('fal.generate')
            page.get_by_role('button',name='已停用 · 启用').wait_for()
            page.get_by_role('button',name='查看',exact=True).click()
            assert 'fal.generate' in page.locator('#modal-body').inner_text()
            page.get_by_role('button',name='关闭',exact=True).click()
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
