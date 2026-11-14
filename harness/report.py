"""Aggregate results/runs.jsonl into the tables used in the write-up.

  uv run python -m harness.report                      # all tags
  uv run python -m harness.report --tag same-model-r1  # one round
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from statistics import mean, median

from .config import RESULTS


def load(tag: str | None) -> list[dict]:
    rows = [json.loads(l) for l in (RESULTS / "runs.jsonl").read_text().splitlines() if l.strip()]
    return [r for r in rows if tag is None or r["tag"] == tag]


def pct(xs: list[bool]) -> str:
    return f"{sum(xs)}/{len(xs)}"


def summary_table(rows: list[dict]) -> str:
    by = defaultdict(list)
    for r in rows:
        by[(r["contestant"], r["model"])].append(r)
    out = [
        "| SDK | Model | Runs | Restored | Data safe | Durable | RCA correct | Median time | Median calls | Total cost | Cost/incident | Dangerous cmds |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for (sdk, model), rs in sorted(by.items()):
        costs = [r["agent"]["cost_usd"] or 0 for r in rs]
        out.append(
            f"| {sdk} | {model} | {len(rs)} "
            f"| {pct([r['verify']['restored'] for r in rs])} "
            f"| {pct([r['verify']['data_safe'] for r in rs])} "
            f"| {pct([r['verify']['durable'] for r in rs])} "
            f"| {pct([r['judge']['rca'] == 'correct' for r in rs])} "
            f"| {median(r['elapsed_s'] for r in rs):.0f}s "
            f"| {median(r['agent']['model_calls'] for r in rs):.0f} "
            f"| ${sum(costs):.2f} | ${mean(costs):.2f} "
            f"| {sum(len(r['ops']['dangerous']) for r in rs)} |"
        )
    return "\n".join(out)


def matrix(rows: list[dict]) -> str:
    sdks = sorted({r["contestant"] for r in rows})
    by = {(r["scenario"], r["contestant"]): r for r in rows}  # last run wins
    out = ["| Incident | " + " | ".join(sdks) + " |", "|---|" + "---|" * len(sdks)]
    for sc in sorted({r["scenario"] for r in rows}):
        cells = []
        for s in sdks:
            r = by.get((sc, s))
            if not r:
                cells.append("–")
                continue
            v = r["verify"]
            mark = "✅" if v["restored"] and v["data_safe"] else ("⚠️ data lost" if v["restored"] else "❌")
            cells.append(f"{mark} {r['judge']['rca']} · {r['elapsed_s']:.0f}s · ${(r['agent']['cost_usd'] or 0):.2f}")
        out.append(f"| {sc} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def incidents(rows: list[dict]) -> str:
    out = []
    for r in rows:
        v, a = r["verify"], r["agent"]
        bad = not (v["restored"] and v["data_safe"] and v["durable"]) or r["judge"]["rca"] != "correct" or r["ops"]["dangerous"] or r["ops"]["blocked"] or a["stopped_by"] != "done"
        if bad:
            out.append(f"- {r['run_id']} ({r['scenario']}, {r['contestant']}): stopped_by={a['stopped_by']} "
                       f"verify={[c for c in v['checks'] if c.startswith('FAIL')]} rca={r['judge']['rca']} "
                       f"dangerous={r['ops']['dangerous']} blocked={r['ops']['blocked']}")
    return "\n".join(out) or "- none"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag")
    args = ap.parse_args()
    rows = load(args.tag)
    print(f"## Summary ({len(rows)} runs)\n\n{summary_table(rows)}\n\n## Per incident\n\n{matrix(rows)}\n\n## Runs worth reading\n\n{incidents(rows)}")


if __name__ == "__main__":
    main()
