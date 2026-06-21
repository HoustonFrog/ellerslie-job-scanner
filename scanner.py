#!/usr/bin/env python3
"""Ellerslie Job Scanner - scan accounting/finance jobs in Ellerslie, Greenlane, Remuera."""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

import yaml

import config
import seek
import careers
import enrich
import report
import linkedin

BASE_DIR = Path(__file__).parent
COMPANIES_FILE = BASE_DIR / "companies.yml"
HISTORY_FILE = BASE_DIR / "output" / "scan-history.json"


def load_history() -> dict:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return {"seen_urls": [], "scans": []}


def save_history(history: dict, new_jobs: list[dict]):
    history["seen_urls"].extend(j["url"] for j in new_jobs)
    history["seen_urls"] = list(set(history["seen_urls"]))
    history["scans"].append({
        "date": date.today().isoformat(),
        "jobs_found": len(new_jobs),
    })
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def _format_whatsapp(enriched: list) -> str:
    today = date.today()
    d = f"{today.month}.{today.day}"
    total = len(enriched)
    new_count = sum(1 for j in enriched if getattr(j, "is_new", True))

    push_jobs = [j for j in enriched if getattr(j, "is_new", True) or j.score_total >= 4.0]
    push_jobs.sort(key=lambda j: j.score_total, reverse=True)

    if not push_jobs and new_count == 0:
        return f"Ellerslie {d} · 今日无新增岗位"

    lines = [f"Ellerslie 岗位速报 {d}", ""]
    lines.append(f"新增 {new_count} 个 · 跟踪 {total} 个")

    for j in push_jobs:
        lines.append("")
        lines.append(f"▎*{j.title}*")
        meta = [j.company]
        if j.location:
            loc = j.location.split(",")[0].strip()
            meta.append(loc)
        sal = getattr(j, "salary_range", "")
        if sal and not getattr(j, "salary_is_estimate", True):
            import re as _re
            m = _re.findall(r"\$\s*([\d,]+)", sal)
            if len(m) >= 2:
                lo_k = int(m[0].replace(",", "")) // 1000
                hi_k = int(m[1].replace(",", "")) // 1000
                meta.append(f"${lo_k}k-{hi_k}k")
            elif m:
                k = int(m[0].replace(",", "")) // 1000
                meta.append(f"${k}k")
            else:
                meta.append(sal)
        lines.append(f"  {' · '.join(meta)}")
        detail = []
        ct = getattr(j, "contract_term", "")
        jt = getattr(j, "job_type", "")
        if ct == "permanent":
            detail.append("Permanent")
        elif ct == "fixed-term":
            detail.append("Fixed-term")
        elif jt and jt != "unknown":
            detail.append(jt.replace("-", " ").title())
        detail.append(f"{j.score_total}/5")
        lines.append(f"  {' · '.join(detail)}")

    rest = total - len(push_jobs)
    if rest > 0:
        rest_jobs = [j for j in enriched if j not in push_jobs]
        if rest_jobs:
            lo = min(j.score_total for j in rest_jobs)
            hi = max(j.score_total for j in rest_jobs)
            lines.append("")
            lines.append(f"其余 {rest} 个岗位 → {lo}-{hi}")

    lines.append("完整报告已生成")
    return "\n".join(lines)


def _send_whatsapp(message: str):
    api_url = os.environ.get("WHATSAPP_API", "")
    recipients_raw = os.environ.get("WHATSAPP_RECIPIENTS", "")
    if not api_url or not recipients_raw:
        return

    try:
        recipients = json.loads(recipients_raw)
    except json.JSONDecodeError:
        recipients = [recipients_raw.strip()]

    for recipient in recipients:
        if not recipient:
            continue
        data = json.dumps({"recipient": recipient, "message": message}).encode("utf-8")
        req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            result = json.loads(resp.read())
            if result.get("success"):
                print(f"  WhatsApp: sent to {recipient}")
            else:
                print(f"  WhatsApp error ({recipient}): {result}", file=sys.stderr)
        except Exception as e:
            print(f"  WhatsApp failed ({recipient}): {e}", file=sys.stderr)


