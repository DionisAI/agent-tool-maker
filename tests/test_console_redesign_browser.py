"""Native Chromium acceptance for the redesigned console (SPEC §19).

Isolated FAKE homes only: fake Keys, fake programs, seeded cached records; no provider, network or OS keyring.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
from urllib.parse import urlsplit

import pytest

import console_fixture as fx
from agent_tool_maker import webapp
from agent_tool_maker.webapp import Console

pytestmark = pytest.mark.browser
WEB = Path(__file__).resolve().parents[1] / 'src/agent_tool_maker/data/web'
FROZEN = {'brands.js': 'b481f1b275403ba43e4a6201a8314f273506ca378e85eb9b8a539fd0569e580b',
          'brand-data.js': '1c7e1d93dbe404e5787349d79cb741529ca1a592e94e8f2cd5cacdabdb3346eb',
          'passkeys.js': '5459e42a5550095a3b45632a6d92990b75e64849df0a6e56e1105d87e181bb9f'}
SECTIONS = ['overview', 'services', 'agents', 'jobs', 'settings']
TABS = ['settings/keys', 'settings/sync', 'settings/tools', 'settings/programs', 'settings/advanced']
NO_CONFIRM = "window.confirm = () => { throw new Error('native confirm is not used'); };"


def chrome():
    path = os.environ.get('ATM_CHROMIUM') or shutil.which('chromium')
    if not path:
        pytest.skip('Native Chromium path not supplied')
    return path


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright, expect
    executable = chrome()
    with sync_playwright() as pw:
        instance = pw.chromium.launch(executable_path=executable, headless=True)
        expect.set_options(timeout=15000)
        yield instance
        instance.close()


@contextmanager
def console(tmp_path, monkeypatch, *, saved=False, empty=False, request=True, sync=True):
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    root = (tmp_path / ('e' if empty else 'b' if saved else 'a' if sync else 'n')).resolve()
    info = fx.build(root, saved_elevenlabs=saved, empty=empty, sync=sync)
    monkeypatch.setenv('PATH', str(info['bin']) + ':/usr/bin:/bin')  # Detection sees only the fixture's programs.
    if request and not empty:
        info['request'] = fx.pending_request(info['home'], info['workspace'])
    server = Console(info['home'], localhost=True, user_home=info['user'])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, info
    finally:
        server.shutdown(); server.server_close(); thread.join(5)


def open_page(browser, server, info=None, *, width=1440, height=1000, init=None, **context):
    ctx = browser.new_context(viewport={'width': width, 'height': height}, **context)
    if init:
        ctx.add_init_script(init)
    page = ctx.new_page()
    page.set_default_timeout(15000)
    log = {'errors': [], 'requests': [], 'console': []}
    page.on('pageerror', lambda e: log['errors'].append(str(e)))
    page.on('console', lambda m: log['console'].append(m.text) if m.type == 'error' else None)
    page.on('request', lambda r: log['requests'].append((r.method, r.url, r.post_data)))
    if info and info.get('request'):
        fx.heartbeat(info['home'], info['request'])
    page.goto(server.origin + '/#token=' + server.token)
    page.wait_for_function("() => { const h = document.querySelector('#main .page-title h1'); return h && !h.textContent.includes('正在连接'); }")
    return ctx, page, log


def posts(log):
    return [urlsplit(url).path for method, url, _ in log['requests'] if method == 'POST']


def go(page, section):
    page.evaluate('s => go(s)', section)
    page.wait_for_timeout(50)


# ---------------------------------------------------------------- A-JOB (viewing; nothing is POSTed)

def test_owner_jobs_from_home_without_any_write(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        # A-JOB-08: the h1, the nav count and the inbox agree; a never-set-up service is not an issue.
        count = page.locator('[data-nav=overview] .nav-count')
        n = int(count.inner_text())
        expect(page.locator('#main .page-title h1')).to_have_text(f'有 {n} 件事需要你处理')
        expect(count).to_have_attribute('aria-label', f'{n} 件事需要你处理')
        page.get_by_role('button', name=re.compile(r'^再显示 \d+ 项$')).click()
        expect(page.locator('#inbox li.issue')).to_have_count(n)
        inbox = page.locator('#inbox')
        for text in ['fal.ai 的 API Key 已过期', 'Exa 的 Key 在两台设备上不一致', 'ffmpeg 程序已更新，需要你重新确认', 'Higgsfield 自动续期没有运行',
                     'Higgsfield 需要重新登录', 'Linear 的 MCP 服务已设置，但缺少 Key：linear', '不确定 tripo.studio.generate 是否已提交']:
            expect(inbox).to_contain_text(text)
        expect(inbox).not_to_contain_text('Runway')
        # A-JOB-06: the pending approval-window request is visible, counted, and cannot be answered here.
        req = page.locator('#home-requests')
        expect(req).to_contain_text('有 Agent 请求在项目 demo-video 中使用 2 个 Key')
        expect(page.locator('[data-nav=agents] .nav-count')).to_have_text('1')
        assert req.locator('button, a').count() == 0
        assert 'Claude Code' not in req.inner_text() and 'Codex' not in req.inner_text()  # The request does not record who asked.
        # A-JOB-07: one credits card per provider row, amounts visible with no click.
        expect(page.locator('#credits-panel .credit-card')).to_have_count(3)
        for provider in ['tripo_studio', 'xyq', 'higgsfield']:
            expect(page.locator(f'.credit-card[data-provider={provider}] .credit-amount')).to_be_visible()
        # A-JOB-01: 服务 → ElevenLabs in two clicks; the Key route says what to do.
        page.locator('[data-nav=services]').click()
        page.locator('#main [data-key="service:elevenlabs"]').click()
        key = page.locator('li.route[data-kind=key]')
        expect(key).to_contain_text('API Key')
        expect(key).to_contain_text('待设置')
        expect(key.get_by_role('button', name='添加 API Key')).to_be_visible()
        key.get_by_role('button', name='添加 API Key').click()
        expect(page.locator('#modal-title')).to_have_text('添加 ElevenLabs 的 API Key')
        page.keyboard.press('Escape')
        # A-JOB-03: the Agent-browser route explains the elevenlabs.web login; D4 and 按工具 say the same.
        browser_route = page.locator('li.route[data-kind=agent_browser]')
        for text in ['不在 ATM 里登录', '在它自己的浏览器里打开', 'elevenlabs.io', '无需在 ATM 设置', '在上面的“API Key”里保存 Key']:
            expect(browser_route).to_contain_text(text)
        page.locator('[data-key="tool:elevenlabs.web"]').first.click()
        expect(page.locator('#modal-body')).to_contain_text('不在 ATM 里登录')
        expect(page.locator('#modal-body')).to_contain_text('任务会显示“等 Agent 的浏览器”')
        page.keyboard.press('Escape')
        go(page, 'services')
        page.get_by_role('button', name='按工具', exact=True).click()
        page.locator('#services-q').fill('elevenlabs.web')
        expect(page.locator('#services-results [data-tool-id="elevenlabs.web"]')).to_contain_text('在 Agent 的浏览器里登录，ATM 里无需设置。')
        page.get_by_role('button', name='按服务', exact=True).click()
        page.locator('#services-q').fill('')
        # A-JOB-02: the top search jumps straight to the service (0 clicks), or to a tool.
        go(page, 'overview')
        page.locator('#global-q').fill('elevenlabs')
        page.locator('#global-q').press('Enter')
        expect(page.locator('#main .page-title h1')).to_have_text('ElevenLabs')
        assert page.evaluate("sessionStorage.getItem('atm-console-section')") == 'services/elevenlabs'
        page.locator('#global-q').fill('elevenlabs.tts')
        page.locator('#global-q').press('Enter')
        expect(page.locator('#tool-elevenlabs\\.tts .tool-title')).to_be_focused()
        # A-JOB-04: Tripo and 小云雀 explain the Chrome login with three steps; a web recipe shows its command.
        go(page, 'services/tripo')
        chrome_route = page.locator('li.route[data-kind=chrome]')
        for text in ['你的 Chrome 登录', 'OpenCLIApp', 'Chrome 里']:
            expect(chrome_route).to_contain_text(text)
        expect(chrome_route.locator('ol.steps > li')).to_have_count(3)
        go(page, 'services/xyq')
        expect(page.locator('li.route[data-kind=chrome]')).to_have_count(1)
        go(page, 'services/fixture')
        expect(page.locator('li.route[data-kind=recipe]')).to_contain_text('atm web login fixture.export')
        # A-JOB-09: Exa's conflict reads 版本冲突 and 选择版本 opens D18.
        go(page, 'services/exa')
        expect(page.locator('li.route[data-kind=key]')).to_contain_text('版本冲突')
        go(page, 'overview')
        page.locator('[data-key="inbox:key-conflict:exa"]').click()
        expect(page.locator('#modal-title')).to_have_text('Exa 的 Key 选哪个版本？')
        expect(page.locator('#modal-body input[type=radio]')).to_have_count(2)
        page.keyboard.press('Escape')
        # A-JOB-13: credits refreshes are hidden by default; an expanded job says how to continue.
        page.locator('[data-nav=jobs]').click()
        jobs = page.locator('#job-list')
        expect(jobs).not_to_contain_text('xyq.web.account')
        page.get_by_label(re.compile(r'^显示额度读取（\d+）$')).check()
        expect(jobs).to_contain_text('xyq.web.account')
        expect(jobs).to_contain_text('读取额度')
        row = page.locator('button.job-row', has_text='elevenlabs.tts')
        row.click()
        expect(row).to_have_attribute('aria-expanded', 'true')
        panel = page.locator('#' + row.get_attribute('aria-controls'))
        expect(panel).to_contain_text('任务编号')
        expect(panel).to_contain_text('atm jobs get ' + row.get_attribute('aria-controls').removeprefix('job-') + ' --refresh')
        expect(panel).to_contain_text(re.compile(r'\$\d+\.\d{2}（[^）]+）'))
        # A-JOB-15: the approved project shows its Keys; revoke opens C3.
        page.locator('[data-nav=agents]').click()
        grant = page.locator('#grants li.grant').first
        expect(grant).to_contain_text('项目 demo-video · 由授权窗口批准')
        expect(grant).to_contain_text('可用 Key：firecrawl、tripo')
        grant.get_by_role('button', name='撤销').click()
        expect(page.locator('#modal-title')).to_have_text('撤销这份授权？')
        page.keyboard.press('Escape')
        # A-JOB-16: the 添加 Key picker preselects nothing.
        page.locator('[data-nav=settings]').click()
        page.locator('#all-keys').get_by_role('button', name='添加 Key', exact=True).click()
        first = page.locator('#modal select option').first
        expect(first).to_have_text('请选择…')
        assert first.evaluate('o => o.disabled && o.selected')
        page.keyboard.press('Escape')
        # A-SEC-06 (in part): all of this was viewing; nothing was POSTed, every request stayed local.
        assert posts(log) == [], posts(log)
        assert all(urlsplit(u).netloc == urlsplit(server.origin).netloc or u.startswith('data:') for _, u, _ in log['requests'])
        assert not log['errors'], log['errors']
        ctx.close()


def test_saved_key_unlock_lock_and_save_in_one_dialog(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, saved=True) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        responses = []
        page.on('response', lambda r: responses.append(r) if '/api/' in r.url else None)
        # A-JOB-01 variant B: the saved Key is ready, with the tools it serves.
        go(page, 'services/elevenlabs')
        key = page.locator('li.route[data-kind=key]')
        expect(key).to_contain_text('可以使用')
        expect(key.get_by_role('button', name='更换', exact=True)).to_be_visible()
        expect(key.locator('dl.facts')).to_contain_text('elevenlabs.tts')
        # A-JOB-10: the pill is the lock control on every section.
        for section in SECTIONS:
            page.locator(f'[data-nav={section}]').click()
            pill = page.locator('#credential-session')
            expect(pill).to_contain_text('已锁定')
            expect(pill.get_by_role('button', name='解锁 30 分钟', exact=True)).to_be_visible()
        page.get_by_role('button', name='解锁 30 分钟', exact=True).click()
        expect(page.locator('#modal-title')).to_have_text('解锁 Key 30 分钟')
        page.get_by_label('ATM 主密码', exact=True).fill(fx.PASSWORD)
        page.get_by_role('button', name='用主密码解锁', exact=True).click()
        expect(page.locator('#credential-session')).to_contain_text('已解锁')
        countdown = page.locator('#lease-countdown')
        expect(countdown).to_have_text(re.compile(r'^\d\d:\d\d$'))
        first = countdown.inner_text(); page.wait_for_timeout(1300)
        assert countdown.inner_text() < first
        assert not page.locator('input[type=password]').evaluate_all('xs => xs.some(x => x.value)')
        # A-JOB-05: a saved Key never reads "needs unlock", locked or not.
        for section in SECTIONS + TABS + ['services/elevenlabs', 'services/tripo']:
            go(page, section)
            expect(page.locator('#main')).not_to_contain_text('需要解锁')
        go(page, 'services')
        page.get_by_role('button', name='按工具', exact=True).click()
        page.locator('#services-q').fill('elevenlabs.tts')
        expect(page.locator('#services-results [data-tool-id="elevenlabs.tts"] .state')).to_have_text('可以使用')
        page.get_by_role('button', name='按服务', exact=True).click()
        page.locator('#services-q').fill('')
        page.get_by_role('button', name='立即锁定', exact=True).click()
        expect(page.locator('#credential-session')).to_contain_text('已锁定')
        assert '/api/session/lock' in posts(log)
        assert page.evaluate('data.session.session_mode_enabled') is True
        # A-JOB-11: locked in session mode, adding a Key unlocks first, in the same dialog.
        go(page, 'services/apify')
        page.locator('li.route[data-kind=key]').get_by_role('button', name='添加 API Key').click()
        steps = page.locator('#modal-steps li')
        expect(steps).to_have_count(2)
        expect(steps.nth(0)).to_contain_text('解锁 Key')
        expect(steps.nth(1)).to_contain_text('填写 Key')
        expect(steps.nth(0)).to_have_attribute('aria-current', 'step')
        page.get_by_label('ATM 主密码', exact=True).fill(fx.PASSWORD)
        page.get_by_role('button', name='用主密码解锁', exact=True).click()
        expect(page.locator('#modal')).to_be_visible()
        expect(steps.nth(1)).to_have_attribute('aria-current', 'step')
        secret = fx.SECRET + '-apify-typed'
        page.get_by_label('API Key', exact=True).fill(secret)
        assert page.get_by_label('ATM 主密码').count() == 0  # Unlocked now: no password for this request.
        page.get_by_role('button', name='加密保存', exact=True).click()
        expect(page.locator('#modal')).to_be_hidden()
        save = [json.loads(body) for method, url, body in log['requests'] if url.endswith('/api/connections/save')]
        assert len(save) == 1 and save[0]['replace'] is False and save[0]['provider'] == 'apify'
        expect(page.locator('li.route[data-kind=key]')).to_contain_text('可以使用')
        # A-SEC-08: no secret or password stays in an input, the DOM, a response, a toast or the console.
        assert not page.locator('input').evaluate_all('xs => xs.some(x => x.value && (x.type === "password" || x.value.includes("FAKE")))')
        content = page.content()
        assert secret not in content and fx.PASSWORD not in content and fx.SECRET not in content
        bodies = [r.text() for r in responses if r.request.method in ('GET', 'POST')]
        assert not any(secret in b or fx.PASSWORD in b or fx.SECRET in b for b in bodies)
        assert not any(secret in m for m in log['console'])
        assert not log['errors'], log['errors']
        ctx.close()


def test_switches_bulk_changes_and_paid_tags(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        ctx, page, log = open_page(browser, server, info, init=NO_CONFIRM)
        go(page, 'services/tripo')
        # A-JOB-12 / A-A11Y-05: a switch flips aria-checked, sends compare-and-set, never confirm().
        switch = page.get_by_role('switch', name='允许 Agent 使用 tripo.studio.generate', exact=True)
        expect(switch).to_have_attribute('aria-checked', 'false')
        switch.click()
        expect(switch).to_have_attribute('aria-checked', 'true')
        toggles = [json.loads(b) for m, u, b in log['requests'] if u.endswith('/api/tools/toggle')]
        assert toggles == [{'tool': 'tripo.studio.generate', 'enabled': True, 'expected_enabled': False}]  # No allow_paid.
        expect(page.locator('#toast')).to_have_text('已允许 tripo.studio.generate。')
        switch.focus(); page.keyboard.press('Space')
        expect(switch).to_have_attribute('aria-checked', 'false')
        expect(switch).to_be_focused()
        for node in page.locator('[role=switch]').all():
            assert node.get_attribute('aria-checked') in ('true', 'false')
            assert node.get_attribute('aria-label').startswith('允许 Agent 使用 ')
        # A-SEC-11: every paid tool is tagged on the service page, in 按工具, in D4 and in D19.
        paid = page.evaluate("[...model.tools.values()].filter(v => v.paid && v.serviceKey === 'tripo').map(v => v.id)")
        assert paid
        for row in page.locator('#tools li.tool-row').all():
            if row.get_attribute('data-tool-id') in paid:
                expect(row.locator('.tag.paid')).to_have_text('可能扣费')
        page.locator('[data-key="tool:tripo.studio.generate"]').first.click()
        expect(page.locator('#modal-body .tag.paid')).to_have_text('可能扣费')
        page.keyboard.press('Escape')
        go(page, 'services')
        page.get_by_role('button', name='按工具', exact=True).click()
        page.get_by_label('只看可能扣费').check()
        for row in page.locator('#services-results [data-tool-id]').all():
            expect(row.locator('.tag.paid')).to_have_text('可能扣费')
        page.get_by_role('button', name='按服务', exact=True).click()
        go(page, 'agents')
        page.get_by_role('button', name='新建受限授权', exact=True).click()
        page.get_by_label('精确工具 ID（逗号分隔）').fill('tripo.studio.generate, ffmpeg.probe, not.a.tool')
        expect(page.locator('#modal-body')).to_contain_text('已识别：tripo.studio.generate')
        expect(page.locator('#modal-body .tag.paid')).to_have_text('可能扣费')
        expect(page.locator('#modal-body')).to_contain_text('不在目录中：not.a.tool')
        page.get_by_label('精确工具 ID（逗号分隔）').fill('ffmpeg.probe')
        page.get_by_label('允许的项目目录').fill(str(info['workspace']))
        page.get_by_role('button', name='检查授权内容', exact=True).click()
        expect(page.get_by_role('button', name='批准并写入', exact=True)).to_be_enabled()
        grant = [json.loads(b) for m, u, b in log['requests'] if u.endswith('/api/access/grant')]
        assert grant and grant[-1]['allow_paid'] is False and 'apply' not in grant[-1]
        page.keyboard.press('Escape')
        # A-JOB-12: 全部停用… asks once (C4), then switches one tool at a time.
        go(page, 'services/xyq')
        group = page.locator('.tool-group', has=page.locator('.group-head', has_text='你的 Chrome 登录'))
        enabled = group.locator('[role=switch][aria-checked=true]').count()
        assert enabled >= 2
        inflight, peak = [0], [0]
        def started(request):
            if request.url.endswith('/api/tools/toggle'):
                inflight[0] += 1; peak[0] = max(peak[0], inflight[0])
        def finished(request):
            if request.url.endswith('/api/tools/toggle'):
                inflight[0] -= 1
        page.on('request', started); page.on('requestfinished', finished)
        group.get_by_role('button', name='全部停用…').click()
        expect(page.locator('#modal-title')).to_have_text(re.compile(r'^停用 你的 Chrome 登录 · 小云雀 的 \d+ 个工具？$'))
        before = len(posts(log))
        page.locator('#modal').get_by_role('button', name='全部停用', exact=True).click()
        expect(page.locator('#modal')).to_be_hidden()
        assert posts(log)[before:] == ['/api/tools/toggle'] * enabled
        assert peak[0] == 1
        expect(page.locator('#main .page-title h1')).to_have_text('小云雀')
        expect(group.locator('[role=switch][aria-checked=true]')).to_have_count(0)
        assert not log['errors'], log['errors']  # window.confirm would have thrown.
        ctx.close()


# ---------------------------------------------------------------- A-SEC

def test_shell_headers_markup_and_frozen_assets(browser, tmp_path, monkeypatch):
    import httpx
    from playwright.sync_api import expect
    index = (WEB / 'index.html').read_text()
    assert '<style' not in index and not re.search(r'\sstyle=', index) and not re.search(r'\son[a-z]+=', index)
    assert all(not body.strip() for body in re.findall(r'<script[^>]*>(.*?)</script>', index, re.S))
    assert 'Agent Tool Maker' in index and '/assets/passkeys.js' in index
    for name in ('app.js', 'model.js'):
        source = (WEB / name).read_text()
        for banned in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write', 'eval(', 'new Function', 'window.confirm', 'document.cookie', 'indexedDB'):
            assert banned not in source, (name, banned)
        assert not re.search(r'\blocalStorage\s*[.\[]', source), name
    app = (WEB / 'app.js').read_text()
    assert 'ATM OAuth' in app and '/api/oauth/login' in app
    for name, digest in FROZEN.items():
        assert hashlib.sha256((WEB / name).read_bytes()).hexdigest() == digest, name
    with console(tmp_path, monkeypatch) as (server, info):
        with httpx.Client(base_url=server.origin, trust_env=False) as client:
            for path in ('/', '/assets/app.js', '/assets/model.js', '/assets/app.css'):
                r = client.get(path)
                assert r.headers['Content-Security-Policy'] == webapp.CSP and r.headers['Cache-Control'] == 'no-store'
        ctx, page, log = open_page(browser, server, info)
        # A-SEC-14: one refresh is exactly the ten bootstrap GETs.
        log['requests'].clear()
        page.get_by_role('button', name='刷新状态').click()
        expect(page.locator('#announce')).to_have_text('已刷新')
        gets = sorted(urlsplit(u).path for m, u, _ in log['requests'] if '/api/' in u)
        assert gets == sorted('/api/' + p for p in ['overview', 'tools', 'connections', 'jobs', 'clis', 'sync', 'access', 'extensions', 'session', 'passkeys'])
        assert page.evaluate('Array.isArray(data.access.requests)')
        # A-SEC-01: the bearer is in this tab's sessionStorage only.
        assert page.evaluate("sessionStorage.getItem('atm-console-token')") == server.token
        assert page.evaluate('localStorage.length') == 0 and page.evaluate('document.cookie') == '' and ctx.cookies() == []
        assert all(server.token not in u for _, u, _ in log['requests'])
        # A-SEC-09: images are the bundled data: URIs only.
        for section in SECTIONS + ['services/tripo']:
            go(page, section)
            assert page.locator('img').evaluate_all("xs => xs.every(x => x.src.startsWith('data:image/svg+xml;base64,'))")
        # A-SEC-04: Back and Forward move between sections, including a service page.
        page.locator('[data-nav=services]').click()
        page.locator('#main [data-key="service:tripo"]').click()
        expect(page.locator('#main .page-title h1')).to_have_text('Tripo3D')
        page.locator('[data-nav=jobs]').click()
        page.go_back(); expect(page.locator('#main .page-title h1')).to_have_text('Tripo3D')
        page.go_back(); expect(page.locator('#main .page-title h1')).to_have_text('服务')
        page.go_forward(); expect(page.locator('#main .page-title h1')).to_have_text('Tripo3D')
        page.reload(); expect(page.locator('#main .page-title h1')).to_have_text('Tripo3D')
        # A-SEC-10: no control answers a request; the console never calls the window's API.
        for section, box in (('overview', '#home-requests'), ('agents', '#requests')):
            go(page, section)
            assert page.locator(box + ' button, ' + box + ' a, ' + box + ' input').count() == 0
        assert not any('/api/desktop' in u for _, u, _ in log['requests'])
        assert not log['errors'], log['errors']
        ctx.close()


def test_removed_payloads_still_render_every_section(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch) as (server, info):
        for missing in ('extensions', 'session', 'passkeys'):
            # Like the mocked multidevice test: that payload is simply absent.
            init = """(() => { const real = window.fetch; window.fetch = async (path, options) => {
              if (path === '/api/%s') return {ok: true, status: 200, json: async () => undefined};
              return real(path, options); }; })();""" % missing
            ctx, page, log = open_page(browser, server, info, init=init)
            for section in SECTIONS + TABS + ['services/tripo']:
                go(page, section)
                expect(page.locator('#main .page-title h1')).to_be_visible()
            assert not log['errors'], (missing, log['errors'])
            ctx.close()


def test_every_api_endpoint_has_a_caller():
    """A-MAP-04: every console endpoint in SPEC §12.14 is called from the page (GET /api/agents and /api/credits stay unused)."""
    app = (WEB / 'app.js').read_text() + (WEB / 'passkeys.js').read_text()
    for path in ['/api/console/redeem', '/api/overview', '/api/tools', '/api/connections', '/api/jobs', '/api/clis', '/api/sync', '/api/access',
                 '/api/extensions', '/api/session', '/api/passkeys', "'/api/tools/'", '/api/session/unlock', '/api/session/lock',
                 '/api/passkeys/register/begin', '/api/passkeys/register/verify', '/api/passkeys/register/finish', '/api/passkeys/auth/begin',
                 '/api/passkeys/cancel', '/api/passkeys/disable', '/api/oauth/login', '/api/oauth/keep-login', '/api/credits/refresh',
                 '/api/credits/cycle', '/api/setup/preview', '/api/setup/apply', '/api/agents/unregister', '/api/tools/toggle', '/api/vault/init',
                 '/api/connections/save', '/api/connections/remove', '/api/verify', '/api/credentials/declare', '/api/extensions/validate',
                 '/api/extensions/install', '/api/sync/init', '/api/sync/trust', '/api/sync/revoke', '/api/sync/export', '/api/sync/import',
                 '/api/sync/resolve', '/api/access/grant', '/api/access/revoke']:
        assert path in app, path
    assert "'/api/agents'" not in app and "'/api/credits'" not in app and '/api/desktop' not in (WEB / 'app.js').read_text()


# ---------------------------------------------------------------- A-MAP-02: every dialog from its opener

def mock(page, path, change):
    """Serve one bootstrap payload with a change (to reach a state the fixture does not hold)."""
    def handle(route):
        response = route.fetch()
        body = response.json()
        change(body)
        route.fulfill(response=response, body=json.dumps(body), headers={**response.headers, 'content-type': 'application/json'})
    page.route('**' + path, handle)


def opener(page, section, locate):
    go(page, section)
    node = locate(page)
    node.scroll_into_view_if_needed()
    return node


DIALOGS = [
    ('D1', 'agents', lambda p: p.get_by_role('button', name='安装到 Codex', exact=True), '安装 ATM 到 Codex'),
    ('D1-cli', 'settings/programs', lambda p: p.locator('[data-program=blender]').get_by_role('button', name='绑定', exact=True), '绑定 blender'),
    ('D2', 'overview', lambda p: p.get_by_role('button', name='解锁 30 分钟', exact=True), '解锁 Key 30 分钟'),
    ('D3', 'overview', lambda p: p.locator('.credit-card[data-provider=tripo_studio] [data-credit-action=cycle]'), '设置续期日 · Tripo Studio'),
    ('D4', 'services/tripo', lambda p: p.locator('[data-key="tool:tripo.text_to_3d"]'), re.compile(r'.+')),
    ('D5', 'services', lambda p: p.get_by_role('button', name='添加自定义 Key', exact=True), '添加自定义 Key'),
    ('D6', 'services', lambda p: p.get_by_role('button', name='安装工具定义', exact=True), '安装工具定义'),
    ('D7', 'services/elevenlabs', lambda p: p.locator('li.route[data-kind=key]').get_by_role('button', name='添加 API Key'), '添加 ElevenLabs 的 API Key'),
    ('D9', 'settings/keys', lambda p: p.get_by_role('button', name='绑定 Passkey', exact=True), '绑定 Passkey'),
    ('D12', 'services/tripo', lambda p: p.locator('li.route[data-kind=key]').get_by_role('button', name='联网测试', exact=True), '联网测试 Tripo3D 的 Key'),
    ('D13', 'services/tripo', lambda p: p.locator('li.route[data-kind=key]').get_by_role('button', name='移除', exact=True), '移除 Tripo3D 的 API Key'),
    ('D14', 'settings/sync', lambda p: p.get_by_role('button', name='导入加密包', exact=True), '导入加密同步包'),
    ('D16', 'settings/sync', lambda p: p.get_by_role('button', name='配对另一台设备', exact=True), '配对另一台设备'),
    ('D17', 'settings/sync', lambda p: p.get_by_role('button', name='导出加密包', exact=True), '导出给 build-server'),
    ('D18', 'services/exa', lambda p: p.locator('li.route[data-kind=key]').get_by_role('button', name='选择版本', exact=True), 'Exa 的 Key 选哪个版本？'),
    ('D19', 'agents', lambda p: p.get_by_role('button', name='新建受限授权', exact=True), '新建受限授权'),
    ('D20', 'settings/sync', lambda p: p.get_by_role('button', name='查看公开身份', exact=True), '本机公开身份（不含任何秘密）'),
    ('C1', 'agents', lambda p: p.locator('[data-agent=claude]').get_by_role('button', name='移除', exact=True), '从 Claude Code 移除 ATM？'),
    ('C2', 'settings/sync', lambda p: p.get_by_role('button', name='撤销信任', exact=True), '撤销对 build-server 的信任？'),
    ('C3', 'agents', lambda p: p.locator('#grants').get_by_role('button', name='撤销', exact=True), '撤销这份授权？'),
    ('C4', 'services/xyq', lambda p: p.get_by_role('button', name='全部停用…').first, re.compile(r'^停用 .+ 的 \d+ 个工具？$')),
    ('C5', 'services/higgsfield', lambda p: p.get_by_role('button', name='停止自动续期', exact=True), '停止 Higgsfield 自动续期？'),
]


def check_dialog(page, expect, name, node, title):
    from playwright.sync_api import expect as _
    key = node.get_attribute('data-key')
    node.click()
    modal = page.locator('#modal')
    expect(modal).to_be_visible()
    expect(page.locator('#modal-title')).to_have_text(title)
    labelled = page.evaluate("document.getElementById(document.getElementById('modal').getAttribute('aria-labelledby')).textContent.trim()")
    assert labelled, name
    assert modal.get_by_role('button', name='关闭', exact=True).count() == 1, name
    page.keyboard.press('Escape')
    expect(modal).to_be_hidden()
    if key:
        expect(page.locator(f'#main [data-key="{key}"]')).to_be_focused()
    else:
        expect(node).to_be_focused()


def test_every_dialog_opens_from_its_opener_and_returns_focus(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        for name, section, locate, title in DIALOGS:
            check_dialog(page, expect, name, opener(page, section, locate), title)
        # The two plans previewed on open are read-only (no network, no change).
        verify = [json.loads(b) for m, u, b in log['requests'] if u.endswith('/api/verify')]
        assert verify and all('allow_network' not in body for body in verify)
        assert set(posts(log)) <= {'/api/setup/preview', '/api/verify'}, posts(log)
        assert not log['errors'], log['errors']
        ctx.close()
        # D10 needs a bound Passkey and D11 a missing ATM login: served as such to this page only.
        ctx, page, log = open_page(browser, server, info)
        mock(page, '/api/passkeys', lambda b: b.update(credentials=[{'id': 'fake-credential', 'label': '1Password', 'disabled': False, 'created_at': 0}]))
        mock(page, '/api/connections', lambda b: b['oauth'][0].update(status='missing', keep_login=False))
        page.get_by_role('button', name='刷新状态').click()
        expect(page.locator('#announce')).to_have_text('已刷新')
        check_dialog(page, expect, 'D10', opener(page, 'settings/keys', lambda p: p.get_by_role('button', name='停用 1Password', exact=True)), '停用 1Password')
        check_dialog(page, expect, 'D11', opener(page, 'services/higgsfield', lambda p: p.locator('li.route[data-kind=oauth]').get_by_role('button', name='登录 Higgsfield', exact=True)),
                     '登录 Higgsfield（ATM 登录）')
        assert posts(log) == []
        ctx.close()
    with console(tmp_path, monkeypatch, empty=True) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        check_dialog(page, expect, 'D8', page.locator('#session-action'), '设置 Key 的保管方式')
        # M39: from the first-run step, both Agents are offered.
        node = page.locator('[data-key="first:agents"]')
        node.click()
        expect(page.locator('#modal fieldset input[type=checkbox]')).to_have_count(2)
        page.keyboard.press('Escape')
        # A-A11Y-08: D8 validation stays inside the dialog: no request and no toast.
        page.locator('#session-action').click()
        page.locator('#modal').get_by_label('ATM 主密码', exact=True).check()
        page.get_by_label('设置 ATM 主密码（至少 12 个字符）', exact=True).fill('fake-long-password-1')
        page.get_by_label('再输入一次', exact=True).fill('fake-long-password-2')
        before = len(posts(log))
        page.get_by_role('button', name='确认设置', exact=True).click()
        expect(page.locator('#modal [role=alert]')).to_have_text('两次输入的 ATM 主密码不一致。')
        expect(page.get_by_label('再输入一次', exact=True)).to_have_attribute('aria-invalid', 'true')
        assert len(posts(log)) == before and page.locator('#toast').is_hidden()
        page.get_by_label('再输入一次', exact=True).fill('fake-long-password-1')
        expect(page.locator('#modal-alert')).to_be_hidden()  # Any change clears it.
        page.keyboard.press('Escape')
        ctx.close()
    with console(tmp_path, monkeypatch, sync=False, request=False) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        check_dialog(page, expect, 'D15', opener(page, 'settings/sync', lambda p: p.get_by_role('button', name='生成本机身份', exact=True)), '生成本机同步身份')
        ctx.close()


# ---------------------------------------------------------------- A-A11Y

CONTRAST = """([fg, bg]) => {
  const rgb = c => { const x = document.createElement('canvas').getContext('2d'); x.fillStyle = '#000'; x.fillStyle = c; x.fillRect(0, 0, 1, 1); return [...x.getImageData(0, 0, 1, 1).data].slice(0, 3); };
  const lum = c => { const [r, g, b] = rgb(c).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }); return .2126 * r + .7152 * g + .0722 * b; };
  const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x); return (a + .05) / (b + .05); }"""
COLOR = "([selector, prop]) => getComputedStyle(document.querySelector(selector))[prop]"
TOKEN = "name => getComputedStyle(document.documentElement).getPropertyValue(name).trim()"


def test_accessibility_rules(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        # A-A11Y-01: no live #main; focus moves to the heading and the title follows the page.
        assert page.locator('#main').get_attribute('aria-live') is None
        assert page.locator('#announce').get_attribute('aria-live') == 'polite'
        titles = {'overview': '首页 · ATM', 'services': '服务 · ATM', 'agents': 'Agent 与权限 · ATM', 'jobs': '记录 · ATM', 'settings': 'Key 保管 · 设置 · ATM'}
        for section, title in titles.items():
            page.locator(f'[data-nav={section}]').click()
            assert page.evaluate("document.activeElement === document.querySelector('#main .page-title h1')"), section
            assert page.title() == title
            # A-A11Y-02: exactly one current nav item, marked both ways.
            assert page.locator('[data-nav][aria-current=page]').count() == 1
            assert page.locator('[data-nav].active').get_attribute('data-nav') == section
        go(page, 'services/tripo'); assert page.title() == 'Tripo3D · 服务 · ATM'
        for tab in TABS:
            go(page, tab)
            assert page.locator('nav.subnav [aria-current=page]').count() == 1
        unnamed = """() => [...document.querySelectorAll('#main input, #main select, #main textarea, #modal input, #modal select, #modal textarea')]
            .filter(x => x.type !== 'hidden' && !(x.labels && [...x.labels].some(l => l.textContent.trim())) && !(x.getAttribute('aria-label') || '').trim())
            .map(x => x.outerHTML.slice(0, 80))"""
        nameless = """() => [...document.querySelectorAll('button')].filter(b => !(b.getAttribute('aria-label') || b.textContent).trim()).map(b => b.outerHTML.slice(0, 80))"""
        glyphless = """() => [...document.querySelectorAll('#main .glyph, #modal .glyph')].filter(g => {
              const host = g.closest('li, .state, .route-chip, .keychip, p, .choice, .credit-card'); return !host || !host.textContent.trim(); }).length"""
        disabled = """() => [...document.querySelectorAll('[aria-disabled=true]')].filter(x => x.offsetParent !== null).filter(x => {
              const id = x.getAttribute('aria-describedby'), t = id && document.getElementById(id); return !t || !t.textContent.trim() || t.offsetParent === null; }).map(x => x.textContent)"""
        for section in SECTIONS + TABS + ['services/tripo', 'services/higgsfield', 'services/elevenlabs']:
            go(page, section)
            assert page.evaluate(unnamed) == [], section
            assert page.evaluate(nameless) == [], section
            assert page.evaluate(glyphless) == 0, section
            assert page.evaluate(disabled) == [], section
            for chip in page.locator('#main .route-strip:not(.large) .route-chip').all():
                assert '：' in chip.text_content()  # A-A11Y-04: the word is there, visually hidden.
        for name, section, locate, title in [d for d in DIALOGS if d[0] in ('D7', 'D16', 'D19', 'D6', 'D13')]:
            opener(page, section, locate).click()
            expect(page.locator('#modal')).to_be_visible()
            assert page.evaluate(unnamed) == [], name
            labels = page.evaluate("() => [...document.querySelectorAll('#modal-body input, #modal-body select, #modal-body textarea')].filter(x => x.offsetParent !== null).every(x => x.labels && x.labels.length && [...x.labels].every(l => l.offsetParent !== null))")
            assert labels, name  # Dialog fields have visible labels.
            assert page.evaluate(disabled) == [], name
            page.keyboard.press('Escape')
        # A-A11Y-07: the focus ring is a solid 2 px outline on buttons, links, inputs and switches.
        go(page, 'services/tripo')
        ring = "e => { const s = getComputedStyle(e); return e.matches(':focus-visible') && s.outlineStyle === 'solid' && parseFloat(s.outlineWidth) >= 2; }"
        page.keyboard.press('Tab')
        for _ in range(80):
            tag = page.evaluate('document.activeElement.tagName + "." + (document.activeElement.getAttribute("role") || document.activeElement.className)')
            assert page.evaluate('() => document.activeElement === document.body') or page.evaluate(f'({ring})(document.activeElement)'), tag
            page.keyboard.press('Tab')
        ctx.close()
        # A-JOB-14 / A-A11Y-06: an unavailable Passkey stays focusable with a visible reason.
        ctx, page, log = open_page(browser, server, info, init='delete window.PublicKeyCredential;')
        go(page, 'settings/keys')
        bind = page.get_by_role('button', name='绑定 Passkey', exact=True)
        expect(bind).to_have_attribute('aria-disabled', 'true')
        expect(bind).to_have_attribute('aria-describedby', 'passkey-reason')
        expect(page.locator('#passkey-reason')).to_have_text('这个浏览器不支持带加密扩展（PRF）的 Passkey。')
        bind.click(force=True)  # Still focusable and clickable: it only points at the reason.
        expect(page.locator('#modal')).to_be_hidden()
        expect(page.locator('#passkey-reason')).to_be_focused()
        assert page.evaluate(disabled) == []
        ctx.close()
        # A-A11Y-10: reduced motion turns every transition and animation off.
        ctx, page, log = open_page(browser, server, info, reduced_motion='reduce')
        assert page.evaluate(COLOR, ['#refresh', 'transitionDuration']) in ('0s',)
        assert page.evaluate(COLOR, ['#nav button', 'transitionDuration']) == '0s'
        page.evaluate("document.getElementById('refresh').setAttribute('aria-busy','true')")
        assert page.evaluate(COLOR, ['#refresh svg', 'animationDuration']) == '0s'
        page.get_by_role('button', name='解锁 30 分钟', exact=True).click()
        assert page.evaluate(COLOR, ['#modal', 'animationDuration']) == '0s'
        ctx.close()
        # A-A11Y-11: text and control colours meet the contrast targets in light and dark.
        for scheme in ('light', 'dark'):
            ctx, page, log = open_page(browser, server, info, color_scheme=scheme)
            go(page, 'services/higgsfield')
            ratio = lambda fg, bg: page.evaluate(CONTRAST, [fg, bg])
            paper, surface = page.evaluate(TOKEN, '--paper'), page.evaluate(TOKEN, '--surface')
            assert ratio(page.evaluate(COLOR, ['body', 'color']), page.evaluate(COLOR, ['body', 'backgroundColor'])) >= 7
            assert ratio(page.evaluate(COLOR, ['.lede', 'color']), paper) >= 4.5
            for state in ('ready', 'attention', 'blocked', 'setup', 'handoff'):
                selector = f'#main .state[data-state={state}]'
                if page.locator(selector).count():
                    assert ratio(page.evaluate(COLOR, [selector, 'color']), surface) >= 4.5, (scheme, state)
            go(page, 'services/tripo')
            assert ratio(page.evaluate(COLOR, ['.tag.paid', 'color']), page.evaluate(COLOR, ['.tag.paid', 'backgroundColor'])) >= 4.5
            assert ratio(page.evaluate(COLOR, ['#main .plain', 'color']), paper) >= 4.5
            go(page, 'services/elevenlabs')
            assert ratio(page.evaluate(COLOR, ['#main .primary', 'color']), page.evaluate(COLOR, ['#main .primary', 'backgroundColor'])) >= 4.5
            assert ratio(page.evaluate(TOKEN, '--control'), surface) >= 3 and ratio(page.evaluate(TOKEN, '--focus'), paper) >= 3
            ctx.close()


def test_keyboard_only_path_saves_a_key(browser, tmp_path, monkeypatch):
    """A-A11Y-09: skip link → search → service page → 添加 API Key → save, without a pointer."""
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch, request=False) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.className') == 'skip-link'
        page.keyboard.press('Enter')
        assert page.evaluate("document.activeElement.id") == 'main'
        page.keyboard.press('/')
        assert page.evaluate("document.activeElement.id") == 'global-q'
        page.keyboard.type('elevenlabs'); page.keyboard.press('Enter')
        expect(page.locator('#main .page-title h1')).to_have_text('ElevenLabs')
        for _ in range(60):
            page.keyboard.press('Tab')
            if page.evaluate('document.activeElement.textContent') == '添加 API Key':
                break
        assert page.evaluate('document.activeElement.textContent') == '添加 API Key'
        page.keyboard.press('Enter')
        expect(page.locator('#modal-title')).to_have_text('添加 ElevenLabs 的 API Key')
        assert page.evaluate('document.activeElement.type') == 'password'
        page.keyboard.type(fx.SECRET + '-keyboard')
        for _ in range(8):
            page.keyboard.press('Tab')
            if page.evaluate("document.activeElement.autocomplete") == 'current-password':
                break
        page.keyboard.type(fx.PASSWORD)
        for _ in range(8):
            page.keyboard.press('Tab')
            if page.evaluate('document.activeElement.textContent') == '加密保存':
                break
        page.keyboard.press('Enter')
        expect(page.locator('#modal')).to_be_hidden()
        expect(page.locator('li.route[data-kind=key]')).to_contain_text('可以使用')
        assert fx.SECRET + '-keyboard' not in page.content()
        ctx.close()


# ---------------------------------------------------------------- A-RESP

ONE_LINE = "e => { const r = document.createRange(); r.selectNodeContents(e.firstChild); return r.getClientRects().length === 1; }"
FILLS_ROW = "g => Math.abs(g.lastElementChild.getBoundingClientRect().right - g.getBoundingClientRect().right) < 2"
ONE_ROW = "g => new Set([...g.children].map(c => Math.round(c.getBoundingClientRect().top))).size === 1"


@pytest.mark.parametrize('width', [1440, 1024, 768, 390, 320])
def test_layout_at_every_width(browser, tmp_path, monkeypatch, width):
    from playwright.sync_api import expect
    with console(tmp_path, monkeypatch) as (server, info):
        ctx, page, log = open_page(browser, server, info, width=width, height=900 if width > 500 else 780)
        wider = ("() => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 0.5 && e.offsetParent !== null)"
                 ".map(e => e.tagName + '.' + e.className + ':' + (e.textContent || '').slice(0, 40)).slice(0, 5)")
        fits = lambda: page.evaluate('document.documentElement.scrollWidth <= innerWidth') or pytest.fail('wider than the page: ' + str(page.evaluate(wider)))
        credits = page.locator('#credits-panel .credits-grid')
        assert credits.evaluate(FILLS_ROW) or width == 768  # Two columns at tablet width: the third card wraps.
        assert credits.evaluate(ONE_ROW) is (width >= 1024)
        for amount in page.locator('.credit-amount').all():
            assert amount.evaluate(ONE_LINE)
        pages = SECTIONS + TABS + ['services/tripo', 'services/elevenlabs']
        for section in pages:
            go(page, section)
            assert fits(), section
            if width < 768:
                assert page.locator('#main table').evaluate_all('xs => xs.filter(x => x.offsetParent !== null).length') == 0, section
        go(page, 'services')
        page.get_by_role('button', name='按工具', exact=True).click()
        assert fits()
        assert (page.locator('#main table.tools').count() == 1) is (width >= 768)
        page.get_by_role('button', name='按服务', exact=True).click()
        go(page, 'jobs')
        page.locator('button.job-row').first.click()
        assert fits()
        if width < 768:  # A-RESP-02: every tab is on screen without scrolling.
            for nav in page.locator('#nav button').all():
                box = nav.bounding_box()
                assert box and box['x'] >= 0 and box['x'] + box['width'] <= width + 1
        for name, section, locate, title in [d for d in DIALOGS if d[0] in ('D7', 'D19')]:
            opener(page, section, locate).click()
            expect(page.locator('#modal')).to_be_visible()
            page.wait_for_timeout(250)
            assert fits(), name
            if width < 768:  # A bottom sheet.
                box = page.locator('#modal').bounding_box()
                assert abs(box['y'] + box['height'] - page.viewport_size['height']) <= 1, box
            page.keyboard.press('Escape')
        assert not log['errors'], log['errors']
        ctx.close()


def test_touch_targets_under_a_coarse_pointer(browser, tmp_path, monkeypatch):
    """A-RESP-04: at 390 px with touch, every visible button and switch is at least 44 x 44."""
    with console(tmp_path, monkeypatch) as (server, info):
        ctx, page, log = open_page(browser, server, info, width=390, height=844, has_touch=True, is_mobile=True)
        assert page.evaluate("matchMedia('(pointer: coarse)').matches")
        small = """() => [...document.querySelectorAll('button, [role=switch]')].filter(b => b.offsetParent !== null && !b.closest('dialog:not([open])'))
            .map(b => [b.textContent.trim() || b.getAttribute('aria-label'), b.getBoundingClientRect()]).filter(([, r]) => r.width && (r.width < 43.5 || r.height < 43.5))
            .map(([t, r]) => t + ' ' + Math.round(r.width) + 'x' + Math.round(r.height))"""
        for section in SECTIONS + ['services/tripo', 'settings/sync', 'settings/programs']:
            go(page, section)
            assert page.evaluate(small) == [], section
        ctx.close()


# ---------------------------------------------------------------- A-MAP-01: nothing from the old console is unreachable

# (probe id, click path from 首页, selector, text that must be there). Probes that need an action
# are checked by the named tests in this file and in the suites listed in SPEC §18.
PROBES = [
    ('M01', 'overview', '[aria-label="Agent Tool Maker"]', None),
    ('M04', 'overview', '#version', 'ATM v'),
    ('M05', 'overview', '#origin', 'localhost'),
    ('M06', 'overview', '#lock', '退出管理台'),
    ('M07', 'overview', '#refresh', '刷新'),
    ('M08', 'overview', 'footer.foot', 'ATM 本地管理 · CLI 与网页共用状态 · 不提供云端远程控制'),
    ('M10', 'jobs', '#main .page-title h1', '记录'),
    ('M17', 'overview', '#credential-session', '已锁定'),
    ('M18', 'agents', '#session-action', '解锁 30 分钟'),
    ('M22', 'settings/keys', '#unlock-panel', '固定 30 分钟'),
    ('M23', 'services', '#main .page-title .lede', '个可以使用'),
    ('M23', 'agents', '#reach', '个工具允许使用'),
    ('M23', 'settings/keys', '#all-keys', '个已保存'),
    ('M23', 'jobs', '#main .segmented', '全部 · '),
    ('M24', 'overview', '#credits-panel', '与开发者 API 余额分开计费'),
    ('M24', 'overview', '#credits-panel', '网站来源会读取本机已登录的浏览器'),
    ('M26', 'overview', '.credit-card[data-provider=tripo_studio] .credit-source[title="tripo.studio.account"]', None),
    ('M27', 'overview', '.credit-card[data-provider=higgsfield] .credit-meta', '超过 24 小时'),
    ('M29', 'overview', '[data-credit-action=cycle]', '设置续期日'),
    ('M30', 'overview', '[data-credit-action=refresh]', '刷新'),
    ('M33', 'jobs', '#main .toolbar', '显示额度读取'),
    ('M34', 'overview', '#home-agents', 'Codex'),
    ('M34', 'agents', '#agents-list', 'Claude Code'),
    ('M35', 'overview', '#main .footnote', '查看本页不会调用任何服务，也不会运行工具。'),
    ('M36', 'services/tripo', '#main .page-title h1', 'Tripo3D'),
    ('M38', 'settings/advanced', '#about', '/atm'),
    ('M40', 'agents', '#agents-list [data-brand=claude]', None),
    ('M41', 'agents', '#agents-list', '已安装 ATM · 新开的会话会加载'),
    ('M41', 'agents', '#agents-list', '还没安装 ATM'),
    ('M42', 'agents', '#agents-list', '已在本机找到'),
    ('M43', 'agents', '#agents-list', 'agent-tool-maker/SKILL.md'),
    ('M46', 'agents', '#agent-commands', 'atm setup --apply'),
    ('M48', 'settings/programs', '[data-program=claude]', 'claude'),
    ('M48', 'settings/programs', '[data-program=codex]', 'codex'),
    ('M49', 'settings/programs', '[data-program=ffmpeg] [data-brand=ffmpeg] img', None),
    ('M50', 'services/tripo', '#tools', '停用只阻止新的调用'),
    ('M64', 'services', '#main .page-actions', '添加自定义 Key'),
    ('M66', 'services', '#main .page-actions', '安装工具定义'),
    ('M67', 'settings/tools', '#make-tools', 'atm make pack'),
    ('M68', 'settings/tools', '#installed-tools', 'tripo.studio.account'),
    ('M69', 'settings/keys', '#web-sessions', 'fixture-login'),
    ('M70', 'settings/tools', '#custom-keys', 'acme.production'),
    ('M72', 'settings/keys', '#vault-panel', '已设置。不要重新设置'),
    ('M73', 'settings/keys', '#passkeys-panel', '绑定 Passkey'),
    ('M74', 'services/higgsfield', 'li.route[data-kind=oauth]', 'ATM 登录 · Higgsfield MCP'),
    ('M76', 'services/exa', 'li.route[data-kind=key]', '版本冲突'),
    ('M81', 'services/tripo', 'li.route[data-kind=key] dl.facts', '到期'),
    ('M84', 'settings/sync', '#sync-device', 'laptop'),
    ('M86', 'settings/sync', '#sync-device', '配对另一台设备'),
    ('M87', 'settings/sync', '#sync-peers', 'build-server'),
    ('M88', 'settings/sync', '#sync-peers', '导出加密包'),
    ('M90', 'settings/sync', '#sync-conflicts', '选择版本'),
    ('M91', 'settings/sync', '#sync-commands', 'atm sync exchange'),
    ('M92', 'agents', '#grants', '新建受限授权'),
    ('M93', 'settings/advanced', '#broker', 'atm broker serve'),
    ('M94', 'agents', '#grants', '可用 Key：'),
    ('M95', 'agents', '#agent-commands', '不是系统级隔离'),
    ('M96', 'jobs', '#main .page-title .lede', '最近 50 个任务'),
]
COVERED = {  # Action probes: where they are exercised.
    'M02 English decor gone': 'test_probes_from_home', 'M03 legacy sections': 'test_console_token_browser legacy test',
    'M09 phone tabs': 'test_layout_at_every_width', 'M11 gate reasons': 'test_console_token_browser', 'M12 placeholder': 'test_console_token_browser',
    'M13 no aria-live': 'test_accessibility_rules', 'M14 Esc focus': 'test_every_dialog_opens_from_its_opener_and_returns_focus',
    'M15 no confirm()': 'test_shell_headers_markup_and_frozen_assets', 'M19-M21 countdown and lock': 'test_saved_key_unlock_lock_and_save_in_one_dialog',
    'M25 M28 M31 M32 credits': 'test_credits_browser', 'M39 M44 M45 M100-M114 dialogs': 'test_every_dialog_opens_from_its_opener_and_returns_focus',
    'M47 programs listed': 'test_probes_from_home', 'M51-M63 tool views': 'test_probes_from_home', 'M71 picker': 'test_owner_jobs_from_home_without_any_write',
    'M75 Key search': 'test_brand_logos_browser', 'M79 verify plan': 'test_every_dialog_opens_from_its_opener_and_returns_focus',
    'M97-M99 records': 'test_owner_jobs_from_home_without_any_write', 'M115 M116 toasts and gate': 'test_console_token_browser',
    'M117 approval window': 'test_quickstart_v08 / test_passkeys_browser / acceptance',
}


def click_path(page, path):
    page.locator('[data-nav=overview]').click()
    top, _, sub = path.partition('/')
    page.locator(f'[data-nav={top}]').click()
    if top == 'services' and sub:
        page.locator(f'#main [data-key="service:{sub}"]').first.click()
    if top == 'settings' and sub:
        label = {'keys': 'Key 保管', 'sync': '设备同步', 'tools': '添加工具', 'programs': '本机程序', 'advanced': '高级'}[sub]
        page.locator('nav.subnav').get_by_role('button', name=label, exact=True).click()


def test_probes_from_home(browser, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    assert COVERED
    with console(tmp_path, monkeypatch) as (server, info):
        ctx, page, log = open_page(browser, server, info)
        for probe, path, selector, text in PROBES:
            click_path(page, path)
            node = page.locator(selector).first
            expect(node, probe).to_be_attached()
            if text:
                expect(node, probe).to_contain_text(text)
        # M02: none of the old English decoration is left.
        for section in SECTIONS + TABS:
            go(page, section)
            text = page.locator('#main').inner_text() + page.locator('#gate').text_content()
            for decor in ['WORKSPACE', 'LOCAL FIRST', 'AGENT TOOL MAKER / YOUR LOCAL WORKSHOP', 'YOUR CONTROL LOOP', 'PRIVATE SESSION', 'SECRETS FIRST', 'LOCKED', 'DEVICE IDENTITY', 'READY', 'CLAUDE CODE / CODEX']:
                assert decor not in text, (section, decor)
        # M47: every known program is listed on 设置 › 本机程序.
        click_path(page, 'settings/programs')
        names = page.evaluate('data.clis.map(c => c.name)')
        listed = page.locator('[data-program]').evaluate_all('xs => xs.map(x => x.dataset.program)')
        assert sorted(names) == sorted(listed)
        # M51-M63: search by capability, the route filter, the disabled filter, five columns, no raw adapter ids as status.
        click_path(page, 'services')
        page.locator('#services-q').fill('speech')
        expect(page.locator('#services-results')).to_contain_text('ElevenLabs')
        page.locator('#services-q').fill('')
        page.locator('#services-route').select_option('chrome')
        expect(page.locator('#services-results')).to_contain_text('Tripo3D')
        expect(page.locator('#services-results')).to_contain_text('小云雀')
        page.locator('#services-route').select_option('')
        page.get_by_role('button', name='按工具', exact=True).click()
        page.get_by_label('工具状态').select_option('off')
        expect(page.locator('#services-results [data-tool-id]')).to_have_count(1)
        expect(page.locator('#services-results [data-tool-id="tripo.studio.generate"]')).to_have_class(re.compile('disabled'))
        expect(page.locator('#tools-count')).to_have_text('1 个工具')
        page.get_by_label('工具状态').select_option('')
        expect(page.locator('table.tools thead th')).to_have_count(5)
        states = page.locator('table.tools tbody td:nth-child(4) .state').all_inner_texts()
        assert states and not set(states) & {'command', 'rest', 'browser', 'mcp', 'web_recipe', 'configured_not_verified'}
        page.locator('#services-q').fill('no-such-tool-anywhere')
        expect(page.locator('#services-results')).to_contain_text('没有符合条件的工具。')
        page.locator('#services-q').fill('tripo.studio')
        click_path(page, 'jobs'); click_path(page, 'services')  # M55: filters survive navigation in this tab.
        expect(page.locator('#services-q')).to_have_value('tripo.studio')
        expect(page.get_by_role('button', name='按工具', exact=True)).to_have_attribute('aria-pressed', 'true')
        # M98: no raw job status code is visible.
        click_path(page, 'jobs')
        for raw in ['submission_unknown', 'requires_browser', 'completed', 'failed']:
            expect(page.locator('#main')).not_to_contain_text(raw)
        assert posts(log) == [] and not log['errors'], (posts(log), log['errors'])
        ctx.close()
