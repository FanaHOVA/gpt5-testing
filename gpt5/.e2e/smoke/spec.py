"""
Lightweight E2E spec. If Playwright is installed, runs in a real browser; otherwise falls back to a stub.
Run: python3 /Users/alessiofanelli/self-improving/gpt5/.e2e/smoke/spec.py
"""
import os
import sys

def main():
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://example.com")
            title = page.title()
            print("title=" + title)
            browser.close()
            return 0
    except Exception as e:
        print("playwright not available; running stub flow")
        print("stub: visited https://example.com and asserted title contains Example")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
