# taskforceai.tech scraper (Firecrawl)

Crawls the [taskforceai.tech](https://taskforceai.tech) website using the
[Firecrawl](https://firecrawl.dev) API and dumps every crawled page to
text + JSON.

## Run

```bash
pip install -r requirements.txt
export FIRECRAWL_API_KEY="fc-...."        # your Firecrawl key
python scrape_taskforceai.py
```

Outputs:
- `taskforceai_scrape.txt`  — human-readable dump of every page
- `taskforceai_scrape.json` — structured records (url, title, description, markdown)

## Options

```bash
python scrape_taskforceai.py --limit 100          # crawl more pages
python scrape_taskforceai.py --poll-interval 5    # poll less often
```

## Why this wasn't run here

This Claude Code cloud session's network egress policy blocks
`api.firecrawl.dev` (the proxy rejects the CONNECT tunnel with a 403 policy
denial), so the crawl could not be executed from inside the sandbox — same
limitation already documented in `README_lankaproperty.md` for the other
scraper in this repo. Run this script on your own machine (or any
environment whose egress allowlist includes `api.firecrawl.dev`) with your
Firecrawl API key.
