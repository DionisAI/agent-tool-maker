"""Native Chromium: the console bearer survives reload in its own tab only (sessionStorage)."""
import json
import os
import shutil
import threading
import time
import pytest
from agent_tool_maker import webapp
from agent_tool_maker.webapp import Console

pytestmark = pytest.mark.browser
KEY = 'atm-console-token'
SECTION = 'atm-console-section'
BLOCK_STORAGE = """Object.defineProperty(window,'sessionStorage',{configurable:true,
  get(){throw new DOMException('storage disabled for this test','SecurityError');}});"""
# Records whether #gate is ever shown: on insertion by the parser, on any hidden change, and every frame.
GATE_PROBE = """(() => {
  window.__gateShown = false;
  const check = () => { const gate = document.getElementById('gate'); if (gate && !gate.hidden) window.__gateShown = true; };
  new MutationObserver(check).observe(document, {subtree: true, childList: true, attributes: true, attributeFilter: ['hidden']});
  const frame = () => { check(); requestAnimationFrame(frame); }; requestAnimationFrame(frame);
})();"""
# Records each distinct "page heading|active nav items" the page holds: on parser insertion, any change, every frame.
SECTION_PROBE = """(() => {
  window.__painted = [];
  const check = () => {
    const h1 = document.querySelector('#main .page-title h1');
    const row = (h1 ? h1.textContent : '') + '|' + [...document.querySelectorAll('[data-nav].active')].map(n => n.dataset.nav).join(',');
    if (window.__painted[window.__painted.length - 1] !== row) window.__painted.push(row);
  };
  new MutationObserver(check).observe(document, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class']});
  const frame = () => { check(); requestAnimationFrame(frame); }; requestAnimationFrame(frame);
})();"""
PLACEHOLDER = '正在连接本机 ATM…'
EXPIRED = '会话已过期：在终端再次运行 atm ui 打开新的管理台'
RESTARTED = '管理台已重启或会话已失效：在终端再次运行 atm ui'
REJECTED = '会话码未被接受：请核对终端所示 token 文件中的会话码'
LAUNCH_USED = '启动链接已使用或已过期：在终端再次运行 atm ui'
OVERVIEW, TOOLS, CONNECTIONS = '连接一次，持续使用。', '一个目录，两种 Agent。', '连接与凭证'


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


def ready(page, expect, heading=OVERVIEW):
    # Rendered from live data: the static placeholder is gone.
    expect(page.locator('#main')).not_to_contain_text('正在连接本机 ATM')
    expect(page.locator('#main .page-title h1')).to_have_text(heading)
    expect(page.locator('#gate')).to_be_hidden()


def locked(page, expect, reason=None):
    expect(page.locator('#gate')).to_be_visible()
    if reason:
        expect(page.locator('#gate-reason')).to_have_text(reason)
    else:
        expect(page.locator('#gate-reason')).to_be_hidden()
    assert stored(page) is None and page.locator('#main').inner_text() == ''
    assert not page.evaluate("document.getElementById('modal').open")
    # Only the gate's own reason: no toast repeats the request error (checked now, not polled until it fades).
    assert page.evaluate("document.getElementById('toast').hidden")


def stored(page, key=KEY):
    return page.evaluate('k=>sessionStorage.getItem(k)', key)


def history(context, page):
    return [entry['url'] for entry in context.new_cdp_session(page).send('Page.getNavigationHistory')['entries']]


def test_token_survives_reload_but_not_new_tab_lock_or_expiry(console):
    server, browser, expect = console
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page(); errors, urls = watch(page, server)
    page.goto(server.origin + '/#token=' + server.token)  # Still accepted from already-open links.
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
    ready(page, expect, TOOLS)
    assert stored(page) == server.token
    page.reload(); ready(page, expect, TOOLS)

    server.expires_at = time.monotonic() - 1
    page.get_by_role('button', name='刷新状态 ↻').click()
    locked(page, expect, EXPIRED)
    server.expires_at = time.monotonic() + 3600
    page.reload(); expect(page.locator('#gate')).to_be_visible()
    assert stored(page) is None

    assert urls and all(server.token not in url for url in urls + other_urls)
    assert server.token not in page.url and not errors and not other_errors
    context.close()


