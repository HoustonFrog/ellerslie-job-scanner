import html
from datetime import date, datetime
from pathlib import Path

import config


ELLERSLIE_AREAS = {"ellerslie", "greenlane", "remuera"}


def _is_ellerslie_area(job) -> bool:
    loc = (getattr(job, "location", "") or "").lower()
    return any(area in loc for area in ELLERSLIE_AREAS)


def generate_report(jobs: list, output_dir: str = "output") -> str:
    """Generate a premium responsive HTML report. Returns file path."""
    out_path = Path(__file__).parent / output_dir
    out_path.mkdir(parents=True, exist_ok=True)
    filename = f"ellerslie-jobs-{date.today().isoformat()}.html"
    filepath = out_path / filename

    source_counts = {}
    new_count = 0
    for j in jobs:
        src = j.source if hasattr(j, "source") else "unknown"
        source_counts[src] = source_counts.get(src, 0) + 1
        if getattr(j, "is_new", True):
            new_count += 1

    sorted_jobs = sorted(jobs, key=lambda j: getattr(j, "score_total", 0), reverse=True)
    ellerslie_jobs = [j for j in sorted_jobs if _is_ellerslie_area(j)]
    other_jobs = [j for j in sorted_jobs if not _is_ellerslie_area(j)]

    ellerslie_cards = "\n".join(_render_card(j) for j in ellerslie_jobs)
    other_cards = "\n".join(_render_card(j) for j in other_jobs)
    if not ellerslie_cards:
        ellerslie_cards = '<div class="empty-state">No jobs in Ellerslie area this period.</div>'
    if not other_cards:
        other_cards = '<div class="empty-state">No jobs in nearby areas this period.</div>'

    page_html = _TEMPLATE.format(
        date=date.today().strftime("%d %B %Y"),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        total=len(jobs),
        new_count=new_count,
        ellerslie_count=len(ellerslie_jobs),
        other_count=len(other_jobs),
        source_count=len(source_counts),
        ellerslie_cards=ellerslie_cards,
        other_cards=other_cards,
    )

    filepath.write_text(page_html, encoding="utf-8")
    return str(filepath)


def _render_mini_bar(score: int) -> str:
    pct = score * 20
    return f'<span class="mini-bar"><span class="mini-bar-fill" style="width:{pct}%"></span></span>'


def _score_color_class(total: float) -> str:
    if total >= 4.0:
        return "score-high"
    if total >= 3.0:
        return "score-mid"
    return "score-low"


