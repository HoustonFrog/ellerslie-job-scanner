from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

import enrich
import report


@pytest.mark.parametrize("salary, expected", [
    ("$80,000 – $100,000 per year (FTE)", 80000),
    ("Up to $120k plus great perks package", 120000),
    ("$65k - $70k", 65000),
    ("$35 - $45/hr", None),
    ("Competitive package", None),
    ("", None),
])
def test_annual_salary_sort_uses_comparable_values(salary, expected):
    assert report._annual_salary_value(salary) == expected


def make_job(**overrides):
    values = dict(title="Accountant", url="https://example.test/role", company="Example",
                  source="seek+linkedin", location="Ellerslie", summary="",
                  company_intro="", job_type="part-time", date_found="2026-10-15",
                  listing_date="2026-10-08", score_total=4.1,
                  recommendation_reason="住房公益项目；预算与月结经验匹配。", salary_range="")
    values.update(overrides)
    return SimpleNamespace(**values)


def test_report_preserves_recommendation_as_text():
    job = make_job(recommendation_reason='预算经验 <script>alert("x")</script>')
    soup = BeautifulSoup(report.render_report([job], report_date="2026-10-15",
                                             generated_at="2026-10-15 19:54"), "html.parser")
    reason = soup.select_one(".recommendation-text")
    assert reason.get_text() == job.recommendation_reason
    assert reason.find("script") is None
    assert soup.select_one(".job-salary").get_text(strip=True) == "Salary not disclosed"
    assert soup.select_one(".job-title a")["href"] == job.url


def test_report_counts_providers_and_preserves_historical_date():
    jobs = [make_job(), make_job(source="seek", location="Penrose", is_new=False)]
    soup = BeautifulSoup(report.render_report(jobs, report_date="2026-10-15",
                                             generated_at="2026-10-15 19:54"), "html.parser")
    assert soup.select_one("[data-source-count]")["data-source-count"] == "2"
    assert "15 October 2026" in soup.get_text()
    assert "2026-10-15 19:54" in soup.get_text()
    assert len(soup.select(".job-card")) == 2
    assert len(soup.select('[data-area="nearby"]')) == 1


def test_enrichment_retains_profile_recommendation(monkeypatch):
    monkeypatch.setattr(enrich, "_call_codex_enrich", lambda batch: [
        {"index": 0, "recommendation_reason": "预算与月结经验契合；每周工时需确认。"}
    ])
    jobs = enrich.enrich_jobs([dict(title="Accountant", company="Example",
                                   url="https://example.test/role", location="Ellerslie")])
    assert jobs[0].recommendation_reason == "预算与月结经验契合；每周工时需确认。"


def test_enrichment_prompt_uses_actual_candidate_and_no_invented_pay(monkeypatch):
    def fake_run(command, **kwargs):
        prompt = command[2]
        assert "CPA Australia" in prompt
        assert "part-time" in prompt
        assert "recommendation_reason" in prompt
        assert "Do not estimate salary" in prompt
        from pathlib import Path
        Path(command[command.index("-o") + 1]).write_text("[]")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(enrich.subprocess, "run", fake_run)
    assert enrich._call_codex_enrich([]) == []


def test_advertised_salary_does_not_become_an_estimate_in_fallback():
    job = enrich._default_enrichment(dict(title="Accountant", company="Example",
                                         url="https://example.test/role", salary="$80,000"))
    assert job.salary_is_estimate is False


def test_salary_score_recognises_k_notation():
    assert enrich._compute_salary_score("Up to $120k", False) == enrich._compute_salary_score("$120,000", False)


def test_bilingual_report_embeds_both_titles_and_reasons():
    job = make_job(title_zh="项目会计", recommendation_reason_en="Programme finance duties match your budgeting experience.")
    soup = BeautifulSoup(report.render_report([job]), "html.parser")
    title = soup.select_one('.job-title [data-en][data-zh]')
    assert title is not None
    assert title['data-en'] == "Accountant"
    assert title['data-zh'] == "项目会计"
    reason = soup.select_one('.recommendation-text')
    assert reason['data-en'] == job.recommendation_reason_en
    assert reason['data-zh'] == job.recommendation_reason
    assert {button['data-language'] for button in soup.select('[data-language]')} == {'zh', 'en'}
    assert not soup.find('script', src=True)


def test_enrichment_retains_both_languages(monkeypatch):
    monkeypatch.setattr(enrich, "_call_codex_enrich", lambda batch: [
        {"index":0, "title_zh":"会计", "recommendation_reason":"项目财务经验契合。", "recommendation_reason_en":"Your programme finance experience is relevant."}
    ])
    job = enrich.enrich_jobs([dict(title="Accountant", company="Example", url="https://example.test/role")])[0]
    assert job.title_zh == "会计"
    assert job.recommendation_reason_en == "Your programme finance experience is relevant."


def test_enrichment_fills_only_missing_company_from_explicit_ad_identity(monkeypatch):
    monkeypatch.setattr(enrich, "_call_codex_enrich", lambda batch: [
        {"index": 0, "employer_name": "Habitat for Humanity New Zealand"},
        {"index": 1, "employer_name": "Different name"},
    ])
    jobs = enrich.enrich_jobs([
        dict(title="Accountant", company="", url="https://example.test/1"),
        dict(title="Accountant", company="Source advertiser", url="https://example.test/2"),
    ])
    assert jobs[0].company == "Habitat for Humanity New Zealand"
    assert jobs[1].company == "Source advertiser"


def test_enrichment_uses_project_model_instead_of_desktop_default(monkeypatch):
    def fake_run(command, **kwargs):
        assert '-m' in command
        assert command[command.index('-m')+1] == 'gpt-6-sol'
        from pathlib import Path
        Path(command[command.index('-o')+1]).write_text('[]')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(enrich.subprocess,'run',fake_run)
    assert enrich._call_codex_enrich([]) == []
