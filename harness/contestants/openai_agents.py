"""OpenAI Agents SDK contestant. Claude models go through LiteLLM; GPT models use the native OpenAI provider."""

from __future__ import annotations

from agents import Agent, ModelSettings, Runner, function_tool, set_tracing_disabled
from agents.exceptions import MaxTurnsExceeded
from agents.extensions.models.litellm_model import LitellmModel
from openai.types.shared import Reasoning

from ..config import SH_TOOL_DESCRIPTION, SYSTEM_PROMPT, Limits, user_prompt
from ..ops import OpsBox
from . import AgentResult, price_from_tokens

set_tracing_disabled(True)  # keep runs local; OpenAI tracing would need an OpenAI key and adds no signal here


async def run(alert: str, ops: OpsBox, model: str, limits: Limits) -> AgentResult:
    @function_tool(name_override="sh", description_override=SH_TOOL_DESCRIPTION)
    async def sh(command: str) -> str:
        return await ops.run(command)

    if model.startswith("claude"):
        llm = LitellmModel(model=f"anthropic/{model}")
        settings = ModelSettings(include_usage=True)  # Opus 5.5 API default effort (medium)
    else:
        llm = model
        settings = ModelSettings(reasoning=Reasoning(effort="medium"))

    agent = Agent(name="oncall-sre", instructions=SYSTEM_PROMPT, tools=[sh], model=llm, model_settings=settings)
    result = AgentResult(cost_source="litellm-price-map")
    run_result = None
    try:
        run_result = await Runner.run(agent, user_prompt(alert), max_turns=limits.max_model_calls)
    except MaxTurnsExceeded as exc:
        result.stopped_by = "max_calls"
        run_result = getattr(exc, "run_data", None)

    if run_result is not None:
        usage = run_result.context_wrapper.usage
        cached = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0
        result.model_calls = usage.requests
        result.input_tokens = usage.input_tokens - cached
        result.cache_read_tokens = cached
        result.output_tokens = usage.output_tokens
        result.final_text = str(getattr(run_result, "final_output", "") or "")
    result.cost_usd = price_from_tokens(model, result)
    return result