def matches_title(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in config.POSITIVE_KEYWORDS)


def is_agency(company: str) -> bool:
    c = company.lower()
    return any(agency in c for agency in config.AGENCY_BLOCKLIST)


def _normalize_title(title: str) -> str:
    """Strip numeric prefixes like '2898 - ' for comparison."""
    import re
    return re.sub(r"^\d+\s*[-–]\s*", "", title).strip().lower()


def _merge_duplicates(jobs: list[dict]) -> list[dict]:
    """Merge Seek, LinkedIn, and career_page entries for the same role.
    Priority: seek > linkedin > career_page. Secondary URLs stored in career_url / linkedin_url."""
    SOURCE_PRIORITY = {"seek": 0, "linkedin": 1, "career_page": 2}

    by_key: dict[str, list[dict]] = {}
    for j in jobs:
        key = (j["company"].lower(), _normalize_title(j["title"]))
        by_key.setdefault(key, []).append(j)

    merged = []
    for group in by_key.values():
        if len(group) == 1:
            merged.append(group[0])
            continue

        by_source: dict[str, list[dict]] = {}
        for j in group:
            by_source.setdefault(j["source"], []).append(j)

        sorted_sources = sorted(by_source.keys(), key=lambda s: SOURCE_PRIORITY.get(s, 9))
        primary = by_source[sorted_sources[0]][0]

        source_labels = []
        for src in sorted_sources:
            if src == "career_page":
                primary.setdefault("career_url", by_source[src][0]["url"])
                source_labels.append("career")
            elif src == "linkedin":
                primary.setdefault("linkedin_url", by_source[src][0]["url"])
                source_labels.append("linkedin")
            elif src == "seek":
                source_labels.append("seek")

        if len(source_labels) > 1:
            primary["source"] = "+".join(source_labels)

        merged.append(primary)
        for src in sorted_sources:
            for extra in by_source[src][1:]:
                merged.append(extra)

    return merged


def cmd_discover():
    """Phase 1: Discover companies in target areas."""
    if COMPANIES_FILE.exists():
        print(f"companies.yml already exists at {COMPANIES_FILE}")
        print("Edit it directly or delete it to re-discover.")
        return

    prompt = """Find companies with offices in Ellerslie, Greenlane, or Remuera in Auckland, New Zealand.
Focus on companies that are likely to hire accounting or finance staff.
Include companies of all sizes - large corporates, mid-size businesses, and SMEs.

For each company provide:
- name: company name
- location: which suburb (Ellerslie, Greenlane, or Remuera)
- industry: what industry they are in
- careers_url: their careers/jobs page URL if you can find it, otherwise leave empty

Return ONLY valid YAML in this exact format, no other text:

companies:
  - name: "Example Company"
    location: "Ellerslie"
    industry: "Healthcare"
    careers_url: ""
    enabled: true"""

    print("Discovering companies via claude -p...")
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "sonnet"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"Error: {e}")
        print("Please install Claude CLI or run manually.")
        _write_template_companies()
        return

    if result.returncode != 0:
        print(f"Warning: claude -p failed, writing template file")
        _write_template_companies()
        return

    output = result.stdout.strip()
    yaml_match = None
    if output.startswith("companies:"):
        yaml_match = output
    else:
        m = __import__("re").search(r"(companies:[\s\S]+)", output)
        if m:
            yaml_match = m.group(1)

    if yaml_match:
        try:
            yaml.safe_load(yaml_match)
            header = "# Companies in Ellerslie, Greenlane, Remuera - Auckland\n"
            header += "# Review and edit this file. Set enabled: false to skip a company.\n"
            header += "# Add careers_url where known for direct career page scanning.\n\n"
            COMPANIES_FILE.write_text(header + yaml_match)
            print(f"Wrote {COMPANIES_FILE}")
            print("Please review and edit the file, then run: python3 scanner.py scan")
            return
        except yaml.YAMLError:
            pass

    print("Could not parse Claude response, writing template file")
    _write_template_companies()


