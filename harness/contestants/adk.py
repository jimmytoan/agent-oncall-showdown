"""Google ADK contestant. Claude models go through LiteLLM; Gemini models use ADK's native provider."""

from __future__ import annotations

import asyncio
import time

from google.adk.agents import LlmAgent, RunConfig
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..config import SH_TOOL_DESCRIPTION, SYSTEM_PROMPT, Limits, user_prompt
from ..ops import OpsBox
from . import TUNED_LITELLM_KWARGS, AgentResult, LiteLLMMeter, price_from_tokens


GEMINI_MIN_INTERVAL_S = 4.5  # free AI Studio keys allow 15 requests/minute; space the calls out instead of hitting 429s


async def run(alert: str, ops: OpsBox, model: str, limits: Limits, tuned: bool = False) -> AgentResult:
    async def sh(command: str) -> str:
        return await ops.run(command)

    sh.__doc__ = SH_TOOL_DESCRIPTION  # ADK builds the tool schema from the signature + docstring

    # Claude and GPT both go through LiteLLM; bare names (e.g. gemini-*) use ADK's native provider.
    if model.startswith("claude"):
        llm = LiteLlm(model=f"anthropic/{model}", **(TUNED_LITELLM_KWARGS if tuned else {}))
    elif model.startswith("gpt"):
        llm = LiteLlm(model=f"openai/{model}", reasoning_effort="medium")
    else:
        llm = model
    throttled = {"last": 0.0, "waited": 0.0}

    async def throttle(callback_context, llm_request):  # noqa: ANN001, ARG001
        wait = throttled["last"] + GEMINI_MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            throttled["waited"] += wait
            await asyncio.sleep(wait)
        throttled["last"] = time.monotonic()
        return None

    agent = LlmAgent(name="oncall_sre", model=llm, instruction=SYSTEM_PROMPT, tools=[sh],
                     before_model_callback=throttle if model.startswith("gemini") else None)

    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name="showdown", user_id="oncall")
    runner = Runner(agent=agent, app_name="showdown", session_service=sessions)

    result = AgentResult(cost_source="litellm-price-map")
    meter = LiteLLMMeter().__enter__()
    try:
        async for ev in runner.run_async(
            user_id="oncall",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=user_prompt(alert))]),
            run_config=RunConfig(max_llm_calls=limits.max_model_calls),
        ):
            um = ev.usage_metadata
            if um and not ev.partial:
                cached = um.cached_content_token_count or 0
                result.model_calls += 1
                result.input_tokens += (um.prompt_token_count or 0) - cached
                result.cache_read_tokens += cached
                result.output_tokens += (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)
            if ev.is_final_response() and ev.content and ev.content.parts:
                result.final_text = "".join(p.text or "" for p in ev.content.parts)
    except Exception as exc:  # ADK raises LlmCallsLimitExceededError when max_llm_calls is hit
        if "LlmCallsLimitExceeded" in type(exc).__name__ or "max_llm_calls" in str(exc):
            result.stopped_by = "max_calls"
        else:
            raise
    finally:
        meter.__exit__()
    result.cost_usd = price_from_tokens(model, result)
    if tuned:
        meter.apply(result)
    if throttled["waited"]:
        result.extra["throttle_wait_s"] = round(throttled["waited"], 1)  # subtract from elapsed for a fair time
    return result
