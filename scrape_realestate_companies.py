#!/usr/bin/env python3
"""
Collect Colombo real-estate companies + their published business phone /
WhatsApp numbers, using the Firecrawl API.

Strategy (accuracy-first):
  Phase 1 - discover candidate company pages via many Firecrawl /search queries.
  Phase 2 - scrape each candidate (contact/home page) with:
              * Firecrawl structured JSON extraction (company, phones, whatsapp,
                email, address), AND
              * raw html parse of tel:/wa.me hrefs as a machine-readable
                cross-check.
            A number is kept only if it is a valid Sri Lanka number; WhatsApp is
            flagged when it comes from a wa.me link or a whatsapp-labelled field.
  Phase 3 - dedupe by company domain + phone, write JSON / CSV / Markdown.

Outputs are written incrementally so a crash never loses collected data.
"""
import json, os, re, sys, time
import requests
from urllib.parse import urlparse

API = "https://api.firecrawl.dev/v2"
KEY = os.environ.get("FIRECRAWL_API_KEY")
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

SEARCH_QUERIES = [
    "real estate agency Colombo Sri Lanka contact",
    "property agents Colombo Sri Lanka whatsapp",
    "real estate company Colombo contact number",
    "estate agents Colombo Sri Lanka",
    "land sale agent Colombo Sri Lanka contact",
    "apartment rental agency Colombo Sri Lanka",
    "luxury property Colombo agency contact",
    "real estate Colombo 03 05 07 agency",
    "property brokers Colombo Sri Lanka phone",
    "real estate agency Nugegoda Dehiwala Rajagiriya contact",
    "real estate agency Battaramulla Kotte Sri Lanka",
    "real estate agency Mount Lavinia Wellawatte contact",
    "site:yellowpages.lk real estate Colombo",
    "site:lankapropertyweb.com agents Colombo",
    "property management company Colombo Sri Lanka contact",
    # --- expansion queries ---
    "real estate (Pvt) Ltd Colombo Sri Lanka contact number",
    "property sales company Colombo Sri Lanka whatsapp",
    "real estate brokers Colombo Sri Lanka phone number",
    "house for sale agent Colombo Sri Lanka contact",
    "land sale company Colombo Sri Lanka whatsapp",
    "commercial property agent Colombo Sri Lanka contact",
    "real estate agency Kollupitiya Bambalapitiya Wellawatte",
    "real estate agency Kohuwala Maharagama Boralesgamuwa contact",
    "real estate agency Kelaniya Wattala Ja-Ela Sri Lanka",
    "real estate agency Sri Jayawardenepura Kotte Pelawatte",
    "property consultants Colombo Sri Lanka contact number",
    "apartment sales agent Colombo Sri Lanka whatsapp",
    "real estate firm Colombo 04 06 08 Sri Lanka contact",
    "site:ikman.lk real estate agent Colombo",
    "site:findqo.lk real estate Colombo",
    "site:adsearch.lk real estate Colombo",
    "luxury apartment agent Colombo Sri Lanka contact number",
    "real estate investment company Colombo Sri Lanka contact",
    "property developers Colombo Sri Lanka contact whatsapp",
    "real estate negotiator Colombo Sri Lanka phone",
]

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "is_real_estate": {"type": "boolean",
            "description": "true only if this is a real estate / property company"},
        "city": {"type": "string"},
        "phones": {"type": "array", "items": {"type": "string"}},
        "whatsapp": {"type": "array", "items": {"type": "string"}},
        "email": {"type": "string"},
        "address": {"type": "string"},
    },
}
EXTRACT_PROMPT = (
    "This page belongs to a business. Extract: the company name; whether it is a "
    "real estate / property agency (is_real_estate); the city it operates in; "
    "EVERY phone number shown (exactly as written); any number explicitly marked "
    "as WhatsApp; the contact email; and the office address. Do not invent "
    "numbers - only list ones actually present on the page."
)

# Sri Lanka number: +94 / 0094 / 0 followed by 9 digits (mobile 7x).
SL_RE = re.compile(r"(?:\+?94|0)\s?(?:\(0\))?\s?7?\d(?:[\s\-]?\d){7,8}")


def norm_phone(raw):
    """Normalise to +94XXXXXXXXX if it is a valid Sri Lanka number, else None."""
    d = re.sub(r"[^\d+]", "", raw or "")
    d = d.lstrip("+")
    if d.startswith("0094"):
        d = d[4:]
    elif d.startswith("94"):
        d = d[2:]
    elif d.startswith("0"):
        d = d[1:]
    else:
        return None
    if len(d) == 9 and d[0] in "1234567":   # 9 national digits
        return "+94" + d
    return None


def firecrawl(path, payload, timeout=120):
    for attempt in range(1, 4):
        try:
            r = requests.post(f"{API}/{path}", json=payload, headers=H, timeout=timeout)
            if r.status_code == 200:
                b = r.json()
                if b.get("success"):
                    return b
                return None
            print(f"   ! HTTP {r.status_code} {path} (try {attempt}): {r.text[:200]}")
        except requests.RequestException as e:
            print(f"   ! {path} error (try {attempt}): {e}")
        time.sleep(2 ** attempt)
    return None


def search(query, limit=15):
    b = firecrawl("search", {"query": query, "limit": limit})
    if not b:
        return []
    data = b.get("data")
    items = data if isinstance(data, list) else (data or {}).get("web", [])
    return [(it.get("url", ""), it.get("title", "")) for it in (items or []) if it.get("url")]


