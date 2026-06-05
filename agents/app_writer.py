"""
Application Writer — produces a tailored CV and cover letter for a specific job.

Takes the job posting, the user's full profile, and the Relevance Evaluator's
gap analysis so it already knows what to emphasise and what to address honestly.
"""

import json
import re

from utils.llm import chat
from utils.security import wrap_untrusted

_SYSTEM_PROMPT = """\
You are an expert CV writer and career advisor.

Given a job posting, the candidate's profile, and an evaluation with identified
strengths and gaps, produce a tailored CV and cover letter for this specific role.

Respond with a single JSON object — no markdown fences, no extra text:
{
  "cv": "the full tailored CV as plain text",
  "cover_letter": "the cover letter as plain text"
}

CV guidelines:
- Reorder and reword the original CV to lead with the most relevant experience.
- Mirror keywords and phrases from the job description where they honestly apply.
- Keep all facts accurate — do not invent experience, qualifications, or metrics.
- Maintain a clean, professional structure: profile summary, skills, experience, education.
- Adjust the profile summary to speak directly to this role and company.

Cover letter guidelines:
- 3-4 paragraphs, no longer.
- Open with genuine interest in the specific role and company — not generic phrases.
- Highlight the top 2-3 strengths identified in the evaluation with concrete evidence.
- Address the main gap(s) honestly and constructively — frame as a growth area
  or explain how adjacent experience compensates.
- Close with a clear, confident call to action.
- Match the tone specified in the profile (cover_letter_tone field).

Non-negotiable: never fabricate or exaggerate anything not in the original CV.\
"""


def write_application(job: dict, profile: dict, evaluation: dict) -> dict:
    """
    Generate a tailored CV and cover letter.

    Returns a dict with: cv, cover_letter.
    """
    jd = (job.get("description") or "")[:3000]
    cv = (profile.get("cv_text") or "").strip()

    user_msg = (
        "Please write a tailored application for this job.\n\n"
        "<job_posting>\n"
        f"Title: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Location: {job.get('location', '')}\n\n"
        f"Description:\n{wrap_untrusted(jd, tag='job_description')}\n"
        "</job_posting>\n\n"
        "<evaluation>\n"
        f"Fit score: {evaluation.get('score', 0)}/100\n"
        f"Strengths to lead with:\n"
        + "\n".join(f"- {s}" for s in evaluation.get("strengths", []))
        + "\n"
        f"Gaps to address honestly:\n"
        + "\n".join(f"- {g}" for g in evaluation.get("gaps", []))
        + "\n</evaluation>\n\n"
        "<candidate_profile>\n"
        f"Name: {profile.get('name', '')}\n"
        f"Current title: {profile.get('current_title', '')}\n"
        f"Years of experience: {profile.get('experience_years', 0)}\n"
        f"Cover letter tone: {profile.get('cover_letter_tone', 'professional')}\n\n"
        f"Original CV:\n{wrap_untrusted(cv, tag='original_cv')}\n"
        "</candidate_profile>"
    )

    response = chat(
        [{"role": "user", "content": user_msg}],
        system=_SYSTEM_PROMPT,
        max_tokens=4096,
    )
    return _parse(response)


def _parse(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
        return {
            "cv": str(data.get("cv") or "").strip(),
            "cover_letter": str(data.get("cover_letter") or "").strip(),
        }
    except (json.JSONDecodeError, TypeError):
        # If JSON fails, treat the whole response as the cover letter
        return {"cv": "", "cover_letter": text}
