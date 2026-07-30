from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import get_settings


def deterministic_narrative(analysis: dict[str, Any]) -> dict[str, str]:
    summary = analysis["summary"]
    executive = (
        f"HUMANBULB's Green Careers Launchpad served {summary['interns_served']} interns and "
        f"showed measurable growth across connected program data, including {summary['clean_tech_growth']} "
        f"growth in clean tech knowledge and {summary['interview_confidence_growth']} growth in interview confidence."
    )
    narrative = (
        f"Based on uploaded surveys, trackers, and testimonial responses, the cohort demonstrated "
        f"{summary['average_skill_growth']} average skill growth, {summary['resume_linkedin_completion']} "
        f"career-material completion, and {summary['projects_completed']} completed project deliverables. "
        "These findings are drawn directly from connected records and matched survey responses."
    )
    return {
        "executive_summary": executive,
        "grant_narrative": narrative,
        "participant_quote": analysis["selected_quote"],
    }


def generate_narrative(analysis: dict[str, Any]) -> dict[str, str]:
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
        ],
    }
    response = client.responses.create(
        model=settings.openai_model,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You write nonprofit grant reporting summaries grounded only in provided evidence. Return strict JSON with keys executive_summary, grant_narrative, participant_quote.",
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": json.dumps(prompt)}],
            },
        ],
    )
    text = response.output_text
    try:
        payload = json.loads(text)
        return {
            "executive_summary": payload["executive_summary"],
            "grant_narrative": payload["grant_narrative"],
            "participant_quote": payload.get("participant_quote") or analysis["selected_quote"],
        }
    except Exception:
        return deterministic_narrative(analysis)
