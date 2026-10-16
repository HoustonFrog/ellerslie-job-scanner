# Ellerslie Job Scanner

Automated accounting & finance job scanner for the Ellerslie area (Auckland, NZ). Aggregates listings from three sources, scores them on six dimensions, and delivers a polished HTML report with optional WhatsApp notification.

## Why

Finding jobs near a specific suburb is tedious — Seek limits by region, LinkedIn only goes to city level, and company career pages require manual checking. This tool automates the entire workflow: search → filter → deduplicate → enrich → score → report.

## Data Sources

| Source | Method | Coverage |
|--------|--------|----------|
| **Seek NZ** | Playwright browser scraping | Suburb-level search across 8 target areas |
| **LinkedIn** | Guest API (no login required) | Auckland-wide, suburb extracted via enrichment |
| **Company Career Pages** | HTTP/API scraping per company | 84 registered companies in the Ellerslie vicinity |

Jobs appearing on multiple sources are merged with source priority (Seek > LinkedIn > Career Page) and tagged with combined badges (e.g. `seek+linkedin`, `seek+linkedin+career`).

## Scoring System

Six weighted dimensions, each scored 1–5:

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Proximity | 30% | Distance from Ellerslie School (134 Main Highway) |
| Relevance | 20% | Match to core accounting/finance work |
| Experience | 15% | Fit to the candidate's senior accounting background, hands-on part-time goal and specialist skill gaps |
| Company | 15% | Company quality and career growth potential |
| Salary | 10% | Competitiveness of compensation |
| Stability | 10% | Permanent vs fixed-term/contract |

Weighted total (max 5.0) determines ranking in the report.

## Candidate and recommendations

`config.CANDIDATE_PROFILE` contains professional facts from the resume supplied on 17 October 2026: CPA Australia, CMA, University of Auckland MProfAcct with Distinction, finance leadership, international accounting firm audit and multinational experience, Excel, Power BI and Xero. It excludes the candidate's name, past employer names and contact details. Each card includes concise Chinese and English explanations of the company's business, main duties, candidate fit and any important mismatch, addressing the candidate as "you". Company and salary information must come from the listing; undisclosed salaries remain empty.

The 15 October report's recommendations and experience-fit scores were reviewed against that resume. Its other original scoring dimensions and data period were preserved.

## Offline report updates

The presentation is in `templates/report.html`. Both published HTML files are self-contained, with no external font or script dependencies. Search, area filters, new-only filtering, sorting and appearance work locally.

The top-right Chinese/English selector changes the interface, job titles and recommendation text without resetting filters or open details. It remembers the selection locally. Complete job descriptions remain labelled English originals. The interface dictionary in `templates/report-i18n.js` is embedded into the generated HTML; no separate script needs to be hosted. AI enrichment supplies `title_zh`, `recommendation_reason` and `recommendation_reason_en`.

Job analysis uses the project-level `CODEX_ENRICH_MODEL` and `CODEX_ENRICH_REASONING_EFFORT` settings in `config.py`, independently of the desktop app's selected model. The compatible `gpt-6-sol` model was verified with the signed-in account on 17 October 2026. Calls use read-only ephemeral sessions and clean last-message output.

To rebuild from saved listings without scraping, AI calls, scan-history updates or notifications:

```bash
python3 report.py --snapshot output/jobs-snapshot.json
```

This preserves the original report date and refreshes both `output/ellerslie-jobs.html` and `index.html`. `generate_report` saves the snapshot on future normal scans too. Annual salary sorting uses the lower advertised amount (or the maximum for "up to" offers), with hourly rates sorted separately afterward; it does not infer annual pay from hourly rates or prorate FTE salaries.

Local review server, restricted to the report page on loopback:

```bash
python3 scripts/preview_report.py
```

## Pipeline

```
scanner.py scan
  │
  ├─ [1/7] Seek NZ ─────────── Playwright, 6 keyword groups × 8 locations
  ├─ [2/7] LinkedIn ─────────── Guest API, 6 keyword groups × 4 pages each
  ├─ [3/7] Career Pages ─────── 84 companies, HTTP scraping
  ├─ [4/7] Filter ───────────── Title matching, agency blocklist, dedup
  ├─ [5/7] Fetch Details ────── Full job descriptions from Seek & LinkedIn
  ├─ [6/7] Enrich ───────────── ChatGPT via Codex CLI (scoring, salary, suburb)
  └─ [7/7] Report ───────────── HTML generation + WhatsApp notification
```

## Output

- **HTML Report** — Dark/light mode, responsive layout, expandable job cards with score breakdown, source badges, salary estimates, and direct application links
- **WhatsApp Notification** — Brief summary with new/high-scoring jobs pushed to phone
- **Scan History** — JSON log preventing duplicate processing across runs

## Project Structure

```
ellerslie job/
├── scanner.py          # Main orchestrator — CLI entry point
├── seek.py             # Seek NZ scraper (Playwright)
├── linkedin.py         # LinkedIn Guest API scraper
├── careers.py          # Company career page scraper
├── enrich.py           # ChatGPT/Codex enrichment (scoring, salary, suburb)
├── report.py           # HTML report generator
├── config.py           # Keywords, locations, weights, constants
├── companies.yml       # 84 companies registry with locations
├── requirements.txt    # Python dependencies
├── tests/
│   └── test_linkedin.py  # LinkedIn parsing & merge tests
└── output/
    ├── ellerslie-jobs-YYYY-MM-DD.html
    └── scan-history.json
```

## Usage

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Full scan with enrichment and report
python scanner.py scan

# Preview mode (no enrichment, no report)
python scanner.py scan --dry-run

# Skip AI enrichment (use default scores)
python scanner.py scan --no-enrich

# Discover companies in target areas (Google Maps API)
python scanner.py discover
```

## Requirements

- Python 3.9+
- [Codex CLI](https://developers.openai.com/codex/cli/) logged in with ChatGPT (`codex login`) for AI enrichment
- Playwright + Chromium for Seek scraping
- WhatsApp Bridge API at `localhost:8080` (optional, for notifications)

## Tech Stack

- **Scraping**: Playwright (Seek), urllib + regex (LinkedIn), requests + BeautifulSoup (Career Pages)
- **AI Enrichment**: ChatGPT via Codex CLI (`codex exec`) — batched in groups of 15
- **Report**: Pure HTML/CSS/JS, no framework — dark mode, responsive, print-friendly
- **Notification**: WhatsApp Bridge HTTP API
