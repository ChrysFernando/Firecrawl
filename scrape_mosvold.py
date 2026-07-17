#!/usr/bin/env python3
"""Scrape the full mosvoldhotels.com site into a clean, organised document."""
import json, re, time, html
import requests
import trafilatura

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
URLS = [u.strip() for u in open("/tmp/mos_urls.txt") if u.strip()]

PHONE_RE = re.compile(r"(?:\+94|0094|0)\s?\d(?:[\s\-]?\d){7,9}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def dedupe_lines(text):
    """Collapse whitespace and drop consecutive duplicate lines (Elementor dupes)."""
    out, prev = [], None
    for ln in (text or "").splitlines():
        ln = re.sub(r"[ \t]+", " ", ln).strip()
        if not ln:
            if out and out[-1] != "":
                out.append("")
            continue
        if ln == prev:
            continue
        # skip if identical to any of the last 3 non-empty lines (near-dupes)
        if ln in [x for x in out[-4:] if x]:
            continue
        out.append(ln)
        prev = ln
    return "\n".join(out).strip()


def fetch(url):
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def main():
    pages = []
    phones, emails, images = set(), set(), {}
    for i, url in enumerate(URLS, 1):
        print(f"[{i}/{len(URLS)}] {url}")
        h = fetch(url)
        if not h:
            pages.append({"url": url, "error": "fetch failed"})
            continue
        md = trafilatura.metadata.extract_metadata(h)
        title = (md.title if md else "") or ""
        desc = (md.description if md else "") or ""
        body = trafilatura.extract(h, include_links=False, include_images=True,
                                   favor_recall=True, include_comments=False) or ""
        body = dedupe_lines(body)
        # global contact + image harvest from raw html
        for p in PHONE_RE.findall(h):
            d = re.sub(r"[^\d+]", "", p)
            if len(re.sub(r"\D", "", d)) >= 9:
                phones.add(p.strip())
        for e in EMAIL_RE.findall(h):
            if not e.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                emails.add(e.lower())
        pageimgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', h, re.I)
        pageimgs = [u for u in pageimgs if "wp-content/uploads" in u]
        images[url] = sorted(set(pageimgs))
        pages.append({"url": url, "title": title.strip(), "description": desc.strip(),
                      "content": body, "images": images[url]})
        time.sleep(0.4)

    data = {"pages": pages,
            "phones": sorted(phones), "emails": sorted(emails)}
    json.dump(data, open("mosvold_site.json", "w"), ensure_ascii=False, indent=2)

    # ---- organise into clean markdown ----
    def section(url):
        p = url.replace("https://www.mosvoldhotels.com", "").strip("/")
        if p.startswith("mosvold-villa"): return "Mosvold Villa (Ahangama)"
        if p.startswith("sundara"): return "Sundara (Balapitiya)"
        if p.startswith("blog"): return "Blog & Travel Guides"
        if p in ("privacy-policy", "terms-conditions", "cancellation-payment-policy"):
            return "Policies"
        return "Group / General"

    order = ["Group / General", "Mosvold Villa (Ahangama)", "Sundara (Balapitiya)",
             "Blog & Travel Guides", "Policies"]
    groups = {k: [] for k in order}
    for pg in pages:
        groups.setdefault(section(pg["url"]), []).append(pg)

    ok = [p for p in pages if not p.get("error")]
    with open("mosvold_site.md", "w", encoding="utf-8") as f:
        f.write("# Mosvold Boutique Hotels — Full Website Content\n\n")
        f.write(f"_Scraped {len(ok)} pages from mosvoldhotels.com_\n\n")
        f.write("**Contact numbers found:** " + (", ".join(sorted(phones)) or "—") + "\n\n")
        f.write("**Emails found:** " + (", ".join(sorted(emails)) or "—") + "\n\n")
        f.write("---\n\n## Table of Contents\n")
        for g in order:
            if groups.get(g):
                f.write(f"- {g} ({len(groups[g])} pages)\n")
        f.write("\n---\n\n")
        for g in order:
            grp = groups.get(g) or []
            if not grp:
                continue
            f.write(f"# {g}\n\n")
            for pg in grp:
                if pg.get("error"):
                    continue
                t = pg["title"] or pg["url"].rstrip("/").split("/")[-1]
                f.write(f"## {t}\n\n")
                f.write(f"*URL:* {pg['url']}\n\n")
                if pg["description"]:
                    f.write(f"> {pg['description']}\n\n")
                if pg["content"]:
                    f.write(pg["content"] + "\n\n")
                if pg["images"]:
                    f.write(f"*Images ({len(pg['images'])}):*\n")
                    for im in pg["images"][:40]:
                        f.write(f"- {im}\n")
                    f.write("\n")
                f.write("---\n\n")

    print(f"\nDone. {len(ok)}/{len(pages)} pages, {len(phones)} phones, "
          f"{len(emails)} emails. -> mosvold_site.md / .json")


if __name__ == "__main__":
    main()