def test_reload_with_a_valid_stored_token_never_shows_the_gate(console):
    server, browser, expect = console
    context = browser.new_context()
    context.add_init_script(GATE_PROBE)
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#token=' + server.token)
    ready(page, expect)
    for _ in range(3):
        page.reload(); ready(page, expect)
        assert page.evaluate('window.__gateShown') is False
    page.get_by_role('button', name='锁定界面', exact=True).click()
    expect(page.locator('#gate')).to_be_visible()
    assert page.evaluate('window.__gateShown') is True  # The probe does see a shown gate.
    page.reload(); expect(page.locator('#gate')).to_be_visible()  # No token: the gate is shown.
    assert not errors, errors
    context.close()


def test_atm_ui_launch_code_opens_the_console_once_and_no_url_holds_the_bearer(console, monkeypatch, capsys):
    server, browser, expect = console
    opened = []
    monkeypatch.setattr(webapp.webbrowser, 'open', lambda url: opened.append(url) or True)
    assert webapp.serve(server.home) == 0  # `atm ui` again: reuses this running console.
    announced = capsys.readouterr().out
    assert json.loads(announced)['reused'] is True and len(opened) == 1
    code = opened[0].removeprefix(server.origin + '/#launch=')
    assert code != opened[0] and server.token not in opened[0] and code not in announced

    context = browser.new_context()
    context.add_init_script(GATE_PROBE)
    page = context.new_page(); errors, urls = watch(page, server)
    page.goto(opened[0])
    ready(page, expect)
    assert page.url == server.origin + '/' and stored(page) == server.token
    assert page.evaluate('window.__gateShown') is False
    page.reload(); ready(page, expect)
    assert all(code not in url and server.token not in url for url in history(context, page))

    other = context.new_page(); other_errors, other_urls = watch(other, server)
    other.goto(opened[0])  # The same link again: used once already.
    locked(other, expect, LAUNCH_USED)
    assert other.url == server.origin + '/' and all(code not in url for url in history(context, other))
    assert not server.launch_codes
    assert urls and all(server.token not in url for url in urls + other_urls)
    assert not errors and not other_errors, errors + other_errors
    context.close()


def test_expired_launch_code_shows_why(console):
    server, browser, expect = console
    code = server.launch_code()
    server.launch_codes[code] = time.monotonic() - 1
    context = browser.new_context()
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#launch=' + code)
    locked(page, expect, LAUNCH_USED)
    page.locator('#session-token').fill(server.token)  # The manual field still works.
    page.get_by_role('button', name='连接工作台 →').click()
    ready(page, expect)
    assert stored(page) == server.token and not errors
    context.close()


def test_rejected_stored_token_is_cleared_on_load(console):
    server, browser, expect = console
    context = browser.new_context()
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin)
    expect(page.locator('#gate')).to_be_visible()
    expect(page.locator('#gate-reason')).to_be_hidden()  # Nothing went wrong yet.
    page.evaluate('([k,v])=>sessionStorage.setItem(k,v)', [KEY, 'stale-token-from-an-old-console'])
    page.reload()
    locked(page, expect, RESTARTED)
    page.locator('#session-token').fill('typed-but-wrong-session-code')
    page.get_by_role('button', name='连接工作台 →').click()
    locked(page, expect, REJECTED)
    assert not errors
    context.close()


def test_lock_and_401_forget_the_same_way(console):
    server, browser, expect = console
    context = browser.new_context()
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#token=' + server.token)
    ready(page, expect)
    page.get_by_role('button', name='锁定界面', exact=True).click()
    locked(page, expect)

    page.locator('#session-token').fill(server.token)
    page.get_by_role('button', name='连接工作台 →').click()
    ready(page, expect)
    page.get_by_role('button', name='配置默认客户端 →').click()
    expect(page.locator('#modal')).to_be_visible()
    server.expires_at = time.monotonic() - 1
    page.get_by_role('button', name='预览变更', exact=True).click()  # Answered 401 session_expired.
    locked(page, expect, EXPIRED)
    page.reload()  # Nothing is stored, so a reload offers the plain gate.
    expect(page.locator('#gate')).to_be_visible()
    expect(page.locator('#gate-reason')).to_be_hidden()
    assert stored(page) is None
    assert not errors
    context.close()


def test_lock_during_a_refresh_stays_locked(console, monkeypatch):
    server, browser, expect = console
    context = browser.new_context()
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#token=' + server.token)
    ready(page, expect)
    answered, original = threading.Event(), webapp.mg.recent_jobs
    def slow_jobs(router):
        time.sleep(1.5)
        try:
            return original(router)
        finally:
            answered.set()
    monkeypatch.setattr(webapp.mg, 'recent_jobs', slow_jobs)
    page.get_by_role('button', name='刷新状态 ↻').click()
    page.get_by_role('button', name='锁定界面', exact=True).click()
    locked(page, expect)
    assert answered.wait(10)
    page.wait_for_timeout(500)  # The late answers for the old bearer have arrived.
    locked(page, expect)
    assert not errors
    context.close()


