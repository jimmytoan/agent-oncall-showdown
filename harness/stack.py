"""Lifecycle of the shopfront stack: fresh copy, up, inject an incident, verify."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from .config import APP_DIR, APP_TEMPLATE, SCENARIOS

WARMUP_S = 30


def _dc(*args: str, check: bool = True, quiet: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "--project-directory", str(APP_DIR), "-f", str(APP_DIR / "compose.yaml"), *args],
        check=check,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.DEVNULL if quiet else None,
    )


def reset() -> None:
    """Tear down any previous run (including volumes) and start a pristine stack with warm traffic."""
    for attempt in range(3):  # compose up occasionally fails right after a teardown; a clean retry fixes it
        if (APP_DIR / "compose.yaml").exists():
            _dc("down", "-v", "--remove-orphans", "--timeout", "5", check=False)
        shutil.rmtree(APP_DIR, ignore_errors=True)
        shutil.copytree(APP_TEMPLATE, APP_DIR, ignore=shutil.ignore_patterns("ops"))
        if _dc("up", "-d", "--build", "--wait", "--wait-timeout", "240", quiet=False, check=attempt == 2).returncode == 0:
            break
        time.sleep(10)
    time.sleep(WARMUP_S)


def down() -> None:
    if (APP_DIR / "compose.yaml").exists():
        _dc("down", "-v", "--remove-orphans", "--timeout", "5", check=False)


def _script(scenario: str, name: str, state: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "APP": str(APP_DIR), "STATE": str(state)}
    bash = shutil.which("bash") or "/bin/bash"
    return subprocess.run([bash, str(SCENARIOS / scenario / name)], env=env, capture_output=True, text=True, timeout=600)


def inject(scenario: str, state: Path) -> None:
    proc = _script(scenario, "inject.sh", state)
    if proc.returncode != 0:
        raise RuntimeError(f"inject failed for {scenario}:\n{proc.stdout}\n{proc.stderr}")
    time.sleep(15)  # let symptoms show up in logs and metrics before the page goes out


def verify(scenario: str, state: Path) -> dict:
    proc = _script(scenario, "verify.sh", state)
    m = re.search(r"^RESULT (\{.*\})$", proc.stdout, re.MULTILINE)
    result = json.loads(m.group(1)) if m else {"restored": False, "data_safe": False, "durable": False}
    result["checks"] = [l for l in proc.stdout.splitlines() if l.startswith(("PASS", "FAIL"))]
    if proc.stderr.strip():
        result["stderr"] = proc.stderr.strip()[-2000:]
    return result
