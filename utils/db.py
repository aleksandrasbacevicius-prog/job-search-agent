import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT,
            url TEXT,
            location TEXT,
            description TEXT,
            raw_data TEXT,
            discovered_at TEXT NOT NULL,
            status TEXT DEFAULT 'new'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            scanned_at TEXT NOT NULL,
            jobs_found INTEGER DEFAULT 0,
            new_jobs INTEGER DEFAULT 0,
            error TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_existing_job_ids() -> set:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT id FROM jobs")
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids


def insert_jobs(jobs: list) -> int:
    if not jobs:
        return 0
    conn = sqlite3.connect(DB_PATH)
    inserted = 0
    for job in jobs:
        try:
            conn.execute(
                "INSERT INTO jobs (id, source_id, title, company, url, location, description, raw_data, discovered_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job["id"],
                    job["source_id"],
                    job["title"],
                    job.get("company", ""),
                    job.get("url", ""),
                    job.get("location", ""),
                    job.get("description", ""),
                    json.dumps(job),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def log_scan(source_id: str, jobs_found: int, new_jobs: int, error: str = None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO scan_log (source_id, scanned_at, jobs_found, new_jobs, error) VALUES (?, ?, ?, ?, ?)",
        (source_id, datetime.now(timezone.utc).isoformat(), jobs_found, new_jobs, error),
    )
    conn.commit()
    conn.close()


def update_job_status(job_id: str, status: str):
    valid = {"new", "saved", "applied", "rejected"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of {valid}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()


def get_recent_jobs(limit: int = 50) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM jobs ORDER BY discovered_at DESC LIMIT ?", (limit,)
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows
