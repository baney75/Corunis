"""search latency over 50,000 passages, the SPEC's speed bar: p95 under 200 ms on chapel1.

Writes a synthetic brain of real files (so search's query-time path checks run as they do in
use), ingests it, then times search through Session.call, the path the MCP server takes, as
the keeper and asking as a role. It runs only while the 1-minute load average is under 8
(--max-load) and records the load before and after. Results go to benchmarks/results/.

    uv run python benchmarks/search_latency.py
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from corunis_mcp import identity  # noqa: E402
from corunis_mcp.tools import Session  # noqa: E402

BRAIN_TOML = """name = "Speed Test"
keeper = "keeper"

[roles.member]
spaces = ["everyone"]

[roles.council]
spaces = ["council", "everyone"]

[roles.staff]
spaces = ["everyone", "staff"]

[members.keeper]
name = "Keeper"
roles = []
"""
SPACES = ("everyone", "council", "staff")
SYLLABLES = "ba be bi bo bu da de di do du ka ke ki ko ku la le li lo lu ma me mi mo mu na ne ni no nu ra re ri ro ru sa se si so su ta te ti to tu va ve vi vo vu".split()


def vocabulary(rng: random.Random, size: int) -> list[str]:
    words: set[str] = set()
    while len(words) < size:
        words.add("".join(rng.choice(SYLLABLES) for _ in range(rng.randint(2, 4))))
    return sorted(words)


def paragraph(rng: random.Random, words: list[str], weights: list[float], length: int) -> str:
    chosen = rng.choices(words, weights=weights, k=length)
    sentences, i = [], 0
    while i < len(chosen):
        n = rng.randint(8, 18)
        piece = chosen[i:i + n]
        sentences.append(piece[0].capitalize() + " " + " ".join(piece[1:]) + ".")
        i += n
    return " ".join(sentences)


def build(root: Path, passages: int, per_file: int, seed: int) -> tuple[int, list[str]]:
    rng = random.Random(seed)
    words = vocabulary(rng, 20_000)
    weights = [1 / (rank + 1) for rank in range(len(words))]  # Zipf, like real text
    root.mkdir(parents=True)
    (root / "brain.toml").write_text(BRAIN_TOML, encoding="utf-8")
    samples: list[str] = []
    files = -(-passages // per_file)
    for n in range(files):
        space = SPACES[n % len(SPACES)]
        folder = root / "spaces" / space / f"batch-{n // 200:03d}"
        folder.mkdir(parents=True, exist_ok=True)
        paragraphs = [paragraph(rng, words, weights, rng.randint(170, 260)) for _ in range(per_file)]
        (folder / f"doc-{n:05d}.txt").write_text("\n\n".join(paragraphs), encoding="utf-8")
        if n % 7 == 0:
            samples.append(rng.choice(paragraphs))
    return files, samples


def questions(samples: list[str], count: int, seed: int) -> list[str]:
    rng = random.Random(seed + 1)
    out = []
    for _ in range(count):
        text = rng.choice(samples).rstrip(".").split()
        start = rng.randrange(0, max(1, len(text) - 8))
        out.append("What about " + " ".join(text[start:start + rng.randint(3, 7)]).replace(".", "") + "?")
    return out


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(p / 100 * len(ordered)) - 1))]


def time_searches(session: Session, asked: list[str], as_role: str | None) -> dict:
    timings, answerable = [], 0
    for question in asked:
        args = {"question": question} | ({"as_role": as_role} if as_role else {})
        start = time.perf_counter()
        result = session.call("search", args)
        timings.append((time.perf_counter() - start) * 1000)
        answerable += bool(result["answerable"])
    return {
        "as": as_role or "keeper", "queries": len(timings), "answerable": answerable,
        "p50_ms": round(statistics.median(timings), 1), "p95_ms": round(percentile(timings, 95), 1),
        "max_ms": round(max(timings), 1), "mean_ms": round(statistics.fmean(timings), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--passages", type=int, default=50_000)
    parser.add_argument("--per-file", type=int, default=20)
    parser.add_argument("--queries", type=int, default=300)
    parser.add_argument("--max-load", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=ROOT / "benchmarks" / "results")
    args = parser.parse_args()

    load_before = os.getloadavg()
    if load_before[0] >= args.max_load:
        print(f"skip: 1-minute load {load_before[0]:.2f} is not under {args.max_load}", file=sys.stderr)
        return 3
    identity.remote_serving = lambda: False  # a benchmark of search, not of the Remote check
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "Speed Test"
        files, samples = build(root, args.passages, args.per_file, args.seed)
        session = Session(home=Path(tmp), brain_path=root)
        start = time.perf_counter()
        report = session.call("ingest", {})
        ingest_s = time.perf_counter() - start
        count = session.index.db.execute("SELECT count(*) FROM passages").fetchone()[0]
        asked = questions(samples, args.queries, args.seed)
        for question in asked[:20]:  # warm the page cache, as a running server would be
            session.call("search", {"question": question})
        runs = [time_searches(session, asked, None), time_searches(session, asked, "member")]
        session.close()
    load_after = os.getloadavg()
    result = {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": platform.node(), "cpu": platform.processor() or platform.machine(), "cores": os.cpu_count(),
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "load_before": [round(x, 2) for x in load_before], "load_after": [round(x, 2) for x in load_after],
        "files": files, "passages": count, "ingest": {"seconds": round(ingest_s, 1), "added": report["added"]},
        "bar_p95_ms": 200, "runs": runs,
        "pass": all(run["p95_ms"] < 200 for run in runs),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"search-latency-{result['host']}-{result['date'][:10]}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"wrote {path}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
