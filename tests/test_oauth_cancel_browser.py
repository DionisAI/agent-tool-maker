"""Native Chromium: a pending Higgsfield ATM login explains a refusal and the owner cancels it at once.

Isolated FAKE console home. The login endpoint runs the real server code with the fixture resolver and an httpx
MockTransport: no DNS query, no OAuth host and no browser window. The callback listener keeps its five-minute
deadline, so a second login that starts at once proves the cancel freed it.
"""
import json
import re
import threading
import time

import httpx
import pytest

import console_fixture as fx
from agent_tool_maker import oauth as oauth_module
from agent_tool_maker import oauth_web
from agent_tool_maker.demo import fixture_resolver
from agent_tool_maker.engine import Router
from agent_tool_maker.network import Network
from agent_tool_maker.oauth import ENDPOINTS, PROTECTED_METADATA, SERVER_METADATA
from test_console_redesign_browser import browser, console, go, open_page, posts  # noqa: F401
from test_fake_ip_browser import bodies, without_atm_login
from test_oauth_refresh import Provider

pytestmark = pytest.mark.browser
TITLE = '登录 Higgsfield（ATM 登录）'
OPENED = '已在系统浏览器里打开 Higgsfield 官方页面。请在那里登录并授权，完成后点“刷新状态”。'
CANCELLED = '已取消这次 ATM 登录。可以重新登录，或改用“higgsfield 程序”。'


@pytest.fixture
def provider(monkeypatch):
    fake = Provider()
    monkeypatch.setattr(oauth_web, 'Router', lambda home: Router(home, network=Network(httpx.MockTransport(fake), fixture_resolver)))
    fake.opened = []
    monkeypatch.setattr(oauth_module.webbrowser, 'open', lambda url: fake.opened.append(url) or True)
    yield fake
    deadline = time.monotonic() + 10  # Every test cancels its logins: no listener outlives it.
    while listeners() and time.monotonic() < deadline:
        time.sleep(.05)
    assert not listeners()


def listeners():
    return [t for t in threading.enumerate() if t.name == 'atm-oauth-login']


def inbox(label):
    """A 首页 line's button: its label, then the service name for screen readers."""
    return re.compile('^' + label + r'\s*（Higgsfield）$')


def whole_inbox(page):
    """The fixture holds more than five lines; the pending one (info) sorts last."""
    more = page.locator('[data-key="inbox:more"]')
    if more.count() and more.get_attribute('aria-expanded') == 'false':
        more.click()


def start_login(page, expect, opener):
    opener.click()
    expect(page.locator('#modal-title')).to_have_text(TITLE)
    page.locator('#modal').get_by_label('ATM 主密码', exact=True).fill(fx.PASSWORD)
    page.locator('#modal').get_by_role('button', name='打开官方登录页面', exact=True).click()
    expect(page.locator('#modal-body')).to_contain_text(OPENED)


