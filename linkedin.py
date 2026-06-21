# linkedin.py
"""LinkedIn Jobs Guest API search."""

import html as html_mod
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

import config


@dataclass
class LinkedInJob:
    id: str
    title: str
    company: str
    url: str
    location: str = ""
    listing_date: str = ""
    employment_type: str = ""


def parse_job_cards(raw_html: str) -> List[LinkedInJob]:
    """Parse LinkedIn guest API HTML response into job objects."""
    seen_ids = set()
    jobs = []

    for m in re.finditer(r'data-entity-urn="urn:li:jobPosting:(\d+)"', raw_html):
        jid = m.group(1)
        if jid in seen_ids:
            continue
        seen_ids.add(jid)

        rest = raw_html[m.start():m.start() + 3000]

        title_m = re.search(
            r'<h3[^>]*class="base-search-card__title[^"]*"[^>]*>\s*(.+?)\s*</h3>',
            rest, re.DOTALL)
        comp_m = re.search(
            r'<a[^>]*hidden-nested-link[^>]*>\s*(.+?)\s*</a>',
            rest, re.DOTALL)
        loc_m = re.search(
            r'<span class="job-search-card__location">\s*(.+?)\s*</span>',
            rest)
        date_m = re.search(r'datetime="([^"]+)"', rest)
        url_m = re.search(
            r'href="(https://nz\.linkedin\.com/jobs/view/[^"]+)"', rest)

        title = html_mod.unescape(title_m.group(1).strip()) if title_m else ""
        if not title:
            continue

        job_url = url_m.group(1).split("?")[0] if url_m else f"https://www.linkedin.com/jobs/view/{jid}"

        jobs.append(LinkedInJob(
            id=jid,
            title=title,
            company=html_mod.unescape(comp_m.group(1).strip()) if comp_m else "",
            url=job_url,
            location=html_mod.unescape(loc_m.group(1).strip()) if loc_m else "",
            listing_date=date_m.group(1)[:10] if date_m else "",
        ))

    return jobs


def parse_job_details(raw_html: str) -> dict:
    """Parse a LinkedIn job detail page for description and metadata."""
    result = {"description_html": "", "employment_type": "", "job_criteria": []}

    jsonld_m = re.search(
        r'<script type="application/ld\+json"[^>]*>([\s\S]*?)</script>',
        raw_html)
    if jsonld_m:
        try:
            ld = json.loads(jsonld_m.group(1))
            result["employment_type"] = ld.get("employmentType", "")
        except json.JSONDecodeError:
            pass

    desc_m = re.search(
        r'<div class="show-more-less-html__markup[^"]*"[^>]*>([\s\S]*?)</div>',
        raw_html)
    if desc_m:
        result["description_html"] = desc_m.group(1).strip()

    result["job_criteria"] = [
        html_mod.unescape(c.strip())
        for c in re.findall(
            r'<span class="description__job-criteria-text[^"]*"[^>]*>\s*([^<]+)',
            raw_html)
    ]

    return result


def _fetch_page(url: str) -> str:
    """Fetch a URL with browser-like headers."""
    req = urllib.request.Request(url, headers={
        "User-Agent": config.BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-NZ,en;q=0.9",
    })
    resp = urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT)
    return resp.read().decode("utf-8")


def search_linkedin(keyword_groups: Optional[List[str]] = None) -> List[LinkedInJob]:
    """Search LinkedIn Jobs guest API for accounting roles in Auckland."""
    if keyword_groups is None:
        keyword_groups = config.SEARCH_KEYWORD_GROUPS

    seen_ids = set()
    results = []
    search_count = 0
    delay = getattr(config, "LINKEDIN_REQUEST_DELAY", 3)

    for keyword in keyword_groups:
        for start in range(0, 40, 10):
            url = config.LINKEDIN_SEARCH_TEMPLATE.format(
                keyword=keyword.replace(" ", "+"),
                start=start,
            )
            search_count += 1
            print(f"  [{search_count}] LinkedIn: {keyword} (start={start})")

            try:
                raw_html = _fetch_page(url)
            except Exception as e:
                print(f"    Warning: request failed: {e}")
                break

            jobs = parse_job_cards(raw_html)
            if not jobs:
                break

            page_new = 0
            for job in jobs:
                if job.id in seen_ids:
                    continue
                seen_ids.add(job.id)
                results.append(job)
                page_new += 1

            if page_new == 0:
                break

            time.sleep(delay)

    print(f"  LinkedIn: {len(results)} jobs found across {search_count} searches")
    return results


def fetch_linkedin_details(job_url: str) -> dict:
    """Fetch description and metadata from a LinkedIn job detail page."""
    try:
        raw_html = _fetch_page(job_url)
        return parse_job_details(raw_html)
    except Exception:
        return {"description_html": "", "employment_type": "", "job_criteria": []}
