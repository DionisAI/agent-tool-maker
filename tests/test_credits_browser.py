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


@pytest.mark.browser
@pytest.mark.parametrize("width", [1440, 390], ids=["desktop", "mobile"])
def test_credits_panel_refresh_busy_state_and_renewal_day(tmp_path, width):
    from playwright.sync_api import sync_playwright, expect
    chrome = os.environ.get("ATM_CHROMIUM") or shutil.which("chromium")
    if not chrome:
        pytest.skip("Native Chromium path not supplied")
    router = Router(tmp_path / "state")
    fakes = Fakes(tmp_path)
    tools = definitions(router.state.home)
    for tool_id in ["pippit.cli.credit_balance", "higgsfield.subscription.account"]:
        install_tool(router, tools[tool_id])
    fakes.bind(router, "pippit-tool-cli")
    fakes.bind(router, "higgsfield")
    fakes.output("pippit-tool-cli", {"total_remain_amount": "4321"})
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
            expect(higgsfield).to_contain_text("读取失败 · cli_failed")
            expect(higgsfield).to_contain_text("未设置续期日")
            assert higgsfield.locator("[data-brand=higgsfield] img").count() == 1
            tripo = page.locator(".credit-card[data-provider=tripo_studio]")
            expect(tripo).to_contain_text("tripo.studio.account / tripo.server.account")
            assert tripo.get_by_role("button", name="刷新", exact=True).count() == 0
            xyq = page.locator(".credit-card[data-provider=xyq]")
            expect(xyq).to_contain_text("尚未读取")
            expect(xyq).to_contain_text("CLI · pippit.cli.credit_balance")

            gate = fakes.root / "pippit-tool-cli.gate"
            gate.write_text("hold")
            xyq.get_by_role("button", name="刷新", exact=True).click()
            busy = page.locator(".credit-card[data-provider=xyq]").get_by_role("button", name="刷新中…", exact=True)
            expect(busy).to_be_disabled()
            deadline = time.time() + 15
            while not (fakes.root / "pippit-tool-cli.started").exists() and time.time() < deadline:
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

            xyq.get_by_role("button", name="设置续期日", exact=True).click()
            expect(page.locator("#modal-body")).to_contain_text("供应商目前不提供续期日期")
            page.get_by_label("每月续期日").fill("0")
            page.locator("#modal").get_by_role("button", name="保存", exact=True).click()
            expect(page.locator("#toast")).to_contain_text("1–31")
            page.get_by_label("每月续期日").fill("31")
            page.locator("#modal").get_by_role("button", name="保存", exact=True).click()
            expected = credits.next_cycle(31, date.today()).isoformat()
            expect(xyq).to_contain_text("下次续期 " + expected + "（你设置的）")
            assert State(server.home).setting("credits_cycle:xyq") == {"day": 31}
            if os.environ.get("ATM_SCREENSHOT_DIR"):
                out = Path(os.environ["ATM_SCREENSHOT_DIR"])
                out.mkdir(parents=True, exist_ok=True)
                page.locator("footer").evaluate("e=>e.textContent='隔离测试状态 · 假 CLI · 没有供应商请求'")
                panel.screenshot(path=str(out / f"credits-{width}.png"))
            xyq.get_by_role("button", name="设置续期日", exact=True).click()
            page.locator("#modal").get_by_role("button", name="清除", exact=True).click()
            expect(xyq).to_contain_text("未设置续期日")

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
