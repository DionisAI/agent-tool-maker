"""Actual Chromium DOM and loopback HTTP bridge, NOT native browser navigation."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from importlib.resources import files

import httpx
import pytest
from agent_tool_maker.engine import Router
from agent_tool_maker.vault import Vault
from agent_tool_maker.secrets_provider import permit_exec
from agent_tool_maker.broker import call
from agent_tool_maker.webapp import Console


@pytest.mark.browser
def test_password_once_ui_then_scoped_program(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    browser_path=os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not browser_path: pytest.skip('Chromium unavailable')
    with tempfile.TemporaryDirectory(prefix='a7ui-') as td:
        root=Path(td);r=Router(root/'s');r.vault=Vault(r.state,password='fake-v07-browser-password');r.vault.init('passphrase')
        r.vault.put('fal','fake-original-key')
        w=root/'project';w.mkdir();(w/'app.py').write_text('import os;print(bool(os.environ["FAL_KEY"]))')
        options=dict(mappings=['FAL_KEY=atm://fal'],argv=[sys.executable,'app.py'],workspace=w,output=root/'c.json')
        plan=permit_exec(r,'claude',**options);permit_exec(r,'claude',**options,apply=True,approve=plan['sha256'])
        ui=Console(r.state.home,executable=shutil.which('atm'),user_home=root/'user')
        t=threading.Thread(target=ui.serve_forever,daemon=True);t.start()
        asset=files('agent_tool_maker.data').joinpath('web')
        try:
            with httpx.Client(base_url=ui.origin,trust_env=False,timeout=30) as client,sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=browser_path,headless=True,args=['--no-sandbox'])
                page=browser.new_page();page.set_default_timeout(8000)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                def bridge(path,options):
                    assert path.startswith('/api/')
                    response=client.request(options.get('method','GET'),path,
                        headers={**options.get('headers',{}),'Origin':ui.origin},content=options.get('body'))
                    return {'status':response.status_code,'body':response.json()}
                page.expose_function('_test_atm_http',bridge)
                html=asset.joinpath('index.html').read_text().replace('<link rel="stylesheet" href="/assets/app.css">','').replace('<script src="/assets/app.js" defer></script>','')
                page.set_content(html);page.add_style_tag(content=asset.joinpath('app.css').read_text())
                page.evaluate("() => {window.fetch=async(path,options)=>{const r=await window._test_atm_http(path,options);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.body};};}")
                # Match the shell's real script order, rather than testing app.js
                # without its reviewed brand/Passkey dependencies on about:blank.
                for name in ('brand-data.js', 'brands.js', 'passkeys.js'):
                    page.add_script_tag(content=asset.joinpath(name).read_text())
                page.add_script_tag(content=asset.joinpath('app.js').read_text())
                page.locator('#session-token').fill(ui.token);page.get_by_role('button',name='连接工作台 →').click()
                page.get_by_role('button',name='解锁 30 分钟',exact=True).click()
                page.get_by_label('现有库口令（仅本机解锁，不写入文件）',exact=True).fill('fake-v07-browser-password')
                page.get_by_role('button',name='确认解锁 30 分钟',exact=True).click()
                expect(page.get_by_role('button',name='立即锁定',exact=True)).to_be_visible()
                page.get_by_role('button',name='连接与凭证',exact=True).click()
                page.get_by_role('button',name='添加 / 更新连接').click()
                page.get_by_label('连接提供方').select_option('fal')
                page.get_by_label('API Key / 凭证（仅写入，无法回读）').fill('fake-v07-new-key')
                page.get_by_label('明确替换这个连接的已有凭证',exact=True).check()
                assert page.get_by_label('现有凭证库口令（仅口令模式需要；仅用于本次请求）').count()==0
                page.get_by_role('button',name='加密保存',exact=True).click()
                expect(page.locator('#modal')).to_be_hidden()
                assert 'fake-v07-new-key' not in page.content() and 'fake-v07-browser-password' not in page.content()
                assert not page.locator('input[type=password]').evaluate_all('xs=>xs.some(x=>!!x.value)')
                result=call(root/'c.json','exec',{'argv':[os.path.abspath(sys.executable),'app.py'],
                    'workspace':str(w),'environment':{'FAL_KEY':'fal'},'request_key':'ui-1'})
                assert result['returncode']==0 and result['stdout']=='True\n'
                assert r.vault.get('fal')=='fake-v07-new-key'
                assert not errors,errors
                browser.close()
        finally:
            ui.shutdown();ui.server_close();t.join(10);r.close()
