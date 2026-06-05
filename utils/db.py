import hashlib
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            cv_text TEXT,
            cover_letter TEXT
        )
    """)

    # Migrate: add evaluation columns to jobs if not present
    existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    for col, col_type in [
        ("relevance_score", "INTEGER"),
        ("recommendation", "TEXT"),
        ("evaluation_json", "TEXT"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()


def get_existing_job_ids() -> set:
    conn = sqlite3.connect(DB_PATH)
    ids = {row[0] for row in conn.execute("SELECT id FROM jobs").fetchall()}
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


def get_recent_jobs(limit: int = 100) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [
        dict(row) for row in
        conn.execute("SELECT * FROM jobs ORDER BY discovered_at DESC LIMIT ?", (limit,)).fetchall()
    ]
    conn.close()
    return rows


# ── Evaluation ────────────────────────────────────────────────────────────────

def save_evaluation(job_id: str, evaluation: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE jobs SET relevance_score=?, recommendation=?, evaluation_json=? WHERE id=?",
        (
            evaluation.get("score"),
            evaluation.get("recommendation"),
            json.dumps(evaluation),
            job_id,
        ),
    )
    conn.commit()
    conn.close()


def get_evaluation(job_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT evaluation_json FROM jobs WHERE id=?", (job_id,)
    ).fetchone()
    conn.close()
    if row and row[0]:
        return json.loads(row[0])
    return None


# ── Applications ──────────────────────────────────────────────────────────────

def save_application(job_id: str, cv_text: str, cover_letter: str) -> str:
    app_id = hashlib.sha256(
        f"{job_id}:{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()[:16]
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO applications (id, job_id, generated_at, cv_text, cover_letter) VALUES (?,?,?,?,?)",
        (app_id, job_id, datetime.now(timezone.utc).isoformat(), cv_text, cover_letter),
    )
    conn.commit()
    conn.close()
    return app_id


def get_latest_application(job_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM applications WHERE job_id=? ORDER BY generated_at DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
