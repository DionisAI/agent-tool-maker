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