def _write_template_companies():
    template = """# Companies in Ellerslie, Greenlane, Remuera - Auckland
# Review and edit this file. Set enabled: false to skip a company.
# Add careers_url where known for direct career page scanning.

companies:
  - name: "Example Company"
    location: "Ellerslie"
    industry: "Example"
    careers_url: ""
    enabled: true
"""
    COMPANIES_FILE.write_text(template)
    print(f"Template written to {COMPANIES_FILE}")
    print("Please fill in company details, then run: python3 scanner.py scan")


def cmd_scan(dry_run: bool = False, no_enrich: bool = False):
    """Phase 2: Scan, filter, enrich, report."""
    if not COMPANIES_FILE.exists():
        print("No companies.yml found. Run 'python3 scanner.py discover' first.")
        sys.exit(1)

    companies_data = yaml.safe_load(COMPANIES_FILE.read_text())
    company_list = companies_data.get("companies", []) if companies_data else []
    enabled_companies = [c for c in company_list if c.get("enabled", True)]

    print(f"=== Ellerslie Job Scanner ===")
    print(f"Date: {date.today().isoformat()}")
    print(f"Areas: Ellerslie, Greenlane, Remuera")
    print(f"Companies in registry: {len(enabled_companies)}")
    print()

    # 1. Seek NZ search
    print("[1/7] Scanning Seek NZ...")
    seek_jobs = seek.search_seek()
    all_jobs = [
        {"title": j.title, "url": j.url, "company": j.company,
         "source": "seek", "location": j.location,
         "listing_date": j.listing_date, "work_type": j.work_type}
        for j in seek_jobs
    ]

    # 2. LinkedIn search
    print(f"\n[2/7] Scanning LinkedIn...")
    li_jobs = linkedin.search_linkedin()

    # Match LinkedIn companies against companies.yml for location
    company_location_map = {c["name"].lower(): c.get("location", "") for c in enabled_companies}
    for lj in li_jobs:
        loc = lj.location
        comp_lower = lj.company.lower()
        for reg_name, reg_loc in company_location_map.items():
            if reg_name in comp_lower or comp_lower in reg_name:
                loc = reg_loc
                break
        all_jobs.append({
            "title": lj.title, "url": lj.url, "company": lj.company,
            "source": "linkedin", "location": loc,
            "listing_date": lj.listing_date,
        })

    # 3. Career page scraping
    print(f"\n[3/7] Scanning {len(enabled_companies)} company career pages...")
    for company in enabled_companies:
        if not company.get("careers_url"):
            continue
        print(f"  {company['name']}...")
        career_jobs = careers.scrape_career_page(company)
        for cj in career_jobs:
            all_jobs.append({
                "title": cj.title, "url": cj.url, "company": cj.company,
                "source": "career_page", "location": cj.location or company.get("location", ""),
            })
    print(f"  Total raw jobs: {len(all_jobs)}")

    # 4. Filter
    print(f"\n[4/7] Filtering...")
    seen_urls: set[str] = set()
    filtered = []
    skipped_title = 0
    skipped_agency = 0
    skipped_dup = 0

    for job in all_jobs:
        if job["url"] in seen_urls:
            skipped_dup += 1
            continue
        seen_urls.add(job["url"])

        if not matches_title(job["title"]):
            skipped_title += 1
            continue

        if is_agency(job["company"]):
            skipped_agency += 1
            continue

        filtered.append(job)

    print(f"  Passed: {len(filtered)} | Skipped: title={skipped_title}, agency={skipped_agency}, dup={skipped_dup}")

    # 4b. Merge Seek + LinkedIn + career_page duplicates for the same role
    filtered = _merge_duplicates(filtered)

    # 4. Mark new vs previously seen
    history = load_history()
    seen_history = set(history["seen_urls"])
    new_count = 0
    for j in filtered:
        j["is_new"] = j["url"] not in seen_history
        if j["is_new"]:
            new_count += 1
    print(f"  New (not in history): {new_count} / {len(filtered)} total")

    if dry_run:
        print(f"\n[DRY RUN] Would process {len(filtered)} jobs ({new_count} new):")
        for j in filtered:
            tag = "NEW" if j["is_new"] else "   "
            print(f"  [{tag}] [{j['source']}] {j['company']}: {j['title']}")
        return

    if not filtered:
        print("\nNo jobs found. Report not generated.")
        if os.environ.get("WHATSAPP_API"):
            d = f"{date.today().month}.{date.today().day}"
            _send_whatsapp(f"Ellerslie {d} · 今日无新增岗位")
        save_history(history, [])
        return

    new_jobs = filtered

    # 5. Fetch job descriptions + details from Seek detail pages
    print(f"\n[5/7] Fetching job details...")
    seek_jobs_to_fetch = [j for j in new_jobs if "seek" in j.get("source", "")]
    if seek_jobs_to_fetch:
        from playwright.sync_api import sync_playwright as _sp
        with _sp() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=config.BROWSER_UA, locale="en-NZ")
            for j in seek_jobs_to_fetch:
                details = seek.fetch_job_details(j["url"], browser_context=ctx)
                j["description_html"] = details["description_html"]
                if details["work_type"]:
                    j["work_type"] = details["work_type"]
                if details["salary"]:
                    j["salary"] = details["salary"]
                if details["description_html"]:
                    print(f"  Fetched: {j['title'][:50]}")
                else:
                    print(f"  No description: {j['title'][:50]}")
                import time
                time.sleep(1)
            browser.close()

    # Fetch LinkedIn job details
    li_jobs_to_fetch = [j for j in new_jobs if "linkedin" in j.get("source", "") and not j.get("description_html")]
    if li_jobs_to_fetch:
        import time
        for j in li_jobs_to_fetch:
            fetch_url = j.get("linkedin_url", j["url"]) if j.get("linkedin_url") else j["url"]
            if "linkedin.com" not in fetch_url:
                continue
            details = linkedin.fetch_linkedin_details(fetch_url)
            if details["description_html"] and not j.get("description_html"):
                j["description_html"] = details["description_html"]
            if details["employment_type"] and not j.get("work_type"):
                etype = details["employment_type"]
                if "FULL" in etype:
                    j["work_type"] = "Full time"
                elif "PART" in etype:
                    j["work_type"] = "Part time"
                elif "CONTRACT" in etype:
                    j["work_type"] = "Contract"
            if details["description_html"]:
                print(f"  Fetched (LI): {j['title'][:50]}")
            else:
                print(f"  No description (LI): {j['title'][:50]}")
            time.sleep(config.LINKEDIN_REQUEST_DELAY)

    # 6. Enrich
    print(f"\n[6/7] Enriching {len(new_jobs)} jobs...")
    if no_enrich:
        enriched = [enrich._default_enrichment(j) for j in new_jobs]
    else:
        enriched = enrich.enrich_jobs(new_jobs)

    # 7. Generate report
    print(f"\n[7/7] Generating HTML report...")
    report_path = report.generate_report(enriched)
    print(f"  Report: {report_path}")

    # 8. WhatsApp notification
    if os.environ.get("WHATSAPP_API"):
        print(f"\n[8/8] Sending WhatsApp notification...")
        msg = _format_whatsapp(enriched)
        _send_whatsapp(msg)

    # 9. Update history
    save_history(history, new_jobs)
    print(f"\nDone. {len(enriched)} new jobs in report.")


def main():
    parser = argparse.ArgumentParser(description="Ellerslie Job Scanner")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("discover", help="Discover companies in target areas")

    scan_parser = subparsers.add_parser("scan", help="Scan for jobs and generate report")
    scan_parser.add_argument("--dry-run", action="store_true", help="Preview without enrichment or report")
    scan_parser.add_argument("--no-enrich", action="store_true", help="Skip Claude enrichment")

    args = parser.parse_args()

    if args.command == "discover":
        cmd_discover()
    elif args.command == "scan":
        cmd_scan(dry_run=args.dry_run, no_enrich=args.no_enrich)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
