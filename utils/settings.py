import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.json"

_DEFAULTS = {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return dict(_DEFAULTS)
    with open(SETTINGS_PATH) as f:
        data = json.load(f)
    return {**_DEFAULTS, **data}


def save_settings(settings: dict):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
