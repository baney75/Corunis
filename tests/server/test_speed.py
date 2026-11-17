"""The SPEC's speed bar: search p95 under 200 ms over 50,000 passages.

Opt in with CORUNIS_SPEED=1. It runs benchmarks/search_latency.py, which itself refuses to run
unless the 1-minute load is under 8 and records the load it ran at.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(os.environ.get("CORUNIS_SPEED") != "1", reason="set CORUNIS_SPEED=1 to run the 50,000 passage speed check")
def test_search_p95_under_200_ms(tmp_path):
    if not hasattr(os, "getloadavg") or os.getloadavg()[0] >= 8:
        pytest.skip("the 1-minute load is not under 8")
    done = subprocess.run([sys.executable, str(REPO / "benchmarks" / "search_latency.py"), "--out", str(tmp_path)],
                          capture_output=True, text=True, timeout=1800)
    if done.returncode == 3:
        pytest.skip(done.stderr.strip())
    result = json.loads(next(tmp_path.glob("*.json")).read_text())
    print(json.dumps({k: result[k] for k in ("load_before", "load_after", "passages", "runs")}))
    assert result["passages"] >= 50_000
    for run in result["runs"]:
        assert run["p95_ms"] < 200, run
