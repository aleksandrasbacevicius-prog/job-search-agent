# Job Search Agent

Multi-agent pipeline: Scanner → Relevance Eval → Application Writer → Quality Eval → Interview Prep → Feedback Loop

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # then add your ANTHROPIC_API_KEY
streamlit run ui/app.py
```

## Architecture

```
config/sources.json   ← job source config (editable via UI or directly)
agents/scanner.py     ← Scanner Agent (LangGraph node)
pipeline/graph.py     ← LangGraph pipeline assembly
ui/app.py             ← Streamlit frontend
utils/scraper.py      ← fetch (httpx) + extract (Claude Haiku)
utils/db.py           ← SQLite helpers
data/jobs.db          ← auto-created on first run
```

## Scanner design

- Sources with `requires_browser: true` use Playwright (headless Chromium) — needed for Oracle portals and JS-heavy career pages
- Sources with `requires_browser: false` use httpx — faster, lower overhead
- Job extraction is AI-assisted: raw HTML → Claude Haiku → structured JSON. No per-site CSS selectors to maintain.
- Deduplication is hash-based on `source_id + title + url`

## Adding a new source

Either use the sidebar in the UI, or edit `config/sources.json` directly:

```json
{
  "id": "unique-slug",
  "name": "Company Name",
  "url": "https://company.com/careers",
  "requires_browser": false,
  "active": true,
  "scan_frequency": "daily",
  "last_scanned": null,
  "notes": ""
}
```

## Next agents to build

1. **Relevance Evaluator** — scores each job against user profile, outputs fit score + gap analysis
2. **Application Writer** — generates bespoke CV + cover letter per role
3. **Quality Evaluator** — LLM-as-judge loop critiquing Application Writer output
4. **Interview Prep** — role-specific question bank + suggested answers
5. **Feedback Loop** — tracks outcomes, improves Relevance Evaluator scoring over time
