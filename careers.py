import re
import json
from typing import List
from urllib.parse import urljoin
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

import config


@dataclass
class CareerJob:
    title: str
    url: str
    company: str
    source: str = "career_page"
    location: str = ""


def scrape_career_page(company: dict) -> List[CareerJob]:
    """Scrape a company's career page for job listings.
    Dispatches based on URL pattern to specialized handlers."""
    url = company.get("careers_url", "")
    name = company.get("name", "Unknown")
    if not url:
        return []

    handlers = [
        (r"boards-api\.greenhouse\.io|boards\.greenhouse\.io|job-boards\.greenhouse\.io", _greenhouse),
        (r"\.myworkdayjobs\.com", _workday),
        (r"careers\.smartrecruiters\.com|api\.smartrecruiters\.com", _smartrecruiters),
        (r"jobs\.ashbyhq\.com", _ashby),
        (r"jobs\.lever\.co|api\.lever\.co", _lever),
    ]

    for pattern, handler in handlers:
        if re.search(pattern, url):
            try:
                return handler(url, name)
            except Exception as e:
                print(f"    Warning: {name}: {handler.__name__} failed: {e}")
                return []

    try:
        return _generic_html(url, name)
    except Exception as e:
        print(f"    Warning: {name}: generic scrape failed: {e}")
        return []


def _http_get(url: str, **kwargs) -> requests.Response:
    return requests.get(
        url,
        headers={"User-Agent": config.BROWSER_UA},
        timeout=config.REQUEST_TIMEOUT,
        **kwargs,
    )


def _http_post_json(url: str, payload: dict) -> dict:
    resp = requests.post(
        url,
        headers={"User-Agent": config.BROWSER_UA, "Content-Type": "application/json"},
        json=payload,
        timeout=config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _greenhouse(url: str, company_name: str) -> List[CareerJob]:
    m = re.search(r"job-boards(?:\.eu)?\.greenhouse\.io/([^/?#]+)", url)
    if not m:
        m = re.search(r"boards-api\.greenhouse\.io/v1/boards/([^/?#]+)", url)
    if not m:
        return []
    slug = m.group(1)
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    resp = _http_get(api_url)
    resp.raise_for_status()
    data = resp.json()
    jobs = data.get("jobs", [])
    return [
        CareerJob(
            title=j.get("title", ""),
            url=j.get("absolute_url", ""),
            company=company_name,
            location=j.get("location", {}).get("name", ""),
        )
        for j in jobs
        if j.get("absolute_url")
    ]


def _lever(url: str, company_name: str) -> List[CareerJob]:
    m = re.search(r"jobs\.lever\.co/([^/?#]+)", url)
    if not m:
        return []
    slug = m.group(1)
    api_url = f"https://api.lever.co/v0/postings/{slug}"
    resp = _http_get(api_url)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    return [
        CareerJob(
            title=j.get("text", ""),
            url=j.get("hostedUrl", ""),
            company=company_name,
            location=j.get("categories", {}).get("location", ""),
        )
        for j in data
        if j.get("hostedUrl")
    ]


def _workday(url: str, company_name: str) -> List[CareerJob]:
    m = re.match(r"https?://([^.]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[\w-]+/)*([^/?#]+)", url)
    if not m:
        return []
    tenant, shard, site = m.group(1), m.group(2), m.group(3)
    api_url = f"https://{tenant}.{shard}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"

    jobs = []
    offset = 0
    while True:
        data = _http_post_json(api_url, {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""})
        total = data.get("total", 0)
        postings = data.get("jobPostings", [])
        if not postings:
            break
        for j in postings:
            if not j.get("title") or not j.get("externalPath"):
                continue
            jobs.append(CareerJob(
                title=j["title"],
                url=f"https://{tenant}.{shard}.myworkdayjobs.com{j['externalPath']}",
                company=company_name,
                location=j.get("locationsText", ""),
            ))
        offset += len(postings)
        if offset >= total:
            break
    return jobs


def _smartrecruiters(url: str, company_name: str) -> List[CareerJob]:
    m = re.search(r"careers\.smartrecruiters\.com/([^/?#]+)", url)
    if not m:
        return []
    company_id = m.group(1)
    api_url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings?limit=100"
    resp = _http_get(api_url)
    resp.raise_for_status()
    data = resp.json()
    postings = data.get("content", [])
    return [
        CareerJob(
            title=j.get("name", ""),
            url=f"https://careers.smartrecruiters.com/{company_id}/{j.get('id', '')}",
            company=company_name,
            location=j.get("location", {}).get("city", ""),
        )
        for j in postings
        if j.get("name")
    ]


def _ashby(url: str, company_name: str) -> List[CareerJob]:
    m = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)", url)
    if not m:
        return []
    slug = m.group(1)
    data = _http_post_json(
        "https://api.ashbyhq.com/posting-api/job-board-list",
        {"apiKey": slug},
    )
    jobs = data.get("jobs", [])
    return [
        CareerJob(
            title=j.get("title", ""),
            url=j.get("jobUrl", f"https://jobs.ashbyhq.com/{slug}/{j.get('id', '')}"),
            company=company_name,
            location=j.get("location", ""),
        )
        for j in jobs
        if j.get("title")
    ]


def _generic_html(url: str, company_name: str) -> List[CareerJob]:
    resp = _http_get(url, allow_redirects=True)
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return []
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    job_path_patterns = ["/job/", "/position/", "/vacancy/", "/career/", "/opening/", "/jobs/"]
    jobs = []
    seen_urls: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        if any(seg in href.lower() for seg in job_path_patterns):
            full_url = urljoin(url, href)
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                jobs.append(CareerJob(title=text, url=full_url, company=company_name))

    if not jobs:
        for container in soup.find_all(class_=re.compile(r"job|career|opening|vacancy|position", re.I)):
            for a in container.find_all("a", href=True):
                text = a.get_text(strip=True)
                if not text or len(text) < 5:
                    continue
                full_url = urljoin(url, a["href"])
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    jobs.append(CareerJob(title=text, url=full_url, company=company_name))

    return jobs
