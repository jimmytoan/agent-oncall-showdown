"""Run the showdown.

  uv run python -m harness.run --scenarios 06 --contestants claude-sdk --model claude-opus-5-5
  uv run python -m harness.run --contestants claude-sdk,openai-agents,adk --model claude-opus-5-5 --tag same-model
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from importlib.metadata import version

import yaml
from dotenv import load_dotenv

from . import judge, stack
from .config import RESULTS, ROOT, SCENARIOS, Limits
from .contestants import AgentResult, registry
from .ops import OpsBox

SDK_PACKAGES = {"claude-sdk": "claude-agent-sdk", "openai-agents": "openai-agents", "adk": "google-adk",
                "openai-agents+tuned": "openai-agents", "adk+tuned": "google-adk"}


def scenario_ids(selector: str | None) -> list[str]:
    all_ids = sorted(p.name for p in SCENARIOS.iterdir() if p.is_dir())
    if not selector:
        return all_ids
    wanted = selector.split(",")
    return [s for s in all_ids if any(s.startswith(w) for w in wanted)]


async def one_run(scenario: str, contestant: str, model: str, limits: Limits, tag: str) -> dict:
    meta = yaml.safe_load((SCENARIOS / scenario / "scenario.yaml").read_text())
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{scenario[:2]}-{contestant}-{uuid.uuid4().hex[:4]}"
    run_dir = RESULTS / "raw" / run_id
    run_dir.mkdir(parents=True)
    print(f"\n=== {run_id}: {meta['title']} | {contestant} | {model}", flush=True)

    stack.reset()
    stack.inject(scenario, run_dir / "state")
    OpsBox.start()
    ops = OpsBox(run_dir / "transcript.jsonl", limits)

    t0 = time.time()
    try:
        result = await asyncio.wait_for(registry()[contestant](meta["alert"], ops, model, limits), timeout=limits.wall_clock_s)
    except asyncio.TimeoutError:
        result = AgentResult(stopped_by="wall_clock")
    except Exception as exc:  # a crashed harness is a result too
        result = AgentResult(stopped_by="error", error=f"{type(exc).__name__}: {exc}")
    elapsed = round(time.time() - t0, 1)
    OpsBox.stop()

    print(f"    agent finished in {elapsed}s ({result.stopped_by}); verifying...", flush=True)
    verdict = stack.verify(scenario, run_dir / "state")
    graded = judge.grade(meta["ground_truth"]["root_cause"], result.final_text)

    record = {
        "run_id": run_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tag": tag,
        "scenario": scenario,
        "contestant": contestant,
        "sdk_version": version(SDK_PACKAGES[contestant]),
        "model": model,
        "elapsed_s": elapsed,
        "agent": {k: v for k, v in result.__dict__.items() if k != "final_text"},
        "ops": ops.summary(),
        "verify": verdict,
        "judge": graded,
        "report": judge.extract_report(result.final_text),
    }
    (run_dir / "final_text.md").write_text(result.final_text)
    (run_dir / "record.json").write_text(json.dumps(record, indent=2, default=str))
    with (RESULTS / "runs.jsonl").open("a") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    v = verdict
    print(
        f"    restored={v['restored']} data_safe={v['data_safe']} durable={v['durable']} rca={graded['rca']} "
        f"calls={result.model_calls} cost=${result.cost_usd} cmds={record['ops']['commands']} "
        f"dangerous={len(record['ops']['dangerous'])}",
        flush=True,
    )
    return record


async def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", help="comma-separated prefixes, e.g. 01,06 (default: all)")
    ap.add_argument("--contestants", default="claude-sdk", help="comma-separated: claude-sdk,openai-agents,adk")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--tag", default="pilot")
    ap.add_argument("--resume", action="store_true", help="skip runs this tag already has (errored runs don't count)")
    ap.add_argument("--keep-stack", action="store_true", help="leave the stack running after the last run")
    args = ap.parse_args()

    OpsBox.build_image()
    limits = Limits()
    done: dict[tuple, int] = {}
    runs_file = RESULTS / "runs.jsonl"
    if args.resume and runs_file.exists():
        for line in runs_file.read_text().splitlines():
            r = json.loads(line)
            if r["tag"] == args.tag and r["agent"]["stopped_by"] != "error":
                key = (r["scenario"], r["contestant"], r["model"])
                done[key] = done.get(key, 0) + 1
    try:
        for trial in range(args.repeat):
            for scenario in scenario_ids(args.scenarios):
                for contestant in args.contestants.split(","):
                    if done.get((scenario, contestant, args.model), 0) > trial:
                        continue
                    try:
                        await one_run(scenario, contestant, args.model, limits, args.tag)
                    except Exception as exc:  # setup failure (stack or inject): log it and keep the batch going
                        print(f"    SETUP FAILED, run skipped: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
    finally:
        OpsBox.stop()
        if not args.keep_stack:
            stack.down()


if __name__ == "__main__":
    asyncio.run(main())
