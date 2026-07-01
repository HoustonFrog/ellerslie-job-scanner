import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date

import config


@dataclass
class EnrichedJob:
    title: str
    url: str
    company: str
    source: str
    location: str
    summary: str
    company_intro: str
    job_type: str
    date_found: str
    listing_date: str = ""
    work_type: str = ""
    contract_term: str = ""
    description_html: str = ""
    score_relevance: int = 0
    score_company: int = 0
    score_experience: int = 0
    score_proximity: int = 0
    score_salary: int = 0
    score_stability: int = 0
    score_total: float = 0.0
    salary_range: str = ""
    salary_is_estimate: bool = True
    career_url: str = ""
    linkedin_url: str = ""
    is_new: bool = True


def _normalize_work_type(wt: str) -> str:
    wt_lower = wt.lower().strip('"')
    if "full" in wt_lower:
        return "full-time"
    if "part" in wt_lower:
        return "part-time"
    if "casual" in wt_lower:
        return "casual"
    if "contract" in wt_lower or "temp" in wt_lower:
        return "contract"
    return "unknown"


def _normalize_contract_term(term: str) -> str:
    t = term.lower().strip()
    if "perm" in t:
        return "permanent"
    if "fixed" in t:
        return "fixed-term"
    if "contract" in t or "temp" in t:
        return "fixed-term"
    return ""


def _compute_proximity_score(location: str) -> int:
    loc_lower = location.lower()
    for area, score in config.LOCATION_PROXIMITY.items():
        if area in loc_lower:
            return score
    return 2


def _compute_salary_score(salary_range: str, is_estimate: bool) -> int:
    if not salary_range:
        return 2
    m = re.search(r"\$\s*([\d,]+)", salary_range)
    if not m:
        return 2
    amount = int(m.group(1).replace(",", ""))
    if "/hr" in salary_range.lower() or "/hour" in salary_range.lower():
        amount = amount * 2080
    if is_estimate:
        return 3 if amount >= 65000 else 2
    if amount >= 80000:
        return 5
    if amount >= 65000:
        return 4
    if amount >= 50000:
        return 3
    return 2


def _compute_stability_score(contract_term: str) -> int:
    if contract_term == "permanent":
        return 5
    if contract_term == "fixed-term":
        return 3
    return 2


def _compute_total_score(proximity: int, relevance: int, experience: int, company: int, salary: int, stability: int) -> float:
    w = config.SCORE_WEIGHTS
    raw = (proximity * w["proximity"] + relevance * w["relevance"]
           + experience * w["experience"] + company * w["company"]
           + salary * w["salary"] + stability * w["stability"])
    return round(raw, 1)


def _default_enrichment(job: dict) -> EnrichedJob:
    jt = _normalize_work_type(job.get("work_type", ""))
    prox = _compute_proximity_score(job.get("location", ""))
    sal_score = _compute_salary_score(job.get("salary", ""), True)
    stab_score = _compute_stability_score("")
    return EnrichedJob(
        title=job["title"],
        url=job["url"],
        company=job["company"],
        source=job.get("source", "seek"),
        location=job.get("location", ""),
        summary="See job listing for details.",
        company_intro="",
        job_type=jt,
        contract_term="",
        date_found=job.get("date_found", date.today().isoformat()),
        listing_date=job.get("listing_date", ""),
        work_type=job.get("work_type", ""),
        description_html=job.get("description_html", ""),
        score_relevance=3,
        score_company=3,
        score_experience=3,
        score_proximity=prox,
        score_salary=sal_score,
        score_stability=stab_score,
        score_total=_compute_total_score(prox, 3, 3, 3, sal_score, stab_score),
        salary_range=job.get("salary", ""),
        career_url=job.get("career_url", ""),
        linkedin_url=job.get("linkedin_url", ""),
        is_new=job.get("is_new", True),
    )


ENRICH_BATCH_SIZE = 15


