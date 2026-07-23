#!/usr/bin/env python3
"""
Crawl the entire taskforceai.tech website using the Firecrawl API.

What it does
------------
1. Starts a Firecrawl crawl job (POST /v1/crawl) for https://www.taskforceai.tech/
   with a `waitFor` delay so the site's JS splash/loading screen finishes
   rendering before each page is captured.
2. Polls the crawl status endpoint (GET /v1/crawl/{id}) until the job
   completes (or fails), paging through all result batches (`next`).
3. Writes everything to:
     - taskforceai_scraped.json  (structured data, one record per page)
     - taskforceai_scraped.txt   (human-readable text dump)

Usage
-----
    export FIRECRAWL_API_KEY="fc-...."          # your key
    python scrape_taskforceai.py

    # optional overrides:
    python scrape_taskforceai.py --limit 50 --wait-for 5000 --poll-interval 5
"""

import argparse
import json
import os
import sys
import time

import requests

API_BASE = "https://api.firecrawl.dev/v1"
DEFAULT_URL = "https://www.taskforceai.tech/"


def start_crawl(api_key: str, url: str, limit: int, wait_for: int) -> str:
    """Kick off a crawl job and return its id."""
    payload = {
        "url": url,
        "limit": limit,
        "scrapeOptions": {
            "formats": ["markdown"],
            "waitFor": wait_for,
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.post(f"{API_BASE}/crawl", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        sys.exit(f"ERROR: failed to start crawl: {body}")
    return body["id"]


def poll_crawl(api_key: str, crawl_id: str, poll_interval: int) -> list:
    """Poll the crawl job until completion, returning all collected page records."""
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{API_BASE}/crawl/{crawl_id}"
    all_data = []

    while True:
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        body = r.json()

        status = body.get("status")
        completed = body.get("completed", 0)
        total = body.get("total", 0)
        print(f"  status={status}  completed={completed}/{total}")

        if status == "completed":
            all_data = body.get("data", [])
            # Follow pagination if the full result set is split across pages.
            next_url = body.get("next")
            while next_url:
                r = requests.get(next_url, headers=headers, timeout=60)
                r.raise_for_status()
                page_body = r.json()
                all_data.extend(page_body.get("data", []))
                next_url = page_body.get("next")
            return all_data

        if status == "failed":
            sys.exit(f"ERROR: crawl failed: {body}")

        time.sleep(poll_interval)


def main():
    ap = argparse.ArgumentParser(description="Crawl taskforceai.tech via Firecrawl")
    ap.add_argument("--api-key", default=os.environ.get("FIRECRAWL_API_KEY"),
                     help="Firecrawl API key (or set FIRECRAWL_API_KEY env var)")
    ap.add_argument("--url", default=DEFAULT_URL,
                     help=f"Site to crawl (default {DEFAULT_URL})")
    ap.add_argument("--limit", type=int, default=100,
                     help="Max pages to crawl (default 100)")
    ap.add_argument("--wait-for", type=int, default=5000,
                     help="Milliseconds to wait for JS render per page (default 5000)")
    ap.add_argument("--poll-interval", type=int, default=5,
                     help="Seconds between crawl status checks (default 5)")
    ap.add_argument("--out", default="taskforceai_scraped",
                     help="Output basename (default 'taskforceai_scraped')")
    args = ap.parse_args()

    if not args.api_key:
        sys.exit("ERROR: provide --api-key or set FIRECRAWL_API_KEY")

    print(f"==> Starting crawl of {args.url} (limit={args.limit})")
    crawl_id = start_crawl(args.api_key, args.url, args.limit, args.wait_for)
    print(f"==> Crawl job id: {crawl_id}")

    print("==> Polling for completion...")
    pages = poll_crawl(args.api_key, crawl_id, args.poll_interval)
    print(f"==> Crawl finished: {len(pages)} pages retrieved")

    json_path = f"{args.out}.json"
    txt_path = f"{args.out}.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"TaskForce AI — full site crawl ({args.url})\n")
        f.write(f"Scraped {len(pages)} pages via Firecrawl\n")
        f.write("=" * 80 + "\n\n")
        for i, page in enumerate(pages, 1):
            meta = page.get("metadata", {}) or {}
            f.write(f"### PAGE {i} ###\n")
            f.write(f"URL: {meta.get('sourceURL') or meta.get('url', '')}\n")
            f.write(f"Title: {meta.get('title', '')}\n")
            f.write(f"Description: {meta.get('description', '')}\n")
            f.write("\n--- Content ---\n")
            f.write(page.get("markdown", "") + "\n")
            f.write("-" * 80 + "\n\n")

    print(f"\n==> Done.\n    Text : {txt_path}\n    JSON : {json_path}")


if __name__ == "__main__":
    main()
