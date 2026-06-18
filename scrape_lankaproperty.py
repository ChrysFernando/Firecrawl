#!/usr/bin/env python3
"""
Scrape lankapropertyweb.com rental listings (Colombo: House / Apartment /
Commercial) using the Firecrawl API.

What it does
------------
1. Walks the search-results pages (handles pagination via ?page=N).
2. Extracts the URL of every individual property ad found on those pages.
3. Visits each property ad page and scrapes its full content.
4. Writes everything to:
     - scraped_data.txt   (human-readable text dump)
     - scraped_data.json  (structured data, one record per property)

Usage
-----
    export FIRECRAWL_API_KEY="fc-...."          # your key
    python scrape_lankaproperty.py

    # optional overrides:
    python scrape_lankaproperty.py --max-pages 10 --delay 1.0

Notes
-----
- Firecrawl bypasses the site's 403 / bot-protection for you.
- If the property-link detection misses ads, run with --debug-links once to
  print all links found on page 1, then tighten/loosen PROPERTY_URL_RE.
"""

import argparse
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

import requests

API_BASE = "https://api.firecrawl.dev/v2/scrape"

# Base search URL (page number is overwritten per request).
BASE_SEARCH_URL = (
    "https://www.lankapropertyweb.com/rentals/index.php"
    "?page=1&location=_Colombo"
    "&property-type=House,Apartment,Commercial"
    "&no-rooms=3-room&min=Any&max=0&search=1"
)

# Heuristic for "this link is an individual property ad" (NOT a search/nav page).
# LankaPropertyWeb ad pages live under /property/<id> style paths and end in a
# numeric id. Adjust if needed (use --debug-links to inspect).
PROPERTY_URL_RE = re.compile(
    r"lankapropertyweb\.com/(?:property|properties|ad|rentals?/property)/?.*?\d{4,}",
    re.IGNORECASE,
)

# Links we never want to treat as a property ad.
EXCLUDE_RE = re.compile(
    r"(index\.php|/login|/register|/agents?|/blog|/contact|/about|"
    r"facebook\.com|twitter\.com|instagram\.com|youtube\.com|wa\.me|"
    r"whatsapp|tel:|mailto:|javascript:|#)",
    re.IGNORECASE,
)


def set_page(url: str, page: int) -> str:
    """Return `url` with its `page` query param set to `page`."""
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q["page"] = str(page)
    return urlunparse(parts._replace(query=urlencode(q, safe=",")))


