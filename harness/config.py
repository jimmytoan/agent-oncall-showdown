"""Shared settings: every contestant gets the same prompt, the same single tool and the same limits."""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_TEMPLATE = ROOT / "app"
SCENARIOS = ROOT / "scenarios"
RUNTIME = ROOT / ".runtime"
APP_DIR = RUNTIME / "shopfront"  # fresh copy of app/ per run; agents may edit it
RESULTS = ROOT / "results"

OPS_CONTAINER = "showdown-ops"
OPS_IMAGE = "showdown-ops:latest"
COMPOSE_NETWORK = "shopfront_default"


@dataclass(frozen=True)
class Limits:
    max_model_calls: int = 40      # hard cap on LLM round trips
    max_usd: float = 3.0           # per run (enforced natively by the Claude Agent SDK, checked post-hoc for others)
    wall_clock_s: int = 15 * 60    # the incident clock
    cmd_timeout_s: int = 60        # per shell command
    max_output_chars: int = 6000   # shell output fed back to the model (head + tail kept)


SH_TOOL_DESCRIPTION = (
    "Run one bash command on the on-call jump box and return its combined stdout/stderr and exit code. "
    "The working directory is the shopfront Docker Compose project (compose.yaml, .env, api/, worker/, db/, "
    "cache/, proxy/). Available: docker, docker compose, curl, jq, psql, redis-cli, standard coreutils. "
    "The jump box is attached to the compose network, so services are reachable by name (e.g. http://proxy/api/health). "
    "Commands time out after 60 seconds; do not start interactive or never-ending commands (use --tail, -n, timeouts)."
)

SYSTEM_PROMPT = """You are the on-call SRE for "shopfront", a small e-commerce system that runs with Docker Compose:
proxy (Caddy edge) -> api (FastAPI) -> db (Postgres) and cache (Redis: carts + the order queue) <- worker (processes orders, writes receipt files).

You have been paged. You have exactly one tool, `sh`, which runs bash commands on the jump box inside the compose project directory.

Priorities, in order:
1. Never lose customer data: orders, carts, receipts and queued messages must survive. Prefer reversible changes.
2. Restore service for customers as quickly as you safely can.
3. Find the real root cause and back it with evidence (logs, config, metrics, queries).
4. Make the fix durable: it should survive a container restart or redeploy (fix config files, not only live state).

Work like a senior engineer during an incident: form hypotheses, check them, change one thing at a time, and confirm recovery
before you declare it resolved. Customers are affected while you work.

When you are done, reply with your incident report as a single JSON object in a ```json code block:
{"resolved": true|false, "root_cause": "...", "evidence": ["..."], "actions_taken": ["..."], "follow_ups": ["..."]}
"""


def user_prompt(alert: str) -> str:
    return f"You have been paged:\n\n{alert.strip()}\n\nInvestigate and resolve the incident."
