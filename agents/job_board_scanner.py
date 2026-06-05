"""
Job Board Scanner Agent — searches LinkedIn, Google Jobs, and Indeed
via python-jobspy using the profile's target roles as search terms.

Runs as a second LangGraph node after the URL scanner, appending results
to the same state so both land in the same jobs table.
"""

import hashlib
import logging

from agents.scanner import ScannerState
from utils.db import get_existing_job_ids, insert_jobs, log_scan
from utils.settings import load_settings

logger = logging.getLogger(__name__)

# jobspy logs can be noisy — suppress INFO-level chatter
logging.getLogger("JobSpy").setLevel(logging.WARNING)


def _job_id(site: str, title: str, url: str, company: str) -> str:
    # Prefer URL-based ID so the same posting on two sources deduplicates cleanly
    key = f"jobspy-{site}:{title.lower()}:{(url or company).lower()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def run_job_board_scanner(state: ScannerState) -> ScannerState:
    settings = load_settings()
    cfg = settings.get("job_board_search", {})

    if not cfg.get("enabled"):
        return state

    profile = state.get("profile") or {}

    # Determine search terms: explicit override or each target role from profile
    custom = (cfg.get("custom_search_term") or "").strip()
    if custom:
        search_terms = [custom]
    else:
        search_terms = [r.strip() for r in profile.get("target_roles", []) if r.strip()]

    if not search_terms:
        return {
            **state,
            "scan_errors": state.get("scan_errors", []) + [
                "Job board search: no search terms — add target roles in your Profile tab "
                "or set a custom search term in the sidebar."
            ],
        }

    location = (cfg.get("location") or profile.get("location") or "").strip()
    sites = cfg.get("sites") or ["linkedin"]
    hours_old = int(cfg.get("hours_old") or 168)
    results_per_search = int(cfg.get("results_per_search") or 10)

    existing_ids = get_existing_job_ids()
    all_new = list(state.get("new_postings", []))
    errors = list(state.get("scan_errors", []))
    summary = dict(state.get("scan_summary", {}))

    try:
        from jobspy import scrape_jobs
    except ImportError:
        errors.append("python-jobspy is not installed. Run: pip install python-jobspy --no-deps")
        return {**state, "scan_errors": errors}

    # Track counts per site across all search terms
    site_counts: dict[str, dict] = {s: {"found": 0, "new": 0} for s in sites}

    for term in search_terms:
        for site in sites:
            try:
                kwargs = dict(
                    site_name=[site],
                    search_term=term,
                    results_wanted=results_per_search,
                    hours_old=hours_old,
                )
                if location:
                    kwargs["location"] = location
                # Indeed needs an explicit country code
                if site == "indeed" and location:
                    kwargs["country_indeed"] = location.split(",")[-1].strip()

                df = scrape_jobs(**kwargs)

                jobs = []
                for _, row in df.iterrows():
                    title = str(row.get("title") or "").strip()
                    if not title:
                        continue
                    company = str(row.get("company") or "").strip()
                    url = str(row.get("job_url") or "").strip()
                    job_id = _job_id(site, title, url, company)
                    jobs.append({
                        "id": job_id,
                        "source_id": f"jobspy-{site}",
                        "title": title,
                        "company": company,
                        "url": url,
                        "location": str(row.get("location") or "").strip(),
                        "description": str(row.get("description") or "")[:500].strip(),
                    })

                new_jobs = [j for j in jobs if j["id"] not in existing_ids]
                inserted = insert_jobs(new_jobs)
                log_scan(f"jobspy-{site}", len(jobs), inserted)

                all_new.extend(new_jobs)
                existing_ids.update(j["id"] for j in new_jobs)
                site_counts[site]["found"] += len(jobs)
                site_counts[site]["new"] += inserted

            except Exception as exc:
                msg = f"{site.title()} (job boards) — {term}: {exc}"
                errors.append(msg)
                log_scan(f"jobspy-{site}", 0, 0, str(exc))

    # Roll up per-site totals into scan summary
    site_labels = {"linkedin": "LinkedIn", "indeed": "Indeed", "google": "Google Jobs"}
    for site, counts in site_counts.items():
        label = site_labels.get(site, site.title())
        if counts["found"] > 0 or site in [s for s in sites]:
            summary[label] = counts

    return {
        **state,
        "new_postings": all_new,
        "scan_errors": errors,
        "scan_summary": summary,
    }
