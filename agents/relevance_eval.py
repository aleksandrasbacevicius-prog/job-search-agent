"""
Relevance Evaluator — scores a job posting against the user's profile.

Outputs a fit score (0-100), recommendation (apply/stretch/skip),
strengths, gaps, and a plain-English summary.
"""

import json
import re

from utils.llm import chat
from utils.security import wrap_untrusted

_SYSTEM_PROMPT = """\
You are an expert career advisor evaluating job fit for a candidate.

Given a job posting and the candidate's profile, assess how well they match.

Respond with a single JSON object — no markdown fences, no extra text:
{
  "score": <integer 0-100>,
  "recommendation": "apply" | "stretch" | "skip",
  "strengths": ["specific strength 1", "specific strength 2"],
  "gaps": ["specific gap 1", "specific gap 2"],
  "summary": "2-3 sentence honest overall assessment"
}

Scoring guide:
  80-100  Strong match — "apply"
  60-79   Good fit, minor gaps — "apply"
  40-59   Possible but notable gaps — "stretch"
  0-39    Poor fit — "skip"

Rules:
- Be specific: reference actual requirements from the job and actual experience from the CV.
- Do not inflate scores to be encouraging.
- Do not invent gaps that aren't supported by the job description.
- Strengths and gaps should each be 1-2 sentence bullet points, not single words.\
"""


def evaluate_job(job: dict, profile: dict) -> dict:
    """
    Score a job posting against the user's profile.

    Returns a dict with: score, recommendation, strengths, gaps, summary.
    """
    jd = (job.get("description") or "")[:3000]
    cv = (profile.get("cv_text") or "").strip()

    user_msg = (
        "Please evaluate this job posting against my profile.\n\n"
        "<job_posting>\n"
        f"Title: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Location: {job.get('location', '')}\n\n"
        f"Description:\n{wrap_untrusted(jd, tag='job_description')}\n"
        "</job_posting>\n\n"
        "<candidate_profile>\n"
        f"Name: {profile.get('name', '')}\n"
        f"Current title: {profile.get('current_title', '')}\n"
        f"Experience: {profile.get('experience_years', 0)} years\n"
        f"Location: {profile.get('location', '')}\n"
        f"Seniority target: {profile.get('seniority', 'mid')}\n"
        f"Target roles: {', '.join(profile.get('target_roles', []))}\n"
        f"Technical skills: {', '.join((profile.get('skills') or {}).get('technical', []))}\n\n"
        f"Full CV:\n{wrap_untrusted(cv, tag='cv_text')}\n"
        "</candidate_profile>"
    )

    response = chat(
        [{"role": "user", "content": user_msg}],
        system=_SYSTEM_PROMPT,
        max_tokens=1500,
    )
    return _parse(response)


def _parse(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
        rec = str(data.get("recommendation", "skip"))
        if rec not in ("apply", "stretch", "skip"):
            rec = "skip"
        return {
            "score": max(0, min(100, int(data.get("score") or 0))),
            "recommendation": rec,
            "strengths": [str(s)[:300] for s in (data.get("strengths") or [])[:8]],
            "gaps": [str(g)[:300] for g in (data.get("gaps") or [])[:8]],
            "summary": str(data.get("summary") or "")[:1000],
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "score": 0,
            "recommendation": "skip",
            "strengths": [],
            "gaps": [],
            "summary": "Evaluation could not be parsed — try again.",
        }
