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

## Commit message format

```
type: short imperative summary (≤72 chars)

- file/module: what changed and why
- only list files where the change is non-obvious from the summary
```

**Types:** `feat` · `fix` · `refactor` · `config` · `docs` · `chore`

**Rules:**
- Subject line is imperative mood ("add X", not "added X" or "adds X")
- Body bullets are `file: reason`, not just `file: changed`
- Skip bullets for trivial touches (formatting, typos) unless they're the whole point
- One blank line between subject and body
- End with `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` on AI-assisted commits

**Examples:**

```
feat: add LinkedIn search via jobspy

- agents/job_board_scanner.py: new LangGraph node; searches each target role
- pipeline/graph.py: chain url_scanner → job_board_scanner → END
- ui/app.py: Job Board Search sidebar with toggle and per-site checkboxes
```

```
fix: correct Nord Security careers URL (404)

- config/sources.json: /jobs → /careers; verified 200 response
```

```
config: add Vinted as active source
```

## Next agents to build

1. **Relevance Evaluator** — scores each job against user profile, outputs fit score + gap analysis
2. **Application Writer** — generates bespoke CV + cover letter per role
3. **Quality Evaluator** — LLM-as-judge loop critiquing Application Writer output
4. **Interview Prep** — role-specific question bank + suggested answers
5. **Feedback Loop** — tracks outcomes, improves Relevance Evaluator scoring over time
