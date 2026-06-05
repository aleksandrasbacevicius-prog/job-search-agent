import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.json"

_DEFAULTS = {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
    "job_board_search": {
        "enabled": False,
        "custom_search_term": "",
        "location": "",
        "hours_old": 168,
        "results_per_search": 10,
        "sites": ["linkedin"],
    },
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return dict(_DEFAULTS)
    with open(SETTINGS_PATH) as f:
        data = json.load(f)
    merged = {**_DEFAULTS, **data}
    # Deep-merge nested job_board_search so new keys always have defaults
    if "job_board_search" in data:
        merged["job_board_search"] = {**_DEFAULTS["job_board_search"], **data["job_board_search"]}
    return merged


def save_settings(settings: dict):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
