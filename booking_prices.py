#!/usr/bin/env python3
"""Render the Mosvold BookingEye engine and extract live room rates."""
import json, re, sys
from playwright.sync_api import sync_playwright

DATES = "ci=15-08-2026&co=17-08-2026&promo=&islocal=0&g=0"
PROPS = {
    "Mosvold Villa (Ahangama)": f"https://mosvoldboutiquehotels.bookingeye.net/rooms?pr=1&{DATES}",
    "Sundara (Balapitiya)":     f"https://mosvoldboutiquehotels.bookingeye.net/rooms?pr=2&{DATES}",
}

def main():
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            proxy={"server": "http://127.0.0.1:37365"},
            args=["--ignore-certificate-errors"])
        page = browser.new_page(viewport={"width": 1400, "height": 2200})
        for name, url in PROPS.items():
            print(f"--> {name}\n    {url}", file=sys.stderr)
            page.goto(url, wait_until="networkidle", timeout=60000)
            try:
                page.wait_for_timeout(6000)  # let rate ajax settle
            except Exception:
                pass
            body = page.inner_text("body")
            # room cards: look for currency amounts near room names
            prices = re.findall(r"(?:LKR|Rs\.?|USD|\$|€)\s?[\d,]+(?:\.\d+)?", body)
            out[name] = {"url": url, "raw_text": body, "price_tokens": prices}
            print(f"    prices found: {sorted(set(prices))[:20]}", file=sys.stderr)
        browser.close()
    json.dump(out, open("booking_prices_raw.json", "w"), ensure_ascii=False, indent=2)
    print("saved booking_prices_raw.json")

if __name__ == "__main__":
    main()
