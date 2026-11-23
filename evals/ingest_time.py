#!/usr/bin/env python3
"""Time a cold ingest of each corpus through corunis-mcp over stdio, against SPEC.md's speed bar.

    python evals/ingest_time.py [--work DIR] [group ...]

The bar is 500 mixed documents in under 5 minutes, a rate of 500 / 300 documents per second.
Each line prints the measured rate as a multiple of that rate (over 1 beats the bar).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from corunis_evals import brains  # noqa: E402
from corunis_evals.mcp import Client  # noqa: E402

KEEPER_CALLER = "local:corunis-evals"
BAR_RATE = 500 / 300


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("groups", nargs="*", choices=brains.GROUPS, help="default: all four")
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()
    work = args.work or Path(tempfile.mkdtemp(prefix="corunis-ingest-"))
    total_docs = total_seconds = 0.0
    for group in args.groups or brains.GROUPS:
        root = brains.build(group, work / group / "home" / group, KEEPER_CALLER)
        with Client(work / group / "home", root, KEEPER_CALLER) as client:
            started = time.perf_counter()
            report = client.tool("ingest", {})
            seconds = time.perf_counter() - started
        docs = report["added"]
        total_docs += docs
        total_seconds += seconds
        print(f"{group:9} {docs:3d} documents  {seconds:7.3f} s  failed {len(report['failed'])}  "
              f"skipped {len(report['skipped'])}  {docs / seconds / BAR_RATE:8.1f}x the bar rate")
    print(f"{'all':9} {int(total_docs):3d} documents  {total_seconds:7.3f} s  "
          f"{total_docs / total_seconds / BAR_RATE:8.1f}x the bar rate (500 in 5 min would take "
          f"{500 * total_seconds / total_docs:.1f} s at this rate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
