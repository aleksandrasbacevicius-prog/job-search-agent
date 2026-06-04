"""
Utilities to reduce prompt injection risk when passing untrusted content
(CV uploads, scraped HTML, user-typed text) into Claude prompts.

Strategy:
  1. HTML-escape ALL angle brackets in untrusted content before wrapping in XML tags.
     This neutralises any XML/HTML inside the content — <system>, </cv_content>,
     <new_instruction>, etc. all become harmless &lt;...&gt; text.
     The old approach of stripping only the specific closing tag was insufficient
     because it left all other tag names (and the opening tag) exploitable.
  2. Validate and sanitize profile dicts returned by agents before storing them.
  3. Enforce field-level length caps so a giant injected payload can't dominate context.
"""

# Maximum character lengths per profile field
_MAX_LENGTHS: dict = {
    "name": 200,
    "current_title": 200,
    "location": 200,
    "summary": 3000,
    "cv_text": 60_000,
    "notes": 3000,
    "min_salary": 200,
    "seniority": 50,
    "cover_letter_tone": 50,
}
_MAX_LIST_ITEM = 300
_MAX_LIST_LEN = 60


def wrap_untrusted(content: str, tag: str = "untrusted_content") -> str:
    """
    Wrap user-supplied content in XML tags with all angle brackets HTML-escaped.

    HTML-escaping every < and > inside the content means no tag — not just the
    closing tag, but <system>, <instruction>, <assistant>, or any other — can
    survive into the prompt as live XML.  The model reads the escaped entities
    as plain text while the outer wrapper tags remain structurally intact.

    Escape order matters: & must come first so we don't double-escape.
    """
    safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<{tag}>\n{safe}\n</{tag}>"


def validate_profile(profile: dict) -> dict:
    """
    Type-check and length-cap every field in a profile dict returned by an
    agent.  Returns a clean copy — never mutates the input.

    This limits the blast radius if an agent returns unexpected content
    (e.g. an injected CV caused it to hallucinate extra fields).
    """
    if not isinstance(profile, dict):
        return {}

    def _str(val, field: str = "") -> str:
        s = str(val) if val is not None else ""
        return s[: _MAX_LENGTHS.get(field, 500)]

    def _list_of_str(val) -> list:
        if not isinstance(val, list):
            return []
        return [str(item)[:_MAX_LIST_ITEM] for item in val[:_MAX_LIST_LEN]]

    def _bool(val, default: bool) -> bool:
        return bool(val) if isinstance(val, bool) else default

    skills_raw = profile.get("skills") or {}
    loc_raw = profile.get("location_preferences") or {}

    return {
        "name": _str(profile.get("name"), "name"),
        "current_title": _str(profile.get("current_title"), "current_title"),
        "experience_years": max(0, min(60, int(profile.get("experience_years") or 0))),
        "location": _str(profile.get("location"), "location"),
        "summary": _str(profile.get("summary"), "summary"),
        "cv_text": _str(profile.get("cv_text"), "cv_text"),
        "target_roles": _list_of_str(profile.get("target_roles")),
        "target_keywords": _list_of_str(profile.get("target_keywords")),
        "excluded_keywords": _list_of_str(profile.get("excluded_keywords")),
        "skills": {
            "technical": _list_of_str(skills_raw.get("technical")),
            "soft": _list_of_str(skills_raw.get("soft")),
            "languages": _list_of_str(skills_raw.get("languages")),
        },
        "location_preferences": {
            "remote": _bool(loc_raw.get("remote"), True),
            "hybrid": _bool(loc_raw.get("hybrid"), True),
            "on_site": _bool(loc_raw.get("on_site"), True),
            "preferred_locations": _list_of_str(loc_raw.get("preferred_locations")),
        },
        "seniority": _str(profile.get("seniority"), "seniority") or "mid",
        "cover_letter_tone": _str(profile.get("cover_letter_tone"), "cover_letter_tone") or "professional",
        "min_salary": _str(profile.get("min_salary"), "min_salary") or None,
        "notes": _str(profile.get("notes"), "notes"),
    }
