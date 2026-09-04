from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import get_settings


def deterministic_narrative(analysis: dict[str, Any]) -> dict[str, str]:
    """Build a safe local narrative when the OpenAI call is unavailable or fails."""
    summary = analysis["summary"]
    executive = (
        f"HUMANBULB's Green Careers Launchpad served {summary['interns_served']} interns and "
        f"showed measurable growth across connected program data, including {summary['clean_tech_growth']} "
        f"growth in clean tech understanding and {summary['career_confidence_growth']} growth in career confidence."
    )
    narrative = (
        f"Based on uploaded surveys, trackers, and testimonial responses, the cohort demonstrated "
        f"{summary['average_skill_growth']} average skill growth, {summary['resume_linkedin_completion']} "
        f"career-material completion, and {summary['projects_completed']} completed project deliverables. "
        "These findings are drawn directly from connected records and paired before/after survey responses."
    )
    return {
        "executive_summary": executive,
        "grant_narrative": narrative,
        "participant_quote": analysis["selected_quote"],
    }


def generate_narrative(analysis: dict[str, Any]) -> dict[str, str]:
    """Generate grant-ready narrative text, falling back to deterministic copy if needed."""
    settings = get_settings()
    if not settings.openai_api_key:
        return deterministic_narrative(analysis)

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = {
        "metrics": analysis["summary"],
        "objectives": analysis["objectives"],
        "quotes": analysis["quotes"][:3],
        "instructions": [
            "Use only the supplied metrics, objectives, and quotes.",
            "Do not invent statistics, program activities, or outcomes.",
            "Return concise funder-ready prose.",
            "Return strict JSON with keys executive_summary, grant_narrative, participant_quote.",
        ],
    }

    try:
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You write nonprofit grant reporting summaries grounded only in provided evidence.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(prompt)}],
                },
            ],
        )
        text = response.output_text
        payload = json.loads(text)
        return {
            "executive_summary": payload["executive_summary"],
            "grant_narrative": payload["grant_narrative"],
            "participant_quote": payload.get("participant_quote") or analysis["selected_quote"],
        }
    except Exception:
        return deterministic_narrative(analysis)
