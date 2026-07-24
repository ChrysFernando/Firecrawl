#!/usr/bin/env python3
"""
Clean up a taskforceai.tech Firecrawl crawl (taskforceai_scraped.json) before
loading it into an n8n knowledge-base / RAG pipeline.

Why
---
The raw crawl output is full of noise that isn't part of the real page
content:
  - Google Maps embed junk (SVG data URIs, map tile request URLs, "Keyboard
    shortcuts", "Map data (c) ...", "Terms", "Report a map error", "Get
    directions")
  - Repeated site-chrome / loading-screen boilerplate ("SCROLL_DEPTH",
    "Launching Interface...", "System Check NN%", "Back to Transmission Log")
  - The repeated footer widget (business name/tagline line, Google review
    widget, "Chat AI [WhatsApp]")
  - Decorative "glitch text" left over from the animated hero heading
    (runs of symbol characters like "an__+![_-?_{_<__}=__#!_+__+_<_>^<_#>")
  - Duplicate pages: the site is a client-side SPA, so several pages get
    crawled under hash-fragment URLs (e.g. .../#/blog/some-post) that just
    re-render the homepage shell instead of unique content.

What it does
------------
1. Loads the input JSON (list of Firecrawl page records).
2. Strips the known junk patterns out of each page's markdown.
3. Drops pages that end up with little/no real content left (pure chrome).
4. De-duplicates: pages whose cleaned content matches another page already
   kept (this catches the hash-fragment SPA duplicates) are dropped, keeping
   whichever copy has the cleanest/canonical URL.
5. Writes:
     - taskforceai_cleaned.json  (structured, cleaned + deduped records)
     - taskforceai_cleaned.txt   (human-readable text dump)

Usage
-----
    python clean_taskforceai_data.py
    python clean_taskforceai_data.py --in taskforceai_scraped.json --out taskforceai_cleaned
"""

import argparse
import json
import re
from urllib.parse import urlparse, urlunparse

# --- Junk removal patterns -------------------------------------------------
# Each pattern is removed from the markdown (case-insensitive, multiline).
JUNK_PATTERNS = [
    # Google Maps embeds
    r"!\[[^\]]*\]\(data:image/svg[^)]*\)",
    r"https?://[^\s)\"']*google[^\s)\"']*(?:map|tile)[^\s)\"']*",
    r"(?im)^\s*Keyboard shortcuts\s*$",
    r"(?im)^\s*Map data\s*(?:\xa9|\(c\)|©)?\s*\d{4}.*$",
    r"(?im)^\s*Report a map error\s*$",
    r"(?im)^\s*Get directions\s*$",
    r"(?im)^\s*Terms\s*$",

    # Loading-screen / site-chrome boilerplate
    r"(?im)^\s*SCROLL_DEPTH.*$",
    r"(?im)^\s*Launching Interface\.\.\.\s*$",
    r"(?im)^\s*System Check\s*\d+%\s*$",
    r"(?im)^\s*Back to Transmission Log\s*$",
    r"(?im)^\s*Verifying Security Protocols\.\.\.\s*$",

    # Footer widget
    r"(?im)^\s*Taskforce Ai\s*\|\s*Voice Agents Sri Lanka\s*\|\s*Business Automation\s*\|\s*Whatsapp Chatbot\s*$",
    r"(?im)^\s*Chat AI\s*\[WhatsApp\]\s*$",
]

# Runs of decorative "glitch" symbol characters left over from the animated
# hero heading, e.g. "an__+![_-?_{_<__}=__#!_+__+_<_>^<_#>_"
GLITCH_RUN_RE = re.compile(r"[_\-+!*?{}<>#=^~|]{5,}")

MIN_CONTENT_CHARS = 80  # pages with less real content than this are dropped


def clean_markdown(markdown: str) -> str:
    text = markdown or ""
    for pattern in JUNK_PATTERNS:
        text = re.sub(pattern, "", text)
    text = GLITCH_RUN_RE.sub("", text)

    # Collapse the blank-line litter left behind by the removals above.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def canonical_url(url: str) -> str:
    """Strip the SPA hash-fragment and trailing slash so real duplicates match."""
    parts = urlparse(url or "")
    path = parts.path.rstrip("/") or "/"
    return urlunparse((parts.scheme, parts.netloc, path, "", "", ""))


def content_fingerprint(cleaned_text: str) -> str:
    """Normalized signature used to detect duplicate/near-duplicate pages."""
    collapsed = re.sub(r"\s+", " ", cleaned_text).strip().lower()
    return collapsed[:400]


def main():
    ap = argparse.ArgumentParser(
        description="Clean and de-duplicate a taskforceai.tech Firecrawl crawl"
    )
    ap.add_argument("--in", dest="infile", default="taskforceai_scraped.json",
                     help="Input JSON from scrape_taskforceai.py (default 'taskforceai_scraped.json')")
    ap.add_argument("--out", default="taskforceai_cleaned",
                     help="Output basename (default 'taskforceai_cleaned')")
    args = ap.parse_args()

    with open(args.infile, "r", encoding="utf-8") as f:
        pages = json.load(f)

    print(f"==> Loaded {len(pages)} pages from {args.infile}")

    kept = []
    seen_urls = set()
    seen_fingerprints = {}  # fingerprint -> index in `kept`
    dropped_empty = 0
    dropped_dup = 0

    for page in pages:
        meta = page.get("metadata", {}) or {}
        raw_url = meta.get("sourceURL") or meta.get("url", "")
        curl = canonical_url(raw_url)

        cleaned = clean_markdown(page.get("markdown", ""))

        if len(cleaned) < MIN_CONTENT_CHARS:
            dropped_empty += 1
            continue

        if curl in seen_urls:
            dropped_dup += 1
            continue

        fp = content_fingerprint(cleaned)
        if fp in seen_fingerprints:
            dropped_dup += 1
            continue

        seen_urls.add(curl)
        seen_fingerprints[fp] = len(kept)
        kept.append({
            "url": curl,
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "markdown": cleaned,
        })

    print(f"==> Kept {len(kept)} pages")
    print(f"    dropped (little/no real content): {dropped_empty}")
    print(f"    dropped (duplicate URL/content):   {dropped_dup}")

    json_path = f"{args.out}.json"
    txt_path = f"{args.out}.txt"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("TaskForce AI — cleaned site content\n")
        f.write(f"{len(kept)} unique pages (cleaned of nav/map/footer boilerplate)\n")
        f.write("=" * 80 + "\n\n")
        for i, page in enumerate(kept, 1):
            f.write(f"### PAGE {i} ###\n")
            f.write(f"URL: {page['url']}\n")
            f.write(f"Title: {page['title']}\n")
            f.write(f"Description: {page['description']}\n")
            f.write("\n--- Content ---\n")
            f.write(page["markdown"] + "\n")
            f.write("-" * 80 + "\n\n")

    print(f"\n==> Done.\n    Text : {txt_path}\n    JSON : {json_path}")


if __name__ == "__main__":
    main()
