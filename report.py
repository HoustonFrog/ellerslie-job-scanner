"""Render the job report, including an offline rebuild from its saved snapshot."""

import argparse
import html
import json
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from string import Template
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import config


BASE_DIR = Path(__file__).parent
ELLERSLIE_AREAS = {"ellerslie", "greenlane", "remuera"}
SOURCE_LABELS = {"seek": "Seek", "linkedin": "LinkedIn", "career_page": "Career page", "career": "Career page"}


def _is_ellerslie_area(job) -> bool:
    return any(area in (getattr(job, "location", "") or "").lower() for area in ELLERSLIE_AREAS)


def _annual_salary_value(salary: str):
    """Return the lower advertised annual amount, without inventing hourly conversions."""
    if not salary or re.search(r"/\s*(?:h(?:ou)?r?s?|day|week|month)\b|per\s+(?:hour|day|week|month)|hourly|p\.?h\.?\b", salary, re.I):
        return None
    match = re.search(r"(?:\$|NZD\s*)?(\d[\d,]*(?:\.\d+)?)\s*(k)?", salary, re.I)
    if not match:
        return None
    amount = float(match.group(1).replace(",", ""))
    if match.group(2) or (amount < 1000 and re.search(r"\d\s*k\b", salary, re.I)):
        amount *= 1000
    return round(amount) if amount >= 10000 else None


def _sources(source: str):
    parts = (source or "unknown").lower().replace("both", "seek+career_page").split("+")
    return list(dict.fromkeys(SOURCE_LABELS.get(p, p.replace("_", " ").title()) for p in parts))


def _fallback_reason(job, language="zh"):
    """Make missing enrichment explicit rather than fabricating company or candidate facts."""
    summary = getattr(job, "summary", "") or ""
    if summary == "See job listing for details.":
        summary = ""
    intro = getattr(job, "company_intro", "") or ""
    facts = " ".join(p for p in (intro, summary) if p)
    if language == "en":
        facts = facts or "The company's business and specific duties need to be checked in the original listing."
        hours = "Confirm the part-time hours." if getattr(job, "job_type", "") == "part-time" else "Confirm whether the working hours can meet your part-time goal."
        return facts + " Assess the role against your budgeting, month-end and controls experience. " + hours
    if not facts:
        facts = "公司业务与具体职责尚待核实，请查看职位原文。"
    hours = "兼职安排可进一步确认。" if getattr(job, "job_type", "") == "part-time" else "工时是否符合兼职目标需确认。"
    return facts + " 可结合你的预算、月结和内控经验评估具体匹配度；" + hours


def _bilingual(en, zh, class_name="", tag="span"):
    esc = lambda value: html.escape(str(value or ""), quote=True)
    return f'<{tag} class="{class_name}" data-en="{esc(en)}" data-zh="{esc(zh)}">{esc(zh)}</{tag}>'