def extract_links_numbers(html):
    """Pull tel: and wa.me numbers straight from hrefs (machine-readable)."""
    phones, wa = set(), set()
    for m in re.findall(r'href=["\']tel:([^"\']+)["\']', html or "", re.I):
        n = norm_phone(m)
        if n:
            phones.add(n)
    for m in re.findall(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{9,15})',
                        html or "", re.I):
        n = norm_phone(m)
        if n:
            wa.add(n)
    return phones, wa


def domain(url):
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return url


def main():
    if not KEY:
        sys.exit("ERROR: set FIRECRAWL_API_KEY")
    target = int(os.environ.get("TARGET", "130"))

    out_json = "realestate_companies.json"
    # Load existing records so an expansion run appends instead of overwriting.
    records = []
    done_domains = set()
    if os.path.exists(out_json):
        try:
            records = json.load(open(out_json, encoding="utf-8"))
            done_domains = {r.get("domain") for r in records}
            print(f"==> loaded {len(records)} existing companies "
                  f"({len(done_domains)} domains) - will append new ones")
        except Exception:
            records = []

    # --- Phase 1: discover candidate URLs -----------------------------------
    print("==> Phase 1: discovering company pages via search")
    candidates = {}          # domain -> url (prefer a contact page)
    for q in SEARCH_QUERIES:
        hits = search(q)
        print(f"  '{q[:50]}...' -> {len(hits)} hits")
        for url, title in hits:
            d = domain(url)
            # skip aggregators/social we can't get a single company from
            if any(s in d for s in ("facebook.", "instagram.", "youtube.",
                                    "linkedin.", "tiktok.", "twitter.", "x.com")):
                continue
            if d not in candidates or "contact" in url.lower():
                candidates[d] = url
        time.sleep(1)
    cand = list(candidates.items())
    print(f"==> {len(cand)} unique candidate domains")

    # --- Phase 2: scrape each candidate -------------------------------------
    print("\n==> Phase 2: extracting contact details")
    seen_phones = set()
    for i, (d, url) in enumerate(cand, 1):
        if len([r for r in records if r.get("phones") or r.get("whatsapp")]) >= target:
            print(f"  reached target ({target}) -> stopping")
            break
        if d in done_domains:
            continue
        print(f"  [{i}/{len(cand)}] {d}")
        b = firecrawl("scrape", {
            "url": url,
            "formats": ["markdown", "rawHtml",
                        {"type": "json", "prompt": EXTRACT_PROMPT, "schema": EXTRACT_SCHEMA}],
            "onlyMainContent": False, "waitFor": 2500,
        })
        if not b:
            continue
        data = b.get("data", {}) or {}
        j = data.get("json", {}) or {}
        html = data.get("rawHtml") or data.get("html") or ""
        link_phones, link_wa = extract_links_numbers(html)

        # merge + validate numbers from both the LLM extraction and the raw links
        phones = set(link_phones)
        for p in (j.get("phones") or []):
            n = norm_phone(p)
            if n:
                phones.add(n)
        wa = set(link_wa)
        for p in (j.get("whatsapp") or []):
            n = norm_phone(p)
            if n:
                wa.add(n)
        # whatsapp numbers are also valid phones
        phones |= wa

        if not phones and not wa:
            continue
        rec = {
            "company": (j.get("company_name") or "").strip(),
            "is_real_estate": j.get("is_real_estate"),
            "city": (j.get("city") or "").strip(),
            "website": url,
            "domain": d,
            "phones": sorted(phones),
            "whatsapp": sorted(wa),
            "email": (j.get("email") or "").strip(),
            "address": (j.get("address") or "").strip(),
        }
        records.append(rec)
        seen_phones |= phones
        print(f"      {rec['company'][:40] or '(no name)'} | "
              f"phones={rec['phones']} wa={rec['whatsapp']}")
        # incremental save
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        time.sleep(0.5)

    # --- Phase 3: write CSV + Markdown --------------------------------------
    import csv
    with open("realestate_companies.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Company", "City", "Phones", "WhatsApp", "Email", "Website", "Address"])
        for r in records:
            w.writerow([r["company"], r["city"], "; ".join(r["phones"]),
                        "; ".join(r["whatsapp"]), r["email"], r["website"], r["address"]])

    with open("realestate_companies.md", "w", encoding="utf-8") as f:
        f.write("# Colombo Real Estate Companies — Contact Numbers\n\n")
        f.write(f"_{len(records)} companies with at least one published number_\n\n")
        for i, r in enumerate(records, 1):
            f.write(f"## {i}. {r['company'] or r['domain']}\n")
            if r["city"]:    f.write(f"- City: {r['city']}\n")
            if r["phones"]:  f.write(f"- Phone: {', '.join(r['phones'])}\n")
            if r["whatsapp"]:f.write(f"- WhatsApp: {', '.join(r['whatsapp'])}\n")
            if r["email"]:   f.write(f"- Email: {r['email']}\n")
            if r["address"]: f.write(f"- Address: {r['address']}\n")
            f.write(f"- Website: {r['website']}\n\n")

    withwa = sum(1 for r in records if r["whatsapp"])
    print(f"\n==> Done. {len(records)} companies ({withwa} with a WhatsApp link).")
    print("    realestate_companies.json / .csv / .md")


if __name__ == "__main__":
    main()
