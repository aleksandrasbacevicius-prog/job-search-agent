import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from utils.db import get_existing_job_ids, init_db, insert_jobs, log_scan
from utils.scraper import scrape_source

SOURCES_PATH = Path(__file__).parent.parent / "config" / "sources.json"


def load_sources() -> list:
    with open(SOURCES_PATH) as f:
        return json.load(f)["sources"]


def save_sources(sources: list):
    with open(SOURCES_PATH, "w") as f:
        json.dump({"sources": sources}, f, indent=2)


class ScannerState(TypedDict):
    sources: list
    profile: dict
    new_postings: list
    scan_errors: list
    scan_summary: dict


def run_scanner(state: ScannerState) -> ScannerState:
    init_db()

    active_sources = [s for s in state["sources"] if s.get("active") and s.get("url")]
    existing_ids = get_existing_job_ids()
    profile = state.get("profile") or {}

    all_new = []
    errors = []
    summary = {}

    for source in active_sources:
        try:
            jobs = scrape_source(source, profile)
            new_jobs = [j for j in jobs if j["id"] not in existing_ids]
            inserted = insert_jobs(new_jobs)
            log_scan(source["id"], len(jobs), inserted)

            all_new.extend(new_jobs)
            existing_ids.update(j["id"] for j in new_jobs)
            summary[source["name"]] = {"found": len(jobs), "new": inserted}
            source["last_scanned"] = datetime.now(timezone.utc).isoformat()

        except Exception as exc:
            error_msg = f"{source['name']}: {exc}"
            errors.append(error_msg)
            log_scan(source["id"], 0, 0, str(exc))
            summary[source["name"]] = {"found": 0, "new": 0, "error": str(exc)}

    # Persist updated last_scanned timestamps
    all_sources = load_sources()
    source_by_id = {s["id"]: s for s in active_sources}
    for s in all_sources:
        if s["id"] in source_by_id:
            s["last_scanned"] = source_by_id[s["id"]].get("last_scanned")
    save_sources(all_sources)

    return {
        **state,
        "new_postings": all_new,
        "scan_errors": errors,
        "scan_summary": summary,
    }
