"""Self-test every scenario without any LLM: inject -> verify (must be broken) -> reference fix -> verify (must pass)."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import stack
from .config import SCENARIOS
from .run import scenario_ids

ok = True
for sid in scenario_ids(sys.argv[1] if len(sys.argv) > 1 else None):
    state = Path(tempfile.mkdtemp(prefix=f"selftest-{sid}-"))
    stack.reset()
    stack.inject(sid, state)
    broken = stack.verify(sid, state)
    fix = subprocess.run(["bash", str(SCENARIOS / sid / "fix.sh")], env={**stack.os.environ, "APP": str(stack.APP_DIR), "STATE": str(state)},
                         capture_output=True, text=True)
    fixed = stack.verify(sid, state)
    good = (not broken["restored"]) and fixed["restored"] and fixed["data_safe"] and fixed["durable"]
    ok &= good
    print(f"{'OK  ' if good else 'BAD '} {sid}: broken.restored={broken['restored']} -> fixed={json.dumps({k: fixed[k] for k in ('restored','data_safe','durable')})}")
    if not good:
        print("   broken:", broken["checks"], "\n   fixed:", fixed["checks"], "\n   fix stderr:", fix.stderr[-500:], fixed.get("stderr", "")[-800:])
stack.down()
sys.exit(0 if ok else 1)
