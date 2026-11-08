"""Real isolated Chromium + fake Tripo DOM. All HTTP intercepted; no provider access."""
import argparse
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from agent_tool_maker.studio_runtime import serve

HTML = '''<!doctype html><meta charset="utf-8"><title>ATM synthetic Tripo server fixture</title>
<style>header,main{padding:24px}div.group{width:200px;height:250px}</style>
<header></header><main>My Assets
<div class="group"><img alt="Synthetic cube" src="https://tripo-data-public.rg1.data.tripo3d.com/tripo-studio/20261004/12345678-1234-1234-1234-123456789abc/studio_mesh.webp"></div>
<div class="min-h-10">No more assets</div></main><button id="fake-login">Fixture login</button>
<a href="/workspace/generate">Workspace</a>
<script>function render(){let balance=99-40*Number(localStorage.getItem('fixture-submits')||0);
document.querySelector('header').innerHTML=document.cookie.includes('atm_fixture_login=1')?
'<i class="i-tripo:bolt:search"></i><p title="'+balance+'">'+balance+'</p>':'<button>Log in</button>';
if(location.pathname==='/workspace/generate'){document.querySelector('main').innerHTML=
'<div role="combobox">Tripo H3.1 Best Quality</div><div role="combobox">Private</div>'+
'<button role="switch" aria-checked="false">Parts</button><button role="switch" aria-checked="false">8K</button>'+
'<textarea placeholder="Describe what you want to create in 3D…"></textarea><button class="animate-button">Generate 40</button>';
document.querySelector('.animate-button').onclick=()=>{localStorage.setItem('fixture-submits',String(Number(localStorage.getItem('fixture-submits')||0)+1));
history.pushState({},'', '/workspace/generate/12345678-1234-1234-1234-123456789abc');render()}}}
document.querySelector('#fake-login').onclick=()=>{document.cookie='atm_fixture_login=1; Max-Age=86400; Path=/; Secure; SameSite=Lax';render()};render();</script>'''


async def main(args):
    async with async_playwright() as manager:
        async def factory(profile):
            context = await manager.chromium.launch_persistent_context(profile, executable_path=args.chromium,
                headless=True, chromium_sandbox=True, viewport={"width": 1280, "height": 900}, accept_downloads=True,
                artifacts_dir=Path(args.home) / "fixture-artifacts")
            async def route_handler(route):
                if route.request.url.startswith("https://studio.tripo3d.ai/"):
                    await route.fulfill(status=200, content_type="text/html", body=HTML)
                else:
                    await route.abort()
            await context.route("**/*", route_handler)
            page = context.pages[0]
            if args.authenticate:
                await page.goto("https://studio.tripo3d.ai/assets")
                await page.locator("#fake-login").click()
            return context
        await serve(Path(args.home), node=args.node, browser_factory=factory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--chromium", required=True)
    parser.add_argument("--authenticate", action="store_true")
    asyncio.run(main(parser.parse_args()))
