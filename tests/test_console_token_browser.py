"""Native Chromium: the console bearer survives reload in its own tab only (sessionStorage)."""
import os
import shutil
import threading
import time
import pytest
from agent_tool_maker.webapp import Console

KEY = 'atm-console-token'
BLOCK_STORAGE = """Object.defineProperty(window,'sessionStorage',{configurable:true,
  get(){throw new DOMException('storage disabled for this test','SecurityError');}});"""


@pytest.fixture
def console(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    chrome = os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not chrome: pytest.skip('Native Chromium path not supplied')
    server = Console(tmp_path/'state', localhost=True, user_home=tmp_path/'user')
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chrome, headless=True)
            expect.set_options(timeout=15000)
            yield server, browser, expect
            browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(5)


def watch(page, server):
    errors, urls = [], []
    page.set_default_timeout(15000)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: urls.append(request.url))
    page.on('framenavigated', lambda frame: urls.append(frame.url))
    return errors, urls


def ready(page, expect):
    page.get_by_role('heading', name='连接一次，持续使用。').wait_for()
    expect(page.locator('#gate')).to_be_hidden()


def stored(page):
    return page.evaluate('k=>sessionStorage.getItem(k)', KEY)


def test_token_survives_reload_but_not_new_tab_lock_or_expiry(console):
    server, browser, expect = console
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page(); errors, urls = watch(page, server)
    page.goto(server.origin + '/#token=' + server.token)
    ready(page, expect)
    assert page.url == server.origin + '/' and stored(page) == server.token
    assert page.evaluate('location.href') == server.origin + '/'
    urls.clear()  # Only the launch navigation carried the fragment.
    page.reload(); ready(page, expect)
    page.get_by_role('button', name='工具目录', exact=True).click()
    expect(page.locator('tbody tr').first).to_be_visible()
    assert page.evaluate('localStorage.length') == 0 and context.cookies() == []

    other = context.new_page(); other_errors, other_urls = watch(other, server)
    other.goto(server.origin)
    expect(other.locator('#gate')).to_be_visible()
    assert stored(other) is None
    other.close()

    page.get_by_role('button', name='锁定界面', exact=True).click()
    expect(page.locator('#gate')).to_be_visible()
    assert stored(page) is None
    page.reload(); expect(page.locator('#gate')).to_be_visible()

    page.locator('#session-token').fill(server.token)
    page.get_by_role('button', name='连接工作台 →').click()
    ready(page, expect)
    assert stored(page) == server.token
    page.reload(); ready(page, expect)

    server.expires_at = time.monotonic() - 1
    page.get_by_role('button', name='刷新状态 ↻').click()
    expect(page.locator('#gate')).to_be_visible()
    assert stored(page) is None
    server.expires_at = time.monotonic() + 3600
    page.reload(); expect(page.locator('#gate')).to_be_visible()
    assert stored(page) is None

    assert urls and all(server.token not in url for url in urls + other_urls)
    assert server.token not in page.url and not errors and not other_errors
    context.close()


def test_rejected_stored_token_is_cleared_on_load(console):
    server, browser, expect = console
    context = browser.new_context()
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin)
    page.evaluate('([k,v])=>sessionStorage.setItem(k,v)', [KEY, 'stale-token-from-an-old-console'])
    page.reload()
    expect(page.locator('#gate')).to_be_visible()
    assert stored(page) is None and not errors
    context.close()


def test_unavailable_storage_falls_back_to_page_memory(console):
    server, browser, expect = console
    context = browser.new_context()
    context.add_init_script(BLOCK_STORAGE)
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#token=' + server.token)
    ready(page, expect)
    assert page.url == server.origin + '/'
    assert page.evaluate('()=>{try{sessionStorage;return false;}catch(e){return e.name==="SecurityError";}}')
    page.get_by_role('button', name='工具目录', exact=True).click()
    expect(page.locator('tbody tr').first).to_be_visible()
    page.reload(); expect(page.locator('#gate')).to_be_visible()
    page.locator('#session-token').fill(server.token)
    page.get_by_role('button', name='连接工作台 →').click()
    ready(page, expect)
    page.get_by_role('button', name='锁定界面', exact=True).click()
    expect(page.locator('#gate')).to_be_visible()
    assert not errors, errors
    context.close()
