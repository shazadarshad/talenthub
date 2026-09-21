"""
AI features for TalentHub, powered by OpenAI.

Two things live here:
1. summarize_cv()      - reads a candidate's CV text and produces a short
                          summary, an extracted skills list, and an estimated
                          years of experience. Run once per CV upload.
2. rank_candidates()   - takes a plain-English search phrase from an employer
                          and a list of candidates, and returns them ordered
                          by how well they match (using their profile + AI
                          summary, not by re-reading every PDF each time).

If OPENAI_API_KEY isn't set, every function here quietly does nothing
(returns None / the original list unchanged) so the rest of the app keeps
working normally without AI configured.
"""
import json
import logging

from flask import current_app

logger = logging.getLogger(__name__)


def _get_client():
    """Build an OpenAI client using the configured API key, or None if
    AI isn't configured for this app.
    """
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    from openai import OpenAI
    return OpenAI(api_key=api_key)


def summarize_cv(cv_text, profile_hints=None):
    """Ask the AI to read a CV's text and produce a structured summary.

    profile_hints is an optional dict of what the candidate already typed
    in their profile (role wanted, skills, experience level) - this gives
    the AI useful context even if the CV text is short or messy.

    Returns a dict like:
        {"summary": "...", "skills": ["Python", "SQL"], "experience_years": 2}
    or None if AI isn't configured, there's no text to work with, or the
    request fails for any reason (network issue, bad response, etc).
    """
    client = _get_client()
    if client is None or not cv_text.strip():
        return None

    hints = profile_hints or {}
    system_prompt = (
        "You are an assistant that reads CVs/resumes and extracts structured "
        "information for a hiring platform. Always respond with valid JSON "
        "matching exactly this shape: "
        '{"summary": string, "skills": [string], "experience_years": number}. '
        "The summary should be 2-3 sentences, professional and neutral, "
        "highlighting the candidate's strongest points for employers. "
        "The skills list should have at most 10 concrete skills/technologies "
        "mentioned in the CV. experience_years should be your best estimate "
        "of total professional experience as a whole number (0 if unclear)."
    )
    user_prompt = (
        f"Candidate's stated role: {hints.get('role_wanted', 'unknown')}\n"
        f"Candidate's stated experience level: {hints.get('experience_level', 'unknown')}\n\n"
        f"CV text:\n{cv_text}"
    )

    try:
        model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=400,
        )
        data = json.loads(response.choices[0].message.content)

        return {
            "summary": str(data.get("summary", "")).strip()[:2000],
            "skills": [str(s).strip() for s in data.get("skills", []) if str(s).strip()][:10],
            "experience_years": int(data.get("experience_years") or 0),
        }
    except Exception:
        # Any failure (network, bad JSON, rate limit, etc.) just means no
        # AI summary this time - it's not worth breaking profile creation.
        logger.exception("AI CV summarization failed")
        return None


def rank_candidates(query, candidates):
    """Rank a list of CandidateProfile objects against a plain-English
    search phrase from an employer, using their profile + AI summary.

    Returns a list of (candidate, reason) tuples in best-match-first order.
    If AI isn't configured, the query is empty, or there are no candidates,
    returns the candidates unranked with an empty reason for each.
    """
    if not candidates:
        return []

    client = _get_client()
    if client is None or not query.strip():
        return [(c, "") for c in candidates]

    # Build a compact description of each candidate for the AI to compare
    # against the query - keeps the request small and fast.
    profiles = []
    for c in candidates:
        profiles.append({
            "id": c.id,
            "role_wanted": c.role_wanted,
            "skills": c.skill_list(),
            "ai_skills": c.ai_skill_list(),
            "experience_level": c.experience_level,
            "ai_experience_years": c.ai_experience_years,
            "location": c.location,
            "summary": c.ai_summary or c.cover_letter[:300],
        })

    system_prompt = (
        "You are a recruiting assistant. Given a hiring requirement and a "
        "list of candidate profiles, rank the candidates from best match to "
        "worst match. Respond with valid JSON matching exactly this shape: "
        '{"ranking": [{"id": number, "reason": string}]}. '
        "Include every candidate id exactly once, ordered best-match-first. "
        "reason should be a short (under 15 words) explanation of the match."
    )
    user_prompt = (
        f"Hiring requirement: {query}\n\n"
        f"Candidates:\n{json.dumps(profiles, indent=2)}"
    )

    try:
        model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=800,
        )
        data = json.loads(response.choices[0].message.content)
        ranking = data.get("ranking", [])

        by_id = {c.id: c for c in candidates}
        ordered = []
        seen_ids = set()
        for entry in ranking:
            cand = by_id.get(entry.get("id"))
            if cand and cand.id not in seen_ids:
                ordered.append((cand, str(entry.get("reason", "")).strip()))
                seen_ids.add(cand.id)

        # Safety net: if the AI skipped anyone, append them at the end
        # unranked rather than silently dropping them from results.
        for c in candidates:
            if c.id not in seen_ids:
                ordered.append((c, ""))

        return ordered
    except Exception:
        logger.exception("AI candidate ranking failed")
        return [(c, "") for c in candidates]
