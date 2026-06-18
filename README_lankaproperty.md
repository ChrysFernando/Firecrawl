# LankaPropertyWeb scraper (Firecrawl)

Scrapes Colombo rental listings (House / Apartment / Commercial, 3-room) from
lankapropertyweb.com using the [Firecrawl](https://firecrawl.dev) API, follows
each property's detail page, and dumps everything to text + JSON.

## Run

```bash
pip install -r requirements.txt
export FIRECRAWL_API_KEY="fc-...."        # your Firecrawl key
python scrape_lankaproperty.py
```

Outputs:
- `scraped_data.txt`  — human-readable dump of every property
- `scraped_data.json` — structured records (url, title, description, markdown)

## Options

```bash
python scrape_lankaproperty.py --max-pages 10   # limit listing pages
python scrape_lankaproperty.py --delay 1.5      # be gentler between requests
python scrape_lankaproperty.py --debug-links    # print all links on page 1
```

If property links aren't detected, run `--debug-links` once and adjust the
`PROPERTY_URL_RE` regex near the top of `scrape_lankaproperty.py` to match the
actual ad URL pattern the site uses.

## Why a script (and not run here)?

The site returns HTTP 403 to plain requests (bot protection) — Firecrawl gets
past that. However, the remote Claude Code environment's network egress policy
blocks `api.firecrawl.dev`, so the API can't be called from inside the sandbox.
Run this script on your own machine, or add `api.firecrawl.dev` (and
`www.lankapropertyweb.com`) to the environment's egress allowlist so it can run
here.
