"""Native Chromium: the Fake-IP refusal in D11, the C6 confirm and the 设置 › 高级 switch.

Isolated FAKE console home. The login endpoint runs the real server code with an injected fake resolver
(Shadowrocket's 198.18.0.x answers) and an httpx MockTransport: no DNS query, no OAuth host, no browser window.
"""
from functools import partialmethod
import json
import re
import time

import httpx
import pytest

import console_fixture as fx
from agent_tool_maker import oauth as oauth_module
from agent_tool_maker import oauth_web
from agent_tool_maker.engine import Router
from agent_tool_maker.network import Network, fake_ip_tunnel, set_fake_ip_tunnel
from agent_tool_maker.oauth import ENDPOINTS, OAuth, PROTECTED_METADATA, SERVER_METADATA
from agent_tool_maker.storage import State
from test_console_redesign_browser import browser, check_dialog, console, go, open_page, opener, posts  # noqa: F401
from test_fake_ip_tunnel import higgsfield_fake_ip
from test_oauth_refresh import Provider

pytestmark = pytest.mark.browser
LEAD = '官方地址被解析成了 198.18.x.x（通常是网络代理的 Fake-IP 模式，例如 Shadowrocket、Clash、Surge）。ATM 默认不连接这类地址，所以没有发出任何请求。'
ALLOWED = '已允许。输入 ATM 主密码后，再点一次“打开官方登录页面”。'  # The fixture vault uses a passphrase.
TITLE = '允许 ATM 连接本机代理给出的 198.18.x.x 地址？'
LABEL = '通过本机代理的 Fake-IP 连接（198.18.0.0/15）'


def bodies(log, path):
    return [json.loads(body) for method, url, body in log['requests'] if method == 'POST' and url.endswith(path)]


def without_atm_login(info):
    """The owner has not logged in yet: 登录 Higgsfield opens D11."""
    router = Router(info['home'])
    try:
        with router.state.db() as db:
            db.execute('DELETE FROM oauth_connections')
    finally:
        router.close()


@pytest.fixture
def provider(monkeypatch):
    """The server's login worker resolves through Fake-IP answers and sends to a fake transport only."""
    fake = Provider()
    monkeypatch.setattr(oauth_web, 'Router', lambda home: Router(home, network=Network(httpx.MockTransport(fake), higgsfield_fake_ip)))
    fake.opened = []
    monkeypatch.setattr(oauth_module.webbrowser, 'open', lambda url: fake.opened.append(url) or True)
    monkeypatch.setattr(OAuth, 'begin_login', partialmethod(OAuth.begin_login, timeout=1))  # The callback listener ends quickly.
    return fake


def answer(error):
    def handle(route):
        route.fulfill(status=400, content_type='application/json', body=json.dumps({'error': error}))
    return handle


def open_login(page, expect):
    go(page, 'services/higgsfield')
    route = page.locator('li.route[data-kind=oauth]')
    route.get_by_role('button', name='登录 Higgsfield', exact=True).click()
    expect(page.locator('#modal-title')).to_have_text('登录 Higgsfield（ATM 登录）')
    page.locator('#modal').get_by_label('ATM 主密码', exact=True).fill(fx.PASSWORD)
    page.locator('#modal').get_by_role('button', name='打开官方登录页面', exact=True).click()