def test_d11_explains_a_refusal_and_cancels_so_a_new_login_starts_at_once(browser, tmp_path, monkeypatch, provider):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        without_atm_login(info)
        ctx, page, log = open_page(browser, server, info)
        refused = page.evaluate('T.oauth.refused')
        go(page, 'services/higgsfield')
        route = page.locator('li.route[data-kind=oauth]')
        start_login(page, expect, route.get_by_role('button', name='登录 Higgsfield', exact=True))
        # D11 stays open on the pending login: the refusal line, 取消登录 and 刷新状态, and the one 关闭 (×).
        modal = page.locator('#modal')
        expect(modal.locator('#modal-body p.quiet')).to_have_text(refused)
        for word in ('authorization_invalid', 'Unauthorized request', 'higgsfield auth login', '套餐不含 MCP', '部分 OAuth 客户端'):
            assert word in refused, word
        expect(modal.get_by_role('button', name='刷新状态', exact=True)).to_be_focused()
        expect(modal.get_by_role('button', name='取消登录', exact=True)).to_be_visible()
        assert modal.get_by_role('button', name='关闭', exact=True).count() == 1
        assert [str(r.url) for r in provider.requests] == [PROTECTED_METADATA, SERVER_METADATA, ENDPOINTS['registration_endpoint']]
        assert len(provider.opened) == 1 and len(listeners()) == 1
        # 取消登录: one POST, no password, nothing sent to Higgsfield; the listener stops within seconds.
        modal.get_by_role('button', name='取消登录', exact=True).click()
        expect(modal).to_be_hidden()
        expect(page.locator('#toast')).to_have_text(CANCELLED)
        assert bodies(log, '/api/oauth/cancel') == [{'provider': 'higgsfield'}]
        assert len(provider.requests) == 3
        expect(route.locator('.state')).to_have_text('需要重新登录')
        expect(route).to_contain_text('你取消了这次登录。')
        expect(route).not_to_contain_text(refused)
        # The opener is gone; the focus lands on the login to click again.
        again = route.get_by_role('button', name='重新登录', exact=True)
        expect(again).to_be_focused()
        deadline = time.monotonic() + 10
        while listeners() and time.monotonic() < deadline:
            time.sleep(.05)
        assert not listeners()
        # The owner logs in again at once, well before the first login's five-minute deadline.
        page.keyboard.press('Enter')
        expect(page.locator('#modal-title')).to_have_text(TITLE)
        page.locator('#modal').get_by_label('ATM 主密码', exact=True).fill(fx.PASSWORD)
        page.locator('#modal').get_by_role('button', name='打开官方登录页面', exact=True).click()
        expect(page.locator('#modal-body')).to_contain_text(OPENED)
        assert len(provider.opened) == 2 and len(bodies(log, '/api/oauth/login')) == 2
        modal.get_by_role('button', name='取消登录', exact=True).click()
        expect(modal).to_be_hidden()
        assert len(bodies(log, '/api/oauth/cancel')) == 2
        assert not [r for r in provider.requests if str(r.url) == ENDPOINTS['token_endpoint']]
        assert fx.PASSWORD not in page.content() and not log['errors'], log['errors']
        ctx.close()


def test_the_route_and_the_home_line_offer_cancel_while_pending(browser, tmp_path, monkeypatch, provider):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        without_atm_login(info)
        ctx, page, log = open_page(browser, server, info)
        refused = page.evaluate('T.oauth.refused')
        go(page, 'services/higgsfield')
        route = page.locator('li.route[data-kind=oauth]')
        start_login(page, expect, route.get_by_role('button', name='登录 Higgsfield', exact=True))
        page.keyboard.press('Escape')  # Closing D11 leaves the login pending.
        expect(page.locator('#modal')).to_be_hidden()
        expect(route.get_by_role('button', name='刷新状态', exact=True)).to_be_focused()
        expect(route.locator('.route-body>p').first).to_have_text(refused)
        expect(route.locator('.state')).to_have_text('等你在浏览器里确认')
        # 首页: the pending line carries the refusal line and 取消登录 beside 刷新状态.
        go(page, 'overview')
        whole_inbox(page)
        line = page.locator('li.issue[data-issue="oauth-pending:higgsfield"]')
        expect(line.locator('p')).to_contain_text('完成后点“刷新状态”。' + refused)
        expect(line.get_by_role('button', name=inbox('刷新状态'))).to_be_visible()
        cancel = line.get_by_role('button', name=inbox('取消登录'))
        cancel.focus()
        page.keyboard.press('Enter')
        expect(page.locator('#toast')).to_have_text(CANCELLED)
        expect(line).to_have_count(0)
        # The login to click again takes the focus.
        expect(page.locator('li.issue[data-issue="oauth:needs_login"]').get_by_role('button', name=inbox('重新登录'))).to_be_focused()
        assert bodies(log, '/api/oauth/cancel') == [{'provider': 'higgsfield'}]
        # Again from the 首页 line's 重新登录, then 取消登录 on the ATM 登录 route.
        start_login(page, expect, page.get_by_role('button', name=inbox('重新登录')))
        page.keyboard.press('Escape')
        go(page, 'services/higgsfield')
        route.get_by_role('button', name='取消登录', exact=True).click()
        expect(page.locator('#toast')).to_have_text(CANCELLED)
        expect(route.get_by_role('button', name='重新登录', exact=True)).to_be_focused()
        expect(route.get_by_role('button', name='取消登录', exact=True)).to_have_count(0)
        assert len(bodies(log, '/api/oauth/cancel')) == 2 and len(provider.opened) == 2
        assert set(posts(log)) == {'/api/oauth/login', '/api/oauth/cancel'}
        assert not log['errors'], log['errors']
        ctx.close()


