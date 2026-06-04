import json
from pathlib import Path

PROFILE_PATH = Path(__file__).parent.parent / "config" / "profile.json"

_DEFAULTS = {
    "name": "",
    "current_title": "",
    "experience_years": 0,
    "location": "",
    "summary": "",
    "cv_text": "",
    "target_roles": [],
    "target_keywords": [],
    "excluded_keywords": [],
    "skills": {"technical": [], "soft": [], "languages": []},
    "location_preferences": {
        "remote": True,
        "hybrid": True,
        "on_site": True,
        "preferred_locations": [],
    },
    "seniority": "mid",
    "cover_letter_tone": "professional",
    "min_salary": None,
    "notes": "",
}


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        return dict(_DEFAULTS)
    with open(PROFILE_PATH) as f:
        data = json.load(f)
    # Merge with defaults so new fields are always present
    merged = dict(_DEFAULTS)
    merged.update(data)
    if "skills" in data:
        merged["skills"] = {**_DEFAULTS["skills"], **data["skills"]}
    if "location_preferences" in data:
        merged["location_preferences"] = {
            **_DEFAULTS["location_preferences"],
            **data["location_preferences"],
        }
    return merged


def save_profile(profile: dict):
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)