def test_d11_offers_the_switch_and_never_retries_the_login(browser, tmp_path, monkeypatch, provider):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        without_atm_login(info)
        ctx, page, log = open_page(browser, server, info)
        open_login(page, expect)
        alert = page.locator('#modal-alert')
        expect(alert).to_contain_text(LEAD)
        expect(alert).to_have_attribute('role', 'alert')
        expect(alert.locator('details summary')).to_have_text('技术信息')
        expect(alert.locator('details p')).to_contain_text('No OAuth request was sent')
        allow = page.locator('#modal').get_by_role('button', name='允许通过本机代理连接…', exact=True)
        expect(allow).to_be_visible()
        assert len(bodies(log, '/api/oauth/login')) == 1 and provider.requests == [] and provider.opened == []
        assert fake_ip_tunnel(State(info['home'])) is False
        # C6 from the error: 取消 returns to D11 with the same error and switch button.
        allow.click()
        expect(page.locator('#modal-title')).to_have_text(TITLE)
        body = page.locator('#modal-body')
        for term in ['会改变', '不变', '代价', '另一种做法']:
            expect(body.locator('dt', has_text=term)).to_have_count(1)
        for text in ['198.18.0.0/15', 'HTTPS 证书', '直接解析成本机、局域网或其他私有地址的应答', '固定的官方域名', '不能再核对连接的真实目的地址',
                     '由代理决定', 'mcp.higgsfield.ai', 'fake-ip-filter', 'always-real-ip', '以你的用户身份运行的程序']:
            expect(body).to_contain_text(text)
        # Names never break at a hyphen or dot.
        expect(body.locator('code.nowrap')).to_have_text(['mcp.higgsfield.ai', 'clerk.higgsfield.ai', 'fake-ip-filter', 'always-real-ip', 'atm ui', 'SECURITY.md'])
        assert body.locator('code.nowrap').first.evaluate('n => getComputedStyle(n).whiteSpace') == 'nowrap'
        actions = page.locator('#modal-actions button')
        expect(actions).to_have_text(['取消', '允许'])
        expect(page.locator('#modal-actions .primary')).to_have_text('允许')
        # It loosens a check: the focus starts on 取消, not on 允许.
        expect(page.locator('#modal-actions').get_by_role('button', name='取消', exact=True)).to_be_focused()
        page.locator('#modal-actions').get_by_role('button', name='取消', exact=True).click()
        expect(page.locator('#modal-title')).to_have_text('登录 Higgsfield（ATM 登录）')
        expect(alert).to_contain_text(LEAD)
        assert bodies(log, '/api/settings/network') == []
        # 允许: one POST of the setting, a refresh, back to D11 with the success line instead of the error.
        page.locator('#modal').get_by_role('button', name='允许通过本机代理连接…', exact=True).click()
        page.locator('#modal-actions').get_by_role('button', name='允许', exact=True).click()
        expect(page.locator('#modal-title')).to_have_text('登录 Higgsfield（ATM 登录）')
        expect(alert).to_have_text(ALLOWED)
        expect(alert).to_have_attribute('role', 'status')
        expect(page.locator('#modal').get_by_role('button', name='允许通过本机代理连接…')).to_have_count(0)
        # The failed attempt cleared the password: the field is focused, empty and in view.
        password = page.locator('#modal').get_by_label('ATM 主密码', exact=True)
        expect(password).to_be_focused()
        expect(password).to_have_value('')
        expect(password).to_be_in_viewport()
        assert bodies(log, '/api/settings/network') == [{'fake_ip_tunnel': True, 'expected': False}]
        assert fake_ip_tunnel(State(info['home'])) is True and page.evaluate('data.overview.network.fake_ip_tunnel') is True
        # No automatic retry of the login or any other network action.
        page.wait_for_timeout(500)
        assert len(bodies(log, '/api/oauth/login')) == 1 and provider.requests == [] and provider.opened == []
        assert set(posts(log)) == {'/api/oauth/login', '/api/settings/network'}
        # The owner clicks again: now the pinned OAuth requests are sent (to the fake transport) and the browser opens.
        page.locator('#modal').get_by_label('ATM 主密码', exact=True).fill(fx.PASSWORD)
        page.locator('#modal').get_by_role('button', name='打开官方登录页面', exact=True).click()
        expect(page.locator('#modal')).to_be_hidden()
        assert len(bodies(log, '/api/oauth/login')) == 2
        assert [str(r.url) for r in provider.requests] == [PROTECTED_METADATA, SERVER_METADATA, ENDPOINTS['registration_endpoint']]
        assert len(provider.opened) == 1 and provider.opened[0].startswith(ENDPOINTS['authorization_endpoint'] + '?')
        assert fx.PASSWORD not in page.content() and not log['errors'], log['errors']
        ctx.close()
        time.sleep(1.5)  # Let the one-second callback listener close before the home is removed.


