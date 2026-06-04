# Job Search Agent

A multi-agent pipeline that automates job discovery, evaluation, and application prep — built with [LangGraph](https://github.com/langchain-ai/langgraph) and the Anthropic / OpenAI APIs.

## What it does

```
Scanner Agent → Relevance Evaluator → Application Writer → Quality Evaluator → Interview Prep → Feedback Loop
```

| Stage | Status | Description |
|---|---|---|
| Scanner Agent | ✅ Built | Scrapes configured career pages daily, deduplicates, stores to SQLite |
| Relevance Evaluator | 🔜 Next | Scores each job against your profile — fit score + gap analysis |
| Application Writer | 🔜 Planned | Generates bespoke CV + cover letter per role |
| Quality Evaluator | 🔜 Planned | LLM-as-judge loop critiquing the Application Writer's output |
| Interview Prep | 🔜 Planned | Role-specific question bank + suggested answers |
| Feedback Loop | 🔜 Planned | Tracks outcomes, self-improves the relevance scoring over time |

## Features

- **Multi-source scanning** — add any career page via the UI; sources are stored in `config/sources.json`
- **Browser-based scraping** — Playwright handles JS-rendered pages (Oracle portals, etc.); httpx handles static ones
- **AI-powered extraction** — Claude/GPT reads raw HTML and returns structured job listings; no CSS selectors to maintain
- **Profile-driven filtering** — Scanner prompt is personalised with your target roles, keywords, excluded terms, and location preferences
- **Conversational profile builder** — upload your CV (PDF/DOCX) or type notes; an agent asks follow-up questions to fill gaps
- **Provider/model selection** — swap between Anthropic and OpenAI models from the sidebar without touching code
- **Job status tracking** — mark jobs as Saved / Applied / Rejected; filter by status
- **Prompt injection defence** — all untrusted content (CV uploads, scraped HTML) is HTML-escaped before being placed in prompts; agent JSON output is validated and length-capped before storage

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/job-search-agent.git
cd job-search-agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Add your API key(s)

```bash
cp .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...   # https://console.anthropic.com
OPENAI_API_KEY=sk-proj-...     # https://platform.openai.com  (optional)
```

You only need one. The default model is `claude-sonnet-4-6`; switch to OpenAI from the sidebar.

### 3. Run

```bash
streamlit run ui/app.py
```

Opens at `http://localhost:8501`.

## First steps in the UI

1. **Profile tab → Build Profile with AI** — upload your CV or type a summary; the agent fills in your profile and asks targeted follow-up questions
2. **Sidebar → Job Sources** — verify the pre-loaded sources (Nord Security, Ignitis) and add your own; paste Oracle portal URLs for Citco / LITIT and enable them
3. **Sidebar → Model** — pick your provider and model
4. **Scan tab → Scan Now** — runs the Scanner Agent across all active sources

## Project structure

```
job-search-agent/
├── agents/
│   ├── scanner.py          # Scanner Agent (LangGraph node)
│   └── profile_builder.py  # Conversational profile onboarding agent
├── config/
│   ├── sources.json        # Job source config (edited via UI or directly)
│   ├── profile.json        # User profile (edited via UI or directly)
│   └── settings.json       # Provider + model selection
├── data/
│   └── jobs.db             # SQLite — auto-created on first scan
├── pipeline/
│   └── graph.py            # LangGraph pipeline assembly
├── ui/
│   └── app.py              # Streamlit frontend
└── utils/
    ├── db.py               # SQLite helpers
    ├── llm.py              # Unified LLM client (Anthropic + OpenAI)
    ├── scraper.py          # Page fetching + AI-assisted job extraction
    ├── security.py         # Prompt injection defences + output validation
    ├── profile.py          # Profile load/save helpers
    ├── settings.py         # Settings load/save helpers
    └── cv_parser.py        # PDF/DOCX text extraction
```

## Adding a job source

Either use the sidebar in the app, or edit `config/sources.json` directly:

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

Set `requires_browser: true` for JavaScript-heavy pages (Oracle HCM portals, Workday, Greenhouse with JS routing).

## Security

- **CV uploads and scraped HTML** are HTML-escaped (`<` → `&lt;`) before being embedded in prompts, neutralising any XML/tag-based injection attempts
- **Agent JSON output** is type-checked and length-capped by `utils/security.py` before being written to disk
- **`.env` is gitignored** — never commit real API keys; use `.env.example` as the template

## Tech stack

- [LangGraph](https://github.com/langchain-ai/langgraph) — agent orchestration
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) — Claude API
- [OpenAI Python SDK](https://github.com/openai/openai-python) — GPT API
- [Playwright](https://playwright.dev/python/) — headless browser for JS-rendered pages
- [Streamlit](https://streamlit.io) — UI
- [pypdf](https://github.com/py-pdf/pypdf) + [python-docx](https://python-docx.readthedocs.io) — CV parsing

## Roadmap

The pipeline is designed so each new agent slots in as the next LangGraph node after the Scanner:

- **Relevance Evaluator** — LLM scores each job 0–100 against your profile with a gap analysis; you only get notified about worthwhile ones
- **Application Writer** — generates a tailored CV and cover letter per role using the job description + your profile + the gap analysis
- **Quality Evaluator** — LLM-as-judge loop that critiques the Application Writer's output and requests revisions if needed
- **Interview Prep** — role-specific question bank with suggested answers grounded in your actual experience
- **Feedback Loop** — logs interview outcomes and analyses patterns to improve the Relevance Evaluator's scoring over time
