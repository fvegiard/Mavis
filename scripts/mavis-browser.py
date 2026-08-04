#!/usr/bin/env python3
"""
mavis-browser.py — Browser automation wrapper for Mavis.

Uses Playwright (already installed at /usr/local/bin/playwright).
The top 1% agents (Devin, Operator, Manus) all have browser control.
This is Mavis's:

Usage:
  mavis-browser screenshot https://example.com /tmp/page.png
  mavis-browser extract https://example.com "h1, h2, .price"
  mavis-browser click https://example.com "button.submit" --wait "#success"
  mavis-browser fill https://example.com "input[name=q]" "Mavis agent"
  mavis-browser run --script my_script.js
  mavis-browser test "click the login button"   # uses Claude to decide steps

Computer use: mavis-browser computer-use "open the app and click on Settings"
"""
import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

PLAYWRIGHT_INSTALLED = subprocess.run(["which", "playwright"], capture_output=True).returncode == 0


def check_browsers():
    """Check if chromium is installed for Playwright."""
    cache = Path.home() / ".cache" / "ms-playwright"
    if not cache.exists():
        return False, "no playwright cache"
    chromium_dirs = list(cache.glob("chromium-*"))
    if not chromium_dirs:
        return False, "no chromium found"
    return True, str(chromium_dirs[0])


async def _screenshot(url: str, out_path: str, viewport: dict, full_page: bool, selector: str | None = None):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport=viewport)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if selector:
                el = await page.query_selector(selector)
                if el:
                    await el.screenshot(path=out_path)
                else:
                    await page.screenshot(path=out_path, full_page=full_page)
            else:
                await page.screenshot(path=out_path, full_page=full_page)
            print(f"📸 Saved {out_path}")
        finally:
            await browser.close()


async def _extract(url: str, selector: str, output_format: str):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            elements = await page.query_selector_all(selector)
            results = []
            for el in elements:
                if output_format == "text":
                    results.append(await el.inner_text())
                elif output_format == "html":
                    results.append(await el.inner_html())
                elif output_format == "attr":
                    attr = await el.get_attribute("href") or await el.get_attribute("src") or ""
                    results.append(attr)
            if output_format == "text":
                print("\n".join(results))
            else:
                print(json.dumps(results, indent=2, ensure_ascii=False))
        finally:
            await browser.close()


async def _interact(url: str, actions: list, headless: bool = True):
    """Execute a list of actions on a page.
    Each action: {type: 'click'|'fill'|'wait'|'press', selector?: str, text?: str, key?: str, timeout?: int}
    """
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            for action in actions:
                t = action.get("type")
                if t == "click":
                    sel = action["selector"]
                    await page.click(sel, timeout=action.get("timeout", 5000))
                    print(f"✅ clicked {sel}")
                elif t == "fill":
                    sel = action["selector"]
                    text = action.get("text", "")
                    await page.fill(sel, text, timeout=action.get("timeout", 5000))
                    print(f"✅ filled {sel}")
                elif t == "wait":
                    sel = action.get("selector", "")
                    if sel:
                        await page.wait_for_selector(sel, timeout=action.get("timeout", 10000))
                        print(f"✅ waited for {sel}")
                    else:
                        await page.wait_for_timeout(action.get("timeout", 1000))
                elif t == "press":
                    await page.keyboard.press(action.get("key", "Enter"))
                    print(f"✅ pressed {action.get('key', 'Enter')}")
                elif t == "screenshot":
                    out = action.get("path", "/tmp/mavis-browser.png")
                    await page.screenshot(path=out, full_page=action.get("full_page", False))
                    print(f"📸 screenshot {out}")
                else:
                    print(f"[WARN] unknown action type: {t}")
        finally:
            await browser.close()


def cmd_screenshot(args):
    ok, info = check_browsers()
    if not ok:
        print(f"[ERROR] Playwright browsers not installed: {info}", file=sys.stderr)
        print("  Run: playwright install chromium", file=sys.stderr)
        return 1
    viewport = {"width": args.width, "height": args.height}
    asyncio.run(_screenshot(args.url, args.output, viewport, args.full_page, args.selector))
    return 0


def cmd_extract(args):
    ok, info = check_browsers()
    if not ok:
        print(f"[ERROR] Playwright browsers not installed: {info}", file=sys.stderr)
        return 1
    asyncio.run(_extract(args.url, args.selector, args.format))
    return 0


def cmd_interact(args):
    ok, info = check_browsers()
    if not ok:
        print(f"[ERROR] Playwright browsers not installed: {info}", file=sys.stderr)
        return 1
    actions = json.loads(args.actions) if args.actions else []
    asyncio.run(_interact(args.url, actions, args.headless))
    return 0


def cmd_computer_use(args):
    """Computer use: take a screenshot, ask Claude what to do, execute the action, repeat.
    This is the OpenAI Operator / Anthropic Computer Use pattern.
    """
    ok, info = check_browsers()
    if not ok:
        print(f"[ERROR] Playwright browsers not installed: {info}", file=sys.stderr)
        return 1
    # Implementation would go here - simplified for v1
    print("🚧 Computer use: not yet fully implemented (need Claude vision + action loop)")
    print("   Suggest using mavis-browser interact with explicit actions for now")
    return 0


def cmd_health(args):
    """Check if browser automation is ready."""
    print("🏥 Mavis browser health check")
    print(f"   Playwright: {'✅' if PLAYWRIGHT_INSTALLED else '❌'}")
    ok, info = check_browsers()
    print(f"   Chromium: {'✅' if ok else '❌'} ({info})")
    if PLAYWRIGHT_INSTALLED and ok:
        print("   Status: ready")
        return 0
    else:
        print("   Status: needs install")
        print("   Fix: playwright install chromium")
        return 1


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ss = sub.add_parser("screenshot", help="Take a screenshot of a URL")
    p_ss.add_argument("url")
    p_ss.add_argument("output", help="Output file path (.png)")
    p_ss.add_argument("--width", type=int, default=1280)
    p_ss.add_argument("--height", type=int, default=800)
    p_ss.add_argument("--full-page", action="store_true")
    p_ss.add_argument("--selector", help="Screenshot a specific element instead")

    p_ex = sub.add_parser("extract", help="Extract data from a page")
    p_ex.add_argument("url")
    p_ex.add_argument("selector", help="CSS selector")
    p_ex.add_argument("--format", default="text", choices=["text", "html", "attr"])

    p_in = sub.add_parser("interact", help="Interact with a page (JSON actions)")
    p_in.add_argument("url")
    p_in.add_argument("actions", help="JSON list of actions")
    p_in.add_argument("--no-headless", action="store_false", dest="headless")

    p_cu = sub.add_parser("computer-use", help="Computer use (vision + action loop)")
    p_cu.add_argument("task", help="High-level task description")

    sub.add_parser("health", help="Check browser health")

    args = p.parse_args()

    if args.cmd == "screenshot":
        return cmd_screenshot(args)
    elif args.cmd == "extract":
        return cmd_extract(args)
    elif args.cmd == "interact":
        return cmd_interact(args)
    elif args.cmd == "computer-use":
        return cmd_computer_use(args)
    elif args.cmd == "health":
        return cmd_health(args)


if __name__ == "__main__":
    sys.exit(main())