def test_section_is_restored_after_reload_and_back_moves_between_sections(console):
    server, browser, expect = console
    context = browser.new_context()
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#token=' + server.token)
    ready(page, expect)
    page.get_by_role('button', name='工具目录', exact=True).click()
    ready(page, expect, TOOLS)
    assert stored(page, SECTION) == 'tools'
    page.reload()
    ready(page, expect, TOOLS)
    expect(page.locator('[data-nav=tools]')).to_have_class('active')
    page.get_by_role('button', name='连接与凭证', exact=True).click()
    ready(page, expect, CONNECTIONS)
    page.go_back(); ready(page, expect, TOOLS)
    page.go_back(); ready(page, expect, OVERVIEW)
    assert stored(page, SECTION) == 'overview'
    page.go_forward(); ready(page, expect, TOOLS)
    expect(page.locator('[data-nav=tools]')).to_have_class('active')
    assert page.url == server.origin + '/' and not errors
    context.close()


def test_reload_into_another_section_never_paints_the_overview(console):
    server, browser, expect = console
    context = browser.new_context()
    context.add_init_script(SECTION_PROBE)
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#token=' + server.token)
    ready(page, expect)
    assert page.evaluate('window.__painted')[-1] == OVERVIEW + '|overview'
    page.get_by_role('button', name='工具目录', exact=True).click()
    ready(page, expect, TOOLS)
    for _ in range(3):
        page.reload(); ready(page, expect, TOOLS)
        painted = page.evaluate('window.__painted')
        # A neutral placeholder, then only the restored section, in the heading and in the navigation.
        assert painted[-1] == TOOLS + '|tools' and PLACEHOLDER + '|tools' in painted, painted  # Marked before data.
        assert {row.split('|')[0] for row in painted} <= {'', PLACEHOLDER, TOOLS}, painted
        assert {row.split('|')[1] for row in painted} <= {'', 'tools'}, painted
    assert not errors, errors
    context.close()


def test_launch_link_opened_in_an_already_open_tab_is_redeemed(console):
    server, browser, expect = console
    context = browser.new_context()
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#launch=' + server.launch_code())
    ready(page, expect)
    page.get_by_role('button', name='工具目录', exact=True).click()
    ready(page, expect, TOOLS)
    for name in ('launch', 'token'):
        value = server.launch_code() if name == 'launch' else server.token
        # The same tab, so only the fragment changes: the page must still take its normal load path.
        with page.expect_event('load'):
            page.goto(server.origin + '/#' + name + '=' + value)
        ready(page, expect, TOOLS)
        assert page.url == server.origin + '/' and stored(page) == server.token
        assert all(value not in url for url in history(context, page)), history(context, page)
        assert not server.launch_codes  # Redeemed, so it cannot be used again.
    page.evaluate('window.__sameDocument = true')
    page.goto(server.origin + '/#unrelated')  # Any other fragment is not a reason to reload.
    page.wait_for_timeout(300)
    assert page.evaluate('window.__sameDocument') is True and page.url == server.origin + '/#unrelated'
    assert stored(page) == server.token and not errors, errors
    context.close()


def test_unavailable_storage_falls_back_to_page_memory(console):
    server, browser, expect = console
    context = browser.new_context()
    context.add_init_script(BLOCK_STORAGE)
    page = context.new_page(); errors, _ = watch(page, server)
    page.goto(server.origin + '/#launch=' + server.launch_code())
    ready(page, expect)
    assert page.url == server.origin + '/'
    assert page.evaluate('()=>{try{sessionStorage;return false;}catch(e){return e.name==="SecurityError";}}')
    page.get_by_role('button', name='工具目录', exact=True).click()
    expect(page.locator('tbody tr').first).to_be_visible()
    page.reload(); expect(page.locator('#gate')).to_be_visible()
    page.locator('#session-token').fill(server.token)
    page.get_by_role('button', name='连接工作台 →').click()
    ready(page, expect, TOOLS)  # The history entry still names its section.
    page.get_by_role('button', name='锁定界面', exact=True).click()
    expect(page.locator('#gate')).to_be_visible()
    assert not errors, errors
    context.close()
