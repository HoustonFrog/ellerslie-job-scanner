import re
import time
import html as html_mod
from typing import List, Optional

from dataclasses import dataclass
from playwright.sync_api import sync_playwright

import config


@dataclass
class SeekJob:
    id: str
    title: str
    company: str
    url: str
    location: str = ""
    listing_date: str = ""
    work_type: str = ""


def extract_jobs_from_html(raw_html: str) -> List[dict]:
    """Parse Seek embedded JSON from script blocks.
    Port of career-ops seek-nz.mjs extractJobs()."""
    script_blocks = [
        m.group(1)
        for m in re.finditer(r"<script[^>]*>([\s\S]+?)</script>", raw_html)
        if '"jobId"' in m.group(1) and len(m.group(1)) > 500
    ]
    if not script_blocks:
        return []

    s = script_blocks[0]

    company_map = {}
    for m in re.finditer(r'"companyName":"([^"]+)".{0,300}?"id":"(\d{7,})"', s, re.DOTALL):
        company, job_id = m.group(1), m.group(2)
        if job_id not in company_map:
            company_map[job_id] = html_mod.unescape(company)

    title_map = {}
    for m in re.finditer(r'"jobId":"(\d{7,})".{10,600}?"title":"([^"]+)"', s, re.DOTALL):
        job_id, title = m.group(1), m.group(2)
        if job_id not in title_map:
            title_map[job_id] = html_mod.unescape(title)

    listing_date_map = {}
    for m in re.finditer(r'"jobId":"(\d{7,})"', s):
        jid = m.group(1)
        if jid in listing_date_map:
            continue
        rest = s[m.end():m.end() + 800]
        ld = re.search(r'"listingDate":"([^"]+)"', rest)
        if ld:
            listing_date_map[jid] = ld.group(1)[:10]

    work_type_map = {}
    for m in re.finditer(r'"jobId":"(\d{7,})"', s):
        jid = m.group(1)
        if jid in work_type_map:
            continue
        rest = s[m.end():m.end() + 800]
        wt = re.search(r'"workTypes":\[([^\]]*)\]', rest)
        if wt:
            work_type_map[jid] = html_mod.unescape(wt.group(1).strip('"'))

    all_ids = set(company_map.keys()) | set(title_map.keys())
    return [
        {
            "id": jid,
            "title": title_map.get(jid, ""),
            "company": company_map.get(jid, ""),
            "listing_date": listing_date_map.get(jid, ""),
            "work_type": work_type_map.get(jid, ""),
        }
        for jid in all_ids
    ]


def _extract_location_from_html(raw_html: str, job_id: str) -> str:
    """Try to extract location for a specific job from the embedded JSON."""
    p1 = rf'"id":"{job_id}".{{0,500}}?"label":"([^"]+)"'
    m1 = re.search(p1, raw_html, re.DOTALL)
    if m1:
        return html_mod.unescape(m1.group(1))

    p2 = rf'"jobId":"{job_id}".{{0,800}}?"location":"([^"]+)"'
    m2 = re.search(p2, raw_html, re.DOTALL)
    if m2:
        return html_mod.unescape(m2.group(1))

    p3 = rf'"jobId":"{job_id}".{{0,800}}?"suburb":"([^"]+)"'
    m3 = re.search(p3, raw_html, re.DOTALL)
    if m3:
        return html_mod.unescape(m3.group(1))
    return ""


def fetch_job_details(job_url: str, browser_context=None) -> dict:
    """Fetch job description, work type, and salary from a Seek job detail page.
    Returns dict with keys: description_html, work_type, salary."""
    result = {"description_html": "", "work_type": "", "salary": ""}
    try:
        if browser_context:
            page = browser_context.new_page()
            page.goto(job_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)
            raw_html = page.content()
            page.close()
        else:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(user_agent=config.BROWSER_UA, locale="en-NZ")
                pg = ctx.new_page()
                pg.goto(job_url, wait_until="domcontentloaded", timeout=15000)
                pg.wait_for_timeout(2000)
                raw_html = pg.content()
                browser.close()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")

        desc = soup.find(attrs={"data-automation": "jobAdDetails"})
        if desc:
            result["description_html"] = desc.decode_contents()

        wt = soup.find(attrs={"data-automation": "job-detail-work-type"})
        if wt:
            result["work_type"] = wt.get_text(strip=True)

        sal = soup.find(attrs={"data-automation": "job-detail-salary"})
        if sal:
            sal_text = sal.get_text(strip=True)
            if "$" in sal_text:
                result["salary"] = sal_text
    except Exception:
        pass
    return result


def _matches_location(location: str) -> bool:
    """Check if a job location matches any of our target areas."""
    if not location:
        return True
    loc_lower = location.lower()
    return any(area in loc_lower for area in config.LOCATION_ALLOW)


def search_seek(keyword_groups: Optional[List[str]] = None) -> List[SeekJob]:
    """Search Seek NZ for jobs matching keywords in target locations.
    Uses Playwright for browser-based fetching (Seek blocks non-browser requests)."""
    if keyword_groups is None:
        keyword_groups = config.SEARCH_KEYWORD_GROUPS

    seen_ids = set()
    results = []

    search_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=config.BROWSER_UA,
            locale="en-NZ",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for keyword in keyword_groups:
            for location in config.LOCATION_TARGETS:
                for page_num in range(1, 4):
                    url = config.SEEK_SEARCH_TEMPLATE.format(
                        keyword=keyword.replace(" ", "+"),
                        location=location,
                    )
                    if page_num > 1:
                        url += "&page={}".format(page_num)

                    search_count += 1
                    print("  [{}] Seek: {} in {} (page {})".format(
                        search_count,
                        keyword, location.replace("+", " "), page_num
                    ))

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(2000)
                        raw_html = page.content()
                    except Exception as e:
                        print("    Warning: page load failed: {}".format(e))
                        break

                    jobs = extract_jobs_from_html(raw_html)

                    if not jobs:
                        break

                    page_new = 0
                    for job in jobs:
                        jid = job["id"]
                        if jid in seen_ids:
                            continue
                        seen_ids.add(jid)

                        loc = _extract_location_from_html(raw_html, jid)
                        if not _matches_location(loc):
                            continue

                        page_new += 1
                        results.append(SeekJob(
                            id=jid,
                            title=job["title"],
                            company=job["company"],
                            url="https://nz.seek.com/job/{}".format(jid),
                            location=loc or location.replace("+", " "),
                            listing_date=job.get("listing_date", ""),
                            work_type=job.get("work_type", ""),
                        ))

                    if page_new == 0:
                        break

                    time.sleep(1)

        browser.close()

    print("  Seek: {} jobs found across {} searches".format(len(results), search_count))
    return results
