"""Native Chromium over local HTTP/CSP: the tool catalog says where each tool is set up.
Isolated home, fake CLIs, fake Key and synthetic browser session; no provider access."""
import json
import os
from pathlib import Path
import shutil
import threading

import pytest

from agent_tool_maker.cli_adapter import bind_cli
from agent_tool_maker.engine import Router
from agent_tool_maker.storage import State
from agent_tool_maker.vault import Vault
from agent_tool_maker.web_recipe import save_session
from agent_tool_maker.webapp import Console
from test_subscription_credits import install_tool
from test_web_recipe_v06 import recipe_tool, storage

PASSPHRASE = "BROWSER-TEST-PASSPHRASE"
SECRET = "BROWSER-TEST-ELEVENLABS-KEY"
STUDIO_QUOTE = Path(__file__).resolve().parents[1] / "generated/tripo-studio/quote/manifest.json"
COLUMNS = ["工具 / 能力", "入口", "配置状态", "在哪里设置", "可用开关", "详情"]
PAID = "付费工具：每次运行仍需明确的付费批准"


@pytest.mark.browser
def test_tool_catalog_setup_hints_and_connect_action(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    chrome = os.environ.get("ATM_CHROMIUM") or shutil.which("chromium")
    if not chrome:
        pytest.skip("Native Chromium path not supplied")
    state = State(tmp_path / "state")
    vault = Vault(state, password=PASSPHRASE)
    vault.init("passphrase")
    router = Router(state.home, vault=vault)
    install_tool(router, json.loads(STUDIO_QUOTE.read_text()))  # OpenCLI website tool; opencliapp left unbound.
    recipe = recipe_tool()
    recipe["recipe"]["session"] = "studio"
    install_tool(router, recipe)
    save_session(vault, "studio", ["https://fixture.example"], storage())
    wrangler = tmp_path / "wrangler"
    wrangler.write_text("#!/bin/sh\nexit 0\n")
    wrangler.chmod(0o700)
    bind_cli(router.state, "wrangler", str(wrangler))
    router.close()
    server = Console(tmp_path / "state", localhost=True, user_home=tmp_path / "user")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chrome, headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1050})
            page.set_default_timeout(15000)
            expect.set_options(timeout=15000)
            errors, console_errors, posts = [], [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            # A CSP violation (inline style or script) is reported as a console error.
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("request", lambda request: posts.append(request.url) if request.method == "POST" else None)
            page.goto(server.origin + "/#token=" + server.token)
            page.get_by_role("heading", name="连接一次，持续使用。").wait_for()
            page.get_by_role("button", name="工具目录").click()
            page.get_by_role("heading", name="一个目录，两种 Agent。").wait_for()
            assert page.locator("thead th").all_inner_texts() == COLUMNS
            assert posts == []  # Viewing the hints sends nothing.
            row = lambda tool: page.locator(f'tr[data-tool="{tool}"]')

            # A vault Key that is not saved yet: 去连接, and paid runs still need approval.
            tts = row("elevenlabs.tts")
            expect(tts.locator("[data-step=api_key]")).to_contain_text("API Key · elevenlabs")
            expect(tts.get_by_role("button", name="去连接", exact=True)).to_be_visible()
            expect(tts.locator("[data-step=paid]")).to_have_text(PAID)
            # Host-Agent browser handoff: the login is the Agent's, at the tool's url.
            web = row("elevenlabs.web")
            expect(web.locator("[data-step=browser_handoff]")).to_contain_text("登录在 Agent 自己的浏览器里，ATM 不保存也不验证")
            expect(web.locator("[data-step=browser_handoff] code")).to_have_text("https://elevenlabs.io/app/")
            expect(web.locator("td").nth(2)).to_have_text("交给浏览器")
            expect(web.locator("[data-step=paid]")).to_have_text(PAID)
            assert web.get_by_role("button", name="去连接").count() == 0
            # OpenCLI website tool: the opencliapp alias, not bound yet, uses the logged-in Chrome.
            studio = row("tripo.studio.quote").locator("[data-step=opencli_chrome]")
            expect(studio.locator("code")).to_have_text("atm cli bind opencliapp <path>")
            expect(studio.locator(".badge")).to_have_text("未绑定")
            expect(studio).to_contain_text("经 OpenCLIApp 使用本机已登录的 Chrome")
            assert row("tripo.studio.quote").locator("[data-step=paid]").count() == 0
            # Bound command tool; its optional Key overrides the CLI's own login.
            deploy = row("wrangler.deployments")
            expect(deploy.locator("[data-step=cli_bind] code")).to_have_text("atm cli bind wrangler <path>")
            expect(deploy.locator("[data-step=cli_bind] .badge")).to_have_text("已绑定")
            expect(deploy.locator("[data-step=cli_bind]")).not_to_contain_text("OpenCLIApp")
            expect(deploy.locator("[data-step=api_key]")).to_contain_text("可选 Key · cloudflare（不填则沿用 CLI 自己的登录）")
            # Web recipe: a private-terminal login, and whether a session is saved.
            login = row("fixture.export").locator("[data-step=web_login]")
            expect(login.locator("code")).to_have_text("atm web login fixture.export")
            expect(login.locator(".badge")).to_have_text("登录态已保存 · 未验证")
            expect(login).to_contain_text("在私有终端运行")
            expect(row("comfyui.queue").locator("[data-step=origin] code")).to_have_text(
                "atm origin set comfyui <url> --approve-origin")
            expect(row("figma.mcp_tools").locator("[data-step=mcp] .badge")).to_have_text("未绑定")
            # Sentences wrap inside the hint cell; the table itself stays one line per cell.
            assert web.locator(".setup-hint").evaluate("e => getComputedStyle(e).whiteSpace") == "normal"

            # 去连接 opens the existing connection dialog for this provider and saves through it.
            tts.get_by_role("button", name="去连接", exact=True).click()
            expect(page.locator("#modal-title")).to_have_text("保存一个连接")
            expect(page.get_by_label("连接提供方")).to_have_value("elevenlabs")
            page.get_by_label("API Key / 凭证（仅写入，无法回读）").fill(SECRET)
            page.get_by_label("现有凭证库口令（仅口令模式需要；仅用于本次请求）").fill(PASSPHRASE)
            page.get_by_role("button", name="加密保存", exact=True).click()
            page.locator("#modal").wait_for(state="hidden")
            expect(page.locator("#toast")).to_have_text("已加密保存")
            expect(page.get_by_role("heading", name="一个目录，两种 Agent。")).to_be_visible()
            credential = row("elevenlabs.tts").locator("[data-step=api_key]")
            expect(credential.locator(".badge.good")).to_have_text("已连接")
            assert credential.get_by_role("button", name="去连接").count() == 0
            assert SECRET not in page.content()
            assert not page.locator("input[type=password]").evaluate_all("xs => xs.some(x => !!x.value)")
            fresh = Router(server.home)
            try:
                assert "elevenlabs" in fresh.state.secret_names()
            finally:
                fresh.close()
            # 检查 is the existing account-check preview; nothing reaches the provider without approval.
            credential.get_by_role("button", name="检查", exact=True).click()
            expect(page.locator("#modal-title")).to_have_text("检查 elevenlabs")
            expect(page.get_by_role("button", name="批准本次账户检查")).to_be_visible()
            page.get_by_role("button", name="关闭", exact=True).click()
            page.locator("#modal").wait_for(state="hidden")

            # The toggle is unchanged: one switch per row, confirmed, persisted for both Agents.
            page.on("dialog", lambda dialog: dialog.accept())
            page.get_by_label("搜索工具").fill("elevenlabs.web")
            row("elevenlabs.web").get_by_role("button", name="已启用 · 停用").click()
            expect(row("elevenlabs.web").get_by_role("button", name="已停用 · 启用")).to_be_visible()
            fresh = Router(server.home)
            try:
                assert fresh.readiness(fresh.catalog.get("elevenlabs.web")) == "disabled"
            finally:
                fresh.close()
            expect(row("elevenlabs.web").locator("[data-step=browser_handoff]")).to_be_visible()
            assert not errors, errors
            assert not console_errors, console_errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