def _call_claude_enrich(jobs_input: list) -> list:
    """Call claude -p for a batch of jobs, return parsed enrichments or []."""
    prompt = f"""You are a job listing analyst helping someone find accounting/finance roles in Auckland NZ.

For each job below, provide:
1. summary: 2-3 sentence summary of the role
2. company_intro: 1-2 sentence company introduction
3. job_type: One of "full-time", "part-time", "casual", "contract", or "unknown" (this is the HOURS dimension)
4. contract_term: One of "permanent", "fixed-term", or "" (this is the EMPLOYMENT TYPE dimension - permanent ongoing role vs fixed-term/contract with end date. Determine from context/description.)
5. score_relevance: 1-5, how well this role matches core accounting/finance work (5 = pure accounting like Management Accountant, Financial Controller; 3 = related like Payroll, Billing; 1 = barely related)
6. score_company: 1-5, company quality and career prospects (5 = large well-known company with clear growth paths; 3 = solid mid-size; 1 = very small or unclear)
7. score_experience: 1-5, how suitable for a mid-level professional (5 = ideal mid-level 2-5 years; 3 = junior or slightly senior; 1 = entry-level data entry or CFO-level)
8. salary_range: If salary is mentioned in the description, extract it. If not, estimate a realistic NZD salary range based on the role, company, and Auckland market rates (e.g. "$65,000 - $80,000" or "$35 - $45/hr"). Always provide a range.
9. suburb: ONLY extract a suburb if the job description explicitly mentions a specific Auckland suburb or area name (e.g. Ellerslie, Greenlane, Penrose, Mt Wellington, Newmarket, Epsom, Remuera, One Tree Hill, Onehunga, CBD, Parnell). Do NOT guess based on company name — many large companies (Big 4, banks, consultancies) have CBD offices, not suburban ones. Return "" if no suburb is explicitly stated in the description.

Jobs:
{json.dumps(jobs_input, indent=2)}

Respond with ONLY a JSON array, no markdown fences:
[{{"index": 0, "summary": "...", "company_intro": "...", "job_type": "...", "contract_term": "permanent", "score_relevance": 4, "score_company": 3, "score_experience": 4, "salary_range": "$65,000 - $80,000", "suburb": "Penrose"}}]"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "sonnet"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        print("    Warning: claude CLI not found")
        return []
    except subprocess.TimeoutExpired:
        print("    Warning: batch timed out")
        return []

    if result.returncode != 0:
        print(f"    Warning: claude -p failed (exit {result.returncode})")
        return []

    output = result.stdout.strip()
    output = re.sub(r"^```json\s*", "", output)
    output = re.sub(r"\s*```$", "", output)

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        json_match = re.search(r"\[[\s\S]*\]", output)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        print("    Warning: could not parse JSON")
        return []


def enrich_jobs(jobs: list) -> list:
    """Batch-enrich jobs via claude -p in chunks of ENRICH_BATCH_SIZE."""
    if not jobs:
        return []

    jobs_input = [
        {"index": i, "title": j["title"], "company": j["company"], "url": j["url"],
         "work_type": j.get("work_type", ""),
         "salary_from_listing": j.get("salary", ""),
         "description_snippet": (j.get("description_html", "") or "")[:500]}
        for i, j in enumerate(jobs)
    ]

    total_batches = (len(jobs_input) + ENRICH_BATCH_SIZE - 1) // ENRICH_BATCH_SIZE
    print(f"  Enriching {len(jobs)} jobs in {total_batches} batches...")

    enrichment_map = {}
    for batch_num in range(total_batches):
        start = batch_num * ENRICH_BATCH_SIZE
        end = min(start + ENRICH_BATCH_SIZE, len(jobs_input))
        batch = jobs_input[start:end]
        print(f"    Batch {batch_num + 1}/{total_batches} ({len(batch)} jobs)...")
        results = _call_claude_enrich(batch)
        for e in results:
            if isinstance(e, dict) and "index" in e:
                enrichment_map[e["index"]] = e

    enriched = []
    for i, job in enumerate(jobs):
        e = enrichment_map.get(i, {})
        seek_work_type = _normalize_work_type(job.get("work_type", ""))
        claude_job_type = e.get("job_type", "unknown")
        job_type = seek_work_type if seek_work_type != "unknown" else claude_job_type

        contract_term = _normalize_contract_term(e.get("contract_term", ""))

        real_salary = job.get("salary", "")
        salary_is_estimate = not bool(real_salary)
        salary_range = real_salary if real_salary else e.get("salary_range", "")

        s_rel = max(1, min(5, e.get("score_relevance", 3)))
        s_com = max(1, min(5, e.get("score_company", 3)))
        s_exp = max(1, min(5, e.get("score_experience", 3)))
        location = job.get("location", "")
        suburb = e.get("suburb", "")
        if suburb and not any(area in location.lower() for area in config.LOCATION_ALLOW):
            location = suburb

        s_prox = _compute_proximity_score(location)
        s_sal = _compute_salary_score(salary_range, salary_is_estimate)
        s_stab = _compute_stability_score(contract_term)

        enriched.append(EnrichedJob(
            title=job["title"],
            url=job["url"],
            company=job["company"],
            source=job.get("source", "seek"),
            location=location,
            summary=e.get("summary", "See job listing for details."),
            company_intro=e.get("company_intro", ""),
            job_type=job_type,
            contract_term=contract_term,
            date_found=job.get("date_found", date.today().isoformat()),
            listing_date=job.get("listing_date", ""),
            work_type=job.get("work_type", ""),
            description_html=job.get("description_html", ""),
            score_relevance=s_rel,
            score_company=s_com,
            score_experience=s_exp,
            score_proximity=s_prox,
            score_salary=s_sal,
            score_stability=s_stab,
            score_total=_compute_total_score(s_prox, s_rel, s_exp, s_com, s_sal, s_stab),
            salary_range=salary_range,
            salary_is_estimate=salary_is_estimate,
            career_url=job.get("career_url", ""),
            linkedin_url=job.get("linkedin_url", ""),
            is_new=job.get("is_new", True),
        ))

    print(f"  Enriched {len(enriched)} jobs successfully")
    return enriched
