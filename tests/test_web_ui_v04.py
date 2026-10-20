"""Real Chromium DOM + HTTP-backed test transport. Not native navigation/CSP proof.

This environment can forbid localhost navigation. The independent acceptance/
suite performs native browser HTTP navigation in CI; no browser policy is changed.
"""
import json
import os
from pathlib import Path
import shutil
import threading
from importlib.resources import files

import httpx
import pytest
from agent_tool_maker.webapp import Console
from agent_tool_maker.engine import Router
from agent_tool_maker.onboarding import setup


@pytest.mark.browser
def test_dom_console_flows_and_cli_state_reuse(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    browser_path=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not browser_path:pytest.skip('Chromium unavailable')
    exe=tmp_path/'atm';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o700)
    server=Console(tmp_path/'state',executable=str(exe),user_home=tmp_path/'user')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    asset=files('agent_tool_maker.data').joinpath('web')
    try:
        with httpx.Client(base_url=server.origin,trust_env=False,timeout=30) as client, sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=browser_path,headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1050})
            page.set_default_timeout(7000)
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            def bridge(path,options):
                assert path.startswith('/api/')
                headers={**options.get('headers',{}),'Origin':server.origin}
                response=client.request(options.get('method','GET'),path,headers=headers,content=options.get('body'))
                return {'status':response.status_code,'body':response.json()}
            page.expose_function('_test_atm_http',bridge)
            html=asset.joinpath('index.html').read_text().replace('<link rel="stylesheet" href="/assets/app.css">','')
            for script in ['brand-data.js','brands.js','passkeys.js','model.js','app.js']:
                html=html.replace('<script src="/assets/'+script+'" defer></script>','')
            page.set_content(html)
            page.add_style_tag(content=asset.joinpath('app.css').read_text())
            page.evaluate("() => {window.fetch=async(path,options)=>{const r=await window._test_atm_http(path,options);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.body};};}")
            for script in ['brand-data.js','brands.js','passkeys.js','model.js','app.js']:
                page.add_script_tag(content=asset.joinpath(script).read_text())
            page.locator('#session-token').fill(server.token)
            page.get_by_role('button',name='打开管理台').click()
            page.get_by_role('heading',name='开始使用 ATM').wait_for()
            assert page.locator('#gate').is_hidden()
            page.locator('[data-nav=agents]').click()
            page.get_by_role('button',name='安装到 Claude Code',exact=True).click()
            page.locator('#modal').get_by_label('Codex',exact=True).check()  # Both Agents; the plan is previewed again.
            expect(page.locator('#modal ul.plan li')).to_have_count(2)
            expect(page.get_by_role('button',name='确认安装',exact=True)).to_be_enabled()
            page.get_by_role('button',name='确认安装',exact=True).click()
            expect(page.locator('#agents-list .agent-row [data-state=ready]')).to_have_count(2)
            # These are clearly synthetic home/state fixtures, not live client accounts.
            page.locator('footer').evaluate("e=>e.textContent+=' · 临时测试状态 / UI 组件测试（HTTP 传输桥接）'")
            screenshot=os.environ.get('ATM_SCREENSHOT_DIR')
            if screenshot:
                Path(screenshot).mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(Path(screenshot)/'atm-v0.4.0-dashboard.png'),full_page=True)
            page.locator('[data-nav=services]').click()
            page.get_by_role('button',name='按工具',exact=True).click()
            page.locator('#services-q').fill('fal.generate')
            expect(page.locator('#services-results [data-tool-id]')).to_have_count(1)
            page.on('dialog',lambda d:d.accept())
            page.get_by_role('switch',name='允许 Agent 使用 fal.generate').click()
            expect(page.get_by_role('switch',name='允许 Agent 使用 fal.generate')).to_have_attribute('aria-checked','false')
            fresh=Router(server.home)
            try:assert fresh.readiness(fresh.catalog.get('fal.generate'))=='disabled'
            finally:fresh.close()
            if screenshot:page.screenshot(path=str(Path(screenshot)/'atm-v0.4.0-tools.png'),full_page=True)
            page.locator('[data-key="tool:fal.generate"]').click()
            expect(page.locator('#modal-body')).to_contain_text('fal.generate')
            page.get_by_role('button',name='关闭',exact=True).click()
            page.locator('[data-nav=settings]').click()
            page.get_by_role('button',name='设置保管方式',exact=True).click()
            page.locator('#modal').get_by_label('ATM 主密码',exact=True).check()
            page.get_by_label('设置 ATM 主密码（至少 12 个字符）',exact=True).fill('BROWSER-TEST-PASSPHRASE')
            page.get_by_label('再输入一次',exact=True).fill('BROWSER-TEST-PASSPHRASE')
            page.get_by_role('button',name='确认设置',exact=True).click()
            page.locator('#modal').wait_for(state='hidden')
            page.get_by_role('button',name='添加 Key',exact=True).click()
            page.get_by_label('Key 名称').select_option('fal')
            page.get_by_label('API Key',exact=True).fill('BROWSER-TEST-SECRET')
            page.get_by_label('ATM 主密码',exact=True).fill('BROWSER-TEST-PASSPHRASE')
            page.get_by_role('button',name='加密保存',exact=True).click()
            page.locator('#modal').wait_for(state='hidden')
            assert 'BROWSER-TEST-SECRET' not in page.content()
            assert not page.locator('input[type=password]').evaluate_all("xs=>xs.some(x=>!!x.value)")
            page.get_by_role('button',name='退出管理台').click()
            assert page.locator('#gate').is_visible() and page.locator('#main').inner_text()==''
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
