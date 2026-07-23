#!/usr/bin/env python3
"""
Crawl taskforceai.tech using the Firecrawl API.

What it does
------------
1. Starts a Firecrawl crawl job for the whole site (POST /v2/crawl).
2. Polls the job until it finishes (GET /v2/crawl/{id}).
3. Writes every crawled page to:
     - taskforceai_scrape.json  (structured: url, title, description, markdown per page)
     - taskforceai_scrape.txt   (human-readable text dump)

Usage
-----
    export FIRECRAWL_API_KEY="fc-...."          # your key
    python scrape_taskforceai.py

    # optional overrides:
    python scrape_taskforceai.py --limit 100 --poll-interval 5
"""

import argparse
import json
import os
import sys
import time

import requests

API_BASE = "https://api.firecrawl.dev/v2"
TARGET_URL = "https://taskforceai.tech"


def start_crawl(api_key: str, url: str, limit: int) -> str:
    """Kick off a crawl job and return its id."""
    payload = {
        "url": url,
        "limit": limit,
        "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True},
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


def poll_crawl(api_key: str, job_id: str, poll_interval: float) -> list:
    """Poll until the crawl finishes, following `next` pagination, and return all pages."""
    headers = {"Authorization": f"Bearer {api_key}"}
    pages = []
    url = f"{API_BASE}/crawl/{job_id}"
    while True:
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        body = r.json()
        status = body.get("status")
        print(f"  status={status} completed={body.get('completed')} total={body.get('total')}")

        if status == "completed":
            pages.extend(body.get("data", []) or [])
            next_url = body.get("next")
            if next_url:
                url = next_url
                continue
            return pages
        if status == "failed":
            sys.exit(f"ERROR: crawl failed: {body}")

        time.sleep(poll_interval)


def main():
    ap = argparse.ArgumentParser(description="Crawl taskforceai.tech via Firecrawl")
    ap.add_argument("--api-key", default=os.environ.get("FIRECRAWL_API_KEY"),
                    help="Firecrawl API key (or set FIRECRAWL_API_KEY env var)")
    ap.add_argument("--limit", type=int, default=50,
                    help="Max pages to crawl (default 50)")
    ap.add_argument("--poll-interval", type=float, default=3.0,
                    help="Seconds between status polls (default 3.0)")
    ap.add_argument("--out", default="taskforceai_scrape",
                    help="Output basename (default 'taskforceai_scrape')")
    args = ap.parse_args()

    if not args.api_key:
        sys.exit("ERROR: provide --api-key or set FIRECRAWL_API_KEY")

    print(f"==> Starting crawl of {TARGET_URL}")
    job_id = start_crawl(args.api_key, TARGET_URL, args.limit)
    print(f"==> Crawl job id: {job_id}")

    print("==> Polling for completion")
    pages = poll_crawl(args.api_key, job_id, args.poll_interval)
    print(f"==> Crawl finished: {len(pages)} pages")

    records = []
    for page in pages:
        meta = page.get("metadata", {}) or {}
        records.append({
            "url": meta.get("url") or meta.get("sourceURL", ""),
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "markdown": page.get("markdown", ""),
        })

    json_path = f"{args.out}.json"
    txt_path = f"{args.out}.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"TaskForce AI ({TARGET_URL}) — full site crawl\n")
        f.write(f"Scraped {len(records)} pages via Firecrawl\n")
        f.write("=" * 80 + "\n\n")
        for i, rec in enumerate(records, 1):
            f.write(f"### PAGE {i} ###\n")
            f.write(f"URL: {rec['url']}\n")
            f.write(f"Title: {rec.get('title','')}\n")
            f.write(f"Description: {rec.get('description','')}\n")
            f.write("\n--- Content ---\n")
            f.write(rec.get("markdown", "") + "\n")
            f.write("-" * 80 + "\n\n")

    print(f"\n==> Done.\n    Text : {txt_path}\n    JSON : {json_path}")


if __name__ == "__main__":
    main()
