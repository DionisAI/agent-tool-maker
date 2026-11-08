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
    from playwright.sync_api import sync_playwright, expect
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
            page.get_by_role('button',name='打开管理台').click()
            page.get_by_role('heading',name='开始使用 ATM').wait_for()
            page.locator('[data-nav=agents]').click()
            page.get_by_role('button',name='安装到 Claude Code',exact=True).click()
            page.locator('#modal').get_by_label('Codex',exact=True).check()
            expect(page.locator('#modal ul.plan li')).to_have_count(2)
            expect(page.get_by_role('button',name='确认安装',exact=True)).to_be_enabled()
            page.get_by_role('button',name='确认安装',exact=True).click()
            expect(page.locator('#agents-list .agent-row [data-state=ready]')).to_have_count(2)
            page.locator('[data-nav=services]').click()
            page.get_by_role('button',name='按工具',exact=True).click()
            page.locator('#services-q').fill('fal.generate')
            page.on('dialog',lambda d:d.accept())
            switch=page.get_by_role('switch',name='允许 Agent 使用 fal.generate',exact=True)
            switch.click()
            expect(switch).to_have_attribute('aria-checked','false')
            page.locator('[data-key="tool:fal.generate"]').click()
            expect(page.locator('#modal-body')).to_contain_text('fal.generate')
            page.get_by_role('button',name='关闭',exact=True).click()
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.body.scrollWidth <= innerWidth')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
