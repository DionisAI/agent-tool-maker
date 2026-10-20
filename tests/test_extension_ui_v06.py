"""Real DOM + real loopback API bridge. Explicitly not native browser navigation."""
import json
import os
from pathlib import Path
from importlib.resources import files
import pytest
from agent_tool_maker.extensions import new_template
from test_webapp_v04 import console
from test_browser_integration import chromium


@pytest.mark.browser
def test_extension_workshop_dom_and_state(console,chromium):
    from playwright.sync_api import expect
    server,client=console
    page=chromium.new_page(viewport={'width':1400,'height':1050});page.set_default_timeout(10000)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def bridge(path,options):
        assert path.startswith('/api/')
        response=client.request(options.get('method','GET'),path,headers={**options.get('headers',{}),'Origin':server.origin},content=options.get('body'))
        return {'status':response.status_code,'body':response.json()}
    page.expose_function('_test_atm_http',bridge)
    assets=files('agent_tool_maker.data').joinpath('web')
    html=assets.joinpath('index.html').read_text().replace('<link rel="stylesheet" href="/assets/app.css">','')
    for name in ('brand-data.js','brands.js','passkeys.js','model.js','app.js'):
        html=html.replace('<script src="/assets/'+name+'" defer></script>','')
    page.set_content(html);page.add_style_tag(content=assets.joinpath('app.css').read_text())
    page.evaluate("() => {window.fetch=async(path,options)=>{const r=await window._test_atm_http(path,options);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.body};};}")
    for name in ('brand-data.js','brands.js','passkeys.js','model.js','app.js'):
        page.add_script_tag(content=assets.joinpath(name).read_text())
    page.locator('#session-token').fill(server.token)
    page.get_by_role('button',name='打开管理台').click();expect(page.locator('#gate')).to_be_hidden()
    page.locator('[data-nav=settings]').click()
    page.locator('nav.subnav').get_by_role('button',name='添加工具',exact=True).click()
    expect(page.locator('nav.subnav [aria-current=page]')).to_have_text('添加工具')
    page.get_by_role('button',name='添加自定义 Key').click();page.get_by_label('Key 名称').fill('studio.private')
    page.get_by_role('button',name='登记名称',exact=True).click()
    page.get_by_role('button',name='稍后再填',exact=True).click();expect(page.locator('#modal')).not_to_be_visible()
    expect(page.locator('#custom-keys')).to_contain_text('studio.private')
    page.locator('#install-tools').get_by_role('button',name='安装工具定义').click()
    page.get_by_label('工具定义 JSON').fill(json.dumps(new_template('studio.export','web',url='https://example.com/')))
    expect(page.get_by_role('button',name='批准安装')).to_be_disabled()
    page.get_by_role('button',name='检查定义',exact=True).click();expect(page.get_by_role('button',name='批准安装')).to_be_enabled()
    expect(page.locator('#modal-body')).to_contain_text('external_write')
    page.get_by_role('button',name='批准安装').click();expect(page.locator('#modal')).not_to_be_visible()
    expect(page.locator('#main')).to_contain_text('studio.export')
    screenshot=os.environ.get('ATM_SCREENSHOT_DIR')
    if screenshot:
        page.locator('footer').evaluate("e=>e.textContent+=' · 合成测试状态 / HTTP桥接组件验收'")
        Path(screenshot).mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(Path(screenshot)/'atm-v0.6.0-workshop.png'),full_page=True)
    assert not errors,errors
    page.close()