def _render_card(job, index=0):
    esc = lambda value: html.escape(str(value or ""), quote=True)
    title = str(job.title).replace(r"\u002F", "/")
    title_zh = getattr(job, "title_zh", "") or title
    title_html = _bilingual(title, title_zh)
    company = getattr(job, "company", "") or "Company not named"
    company_html = _bilingual(company, getattr(job, "company", "") or "招聘方未披露")
    location = getattr(job, "location", "") or "Location not disclosed"
    area = "nearby" if _is_ellerslie_area(job) else "other"
    is_new = bool(getattr(job, "is_new", True))
    salary = getattr(job, "salary_range", "") or ""
    salary_value = _annual_salary_value(salary)
    hourly = bool(re.search(r"/\s*h|per\s+hour|hourly", salary, re.I))
    first_number = re.search(r"\d[\d,]*(?:\.\d+)?", salary)
    hourly_value = float(first_number.group().replace(",", "")) if hourly and first_number else 0
    salary_band = 2 if salary_value is not None else (1 if hourly else 0)
    sort_salary = salary_value if salary_value is not None else hourly_value
    jt = getattr(job, "job_type", "unknown")
    work = config.JOB_TYPE_STYLES.get(jt, config.JOB_TYPE_STYLES["unknown"])["label"]
    if work == "Unknown":
        work = "Hours not disclosed"
    work_zh = {"part-time":"兼职", "full-time":"全职", "casual":"临时", "contract":"合同工"}.get(jt,"工时未披露")
    term = {"permanent": "Permanent", "fixed-term": "Fixed term"}.get(getattr(job, "contract_term", ""), "")
    work += " · " + term if term else ""
    work_zh += " · " + {"Permanent":"长期职位", "Fixed term":"固定期限"}.get(term, "") if term else ""
    work_html = _bilingual(work, work_zh)
    source = " + ".join(_sources(getattr(job, "source", "")))
    listing_date = getattr(job, "listing_date", "") or ""
    found_date = getattr(job, "date_found", "") or ""
    shown_date = listing_date or found_date
    try:
        shown_date = date.fromisoformat(shown_date[:10]).strftime("%d %b %Y")
    except ValueError:
        pass
    date_label = ("Posted " if listing_date else "Found ") + shown_date if shown_date else "Date not disclosed"
    date_zh = ("发布于 " if listing_date else "发现于 ") + (listing_date or found_date) if shown_date else "日期未披露"
    date_html = _bilingual(date_label, date_zh)
    reason = getattr(job, "recommendation_reason", "") or _fallback_reason(job)
    reason_en = getattr(job, "recommendation_reason_en", "") or _fallback_reason(job, "en")
    reason_html = _bilingual(reason_en, reason, "recommendation-text", "p")
    score = float(getattr(job, "score_total", 0))
    score_rows = []
    for key, label, label_zh in (("proximity", "Location", "地点"), ("relevance", "Role relevance", "职责相关度"), ("experience", "Experience fit", "经验匹配度"), ("company", "Company", "公司"), ("salary", "Salary", "薪资"), ("stability", "Stability", "稳定性")):
        value = max(0, min(5, int(getattr(job, "score_" + key, 0))))
        score_rows.append(f'<div class="score-dim">{_bilingual(label, label_zh)}<meter min="0" max="5" value="{value}">{value}/5</meter><span>{value}/5</span></div>')
    salary_label = esc(salary) if salary else '<span data-i18n="salaryUndisclosed">Salary not disclosed</span>'
    estimated = '<span class="salary-est" data-i18n="estimated">Estimated</span>' if salary and getattr(job, "salary_is_estimate", False) else ""
    new_label = '<span class="badge-new" data-i18n="newThisScan">New this scan</span>' if is_new else ""
    career_url = getattr(job, "career_url", "") or ""
    alternate = f'<a class="text-link" href="{esc(career_url)}" target="_blank" rel="noopener noreferrer"><span data-i18n="companyCareers">Company careers</span> ↗</a>' if career_url and career_url != job.url else ""
    description = getattr(job, "description_html", "") or '<p data-i18n="descriptionMissing">View the original listing for the full job description.</p>'
    search = " ".join((title, title_zh, company, location)).lower()
    return f'''<article class="job-card" id="job-{index}" data-area="{area}" data-new="{str(is_new).lower()}" data-score="{score}" data-date="{esc(listing_date or found_date)}" data-salary-band="{salary_band}" data-salary-sort="{sort_salary}" data-search="{esc(search)}">
      <div class="card-topline"><span class="work-type">{work_html}</span>{new_label}<span class="date-tag">{date_html}</span></div>
      <div class="card-heading"><div class="job-heading-text"><h2 class="job-title"><a href="{esc(job.url)}" target="_blank" rel="noopener noreferrer">{title_html}</a></h2><p class="company-name">{company_html}</p></div>
        <div class="score-summary" data-i18n-aria="match" aria-label="Match"><span class="score-number">{score:.1f}<small>/5</small></span><span class="score-caption" data-i18n="match">Match</span></div></div>
      <div class="job-facts"><span class="job-location">{esc(location)}</span><span class="job-salary{' undisclosed' if not salary else ''}">{salary_label}</span>{estimated}</div>
      <div class="recommendation" lang="zh-CN"><span class="recommendation-label" data-i18n="recommendation">推荐理由</span>{reason_html}</div>
      <div class="card-actions"><a class="apply-btn" href="{esc(job.url)}" target="_blank" rel="noopener noreferrer"><span data-i18n="viewJob">View job</span> <span aria-hidden="true">↗</span></a><a class="details-link" href="#details-{index}" data-details="details-{index}"><span data-detail-label>Read details</span> <span aria-hidden="true">＋</span></a><span class="source-label">{_bilingual(source, source.replace('Career page','公司官网'))}</span></div>
      <details class="job-details" id="details-{index}"><summary><span data-i18n="jobDescription">Original job description (English)</span><span aria-hidden="true">＋</span></summary><div class="job-description" lang="en">{description}</div>{alternate}</details>
      <details class="score-details"><summary><span data-i18n="matchBreakdown">Match breakdown</span><span aria-hidden="true">＋</span></summary><div class="score-dims">{''.join(score_rows)}</div></details>
    </article>'''


def render_report(jobs: list, report_date=None, generated_at=None) -> str:
    now = datetime.now(ZoneInfo("Pacific/Auckland"))
    day = date.fromisoformat(report_date) if isinstance(report_date, str) else (report_date or now.date())
    timestamp = generated_at or now.strftime("%Y-%m-%d %H:%M")
    ordered = sorted(jobs, key=lambda j: getattr(j, "score_total", 0), reverse=True)
    providers = {source for j in jobs for source in _sources(getattr(j, "source", ""))}
    nearby = sum(_is_ellerslie_area(j) for j in jobs)
    template = Template((BASE_DIR / "templates/report.html").read_text())
    return template.substitute(
        date=day.strftime("%d %B %Y"), date_iso=day.isoformat(), timestamp=html.escape(timestamp),
        total=len(jobs), new_count=sum(bool(getattr(j, "is_new", True)) for j in jobs),
        nearby_count=nearby, other_count=len(jobs) - nearby, source_count=len(providers),
        sources=html.escape(" · ".join(sorted(providers))),
        cards="\n".join(_render_card(job, i) for i, job in enumerate(ordered)),
        i18n_script=(BASE_DIR / "templates/report-i18n.js").read_text(),
    )


def generate_report(jobs: list, output_dir: str = "output", report_date=None, generated_at=None) -> str:
    out_path = BASE_DIR / output_dir
    out_path.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ZoneInfo("Pacific/Auckland"))
    day = report_date.isoformat() if isinstance(report_date, date) else (report_date or now.date().isoformat())
    timestamp = generated_at or now.strftime("%Y-%m-%d %H:%M")
    filepath = out_path / "ellerslie-jobs.html"
    filepath.write_text(render_report(jobs, day, timestamp), encoding="utf-8")
    snapshot = {"report_date": day, "generated_at": timestamp, "jobs": [vars(job) for job in jobs]}
    (out_path / "jobs-snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(filepath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild the local report from saved jobs; no scraping or notifications.")
    parser.add_argument("--snapshot", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text(encoding="utf-8"))
    jobs = [SimpleNamespace(**job) for job in data["jobs"]]
    result = generate_report(jobs, report_date=data["report_date"], generated_at=data["generated_at"])
    shutil.copy2(result, BASE_DIR / "index.html")
    print(f"Rebuilt {len(jobs)} jobs from {data['report_date']}: {result}")
