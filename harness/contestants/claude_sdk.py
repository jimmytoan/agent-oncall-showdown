"""Claude Agent SDK contestant (round 1: built-in tools OFF, only the shared `sh` tool)."""

from __future__ import annotations

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from ..config import SH_TOOL_DESCRIPTION, SYSTEM_PROMPT, Limits, RUNTIME, user_prompt
from ..ops import OpsBox
from . import AgentResult


async def run(alert: str, ops: OpsBox, model: str, limits: Limits) -> AgentResult:
    @tool("sh", SH_TOOL_DESCRIPTION, {"command": str})
    async def sh(args: dict) -> dict:
        return {"content": [{"type": "text", "text": await ops.run(args["command"])}]}

    server = create_sdk_mcp_server(name="ops", version="1.0.0", tools=[sh])
    scratch = RUNTIME / "claude-cwd"  # empty dir: the SDK's own file tools are off anyway, nothing to read here
    scratch.mkdir(parents=True, exist_ok=True)

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=SYSTEM_PROMPT,     # replaces the Claude Code preset: same prompt as the other SDKs
        tools=[],                        # no built-in Bash/Read/Edit: level playing field
        mcp_servers={"ops": server},
        allowed_tools=["mcp__ops__sh"],
        permission_mode="dontAsk",
        setting_sources=[],              # don't load ~/.claude or project settings, skills, CLAUDE.md
        max_turns=limits.max_model_calls,
        max_budget_usd=limits.max_usd,
        effort="medium",                 # the Messages API default for Opus 5.5, so all harnesses match
        cwd=str(scratch),
    )

    result = AgentResult(cost_source="sdk")
    texts: list[str] = []
    async for msg in query(prompt=user_prompt(alert), options=options):
        if isinstance(msg, AssistantMessage):
            texts.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage):
            usage = msg.usage or {}
            result.model_calls = msg.num_turns
            result.input_tokens = usage.get("input_tokens", 0)
            result.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            result.cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
            result.output_tokens = usage.get("output_tokens", 0)
            result.cost_usd = msg.total_cost_usd
            result.final_text = msg.result or (texts[-1] if texts else "")
            result.extra = {"subtype": msg.subtype, "duration_api_ms": msg.duration_api_ms, "model_usage": msg.model_usage}
            if msg.subtype == "error_max_turns":
                result.stopped_by = "max_calls"
            elif msg.subtype == "error_max_budget_usd":
                result.stopped_by = "budget"
            elif msg.is_error:
                result.stopped_by, result.error = "error", str(msg.errors or msg.subtype)
    return result
