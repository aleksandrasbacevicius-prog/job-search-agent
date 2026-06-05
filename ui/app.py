import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import streamlit as st

from agents.scanner import load_sources, save_sources
from pipeline.graph import run_scan
from utils.db import get_recent_jobs, init_db, update_job_status
from utils.llm import PROVIDER_MODELS
from utils.profile import load_profile, save_profile
from utils.settings import load_settings, save_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_last_scanned_label(source: dict) -> str:
    ts = source.get("last_scanned")
    if not ts:
        return "never scanned"
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        hours = int((datetime.now(timezone.utc) - dt).total_seconds() // 3600)
        return f"last scanned {hours}h ago" if hours < 48 else ts[:10]
    except ValueError:
        return ts[:10]


def _lines_to_list(text: str) -> list:
    """
    Parse a text area into a clean list of strings.
    Accepts both newline-separated and comma-separated input (or a mix),
    so "AI Engineer, Data Analyst" and "AI Engineer\nData Analyst" both work.
    Strips surrounding whitespace and ignores blank entries.
    """
    items = []
    for line in text.splitlines():
        for part in line.split(","):
            clean = part.strip()
            if clean:
                items.append(clean)
    return items


def _list_to_lines(items: list) -> str:
    return "\n".join(items)


def _init_chat_state():
    if "pb_status" not in st.session_state:
        st.session_state.pb_status = "idle"          # idle | active | complete
    if "pb_messages" not in st.session_state:
        st.session_state.pb_messages = []             # display messages: [{role, content}]
    if "pb_api_messages" not in st.session_state:
        st.session_state.pb_api_messages = []         # raw API message history
    if "pb_draft" not in st.session_state:
        st.session_state.pb_draft = {}                # profile draft from agent


# ---------------------------------------------------------------------------
# Sidebar: source management
# ---------------------------------------------------------------------------
# Sidebar: job board search
# ---------------------------------------------------------------------------

def sidebar_job_boards():
    st.header("Job Board Search")
    settings = load_settings()
    cfg = settings.get("job_board_search", {})
    profile = load_profile()

    enabled = st.toggle("Enable", value=cfg.get("enabled", False), key="jb_enabled")

    if not enabled:
        st.caption("Enable to search LinkedIn and other boards using your target roles.")
        if not cfg.get("enabled"):
            # Save disabled state without re-rendering everything
            return
        settings["job_board_search"] = {**cfg, "enabled": False}
        save_settings(settings)
        return

    st.divider()

    # Search term — default to blank (= use target roles from profile)
    target_roles = profile.get("target_roles", [])
    custom = st.text_input(
        "Custom search term",
        value=cfg.get("custom_search_term", ""),
        placeholder="Leave blank to use target roles from profile",
        key="jb_search_term",
    )
    if not custom and target_roles:
        st.caption(f"Will search: {', '.join(target_roles)}")
    elif not custom:
        st.caption("⚠️ No target roles set — add them in the Profile tab or enter a custom term above.")

    location = st.text_input(
        "Location",
        value=cfg.get("location", "") or profile.get("location", ""),
        placeholder="e.g. Lithuania, Vilnius",
        key="jb_location",
    )

    col_hours, col_results = st.columns(2)
    hours_options = [24, 72, 168, 336, 720]
    hours_val = int(cfg.get("hours_old", 168))
    hours_old = col_hours.selectbox(
        "Posted within",
        hours_options,
        index=hours_options.index(hours_val) if hours_val in hours_options else 2,
        format_func=lambda h: f"{h}h" if h < 168 else f"{h // 24}d",
        key="jb_hours",
    )
    results_options = [5, 10, 20, 50]
    res_val = int(cfg.get("results_per_search", 10))
    results_per_search = col_results.selectbox(
        "Results/search",
        results_options,
        index=results_options.index(res_val) if res_val in results_options else 1,
        key="jb_results",
    )

    st.write("**Boards**")
    # LinkedIn works reliably for Lithuania; Google/Indeed shown but may return fewer results
    all_sites = {"linkedin": "LinkedIn", "google": "Google Jobs", "indeed": "Indeed"}
    active_sites = cfg.get("sites", ["linkedin"])
    selected_sites = [
        site for site, label in all_sites.items()
        if st.checkbox(label, value=site in active_sites, key=f"jb_{site}")
    ]
    st.caption("LinkedIn works best for Lithuania. Google/Indeed may return fewer regional results.")

    if st.button("Save", key="jb_save"):
        settings["job_board_search"] = {
            "enabled": True,
            "custom_search_term": custom.strip(),
            "location": location.strip(),
            "hours_old": hours_old,
            "results_per_search": results_per_search,
            "sites": selected_sites or ["linkedin"],
        }
        save_settings(settings)
        st.success("Saved.")


# ---------------------------------------------------------------------------
# Sidebar: model selection
# ---------------------------------------------------------------------------

def sidebar_model():
    st.header("Model")
    settings = load_settings()

    providers = list(PROVIDER_MODELS.keys())
    current_provider = settings.get("provider", "anthropic")
    provider_idx = providers.index(current_provider) if current_provider in providers else 0

    provider = st.selectbox("Provider", providers, index=provider_idx, key="sb_provider")

    models = PROVIDER_MODELS[provider]
    current_model = settings.get("model", models[0])
    model_idx = models.index(current_model) if current_model in models else 0

    model = st.selectbox("Model", models, index=model_idx, key="sb_model")

    key_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    st.caption(f"Set `{key_name}` in `.env`")

    if st.button("Save model", key="save_model"):
        save_settings({"provider": provider, "model": model})
        st.success(f"Using {provider} / {model}")


# ---------------------------------------------------------------------------

def sidebar_sources():
    st.header("Job Sources")
    sources = load_sources()

    for i, source in enumerate(sources):
        label = f"{'✓' if source.get('active') else '✗'} {source['name']}"
        with st.expander(label):
            source["active"] = st.checkbox(
                "Active", value=source.get("active", False), key=f"active_{source['id']}"
            )
            source["url"] = st.text_input(
                "URL", value=source.get("url", ""), key=f"url_{source['id']}"
            )
            source["requires_browser"] = st.checkbox(
                "Needs browser (JS rendering)",
                value=source.get("requires_browser", False),
                key=f"browser_{source['id']}",
            )
            source["scan_frequency"] = st.selectbox(
                "Frequency", ["daily", "weekly"],
                index=0 if source.get("scan_frequency") != "weekly" else 1,
                key=f"freq_{source['id']}",
            )
            st.caption(_source_last_scanned_label(source))

            # Confirm-before-remove so it can't be triggered by accident
            if st.session_state.get(f"confirm_remove_{source['id']}"):
                st.warning(f"Remove **{source['name']}**? This cannot be undone.")
                col_yes, col_no = st.columns(2)
                if col_yes.button("Yes, remove", key=f"yes_remove_{source['id']}", type="primary"):
                    sources.pop(i)
                    save_sources(sources)
                    st.session_state.pop(f"confirm_remove_{source['id']}", None)
                    st.rerun()
                if col_no.button("Cancel", key=f"no_remove_{source['id']}"):
                    st.session_state.pop(f"confirm_remove_{source['id']}", None)
                    st.rerun()
            else:
                if st.button("🗑 Remove source", key=f"remove_{source['id']}"):
                    st.session_state[f"confirm_remove_{source['id']}"] = True
                    st.rerun()

            sources[i] = source

    if st.button("Save Sources"):
        save_sources(sources)
        st.success("Saved.")

    st.divider()
    st.subheader("Add New Source")
    with st.form("add_source_form", clear_on_submit=True):
        new_name = st.text_input("Name", placeholder="Company Name")
        new_url = st.text_input("URL", placeholder="https://company.com/careers")
        new_browser = st.checkbox("Requires browser (JS rendering)")
        submitted = st.form_submit_button("Add Source")

    if submitted:
        if new_name and new_url:
            slug = new_name.lower().replace(" ", "-")
            sources.append({
                "id": f"{slug}-{uuid.uuid4().hex[:4]}",
                "name": new_name,
                "url": new_url,
                "requires_browser": new_browser,
                "active": True,
                "scan_frequency": "daily",
                "last_scanned": None,
                "notes": "",
            })
            save_sources(sources)
            st.rerun()
        else:
            st.warning("Name and URL are required.")


# ---------------------------------------------------------------------------
# Tab: Profile — AI onboarding chat
# ---------------------------------------------------------------------------

def _profile_builder_chat():
    _init_chat_state()

    status = st.session_state.pb_status

    # ── Idle: show input options ──────────────────────────────────────────
    if status == "idle":
        st.subheader("Build Profile with AI")
        st.caption(
            "Upload your CV and/or type a quick summary of your skills. "
            "The agent will extract what it can and ask follow-up questions for anything unclear."
        )

        uploaded_file = st.file_uploader(
            "Upload CV (PDF, DOCX, or plain text)", type=["pdf", "docx", "txt"]
        )
        typed_notes = st.text_area(
            "Or type competencies / experience notes",
            height=150,
            placeholder=(
                "e.g. 3 years Python, built LLM pipelines with LangGraph, "
                "currently ML engineer at Citco, looking for AI adoption roles in Vilnius or remote..."
            ),
        )

        if st.button("Start building", type="primary"):
            cv_text = ""
            if uploaded_file:
                try:
                    from utils.cv_parser import extract_text_from_upload
                    cv_text = extract_text_from_upload(uploaded_file)
                except ValueError as exc:
                    st.error(str(exc))
                    return

            if not cv_text and not typed_notes.strip():
                st.warning("Provide a CV upload or type some notes to get started.")
                return

            existing_profile = load_profile()

            with st.spinner("Reading your CV and thinking of the first question..."):
                from agents.profile_builder import start_conversation
                result, api_msgs = start_conversation(cv_text, typed_notes.strip(), existing_profile)

            st.session_state.pb_status = result["status"]
            st.session_state.pb_api_messages = api_msgs
            st.session_state.pb_draft = result["profile"]
            st.session_state.pb_messages = [
                {"role": "assistant", "content": result["message"]}
            ]
            st.rerun()

    # ── Active: show chat ─────────────────────────────────────────────────
    elif status in ("active", "asking"):
        st.subheader("Build Profile with AI")

        for msg in st.session_state.pb_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        answer = st.chat_input("Your answer…")
        if answer:
            st.session_state.pb_messages.append({"role": "user", "content": answer})

            with st.spinner("Thinking..."):
                from agents.profile_builder import continue_conversation
                result, api_msgs = continue_conversation(
                    answer,
                    st.session_state.pb_api_messages,
                    st.session_state.pb_draft,
                )

            st.session_state.pb_api_messages = api_msgs
            st.session_state.pb_draft = result["profile"]
            st.session_state.pb_status = result["status"]
            st.session_state.pb_messages.append(
                {"role": "assistant", "content": result["message"]}
            )
            st.rerun()

        col_apply, col_reset = st.columns([1, 1])
        with col_apply:
            if st.button("Apply draft to profile now"):
                save_profile(st.session_state.pb_draft)
                st.session_state.pb_status = "idle"
                st.session_state.pb_messages = []
                st.session_state.pb_api_messages = []
                st.session_state.pb_draft = {}
                st.success("Profile saved. Edit any fields below.")
                st.rerun()
        with col_reset:
            if st.button("Start over"):
                st.session_state.pb_status = "idle"
                st.session_state.pb_messages = []
                st.session_state.pb_api_messages = []
                st.session_state.pb_draft = {}
                st.rerun()

    # ── Complete ──────────────────────────────────────────────────────────
    elif status == "complete":
        st.subheader("Build Profile with AI")

        for msg in st.session_state.pb_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        st.success("Profile looks complete. Review the fields below and click Apply.")

        col_apply, col_reset = st.columns([1, 1])
        with col_apply:
            if st.button("Apply to profile", type="primary"):
                save_profile(st.session_state.pb_draft)
                st.session_state.pb_status = "idle"
                st.session_state.pb_messages = []
                st.session_state.pb_api_messages = []
                st.session_state.pb_draft = {}
                st.rerun()
        with col_reset:
            if st.button("Keep chatting"):
                st.session_state.pb_status = "asking"
                st.rerun()


# ---------------------------------------------------------------------------
# Tab: Profile — manual edit form
# ---------------------------------------------------------------------------

def _profile_manual_form():
    # If there's a draft in progress, show it in the form so the user can preview
    if st.session_state.get("pb_draft"):
        profile = st.session_state.pb_draft
        st.info("Showing draft from the AI builder above. Click **Apply to profile** to save it, or edit fields directly here.")
    else:
        profile = load_profile()

    st.divider()
    st.subheader("Manual edit")

    st.subheader("Identity")
    col1, col2, col3 = st.columns(3)
    profile["name"] = col1.text_input("Full name", value=profile.get("name", ""))
    profile["current_title"] = col2.text_input("Current title", value=profile.get("current_title", ""))
    profile["experience_years"] = col3.number_input(
        "Years of experience", min_value=0, max_value=40,
        value=int(profile.get("experience_years") or 0)
    )
    profile["location"] = st.text_input(
        "Your location", value=profile.get("location", ""), placeholder="Vilnius, Lithuania"
    )

    st.divider()
    st.subheader("What you're looking for")
    st.caption("Fed directly into the Scanner's extraction prompt.")

    col_roles, col_kw = st.columns(2)
    with col_roles:
        target_roles_text = st.text_area(
            "Target job titles",
            value=_list_to_lines(profile.get("target_roles", [])),
            height=120,
            placeholder="AI Engineer\nML Engineer\nAI Adoption Engineer",
            help="One per line.",
        )
        profile["target_roles"] = _lines_to_list(target_roles_text)
    with col_kw:
        target_kw_text = st.text_area(
            "Must-have keywords",
            value=_list_to_lines(profile.get("target_keywords", [])),
            height=120,
            placeholder="LLM\nLangGraph\nPython",
            help="One per line.",
        )
        profile["target_keywords"] = _lines_to_list(target_kw_text)

    excl_text = st.text_area(
        "Excluded keywords",
        value=_list_to_lines(profile.get("excluded_keywords", [])),
        height=80,
        placeholder="SAP\nCobol",
        help="One per line. Postings matching these are skipped.",
    )
    profile["excluded_keywords"] = _lines_to_list(excl_text)

    st.divider()
    st.subheader("Location preferences")
    loc = profile.get("location_preferences", {})
    col_modes, col_locs = st.columns(2)
    with col_modes:
        loc["remote"] = st.checkbox("Remote", value=loc.get("remote", True))
        loc["hybrid"] = st.checkbox("Hybrid", value=loc.get("hybrid", True))
        loc["on_site"] = st.checkbox("On-site", value=loc.get("on_site", True))
    with col_locs:
        pref_locs_text = st.text_area(
            "Preferred locations",
            value=_list_to_lines(loc.get("preferred_locations", [])),
            height=100,
            placeholder="Vilnius\nRemote",
        )
        loc["preferred_locations"] = _lines_to_list(pref_locs_text)
    profile["location_preferences"] = loc

    seniority_options = ["junior", "mid", "senior", "lead", "any"]
    seniority_val = profile.get("seniority", "mid")
    profile["seniority"] = st.selectbox(
        "Seniority level", seniority_options,
        index=seniority_options.index(seniority_val) if seniority_val in seniority_options else 1,
    )

    st.divider()
    st.subheader("Skills")
    skills = profile.get("skills", {})
    col_tech, col_lang = st.columns(2)
    with col_tech:
        skills["technical"] = _lines_to_list(st.text_area(
            "Technical skills",
            value=_list_to_lines(skills.get("technical", [])),
            height=150,
            placeholder="Python\nLangGraph\nAnthropic API",
        ))
    with col_lang:
        skills["languages"] = _lines_to_list(st.text_area(
            "Languages spoken",
            value=_list_to_lines(skills.get("languages", [])),
            height=100,
            placeholder="Lithuanian (native)\nEnglish (fluent)",
        ))
    skills["soft"] = _lines_to_list(st.text_area(
        "Soft skills",
        value=_list_to_lines(skills.get("soft", [])),
        height=80,
        placeholder="Technical communication\nProject management",
    ))
    profile["skills"] = skills

    st.divider()
    st.subheader("Summary & CV")
    profile["summary"] = st.text_area(
        "Professional summary",
        value=profile.get("summary", ""),
        height=120,
        placeholder="2-3 sentences describing your background and what you're looking for.",
    )
    profile["cv_text"] = st.text_area(
        "Full CV text",
        value=profile.get("cv_text", ""),
        height=300,
        placeholder="Paste your full CV here. Used by the Application Writer agent.",
    )

    st.divider()
    st.subheader("Application preferences")
    tone_options = ["professional", "conversational", "concise", "enthusiastic"]
    tone_val = profile.get("cover_letter_tone", "professional")
    col_tone, col_sal = st.columns(2)
    profile["cover_letter_tone"] = col_tone.selectbox(
        "Cover letter tone", tone_options,
        index=tone_options.index(tone_val) if tone_val in tone_options else 0,
    )
    profile["min_salary"] = col_sal.text_input(
        "Minimum salary expectation",
        value=str(profile.get("min_salary") or ""),
        placeholder="e.g. 3500 EUR/month",
    ) or None
    profile["notes"] = st.text_area(
        "Additional notes for agents",
        value=profile.get("notes", ""),
        height=80,
        placeholder="Visa requirements, notice period, anything else agents should know.",
    )

    if st.button("Save Profile", type="primary"):
        from utils.security import validate_profile
        save_profile(validate_profile(profile))
        st.success("Profile saved. Agents will use it on the next scan.")


def tab_profile():
    _profile_builder_chat()
    _profile_manual_form()


# ---------------------------------------------------------------------------
# Job list with status tracking + apply links
# ---------------------------------------------------------------------------

_JOB_STATUSES = ["new", "saved", "applied", "rejected"]
_STATUS_LABEL = {
    "new":      "🔵 New",
    "saved":    "⭐ Saved",
    "applied":  "✅ Applied",
    "rejected": "❌ Skip",
}
_STATUS_BADGE = {
    "new":      "",
    "saved":    "⭐ ",
    "applied":  "✅ ",
    "rejected":  "❌ ",
}


def _on_status_change(job_id: str):
    update_job_status(job_id, st.session_state[f"status_{job_id}"])


def _render_job_list(jobs: list):
    col_src, col_status = st.columns(2)
    source_ids = sorted({j["source_id"] for j in jobs})
    filter_source = col_src.selectbox("Source", ["All"] + source_ids)
    filter_status = col_status.selectbox(
        "Status",
        ["All"] + _JOB_STATUSES,
        format_func=lambda s: s if s == "All" else _STATUS_LABEL[s],
    )

    filtered = [
        j for j in jobs
        if (filter_source == "All" or j["source_id"] == filter_source)
        and (filter_status == "All" or j.get("status", "new") == filter_status)
    ]

    st.write(f"**{len(filtered)} job(s)**")

    for job in filtered:
        job_status = job.get("status", "new")
        badge = _STATUS_BADGE.get(job_status, "")
        label = f"{badge}{job['title']} — {job['company']}"
        if job.get("location"):
            label += f"  ·  {job['location']}"

        with st.expander(label):
            top_left, top_right = st.columns([3, 1])

            with top_left:
                if job.get("url"):
                    st.link_button("Apply →", job["url"], type="primary")
                else:
                    st.caption("No direct URL — check the source site.")

            with top_right:
                current_idx = _JOB_STATUSES.index(job_status) if job_status in _JOB_STATUSES else 0
                st.selectbox(
                    "Status",
                    _JOB_STATUSES,
                    index=current_idx,
                    format_func=lambda s: _STATUS_LABEL[s],
                    key=f"status_{job['id']}",
                    on_change=_on_status_change,
                    args=(job["id"],),
                    label_visibility="collapsed",
                )

            if job.get("description"):
                st.write(job["description"])

            st.caption(f"Discovered {job['discovered_at'][:10]}  ·  source: {job['source_id']}")


# ---------------------------------------------------------------------------
# Tab: Scan
# ---------------------------------------------------------------------------

def tab_scan():
    profile = load_profile()
    if not profile.get("target_roles") and not profile.get("target_keywords"):
        st.warning(
            "No target roles or keywords in your profile — the Scanner will return all jobs on each page. "
            "Fill in the **Profile** tab to focus results."
        )

    col_scan, col_manual = st.columns([2, 1])

    with col_scan:
        if st.button("Scan Now", type="primary"):
            with st.spinner("Scanning active sources..."):
                result = run_scan()

            summary = result.get("scan_summary", {})
            new_count = len(result.get("new_postings", []))

            if new_count:
                st.success(f"Found {new_count} new job(s).")
            else:
                st.info("No new jobs found.")

            for source_name, stats in summary.items():
                if "error" in stats:
                    st.error(f"**{source_name}**: {stats['error']}")
                else:
                    st.write(f"**{source_name}**: {stats['found']} total, {stats['new']} new")

            errors = result.get("scan_errors", [])
            if errors:
                with st.expander("Scan errors"):
                    for e in errors:
                        st.error(e)

    with col_manual:
        st.caption("Paste a job description from LinkedIn, Indeed, or any blocked site.")
        manual_text = st.text_area(
            "Job description", height=200, placeholder="Paste full job description here..."
        )
        if st.button("Process") and manual_text:
            st.info("Manual processing coming soon — Relevance Evaluator is next.")

    st.divider()
    jobs = get_recent_jobs(100)
    if not jobs:
        st.info("No jobs yet — configure your sources in the sidebar and click Scan Now.")
        return

    _render_job_list(jobs)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Job Search Agent", layout="wide")
    st.title("Job Search Agent")

    init_db()

    with st.sidebar:
        sidebar_model()
        st.divider()
        sidebar_job_boards()
        st.divider()
        sidebar_sources()

    scan_tab, profile_tab = st.tabs(["Scan", "Profile"])

    with scan_tab:
        tab_scan()

    with profile_tab:
        tab_profile()


if __name__ == "__main__":
    main()