def answer(status, body):
    def handle(route):
        route.fulfill(status=status, content_type='application/json', body=json.dumps(body))
    return handle


def test_cancel_outcomes_are_said_plainly(browser, tmp_path, monkeypatch):
    """Answered in the page: a code already at the token endpoint, a login that already ended, a replacement restored."""
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        without_atm_login(info)
        for status, body, said in [
            (400, {'error': {'code': 'oauth_exchanging', 'message': 'Fixture.', 'outcome_uncertain': False}}, None),
            (200, {'provider': 'higgsfield', 'status': 'needs_login', 'action': 'not_pending'}, '这次登录已经结束，不需要取消。状态已刷新。'),
            (200, {'provider': 'higgsfield', 'status': 'ready', 'action': 'cancelled'}, '已取消这次登录，原来的 ATM 登录继续有效。')]:
            ctx, page, log = open_page(browser, server, info)
            page.route('**/api/oauth/login', answer(200, {'provider': 'higgsfield', 'status': 'pending', 'browser_opened': False, 'action': 'preserved'}))
            page.route('**/api/oauth/cancel', answer(status, body))  # Nothing reaches the server.
            go(page, 'services/higgsfield')
            start = page.locator('li.route[data-kind=oauth]').get_by_role('button', name='登录 Higgsfield', exact=True)
            start.click()
            page.locator('#modal').get_by_label('ATM 主密码', exact=True).fill(fx.PASSWORD)
            page.locator('#modal').get_by_role('button', name='打开官方登录页面', exact=True).click()
            expect(page.locator('#modal-body')).to_contain_text('登录窗口没有打开，或者已有一个登录在进行。')
            page.locator('#modal').get_by_role('button', name='取消登录', exact=True).click()
            if said is None:
                # The refusal stays in D11, in Chinese; the dialog stays open on the pending login.
                expect(page.locator('#modal-alert')).to_have_text('Higgsfield 正在确认这次登录，不能再取消。请稍等几秒后点“刷新状态”。')
                expect(page.locator('#modal-body')).to_contain_text('登录窗口没有打开')
            else:
                expect(page.locator('#modal')).to_be_hidden()
                expect(page.locator('#toast')).to_have_text(said)
            assert not log['errors'], log['errors']
            ctx.close()


@pytest.mark.parametrize('width', [390, 320])
def test_pending_views_fit_a_phone(browser, tmp_path, monkeypatch, width):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        ctx, page, log = open_page(browser, server, info, width=width, height=800)
        def pending(body):
            body['oauth'][0].update(status='pending', login_deadline=time.time() + 300, keep_login=False)
        from test_console_redesign_browser import mock
        mock(page, '/api/connections', pending)
        page.evaluate('refresh()')
        go(page, 'overview')
        whole_inbox(page)
        line = page.locator('li.issue[data-issue="oauth-pending:higgsfield"]')
        expect(line.get_by_role('button', name=inbox('取消登录'))).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        go(page, 'services/higgsfield')
        expect(page.locator('li.route[data-kind=oauth]').get_by_role('button', name='取消登录', exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not log['errors'], log['errors']
        ctx.close()
