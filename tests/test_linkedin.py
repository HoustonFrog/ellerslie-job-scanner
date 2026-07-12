import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linkedin import LinkedInJob, parse_job_cards, parse_job_details

SAMPLE_CARD_HTML = """
<li>
<div class="base-card relative w-full hover:no-underline focus:no-underline
    base-card--link base-search-card base-search-card--link job-search-card"
    data-entity-urn="urn:li:jobPosting:4424830638">
  <a class="base-card__full-link" href="https://nz.linkedin.com/jobs/view/management-accountant-at-hynds-4424830638?position=1&amp;pageNum=0&amp;refId=abc123">
    <span class="sr-only">Management Accountant</span>
  </a>
  <div class="base-search-card__info">
    <h3 class="base-search-card__title">
      Management Accountant
    </h3>
    <h4 class="base-search-card__subtitle">
      <a class="hidden-nested-link" href="https://nz.linkedin.com/company/hynds">
        Hynds Pipe Systems Limited
      </a>
    </h4>
    <div class="base-search-card__metadata">
      <span class="job-search-card__location">
        Auckland, Auckland, New Zealand
      </span>
      <time class="job-search-card__listdate" datetime="2026-06-12">
        1 week ago
      </time>
    </div>
  </div>
</div>
</li>
"""

SAMPLE_DETAIL_HTML = """
<script type="application/ld+json">
{"title":"Management Accountant","employmentType":"FULL_TIME",
 "datePosted":"2026-06-12T01:00:00.000Z",
 "hiringOrganization":{"name":"Hynds Pipe Systems"},
 "jobLocation":{"address":{"addressLocality":"Auckland","addressCountry":"NZ"}}}
</script>
<div class="show-more-less-html__markup">
  <p>We are looking for a Management Accountant based in our <strong>Penrose</strong> office.</p>
  <ul><li>Prepare monthly reports</li></ul>
</div>
<span class="description__job-criteria-text">Mid-Senior level</span>
<span class="description__job-criteria-text">Full-time</span>
<span class="description__job-criteria-text">Accounting/Auditing</span>
<span class="description__job-criteria-text">Manufacturing</span>
"""


def test_parse_job_cards_extracts_fields():
    jobs = parse_job_cards(SAMPLE_CARD_HTML)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.id == "4424830638"
    assert j.title == "Management Accountant"
    assert j.company == "Hynds Pipe Systems Limited"
    assert "Auckland" in j.location
    assert j.listing_date == "2026-06-12"
    assert j.url == "https://nz.linkedin.com/jobs/view/management-accountant-at-hynds-4424830638"


def test_parse_job_cards_empty_html():
    jobs = parse_job_cards("<html><body>No jobs</body></html>")
    assert jobs == []


def test_parse_job_cards_deduplicates():
    double_html = SAMPLE_CARD_HTML + SAMPLE_CARD_HTML
    jobs = parse_job_cards(double_html)
    assert len(jobs) == 1


def test_parse_job_details():
    details = parse_job_details(SAMPLE_DETAIL_HTML)
    assert "Management Accountant" in details["description_html"] or "Penrose" in details["description_html"]
    assert details["employment_type"] == "FULL_TIME"
    assert len(details["job_criteria"]) == 4
    assert details["job_criteria"][0] == "Mid-Senior level"


def test_parse_job_details_empty():
    details = parse_job_details("<html></html>")
    assert details["description_html"] == ""
    assert details["employment_type"] == ""
    assert details["job_criteria"] == []


from scanner import _merge_duplicates, _normalize_title


def test_normalize_title_strips_prefix():
    assert _normalize_title("2898 - Accountant") == "accountant"
    assert _normalize_title("Senior Accountant") == "senior accountant"


def test_merge_seek_and_linkedin():
    jobs = [
        {"title": "Accountant", "company": "Acme", "url": "https://seek/1", "source": "seek", "location": "Ellerslie"},
        {"title": "Accountant", "company": "Acme", "url": "https://linkedin/1", "source": "linkedin", "location": "Auckland"},
    ]
    merged = _merge_duplicates(jobs)
    assert len(merged) == 1
    assert merged[0]["source"] == "seek+linkedin"
    assert merged[0]["url"] == "https://seek/1"
    assert merged[0]["linkedin_url"] == "https://linkedin/1"


def test_merge_all_three_sources():
    jobs = [
        {"title": "Accountant", "company": "Acme", "url": "https://seek/1", "source": "seek", "location": "Ellerslie"},
        {"title": "Accountant", "company": "Acme", "url": "https://linkedin/1", "source": "linkedin", "location": "Auckland"},
        {"title": "Accountant", "company": "Acme", "url": "https://career/1", "source": "career_page", "location": "Ellerslie"},
    ]
    merged = _merge_duplicates(jobs)
    assert len(merged) == 1
    assert merged[0]["source"] == "seek+linkedin+career"
    assert merged[0]["career_url"] == "https://career/1"
    assert merged[0]["linkedin_url"] == "https://linkedin/1"


def test_merge_linkedin_only_stays_linkedin():
    jobs = [
        {"title": "Accountant", "company": "Acme", "url": "https://linkedin/1", "source": "linkedin", "location": "Auckland"},
    ]
    merged = _merge_duplicates(jobs)
    assert len(merged) == 1
    assert merged[0]["source"] == "linkedin"


def test_merge_different_companies_not_merged():
    jobs = [
        {"title": "Accountant", "company": "Acme", "url": "https://seek/1", "source": "seek", "location": "Ellerslie"},
        {"title": "Accountant", "company": "Other Corp", "url": "https://linkedin/1", "source": "linkedin", "location": "Auckland"},
    ]
    merged = _merge_duplicates(jobs)
    assert len(merged) == 2


def test_merge_company_name_variants_across_sources():
    # Seek, LinkedIn, and a company's own career page each report the company
    # name differently (e.g. "Mercury" / "Mercury NZ" / "Mercury NZ (Mercury Energy)").
    # These are the same real-world employer and should still be merged.
    jobs = [
        {"title": "Treasury Manager", "company": "Mercury", "url": "https://seek/1", "source": "seek", "location": "Newmarket"},
        {"title": "Treasury Manager", "company": "Mercury NZ", "url": "https://linkedin/1", "source": "linkedin", "location": "Newmarket"},
        {"title": "Treasury Manager", "company": "Mercury NZ (Mercury Energy)", "url": "https://career/1", "source": "career_page", "location": "Newmarket"},
    ]
    merged = _merge_duplicates(jobs)
    assert len(merged) == 1
    assert merged[0]["source"] == "seek+linkedin+career"
    assert merged[0]["linkedin_url"] == "https://linkedin/1"
    assert merged[0]["career_url"] == "https://career/1"
