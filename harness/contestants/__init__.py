"""Contestants: one adapter per agent SDK. Each gets the same system prompt, the same `sh` tool and the same limits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

import litellm
from litellm.integrations.custom_logger import CustomLogger

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


# ---- "tuned" LiteLLM variants ---------------------------------------------------------------------------------
# The Claude Agent SDK caches the conversation and runs at effort=medium out of the box. Through LiteLLM neither
# happens unless you ask. The "+tuned" contestants ask: cache breakpoints on the system prompt and the latest message
# (LiteLLM's documented injection points) and reasoning_effort=medium.
TUNED_LITELLM_KWARGS = {
    "reasoning_effort": "medium",
    "cache_control_injection_points": [
        {"location": "message", "role": "system"},
        {"location": "message", "index": -1},
    ],
}


class LiteLLMMeter(CustomLogger):
    """Sums what LiteLLM itself bills per call (response_cost), including cache writes and reads."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = self.input = self.cache_read = self.cache_write = self.output = 0
        self.cost = 0.0

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):  # noqa: ANN001
        u = getattr(response_obj, "usage", None)
        self.calls += 1
        self.cost += kwargs.get("response_cost") or 0.0
        if u is None:
            return
        cread = getattr(u, "cache_read_input_tokens", 0) or 0
        cwrite = getattr(u, "cache_creation_input_tokens", 0) or 0
        self.cache_read += cread
        self.cache_write += cwrite
        self.input += (u.prompt_tokens or 0) - cread - cwrite
        self.output += u.completion_tokens or 0

    def __enter__(self) -> "LiteLLMMeter":
        litellm.callbacks.append(self)
        return self

    def __exit__(self, *exc: object) -> None:
        litellm.callbacks.remove(self)

    def apply(self, r: AgentResult) -> None:
        r.model_calls, r.input_tokens, r.output_tokens = self.calls, self.input, self.output
        r.cache_read_tokens, r.cache_write_tokens = self.cache_read, self.cache_write
        r.cost_usd, r.cost_source = round(self.cost, 4), "litellm-response-cost"


def registry() -> dict[str, Runner]:
    from functools import partial

    from . import adk, claude_sdk, openai_agents

    return {
        "claude-sdk": claude_sdk.run,
        "openai-agents": openai_agents.run,
        "adk": adk.run,
        "openai-agents+tuned": partial(openai_agents.run, tuned=True),
        "adk+tuned": partial(adk.run, tuned=True),
    }
