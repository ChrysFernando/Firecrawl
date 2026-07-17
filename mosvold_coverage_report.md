# Mosvold Site — Coverage Audit & "Embedded URL" Report

## 1. Are all sibling pages scraped? ✅ YES

I cross-checked the 75 scraped pages against **every internal link found across all pages** (221 link references). Every real **content page** is scraped, including all the siblings you mentioned:

| Sibling | Scraped |
|---|---|
| /experiences/ | ✅ |
| /contact-us/ | ✅ |
| /about-us/ · /our-hotels/ · /offers/ · /our-gallery/ | ✅ |
| Mosvold Villa: rooms (6), dining, experiences (9), offers (3), gallery, location, contact | ✅ |
| Sundara: rooms (6), dining, experiences (9), offers (3), gallery, location | ✅ |
| Blog (all posts + categories) | ✅ |
| Policies (privacy, terms, cancellation/payment) | ✅ |

**Nothing content-bearing was missed.** The links that showed up as "not scraped" in the raw audit were all **non-content**:
- Malformed duplicates (a doubled hostname in some hreflang links) — same pages already scraped.
- `/*/feed`, `/comments/feed` — RSS feeds (machine data, not pages).
- `/experiences/page/2,3,4` etc. — pagination of the experience **listing**; all 23 individual experience pages they point to are already scraped.
- `/blog/tag/hotel-news-events` — a tag archive (re-lists existing posts).
- `/wp-json/...`, `/xmlrpc.php`, `/cdn-cgi/l/email-protection` — WordPress/Cloudflare system endpoints.

## 2. Is any data "embedded as URL"? ⚠️ YES — three kinds

**a) Room PRICES → external booking engine (dynamic).**
Prices are **not stored on the website.** Every "Book Now" / rate points to a third-party reservation engine:
`https://mosvoldboutiquehotels.bookingeye.net/rooms?pr=1&ci=<date>&co=<date>` (pr=1 Mosvold Villa, pr=2 Sundara).
Rates are fetched live per check-in/check-out date via an authenticated AJAX call, so there is no fixed price list to scrape — the number only exists once you pick dates. (The page ships with `avail = false` until that call runs.)

**b) Structured content API (WordPress REST).**
The whole site's content is also exposed as JSON at `/wp-json/wp/v2/pages/<id>` and `/wp-json/wp/v2/posts/<id>`. Same content I already scraped, just in raw JSON form.

**c) External destinations linked from the site:**
- Booking engine: mosvoldboutiquehotels.bookingeye.net
- Facebook: /MosvoldVillas, /mosvoldsundara
- Instagram: /mosvold.villa, /sundarabymosvold

## 3. Prices & Offers
- **Offers:** fully scraped — 6 packages with inclusions, discount %, min-stay, validity & full T&Cs (see `mosvold_offers.md`). ⚠️ All validity dates are 2025 → currently **expired** on the site.
- **Prices:** dynamic via BookingEye (see 2a). If you want, I can fetch a **live quote** for specific dates from that engine.