def firecrawl_scrape(api_key: str, url: str, formats, timeout=120):
    """Call Firecrawl /v2/scrape and return the `data` dict (or None on error)."""
    payload = {
        "url": url,
        "formats": formats,
        "onlyMainContent": False,   # listing pages need full DOM for all links
        "waitFor": 2500,            # let JS render
        "blockAds": True,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, 4):
        try:
            r = requests.post(API_BASE, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                body = r.json()
                if body.get("success"):
                    return body.get("data", {})
                print(f"   ! Firecrawl returned success=false for {url}: {body}")
                return None
            print(f"   ! HTTP {r.status_code} for {url} (attempt {attempt}): {r.text[:300]}")
        except requests.RequestException as e:
            print(f"   ! Request error for {url} (attempt {attempt}): {e}")
        time.sleep(2 ** attempt)
    return None


def extract_property_links(data, base_url) -> list:
    """Pull candidate property-ad URLs out of a Firecrawl scrape result."""
    found = set()

    # 1) Firecrawl-provided links list (most reliable).
    for link in data.get("links", []) or []:
        if not link:
            continue
        absolute = urljoin(base_url, link)
        if PROPERTY_URL_RE.search(absolute) and not EXCLUDE_RE.search(absolute):
            found.add(absolute.split("#")[0])

    # 2) Fallback: scrape hrefs out of the raw HTML / markdown.
    blob = (data.get("html") or "") + "\n" + (data.get("markdown") or "")
    for m in re.findall(r'href=["\']([^"\']+)["\']', blob):
        absolute = urljoin(base_url, m)
        if PROPERTY_URL_RE.search(absolute) and not EXCLUDE_RE.search(absolute):
            found.add(absolute.split("#")[0])

    return sorted(found)


def main():
    ap = argparse.ArgumentParser(description="Scrape lankapropertyweb.com via Firecrawl")
    ap.add_argument("--api-key", default=os.environ.get("FIRECRAWL_API_KEY"),
                    help="Firecrawl API key (or set FIRECRAWL_API_KEY env var)")
    ap.add_argument("--max-pages", type=int, default=20,
                    help="Max number of search-result pages to walk (default 20)")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="Seconds to wait between requests (default 1.0)")
    ap.add_argument("--out", default="scraped_data",
                    help="Output basename (default 'scraped_data')")
    ap.add_argument("--debug-links", action="store_true",
                    help="Print ALL links found on page 1 and exit")
    args = ap.parse_args()

    if not args.api_key:
        sys.exit("ERROR: provide --api-key or set FIRECRAWL_API_KEY")

    # --- Phase 1: collect property URLs across all listing pages -------------
    print("==> Phase 1: collecting property links from search-result pages")
    property_urls = []
    seen = set()
    for page in range(1, args.max_pages + 1):
        page_url = set_page(BASE_SEARCH_URL, page)
        print(f"  - listing page {page}: {page_url}")
        data = firecrawl_scrape(args.api_key, page_url, ["markdown", "links", "html"])
        if not data:
            print("    (no data; stopping pagination)")
            break

        if args.debug_links and page == 1:
            print("\n--- ALL links on page 1 ---")
            for link in sorted(set(data.get("links", []) or [])):
                print(link)
            print("--- end ---")
            return

        page_links = extract_property_links(data, page_url)
        new = [u for u in page_links if u not in seen]
        for u in new:
            seen.add(u)
            property_urls.append(u)
        print(f"    found {len(page_links)} property links ({len(new)} new)")

        # Stop when a page yields no new ads (past the last page).
        if not new:
            print("    no new listings -> reached the end")
            break
        time.sleep(args.delay)

    print(f"==> Total unique property URLs: {len(property_urls)}")
    if not property_urls:
        print("No property URLs found. Re-run with --debug-links to inspect the "
              "links Firecrawl sees, then adjust PROPERTY_URL_RE.")
        return

    # --- Phase 2: scrape each property page ----------------------------------
    print("\n==> Phase 2: scraping each property page")
    records = []
    for i, url in enumerate(property_urls, 1):
        print(f"  [{i}/{len(property_urls)}] {url}")
        data = firecrawl_scrape(args.api_key, url, ["markdown"])
        if not data:
            records.append({"url": url, "error": "scrape failed"})
            continue
        meta = data.get("metadata", {}) or {}
        records.append({
            "url": url,
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "markdown": data.get("markdown", ""),
        })
        time.sleep(args.delay)

    # --- Phase 3: write outputs ----------------------------------------------
    json_path = f"{args.out}.json"
    txt_path = f"{args.out}.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("LankaPropertyWeb — Colombo rentals (House / Apartment / Commercial)\n")
        f.write(f"Scraped {len(records)} properties via Firecrawl\n")
        f.write("=" * 80 + "\n\n")
        for i, rec in enumerate(records, 1):
            f.write(f"### PROPERTY {i} ###\n")
            f.write(f"URL: {rec['url']}\n")
            if rec.get("error"):
                f.write(f"ERROR: {rec['error']}\n\n")
                f.write("-" * 80 + "\n\n")
                continue
            f.write(f"Title: {rec.get('title','')}\n")
            f.write(f"Description: {rec.get('description','')}\n")
            f.write("\n--- Content ---\n")
            f.write(rec.get("markdown", "") + "\n")
            f.write("-" * 80 + "\n\n")

    print(f"\n==> Done.\n    Text : {txt_path}\n    JSON : {json_path}")


if __name__ == "__main__":
    main()
