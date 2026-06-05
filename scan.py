"""
Standalone scan runner — called by Windows Task Scheduler (or manually).

Usage:
    python scan.py              # respects scan_frequency; skips recently-scanned sources
    python scan.py --force      # scans everything regardless of last_scanned

Logs to data/scan.log (rotating, 500 KB max, 3 backups kept).
Exit 0 = success, Exit 1 = unrecoverable error.
"""

import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_FILE = ROOT / "data" / "scan.log"
LOG_FILE.parent.mkdir(exist_ok=True)

_fmt = "%(asctime)s  %(levelname)-8s  %(message)s"
_datefmt = "%Y-%m-%d %H:%M"
logging.basicConfig(
    level=logging.INFO,
    format=_fmt,
    datefmt=_datefmt,
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=500_000, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# Suppress noisy third-party loggers
for _noisy in ("JobSpy", "httpx", "playwright"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def _ensure_chromium():
    """Auto-install Chromium if Playwright updated and the binary is missing."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            log.info("Chromium binary missing (Playwright updated) — installing now...")
            import subprocess
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            log.info("Chromium installed.")

# ── Frequency helpers ─────────────────────────────────────────────────────────

_FREQ_WINDOWS = {
    "daily": timedelta(hours=20),   # 4-hour buffer so 8am task isn't blocked by an 8:05am run
    "weekly": timedelta(days=6, hours=12),
}


def _should_scan(source: dict, force: bool) -> bool:
    if force:
        return True
    if not source.get("active") or not source.get("url"):
        return False
    ts = source.get("last_scanned")
    if not ts:
        return True
    try:
        last = datetime.fromisoformat(ts)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        window = _FREQ_WINDOWS.get(source.get("scan_frequency", "daily"), timedelta(hours=20))
        return datetime.now(timezone.utc) - last >= window
    except ValueError:
        return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main(force: bool = False) -> int:
    log.info("=" * 60)
    log.info(f"Scan started  {'(forced)' if force else ''}")
    _ensure_chromium()

    try:
        from agents.scanner import load_sources, save_sources
        from utils.profile import load_profile
        from utils.settings import load_settings

        all_sources = load_sources()
        due_sources = [s for s in all_sources if _should_scan(s, force)]
        skipped = [s["name"] for s in all_sources if s.get("active") and s not in due_sources]

        if skipped:
            log.info(f"Skipping (not due yet): {', '.join(skipped)}")
        if not due_sources and not load_settings().get("job_board_search", {}).get("enabled"):
            log.info("Nothing to scan.")
            return 0

        from pipeline.graph import build_pipeline
        pipeline = build_pipeline()

        result = pipeline.invoke({
            "sources": due_sources,
            "profile": load_profile(),
            "new_postings": [],
            "scan_errors": [],
            "scan_summary": {},
        })

        summary = result.get("scan_summary", {})
        errors = result.get("scan_errors", [])
        new_count = len(result.get("new_postings", []))

        for source_name, stats in summary.items():
            if "error" in stats:
                log.warning(f"  {source_name}: ERROR — {stats['error']}")
            else:
                log.info(f"  {source_name}: {stats['found']} found, {stats['new']} new")

        for err in errors:
            log.error(f"  {err}")

        log.info(f"Scan complete — {new_count} new job(s) across {len(summary)} source(s)")
        return 0

    except Exception:
        log.exception("Scan failed with unhandled exception")
        return 1


if __name__ == "__main__":
    force = "--force" in sys.argv
    sys.exit(main(force=force))
