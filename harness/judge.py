"""Root-cause grading: an LLM judge compares the agent's report with the scenario's ground truth.

The judge only sees the ground truth and the agent's final report (not which SDK produced it).
"""

from __future__ import annotations

import json
import re
from typing import Literal

import anthropic
from pydantic import BaseModel

JUDGE_MODEL = "claude-opus-5-5"


class Verdict(BaseModel):
    rca: Literal["correct", "partial", "wrong", "missing"]
    rationale: str


JUDGE_PROMPT = """You grade incident root-cause analyses written by on-call agents.

Ground truth root cause:
{root_cause}

Agent's final incident report:
<report>
{report}
</report>

Grade the agent's stated ROOT CAUSE only (not the quality of its fix):
- "correct": names the same specific cause (the actual changed setting/object and why it breaks the system).
- "partial": right area or symptom-level cause but misses the specific trigger, or mixes it with a wrong primary cause.
- "wrong": a different cause.
- "missing": no root cause stated.
Give a one-sentence rationale."""


def extract_report(final_text: str) -> dict | None:
    m = re.search(r"```json\s*(\{.*?\})\s*```", final_text, re.DOTALL) or re.search(r"(\{.*\"root_cause\".*\})", final_text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def grade(root_cause: str, final_text: str) -> dict:
    if not final_text.strip():
        return {"rca": "missing", "rationale": "agent produced no final report"}
    client = anthropic.Anthropic()
    resp = client.beta.messages.parse(
        model=JUDGE_MODEL,
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if the judge model declines, fall back server-side instead of failing the grade
        output_format=Verdict,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(root_cause=root_cause.strip(), report=final_text.strip()[-8000:])}],
    )
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        return {"rca": "ungraded", "rationale": f"judge stop_reason={resp.stop_reason}"}
    return resp.parsed_output.model_dump()