def _render_card(job) -> str:
    jt = job.job_type if hasattr(job, "job_type") else "unknown"
    jt_label = config.JOB_TYPE_STYLES.get(jt, config.JOB_TYPE_STYLES["unknown"])["label"]
    ct = getattr(job, "contract_term", "") or ""
    is_new = getattr(job, "is_new", True)
    source = job.source if hasattr(job, "source") else "unknown"
    career_url = getattr(job, "career_url", "") or ""

    title_escaped = html.escape(job.title)
    company_escaped = html.escape(job.company)
    summary_escaped = html.escape(job.summary if hasattr(job, "summary") else "")
    company_intro_escaped = html.escape(job.company_intro if hasattr(job, "company_intro") else "")
    location_escaped = html.escape(job.location if hasattr(job, "location") else "")
    raw_salary = getattr(job, "salary_range", "") or ""
    salary_is_estimate = getattr(job, "salary_is_estimate", True)
    salary_range = html.escape(raw_salary)
    url_escaped = html.escape(job.url)
    listing_date = job.listing_date if hasattr(job, "listing_date") and job.listing_date else ""
    date_found = job.date_found if hasattr(job, "date_found") else date.today().isoformat()
    description_html = job.description_html if hasattr(job, "description_html") and job.description_html else ""

    # Badge: combined work type
    ct_label = " / Permanent" if ct == "permanent" else " / Fixed Term" if ct == "fixed-term" else ""
    work_badge_class = f"badge-{jt}" if jt != "unknown" else "badge-unknown"
    work_badge = f'<span class="badge {work_badge_class}">{jt_label}{ct_label}</span>'

    # Badge: source
    src = source.lower()
    if "seek" in src and "linkedin" in src and "career" in src:
        source_badge = '<span class="badge badge-source-all">Seek + LinkedIn + Career</span>'
    elif "seek" in src and "linkedin" in src:
        source_badge = '<span class="badge badge-source-seek-li">Seek + LinkedIn</span>'
    elif "seek" in src and "career" in src:
        source_badge = '<span class="badge badge-source-both">Seek + Career</span>'
    elif "linkedin" in src and "career" in src:
        source_badge = '<span class="badge badge-source-li-career">LinkedIn + Career</span>'
    elif "linkedin" in src:
        source_badge = '<span class="badge badge-source-linkedin">LinkedIn</span>'
    elif src == "seek":
        source_badge = '<span class="badge badge-source-seek">Seek</span>'
    else:
        source_badge = '<span class="badge badge-source-career">Career</span>'

    # Badge: NEW
    new_badge = '<span class="badge badge-new">NEW</span>' if is_new else ""

    # Meta line: company / location / salary combined
    meta_parts = []
    if company_escaped:
        meta_parts.append(company_escaped)
    if location_escaped:
        meta_parts.append(location_escaped)
    salary_html = ""
    if salary_range:
        est = ' <span class="salary-est">(est.)</span>' if salary_is_estimate else ""
        salary_html = f'<span class="job-salary">{salary_range}{est}</span>'
        meta_parts.append(salary_html)
    meta_line = ' <span class="meta-sep">/</span> '.join(meta_parts) if meta_parts else ""

    # Score bar
    s_prox = getattr(job, "score_proximity", 0)
    s_rel = getattr(job, "score_relevance", 0)
    s_exp = getattr(job, "score_experience", 0)
    s_com = getattr(job, "score_company", 0)
    s_sal = getattr(job, "score_salary", 0)
    s_stab = getattr(job, "score_stability", 0)
    s_total = getattr(job, "score_total", 0.0)
    color_class = _score_color_class(s_total)

    score_html = f"""<div class="score-bar">
        <div class="score-total {color_class}">{s_total}<span class="score-max">/5</span></div>
        <div class="score-dims">
          <div class="score-dim"><span class="dim-label">Proximity</span>{_render_mini_bar(s_prox)}</div>
          <div class="score-dim"><span class="dim-label">Relevance</span>{_render_mini_bar(s_rel)}</div>
          <div class="score-dim"><span class="dim-label">Experience</span>{_render_mini_bar(s_exp)}</div>
          <div class="score-dim"><span class="dim-label">Company</span>{_render_mini_bar(s_com)}</div>
          <div class="score-dim"><span class="dim-label">Salary</span>{_render_mini_bar(s_sal)}</div>
          <div class="score-dim"><span class="dim-label">Stability</span>{_render_mini_bar(s_stab)}</div>
        </div>
      </div>"""

    # Details content
    detail_rows = []
    if company_intro_escaped:
        detail_rows.append(f'<p class="company-intro">{company_intro_escaped}</p>')
    if description_html:
        detail_rows.append(f'<div class="job-description">{description_html}</div>')
    source_label = "Seek + Career Page" if source == "both" else ("Seek" if source == "seek" else "Career Page")
    detail_rows.append(f"<p><strong>Source:</strong> {source_label}</p>")
    detail_rows.append(f'<p><strong>Link:</strong> <a href="{url_escaped}" target="_blank" rel="noopener">{url_escaped}</a></p>')
    if career_url:
        career_url_escaped = html.escape(career_url)
        detail_rows.append(f'<p><strong>Career Page:</strong> <a href="{career_url_escaped}" target="_blank" rel="noopener">{career_url_escaped}</a></p>')
    detail_content = "\n          ".join(detail_rows)

    # Summary
    summary_html = ""
    if summary_escaped and summary_escaped != "See job listing for details.":
        summary_html = f'<p class="job-summary">{summary_escaped}</p>'

    return f"""    <div class="job-card" data-score="{s_total}" data-date="{listing_date or date_found}" data-salary="{html.escape(raw_salary)}" style="border-left: 4px solid var(--{color_class})">
      <div class="job-meta">
        {work_badge}
        {source_badge}
        {new_badge}
        <span class="date-tag">Posted: {listing_date or date_found}</span>
      </div>
      <h2 class="job-title"><a href="{url_escaped}" target="_blank" rel="noopener">{title_escaped}</a></h2>
      <p class="job-meta-line">{meta_line}</p>
      {score_html}
      {summary_html}
      <details>
        <summary>View details</summary>
        <div class="detail-content">
          {detail_content}
        </div>
      </details>
      <div class="card-actions">
        <a href="{url_escaped}" class="apply-btn" target="_blank" rel="noopener">{'Seek' if career_url else 'Apply'}</a>
        {'<a href="' + html.escape(career_url) + '" class="apply-btn apply-btn-alt" target="_blank" rel="noopener">Career Page</a>' if career_url else ''}
      </div>
    </div>"""


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ellerslie Area Jobs - {date}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #fafafa;
      --bg-elevated: #ffffff;
      --text: #18181b;
      --text-secondary: #52525b;
      --text-tertiary: #a1a1aa;
      --border: #e4e4e7;
      --accent: #4f46e5;
      --accent-hover: #4338ca;
      --accent-subtle: #eef2ff;
      --score-high: #059669;
      --score-mid: #4f46e5;
      --score-low: #a1a1aa;
      --radius: 12px;
      --radius-sm: 8px;
      --shadow: 0 1px 2px rgba(0,0,0,0.03), 0 4px 16px rgba(0,0,0,0.04);
      --shadow-hover: 0 8px 24px rgba(0,0,0,0.08);
    }}

    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #09090b;
        --bg-elevated: #18181b;
        --text: #fafafa;
        --text-secondary: #a1a1aa;
        --text-tertiary: #71717a;
        --border: #27272a;
        --accent: #818cf8;
        --accent-hover: #a5b4fc;
        --accent-subtle: #1e1b4b;
        --score-high: #34d399;
        --score-mid: #818cf8;
        --score-low: #71717a;
        --shadow: 0 1px 2px rgba(0,0,0,0.2), 0 4px 16px rgba(0,0,0,0.15);
        --shadow-hover: 0 8px 24px rgba(0,0,0,0.3);
      }}
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      max-width: 900px;
      margin: 0 auto;
      padding: 0 20px 48px;
      -webkit-font-smoothing: antialiased;
    }}

    .accent-bar {{
      height: 4px;
      background: var(--accent);
      margin: 0 -20px 32px;
    }}

    .header {{
      padding: 0 0 24px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }}

    .header h1 {{
      font-size: 1.625rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1.2;
    }}

    .header .subtitle {{
      color: var(--text-secondary);
      font-size: 0.875rem;
      margin-top: 4px;
    }}

    .stats {{
      display: flex;
      gap: 32px;
      margin-top: 20px;
    }}

    .stat {{
      text-align: left;
    }}

    .stat-num {{
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--accent);
      line-height: 1;
    }}

    .stat-label {{
      font-size: 0.75rem;
      color: var(--text-tertiary);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-top: 4px;
    }}

    /* Tabs */
    .tabs {{
      display: flex;
      gap: 0;
      margin-bottom: 16px;
      border-bottom: 2px solid var(--border);
    }}

    .tab {{
      padding: 10px 20px;
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-tertiary);
      cursor: pointer;
      border-bottom: 2px solid transparent;
      margin-bottom: -2px;
      transition: color 0.15s ease, border-color 0.15s ease;
      user-select: none;
    }}

    .tab:hover {{ color: var(--text-secondary); }}
    .tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}

    .tab-count {{
      display: inline-block;
      background: var(--border);
      color: var(--text-secondary);
      font-size: 0.65rem;
      font-weight: 700;
      padding: 1px 7px;
      border-radius: 99px;
      margin-left: 6px;
      vertical-align: middle;
    }}

    .tab.active .tab-count {{
      background: var(--accent);
      color: #fff;
    }}

    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}

    /* Sort bar */
    .sort-bar {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
    }}

    .sort-label {{
      font-size: 0.75rem;
      color: var(--text-tertiary);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .sort-btn {{
      font-family: 'Inter', system-ui, sans-serif;
      font-size: 0.75rem;
      font-weight: 500;
      padding: 4px 12px;
      border-radius: 99px;
      border: 1px solid var(--border);
      background: var(--bg-elevated);
      color: var(--text-secondary);
      cursor: pointer;
      transition: all 0.15s ease;
    }}

    .sort-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    .sort-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}

    /* Cards */
    .job-card {{
      background: var(--bg-elevated);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px 24px 20px 28px;
      margin-bottom: 16px;
      box-shadow: var(--shadow);
      transition: box-shadow 0.2s ease, transform 0.2s ease;
    }}

    .job-card:hover {{
      transform: translateY(-2px);
      box-shadow: var(--shadow-hover);
    }}

    .job-meta {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 8px;
    }}

    /* Badges */
    .badge {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 99px;
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.01em;
      line-height: 1.6;
    }}

    .badge-full-time {{ background: #eef2ff; color: #3730a3; }}
    .badge-part-time {{ background: #f5f3ff; color: #5b21b6; }}
    .badge-casual {{ background: #fefce8; color: #854d0e; }}
    .badge-contract {{ background: #fdf2f8; color: #9d174d; }}
    .badge-unknown {{ background: #f4f4f5; color: #52525b; }}

    .badge-source-seek {{ background: #fef2f2; color: #991b1b; }}
    .badge-source-career {{ background: #ecfdf5; color: #065f46; }}
    .badge-source-both {{ background: #eff6ff; color: #1e40af; }}
    .badge-source-linkedin {{ background: #eff6ff; color: #1d4ed8; }}
    .badge-source-seek-li {{ background: #eff6ff; color: #1e40af; }}
    .badge-source-li-career {{ background: #ecfdf5; color: #065f46; }}
    .badge-source-all {{ background: #eef2ff; color: #3730a3; }}

    .badge-new {{
      background: #dc2626;
      color: #fff;
      animation: pulse-new 2s ease-in-out 3;
    }}

    @keyframes pulse-new {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.6; }}
    }}

    @media (prefers-color-scheme: dark) {{
      .badge-full-time {{ background: #1e1b4b; color: #a5b4fc; }}
      .badge-part-time {{ background: #2e1065; color: #c4b5fd; }}
      .badge-casual {{ background: #422006; color: #fde68a; }}
      .badge-contract {{ background: #500724; color: #fbcfe8; }}
      .badge-unknown {{ background: #27272a; color: #a1a1aa; }}

      .badge-source-seek {{ background: #450a0a; color: #fca5a5; }}
      .badge-source-career {{ background: #022c22; color: #6ee7b7; }}
      .badge-source-both {{ background: #172554; color: #93c5fd; }}
      .badge-source-linkedin {{ background: #172554; color: #93c5fd; }}
      .badge-source-seek-li {{ background: #172554; color: #93c5fd; }}
      .badge-source-li-career {{ background: #022c22; color: #6ee7b7; }}
      .badge-source-all {{ background: #1e1b4b; color: #a5b4fc; }}

      .badge-new {{ background: #ef4444; }}
    }}

    .date-tag {{
      color: var(--text-tertiary);
      font-size: 0.75rem;
      margin-left: auto;
    }}

    /* Title */
    .job-title {{
      font-size: 1.05rem;
      font-weight: 600;
      line-height: 1.3;
      margin-bottom: 4px;
      letter-spacing: -0.01em;
    }}

    .job-title a {{ color: var(--text); text-decoration: none; }}
    .job-title a:hover {{ color: var(--accent); }}

    /* Meta line: Company / Location / Salary */
    .job-meta-line {{
      font-size: 0.875rem;
      color: var(--text-secondary);
      margin-bottom: 10px;
      line-height: 1.5;
    }}

    .meta-sep {{
      color: var(--text-tertiary);
      margin: 0 2px;
    }}

    .job-salary {{
      color: var(--accent);
      font-weight: 600;
    }}

    .salary-est {{
      color: var(--text-tertiary);
      font-weight: 400;
      font-size: 0.75rem;
    }}

    /* Score bar */
    .score-bar {{
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 8px 12px;
      background: var(--bg);
      border-radius: var(--radius-sm);
      margin-bottom: 10px;
    }}

    .score-total {{
      font-size: 1.375rem;
      font-weight: 700;
      min-width: 52px;
      text-align: center;
      line-height: 1;
    }}

    .score-total.score-high {{ color: var(--score-high); }}
    .score-total.score-mid {{ color: var(--score-mid); }}
    .score-total.score-low {{ color: var(--score-low); }}

    .score-max {{
      font-size: 0.75rem;
      font-weight: 400;
      color: var(--text-tertiary);
    }}

    .score-dims {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px 14px;
      flex: 1;
    }}

    .score-dim {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.75rem;
    }}

    .dim-label {{
      color: var(--text-tertiary);
      min-width: 62px;
    }}

    .mini-bar {{
      display: inline-block;
      width: 40px;
      height: 4px;
      background: var(--border);
      border-radius: 2px;
      overflow: hidden;
      vertical-align: middle;
    }}

    .mini-bar-fill {{
      display: block;
      height: 100%;
      background: var(--accent);
      border-radius: 2px;
      transition: width 0.3s ease;
    }}

    /* Summary */
    .job-summary {{
      font-size: 0.875rem;
      color: var(--text-secondary);
      margin-bottom: 10px;
      line-height: 1.55;
    }}

    /* Details */
    details {{ margin-top: 6px; }}

    summary {{
      cursor: pointer;
      font-size: 0.875rem;
      color: var(--accent);
      font-weight: 500;
      user-select: none;
    }}

    summary:hover {{ color: var(--accent-hover); }}
    details[open] summary {{ margin-bottom: 8px; }}

    .detail-content {{
      font-size: 0.875rem;
      color: var(--text-secondary);
      padding: 12px 14px;
      background: var(--bg);
      border-radius: var(--radius-sm);
      line-height: 1.6;
    }}

    .detail-content p {{ margin-bottom: 4px; }}
    .detail-content a {{ color: var(--accent); word-break: break-all; }}

    .company-intro {{
      font-size: 0.875rem;
      color: var(--text-tertiary);
      font-style: italic;
      margin-bottom: 8px;
      line-height: 1.5;
    }}

    .job-description {{
      margin-bottom: 12px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
      font-size: 0.875rem;
      line-height: 1.65;
      color: var(--text-secondary);
    }}

    .job-description ul, .job-description ol {{ padding-left: 1.2em; margin: 6px 0; }}
    .job-description li {{ margin-bottom: 3px; }}
    .job-description p {{ margin-bottom: 6px; }}
    .job-description strong {{ color: var(--text); }}

    /* Actions */
    .card-actions {{ margin-top: 14px; }}

    .apply-btn {{
      display: inline-block;
      padding: 8px 22px;
      background: var(--accent);
      color: #fff;
      text-decoration: none;
      border-radius: var(--radius-sm);
      font-size: 0.875rem;
      font-weight: 500;
      transition: background 0.15s ease, transform 0.1s ease;
    }}

    .apply-btn:hover {{ background: var(--accent-hover); }}
    .apply-btn:active {{ transform: scale(0.98); }}

    .apply-btn-alt {{
      background: var(--bg-elevated);
      color: var(--accent);
      border: 1px solid var(--accent);
      margin-left: 8px;
    }}

    .apply-btn-alt:hover {{
      background: var(--accent);
      color: #fff;
    }}

    /* Empty state */
    .empty-state {{
      text-align: center;
      padding: 48px 20px;
      color: var(--text-tertiary);
      font-size: 0.875rem;
    }}

    /* Footer */
    .footer {{
      text-align: center;
      padding: 24px 0 0;
      color: var(--text-tertiary);
      font-size: 0.75rem;
      border-top: 1px solid var(--border);
      margin-top: 32px;
    }}

    /* Mobile */
    @media (max-width: 640px) {{
      body {{ padding: 0 14px 36px; }}
      .accent-bar {{ margin: 0 -14px 24px; }}
      .header h1 {{ font-size: 1.3rem; }}
      .stats {{ gap: 20px; }}
      .stat-num {{ font-size: 1.4rem; }}
      .job-card {{ padding: 16px 18px 16px 22px; }}
      .date-tag {{ margin-left: 0; }}
      .score-dims {{ gap: 4px 10px; }}
      .dim-label {{ min-width: 56px; }}
    }}
  </style>
</head>
<body>
  <div class="accent-bar"></div>
  <header class="header">
    <h1>Ellerslie Area Job Scan</h1>
    <p class="subtitle">Accounting & Finance roles near Ellerslie School - {date}</p>
    <div class="stats">
      <div class="stat">
        <div class="stat-num">{total}</div>
        <div class="stat-label">Total Jobs</div>
      </div>
      <div class="stat">
        <div class="stat-num">{new_count}</div>
        <div class="stat-label">New</div>
      </div>
      <div class="stat">
        <div class="stat-num">{source_count}</div>
        <div class="stat-label">Sources</div>
      </div>
    </div>
  </header>

  <main>
    <div class="tabs">
      <div class="tab active" onclick="switchTab('ellerslie')">Ellerslie<span class="tab-count">{ellerslie_count}</span></div>
      <div class="tab" onclick="switchTab('other')">Other Areas<span class="tab-count">{other_count}</span></div>
    </div>

    <div class="sort-bar">
      <span class="sort-label">Sort:</span>
      <button class="sort-btn active" onclick="sortJobs('score')">Score</button>
      <button class="sort-btn" onclick="sortJobs('date')">Date</button>
      <button class="sort-btn" onclick="sortJobs('salary')">Salary</button>
    </div>

    <div id="panel-ellerslie" class="tab-panel active">
{ellerslie_cards}
    </div>

    <div id="panel-other" class="tab-panel">
{other_cards}
    </div>
  </main>

  <footer class="footer">
    Ellerslie Job Scanner - Generated {timestamp}
  </footer>

  <script>
    function switchTab(name) {{
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      event.currentTarget.classList.add('active');
      document.getElementById('panel-' + name).classList.add('active');
    }}

    function sortJobs(by) {{
      document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
      event.currentTarget.classList.add('active');
      document.querySelectorAll('.tab-panel').forEach(panel => {{
        const cards = Array.from(panel.querySelectorAll('.job-card'));
        cards.sort((a, b) => {{
          if (by === 'score') return parseFloat(b.dataset.score) - parseFloat(a.dataset.score);
          if (by === 'date') return (b.dataset.date || '').localeCompare(a.dataset.date || '');
          if (by === 'salary') {{
            const sa = parseInt((a.dataset.salary || '').replace(/[^0-9]/g, '')) || 0;
            const sb = parseInt((b.dataset.salary || '').replace(/[^0-9]/g, '')) || 0;
            return sb - sa;
          }}
          return 0;
        }});
        cards.forEach(c => panel.appendChild(c));
      }});
    }}
  </script>
</body>
</html>"""
