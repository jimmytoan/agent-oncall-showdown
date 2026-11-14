"""Contestants: one adapter per agent SDK. Each gets the same system prompt, the same `sh` tool and the same limits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

import litellm

from ..config import Limits
from ..ops import OpsBox


@dataclass
class AgentResult:
    final_text: str = ""
    model_calls: int = 0
    input_tokens: int = 0          # uncached input
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    cost_source: str = ""          # "sdk" (reported by the SDK) or "litellm-price-map" (tokens x list price)
    stopped_by: str = "done"       # done | max_calls | budget | wall_clock | error
    error: str | None = None
    extra: dict = field(default_factory=dict)


Runner = Callable[[str, OpsBox, str, Limits], Awaitable[AgentResult]]


def price_from_tokens(model: str, r: AgentResult) -> float | None:
    """List-price cost from token counts, using LiteLLM's bundled price map (same table for every SDK)."""
    bare = model.split("/")[-1]
    info = next((litellm.model_cost[k] for k in (model, bare, f"gemini/{bare}", f"anthropic/{bare}") if k in litellm.model_cost), None)
    if not info:
        return None
    inp = info.get("input_cost_per_token") or 0
    out = info.get("output_cost_per_token") or 0
    cread = info.get("cache_read_input_token_cost") or inp
    cwrite = info.get("cache_creation_input_token_cost") or inp
    return round(r.input_tokens * inp + r.cache_read_tokens * cread + r.cache_write_tokens * cwrite + r.output_tokens * out, 4)


def registry() -> dict[str, Runner]:
    from . import adk, claude_sdk, openai_agents

    return {"claude-sdk": claude_sdk.run, "openai-agents": openai_agents.run, "adk": adk.run}
