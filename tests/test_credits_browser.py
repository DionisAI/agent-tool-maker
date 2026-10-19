"""Native Chromium over local HTTP/CSP; isolated home, fake CLIs, synthetic cached credits; no provider access."""
from datetime import date
import os
from pathlib import Path
import shutil
import threading
import time
from urllib.parse import urlsplit

import pytest

from agent_tool_maker import credits
from agent_tool_maker.engine import Router
from agent_tool_maker.storage import State
from agent_tool_maker.webapp import Console
from test_subscription_credits import Fakes, HIGGSFIELD, definitions, install_tool

# The number's text node lays out on one line: large numbers shrink rather than break.
ONE_LINE = "e => { const r = document.createRange(); r.selectNodeContents(e.firstChild); return r.getClientRects().length === 1; }"
# The last card ends at the grid's right edge: the cards fill the row.
FILLS_ROW = "g => Math.abs(g.lastElementChild.getBoundingClientRect().right - g.getBoundingClientRect().right) < 2"


def chromium():
    chrome = os.environ.get("ATM_CHROMIUM") or shutil.which("chromium")
    if not chrome:
        pytest.skip("Native Chromium path not supplied")
    return chrome


@pytest.mark.browser
@pytest.mark.parametrize("width", [1440, 390], ids=["desktop", "mobile"])
def test_credits_panel_refresh_busy_state_and_renewal_day(tmp_path, width):
    from playwright.sync_api import sync_playwright, expect
    chrome = chromium()
    router = Router(tmp_path / "state")
    fakes = Fakes(tmp_path)
    tools = definitions(router.state.home)
    for tool_id in ["pippit.cli.credit_balance", "higgsfield.subscription.account"]:
        install_tool(router, tools[tool_id])
    fakes.bind(router, "xyq")
    fakes.bind(router, "higgsfield")
    fakes.output("xyq", {"total_remain_amount": "4321"})
    fakes.output("higgsfield", HIGGSFIELD)
    now = int(time.time())
    # Synthetic cached state: last good value kept after a failed refresh, older than 24h.
    router.state.set_setting("credits:higgsfield", {
        "provider": "higgsfield", "status": "error", "credits": 1234567, "plan": "pro", "unit": "credits",
        "source": "higgsfield.subscription.account", "checked_at": now - 3600, "last_ok_at": now - 3 * 86400,
        "error": {"code": "cli_failed", "message": "Fixture failure."}})
    router.close()
    server = Console(tmp_path / "state", localhost=True, user_home=tmp_path / "user")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chrome, headless=True)
            page = browser.new_page(viewport={"width": width, "height": 1050 if width > 780 else 844})
            page.set_default_timeout(15000)
            expect.set_options(timeout=15000)
            errors, failures, requests, console_errors = [], [], [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("requestfailed", lambda request: failures.append(request.failure))
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.goto(server.origin + "/#token=" + server.token)
            page.get_by_role("heading", name="订阅额度").wait_for()
            panel = page.locator("#credits-panel")
            expect(panel).to_contain_text("与开发者 API 余额分开计费")
            expect(panel).to_contain_text("网站来源会读取本机已登录的浏览器")
            assert not [r for r in requests if r[0] == "POST"] and fakes.calls() == []  # Viewing never runs a tool.

            higgsfield = page.locator(".credit-card[data-provider=higgsfield]")
            expect(higgsfield.locator(".credit-amount")).to_contain_text("1,234,567")
            expect(higgsfield).to_contain_text("pro")
            expect(higgsfield).to_contain_text("CLI · higgsfield.subscription.account")
            expect(higgsfield).to_contain_text("上次读取 3 天前")
            expect(higgsfield).to_contain_text("超过 24 小时")
            # Short label for a known error code; the full message is the badge title.
            error = higgsfield.locator(".credit-meta .badge.bad")
            expect(error).to_have_text("读取失败")
            expect(error).to_have_attribute("title", "Fixture failure.")
            expect(higgsfield).to_contain_text("未设置续期日")
            # The plan badge sits in the meta row, not in the card head.
            expect(higgsfield.locator(".credit-meta .badge").first).to_have_text("pro")
            assert higgsfield.locator(".card-head .badge").count() == 0
            assert higgsfield.locator(".credit-amount").evaluate(ONE_LINE)
            assert higgsfield.locator(".credit-next").count() == 0  # The next refresh runs the stored source.
            assert higgsfield.locator("[data-brand=higgsfield] img").count() == 1
            assert page.locator(".credits-grid").evaluate(FILLS_ROW)
            # Not installed: a compact card with the tool to install and the renewal day only.
            tripo = page.locator(".credit-card[data-provider=tripo_studio]")
            expect(tripo).to_contain_text("tripo.studio.account / tripo.server.account")
            expect(tripo).to_contain_text("未设置续期日")
            expect(tripo.get_by_role("button", name="设置续期日", exact=True)).to_be_visible()
            assert tripo.get_by_role("button", name="刷新", exact=True).count() == 0
            assert tripo.locator(".credit-amount, .credit-meta").count() == 0
            expect(tripo).not_to_contain_text("尚未读取")
            expect(tripo).not_to_contain_text("—")
            xyq = page.locator(".credit-card[data-provider=xyq]")
            expect(xyq).to_contain_text("尚未读取")
            expect(xyq).to_contain_text("CLI · pippit.cli.credit_balance")

            gate = fakes.root / "xyq.gate"
            gate.write_text("hold")
            xyq.get_by_role("button", name="刷新", exact=True).click()
            busy = page.locator(".credit-card[data-provider=xyq]").get_by_role("button", name="刷新中…", exact=True)
            expect(busy).to_be_disabled()
            deadline = time.time() + 15
            while not (fakes.root / "xyq.started").exists() and time.time() < deadline:
                time.sleep(0.02)
            # The rest of the console keeps working while the account tool runs.
            page.get_by_role("button", name="刷新状态 ↻", exact=True).click()
            page.get_by_role("button", name="工具目录", exact=True).click()
            page.get_by_label("搜索工具").fill("pippit.cli")
            expect(page.locator("tbody tr")).to_have_count(1)
            page.get_by_role("button", name="总览", exact=True).click()
            expect(page.locator(".credit-card[data-provider=xyq]").get_by_role("button", name="刷新中…", exact=True)).to_be_disabled()
            gate.unlink()
            xyq = page.locator(".credit-card[data-provider=xyq]")
            expect(xyq.locator(".credit-amount")).to_contain_text("4,321")
            expect(xyq).to_contain_text("上次读取 刚刚")
            expect(xyq.get_by_role("button", name="刷新", exact=True)).to_be_enabled()
            expect(page.locator("#toast")).to_contain_text("订阅额度已更新")
            assert len(fakes.calls()) == 1

            cycle = page.locator(".credit-card[data-provider=xyq] [data-credit-action=cycle]")
            cycle.click()
            expect(page.locator("#modal-body")).to_contain_text("供应商目前不提供续期日期")
            page.keyboard.press("Escape")
            expect(page.locator("#modal")).to_be_hidden()
            expect(cycle).to_be_focused()  # Focus returns to the control that opened the dialog.
            cycle.click()
            day = page.get_by_label("每月续期日")
            # Validation stays inside the dialog: no toast behind the backdrop and no request.
            for value in ["0", "32", "2.5", ""]:
                day.fill(value)
                page.locator("#modal").get_by_role("button", name="保存", exact=True).click()
                expect(page.locator("#modal")).to_be_visible()
                assert day.evaluate("e => e.validationMessage") == "请输入 1–31 的整数。"
            expect(page.locator("#toast")).not_to_contain_text("1–31")
            day.fill("31")
            day.press("Enter")  # Enter in the input submits.
            expected = credits.next_cycle(31, date.today()).isoformat()
            expect(xyq).to_contain_text("下次续期 " + expected + "（你设置的）")
            expect(page.locator("#modal")).to_be_hidden()
            expect(cycle).to_be_focused()  # The re-rendered card's button.
            assert State(server.home).setting("credits_cycle:xyq") == {"day": 31}
            if os.environ.get("ATM_SCREENSHOT_DIR"):
                out = Path(os.environ["ATM_SCREENSHOT_DIR"])
                out.mkdir(parents=True, exist_ok=True)
                page.locator("footer").evaluate("e=>e.textContent='隔离测试状态 · 假 CLI · 没有供应商请求'")
                panel.screenshot(path=str(out / f"credits-{width}.png"))
            cycle.click()
            page.locator("#modal").get_by_role("button", name="清除", exact=True).click()
            expect(xyq).to_contain_text("未设置续期日")
            expect(cycle).to_be_focused()

            assert page.evaluate("document.documentElement.scrollWidth") <= width
            state = State(server.home)
            assert state.setting("credits_cycle:xyq") is None
            assert (state.setting("credits:xyq")["status"], state.setting("credits:xyq")["credits"]) == ("ok", 4321)
            assert state.setting("credits:higgsfield")["credits"] == 1234567  # Not refreshed by this flow.
            assert all(urlsplit(url).netloc == urlsplit(server.origin).netloc or url.startswith("data:") for _, url in requests)
            assert sorted(urlsplit(url).path for method, url in requests if method == "POST") == [
                "/api/credits/cycle", "/api/credits/cycle", "/api/credits/refresh"]
            assert not errors, errors
            assert not failures, failures
            assert not console_errors, console_errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.browser
@pytest.mark.parametrize("width", [1440, 390], ids=["desktop", "mobile"])
def test_credits_refreshes_are_serialized_and_keep_focus(tmp_path, width):
    from playwright.sync_api import sync_playwright, expect
    chrome = chromium()
    router = Router(tmp_path / "state")
    fakes = Fakes(tmp_path)
    tools = definitions(router.state.home)
    for tool_id in ["pippit.cli.credit_balance", "higgsfield.subscription.account", "tripo.studio.account"]:
        install_tool(router, tools[tool_id])
    fakes.bind(router, "xyq")
    fakes.bind(router, "higgsfield")  # opencliapp stays unbound: Tripo Studio shows the bind hint.
    fakes.output("xyq", {"total_remain_amount": "4321"})
    fakes.output("higgsfield", HIGGSFIELD)
    now = int(time.time())
    # Synthetic cached errors; the XYQ value came from the website, the next refresh runs the CLI.
    router.state.set_setting("credits:xyq", {
        "provider": "xyq", "status": "error", "credits": 123456789012, "plan": None, "unit": "credits",
        "source": "xyq.web.account", "checked_at": now - 60, "last_ok_at": now - 120,
        "error": {"code": "fixture_new_code", "message": "Fixture message for an unlisted code."}})
    router.state.set_setting("credits:higgsfield", {
        "provider": "higgsfield", "status": "error", "credits": 5, "plan": "pro", "unit": "credits",
        "source": "higgsfield.subscription.account", "checked_at": now - 60, "last_ok_at": now - 120,
        "error": {"code": "login_required", "message": "Fixture: log in to the CLI first."}})
    router.close()
    server = Console(tmp_path / "state", localhost=True, user_home=tmp_path / "user")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chrome, headless=True)
            page = browser.new_page(viewport={"width": width, "height": 1050 if width > 780 else 844})
            page.set_default_timeout(15000)
            expect.set_options(timeout=15000)
            errors, requests, console_errors = [], [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.goto(server.origin + "/#token=" + server.token)
            page.get_by_role("heading", name="订阅额度").wait_for()
            panel = page.locator("#credits-panel")
            xyq = panel.locator(".credit-card[data-provider=xyq]")
            higgsfield = panel.locator(".credit-card[data-provider=higgsfield]")
            tripo = panel.locator(".credit-card[data-provider=tripo_studio]")
            refresh_all = panel.locator("[data-credit-action=all]")
            xyq_refresh = xyq.locator("[data-credit-action=refresh]")
            higgsfield_refresh = higgsfield.locator("[data-credit-action=refresh]")

            # Error badges: a short label (the code for unlisted ones) and the full message as title.
            expect(xyq.locator(".badge.bad")).to_have_text("读取失败 · fixture_new_code")
            expect(xyq.locator(".badge.bad")).to_have_attribute("title", "Fixture message for an unlisted code.")
            expect(higgsfield.locator(".badge.bad")).to_have_text("需要登录")
            expect(higgsfield.locator(".badge.bad")).to_have_attribute("title", "Fixture: log in to the CLI first.")
            expect(xyq).to_contain_text("网站 · xyq.web.account")
            expect(xyq.locator(".credit-next")).to_have_text("下次刷新读取 CLI")
            expect(xyq.locator(".credit-next")).to_have_attribute("title", "pippit.cli.credit_balance")
            assert higgsfield.locator(".credit-next").count() == 0
            expect(xyq.locator(".credit-amount")).to_contain_text("123,456,789,012")
            assert xyq.locator(".credit-amount").evaluate(ONE_LINE)
            # Installed but unbound: how to bind, and nothing to refresh.
            expect(tripo).to_contain_text("先运行 atm cli bind opencliapp <path> 绑定 CLI")
            assert tripo.locator("[data-credit-action=refresh]").count() == 0
            expect(refresh_all).to_have_text("全部刷新")

            gate = fakes.root / "xyq.gate"
            gate.write_text("hold")
            xyq_refresh.focus()
            page.keyboard.press("Enter")
            expect(xyq_refresh).to_have_text("刷新中…")
            expect(xyq_refresh).to_be_disabled()
            expect(xyq_refresh).to_be_focused()  # Kept across the re-render.
            expect(refresh_all).to_have_text("全部刷新")  # Higgsfield is not busy yet.
            deadline = time.time() + 15
            while not (fakes.root / "xyq.started").exists() and time.time() < deadline:
                time.sleep(0.02)
            higgsfield_refresh.click()
            expect(higgsfield_refresh).to_have_text("刷新中…")
            expect(refresh_all).to_have_text("刷新中…")  # Every refreshable provider is busy now.
            expect(refresh_all).to_be_disabled()
            page.wait_for_timeout(500)
            # Serialized: the queued Higgsfield refresh waits for XYQ, even though the server would allow it.
            assert [c["exe"] for c in fakes.calls()] == ["xyq"]
            assert [urlsplit(url).path for method, url in requests if method == "POST"] == ["/api/credits/refresh"]
            gate.unlink()
            expect(higgsfield.locator(".credit-amount")).to_contain_text("1,234")
            expect(xyq.locator(".credit-amount")).to_contain_text("4,321")
            expect(higgsfield_refresh).to_have_text("刷新")
            expect(higgsfield_refresh).to_be_focused()  # Still the same control after several re-renders.
            assert [c["exe"] for c in fakes.calls()] == ["xyq", "higgsfield"]
            assert xyq.locator(".credit-next, .badge.bad").count() == 0
            expect(refresh_all).to_have_text("全部刷新")

            # The panel re-renders behind an open dialog; closing it focuses the new card's button.
            (fakes.root / "xyq.started").unlink()
            gate.write_text("hold")
            xyq_refresh.click()
            deadline = time.time() + 15
            while not (fakes.root / "xyq.started").exists() and time.time() < deadline:
                time.sleep(0.02)
            xyq.locator("[data-credit-action=cycle]").click()
            expect(page.locator("#modal")).to_be_visible()
            gate.unlink()
            expect(xyq_refresh).to_have_text("刷新")
            page.keyboard.press("Escape")
            expect(page.locator("#modal")).to_be_hidden()
            expect(xyq.locator("[data-credit-action=cycle]")).to_be_focused()

            assert page.evaluate("document.documentElement.scrollWidth") <= width
            assert len(fakes.calls()) == 3
            assert [urlsplit(url).path for method, url in requests if method == "POST"] == ["/api/credits/refresh"] * 3
            assert not errors, errors
            assert not console_errors, console_errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