def test_hintless_and_already_allowed_errors_show_no_switch(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        without_atm_login(info)
        for state, error, text in [
            (False, {'code': 'oauth_dns_policy', 'message': 'Official OAuth host resolves to a private or reserved address.', 'outcome_uncertain': False},
             'Higgsfield 的官方登录地址被解析成了本机、局域网或其他保留地址。ATM 不连接这类地址，所以没有发出任何请求。'),
            (False, {'code': 'oauth_busy', 'message': 'Busy.', 'outcome_uncertain': False}, '已经有一个登录在进行。'),
            (True, {'code': 'oauth_dns_policy', 'message': 'Fixture.', 'outcome_uncertain': False, 'hint': 'fake_ip_tunnel'}, LEAD)]:
            set_fake_ip_tunnel(State(info['home']), state)
            ctx, page, log = open_page(browser, server, info)
            page.route('**/api/oauth/login', answer(error))  # Answered in the page: nothing reaches the server.
            open_login(page, expect)
            alert = page.locator('#modal-alert')
            expect(alert).to_contain_text(text)
            expect(page.locator('#modal').get_by_role('button', name='允许通过本机代理连接…')).to_have_count(0)
            if error['code'] == 'oauth_dns_policy':
                expect(alert.locator('details p')).to_have_text(error['message'])  # The technical text stays under 技术信息.
            assert bodies(log, '/api/settings/network') == []
            ctx.close()


def test_advanced_switch_confirms_on_and_turns_off_at_once(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        go(page, 'settings/advanced')
        section = page.locator('#network')
        expect(section.locator('h2')).to_have_text('网络')
        switch = page.get_by_role('switch', name=LABEL, exact=True)
        expect(switch).to_have_attribute('aria-checked', 'false')
        expect(switch).to_have_attribute('aria-describedby', 'fake-ip-help fake-ip-state')
        expect(page.locator('#fake-ip-help')).to_contain_text('198.18.x.x')
        expect(page.locator('#fake-ip-state')).to_contain_text('已关闭（默认）')
        # Esc and 取消 close C6 with nothing sent, and the focus returns to the switch.
        check_dialog(page, expect, 'C6', switch, TITLE)
        switch.click()
        page.locator('#modal-actions').get_by_role('button', name='取消', exact=True).click()
        expect(page.locator('#modal')).to_be_hidden()
        expect(page.locator('#main [data-key="network:fake-ip"]')).to_be_focused()
        assert bodies(log, '/api/settings/network') == []
        # On: through C6. The switch is re-rendered, checked, and focused again.
        page.locator('#main [data-key="network:fake-ip"]').click()
        page.locator('#modal-actions').get_by_role('button', name='允许', exact=True).click()
        expect(page.locator('#modal')).to_be_hidden()
        switch = page.locator('#main [data-key="network:fake-ip"]')
        expect(switch).to_have_attribute('aria-checked', 'true')
        expect(switch).to_be_focused()
        expect(page.locator('#fake-ip-state')).to_contain_text('已开启')
        expect(page.locator('#announce')).to_have_text('已允许通过本机代理连接（198.18.0.0/15）。')
        assert fake_ip_tunnel(State(info['home'])) is True
        # Off: at once from the keyboard, with no dialog.
        page.keyboard.press('Space')
        expect(switch).to_have_attribute('aria-checked', 'false')
        expect(page.locator('#modal')).to_be_hidden()
        expect(switch).to_be_focused()
        expect(page.locator('#fake-ip-state')).to_contain_text('已关闭（默认）')
        assert bodies(log, '/api/settings/network') == [{'fake_ip_tunnel': True, 'expected': False}, {'fake_ip_tunnel': False, 'expected': True}]
        assert fake_ip_tunnel(State(info['home'])) is False
        assert not log['errors'], log['errors']
        ctx.close()


def test_a_download_stopped_by_fake_ip_links_to_the_switch(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        state = State(info['home'])
        job_id = fx.job(state, info['workspace'], 'fal.generate', 'download_failed', age=600)
        state.update_job(job_id, 'download_failed', provider_completed=True, error={
            'code': 'unsafe_download', 'message': 'Artifact host resolves to a private, local or special-purpose address.',
            'outcome_uncertain': False, 'hint': 'fake_ip_tunnel'})
        ctx, page, log = open_page(browser, server, info)
        cause = '结果文件的地址被解析成了 198.18.x.x'
        line = page.locator(f'#inbox [data-issue="job-needs:{job_id}"]')
        if not line.count():
            page.get_by_role('button', name='再显示').first.click()
        expect(line).to_contain_text(cause)
        expect(line.get_by_role('button', name='打开网络设置')).to_be_visible()
        go(page, 'jobs')
        page.locator(f'#main [data-key="job:{job_id}"]').click()
        panel = page.locator(f'#job-{job_id}')
        expect(panel).to_contain_text(cause)
        expect(panel).to_contain_text('让 Agent 刷新这个任务重试下载')
        panel.get_by_role('button', name='打开网络设置', exact=True).click()
        expect(page.locator('#main .page-title h1')).to_have_text('设置')
        expect(page.locator('#main [data-key="network:fake-ip"]')).to_be_focused()
        assert posts(log) == [] and not log['errors'], (posts(log), log['errors'])
        # Only the range is named; no resolved address reached the page.
        assert set(re.findall(r'198\.1[89]\.\d+\.\d+(?:/\d+)?', page.content())) <= {'198.18.0.0/15'}
        ctx.close()


def fail_login_then_refresh(page, expect):
    """The real login fails on the Fake-IP answers, the owner closes D11 and refreshes."""
    open_login(page, expect)
    expect(page.locator('#modal-alert')).to_contain_text(LEAD)
    page.keyboard.press('Escape')
    expect(page.locator('#modal')).to_be_hidden()
    page.evaluate('refresh()')
    expect(page.locator('li.route[data-kind=oauth]')).to_contain_text(LEAD)


@pytest.mark.parametrize('width', [1440, 390])
def test_route_and_inbox_allow_then_focus_the_login_again(browser, tmp_path, monkeypatch, provider, width):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        without_atm_login(info)
        ctx, page, log = open_page(browser, server, info, width=width, height=900)
        fail_login_then_refresh(page, expect)
        route = page.locator('li.route[data-kind=oauth]')
        # The code is under 技术信息; the raw "最近一次续期失败" fact is gone.
        expect(route).not_to_contain_text('最近一次续期失败')
        expect(route.locator('details summary', has_text='技术信息')).to_have_count(1)
        # 首页: the line offers the switch, not a login that would fail again.
        go(page, 'overview')
        line = page.locator('#inbox [data-issue="oauth:needs_login"]')
        expect(line).to_contain_text(LEAD)
        expect(line.get_by_role('button', name='允许通过本机代理连接…')).to_be_visible()
        go(page, 'services/higgsfield')
        allow = route.get_by_role('button', name='允许通过本机代理连接…', exact=True)
        # Keyboard: Enter opens C6 on 取消, a second Enter only closes it.
        allow.focus()
        page.keyboard.press('Enter')
        expect(page.locator('#modal-title')).to_have_text(TITLE)
        page.keyboard.press('Enter')
        expect(page.locator('#modal')).to_be_hidden()
        expect(allow).to_be_focused()
        assert bodies(log, '/api/settings/network') == [] and fake_ip_tunnel(State(info['home'])) is False
        allow.click()
        page.locator('#modal-actions').get_by_role('button', name='允许', exact=True).click()
        expect(page.locator('#modal')).to_be_hidden()
        # The allow button is gone; the focus is on the login it unblocked, and the toast says to click it.
        expect(route.get_by_role('button', name='允许通过本机代理连接…')).to_have_count(0)
        expect(page.locator('#main [data-key="route:oauth:oauth:重新登录"]')).to_be_focused()
        expect(page.locator('#toast')).to_have_text('已允许。再点“重新登录”。')
        expect(route).not_to_contain_text(LEAD)
        expect(route.locator('details summary', has_text='技术信息')).to_have_count(0)
        go(page, 'overview')
        expect(line.get_by_role('button', name='重新登录')).to_be_visible()
        # Nothing was retried.
        assert len(bodies(log, '/api/oauth/login')) == 1 and provider.requests == [] and provider.opened == []
        assert bodies(log, '/api/settings/network') == [{'fake_ip_tunnel': True, 'expected': False}]
        assert not log['errors'], log['errors']
        ctx.close()
        time.sleep(1.5)


def test_inbox_allow_returns_focus_to_the_line(browser, tmp_path, monkeypatch, provider):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        without_atm_login(info)
        ctx, page, log = open_page(browser, server, info)
        fail_login_then_refresh(page, expect)
        go(page, 'overview')
        line = page.locator('#inbox [data-issue="oauth:needs_login"]')
        line.get_by_role('button', name='允许通过本机代理连接…').click()
        expect(page.locator('#modal-title')).to_have_text(TITLE)
        page.locator('#modal-actions').get_by_role('button', name='允许', exact=True).click()
        expect(page.locator('#modal')).to_be_hidden()
        expect(page.locator('#main [data-key="inbox:oauth:needs_login"]')).to_be_focused()
        expect(page.locator('#main [data-key="inbox:oauth:needs_login"]')).to_have_text(re.compile('^重新登录'))
        expect(page.locator('#toast')).to_have_text('已允许。再点“重新登录”。')
        assert len(bodies(log, '/api/oauth/login')) == 1 and provider.requests == []
        ctx.close()
        time.sleep(1.5)


@pytest.mark.parametrize('opened_from', ['settings', 'd11'])
def test_allow_when_another_tab_already_allowed(browser, tmp_path, monkeypatch, provider, opened_from):
    """Two writes: the other tab turned it on while C6 was open. The 409 refreshes and counts as allowed."""
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        without_atm_login(info)
        ctx, page, log = open_page(browser, server, info)
        if opened_from == 'settings':
            go(page, 'settings/advanced')
            page.locator('#main [data-key="network:fake-ip"]').click()
        else:
            open_login(page, expect)
            page.locator('#modal').get_by_role('button', name='允许通过本机代理连接…', exact=True).click()
        expect(page.locator('#modal-title')).to_have_text(TITLE)
        set_fake_ip_tunnel(State(info['home']), True, expected=False)  # The other tab.
        page.locator('#modal-actions').get_by_role('button', name='允许', exact=True).click()
        if opened_from == 'settings':
            expect(page.locator('#modal')).to_be_hidden()
            switch = page.locator('#main [data-key="network:fake-ip"]')
            expect(switch).to_have_attribute('aria-checked', 'true')
            expect(switch).to_be_focused()
            expect(page.locator('#toast')).to_have_text('已允许通过本机代理连接（198.18.0.0/15）。')
        else:
            expect(page.locator('#modal-title')).to_have_text('登录 Higgsfield（ATM 登录）')
            expect(page.locator('#modal-alert')).to_have_text(ALLOWED)
        assert bodies(log, '/api/settings/network') == [{'fake_ip_tunnel': True, 'expected': False}]
        assert page.evaluate('data.overview.network.fake_ip_tunnel') is True
        assert fake_ip_tunnel(State(info['home'])) is True and not log['errors'], log['errors']
        ctx.close()
        time.sleep(1.5)
