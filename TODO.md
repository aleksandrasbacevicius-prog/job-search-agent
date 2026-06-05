# Job Search Agent — Task List

## 🐛 Bugs & UI
- [ ] Fix Remove Source button — move out of column layout to bottom of expander with confirmation step
- [ ] Target roles field: strip trailing commas/whitespace on save (guard against formatting mistakes)
- [ ] Show model/provider actively in use somewhere visible (e.g. scan results header)

## 🔍 Job Discovery
- [ ] **Add jobspy scanner** — keyword-based search across LinkedIn, Indeed, Google Jobs, Glassdoor using `python-jobspy`; no API key needed, uses `target_roles` from profile as search terms
- [ ] **LinkedIn via jobspy** — jobspy hits LinkedIn's public job search without login; replaces manual paste for LinkedIn jobs
- [ ] **Google Jobs via jobspy** — broad keyword sweep across Google's aggregated listings
- [ ] Deduplicate across sources — same job can appear on company page AND LinkedIn; hash on title+company+location
- [ ] Per-source scan frequency respected — skip sources that were scanned within their `scan_frequency` window

## 🤖 Pipeline — Next Agents
- [ ] **Relevance Evaluator** — scores each job 0–100 against profile; outputs fit score + gap analysis; only surfaces jobs above threshold
- [ ] **Application Writer** — generates tailored CV + cover letter per role using job description + profile + gap analysis
- [ ] **Quality Evaluator** — LLM-as-judge loop critiquing Application Writer output; loops back for revisions
- [ ] **Interview Prep** — role-specific question bank + suggested answers grounded in actual experience
- [ ] **Feedback Loop** — logs interview outcomes, analyses patterns, feeds back to improve Relevance Evaluator scoring

## ⚙️ Infrastructure
- [ ] Scheduled daily scan — Windows Task Scheduler or background thread; runs active sources automatically
- [ ] Notification on new relevant jobs — desktop toast or email summary after each scan
- [ ] Export jobs to CSV/Excel — one-click export of current filtered view
- [ ] Pagination in job list — currently capped at 100; add load-more or pages

## 🔒 Security & Quality
- [ ] Rate limiting on scraper — add delay between requests to avoid IP bans
- [ ] Retry logic with backoff for failed fetches
- [ ] Unit tests for `utils/security.py` validation functions
