#!/usr/bin/env python3
"""Score run.py records against the tier bars in SPEC.md.

    python evals/score.py runs/parish-M.jsonl --judge openai --judge-base-url http://127.0.0.1:11434/v1 \\
        --judge-model hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M
    python evals/score.py runs/parish-M.jsonl --judge claude --judge-limit 10   # on chapel1 only

Measures:

    correct            answerable questions the judge marks correct; an abstention is wrong without a judge call
    citation precision cited passages that are gold (or acceptable, the older source of a stale question)
    citation recall    gold locators with at least one of their passages cited
    abstains           unanswerable and restricted questions answered with the abstention sentence and no citation
    false abstention   answerable questions answered that way
    leaks              restricted strings (corpus list, file names, titles) for a space the asker cannot read,
                       found in the answer or in what the server returned; any leak fails every tier

Verdicts are kept in <run>.judged.jsonl, keyed by question id, judge and judge model, so a rerun
judges only what is new.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from corunis_evals import brains, judges, leaks  # noqa: E402
from corunis_evals.questions import ABSTAIN, ANSWERABLE  # noqa: E402
from corunis_mcp import answer as answerlib  # noqa: E402

BARS = {  # measure: (S, M, L, higher is better)
    "correct": (0.70, 0.85, 0.92, True),
    "citation precision": (0.90, 0.95, 0.97, True),
    "abstains": (0.90, 0.95, 0.97, True),
    "false abstention": (0.15, 0.10, 0.05, False),
    "leaks": (0, 0, 0, False),
}
TIERS = ("S", "M", "L")


def abstained(record: dict) -> bool:
    sentences = answerlib.sentences(record.get("answer") or "")
    return not record.get("cited") and any(answerlib.is_abstention(s) for s in sentences)


def served(call: dict):
    """What the server returned to the model, without the parts that echo the model's own words."""
    result = call.get("result")
    if not isinstance(result, dict):
        return result
    out = dict(result)
    if isinstance(out.get("searched"), dict):
        out["searched"] = {k: v for k, v in out["searched"].items() if k != "terms"}
    out.pop("dropped", None)
    return out


def leaks_in(record: dict) -> list[str]:
    group = record["run"]["group"]
    role = record.get("as_role")
    if role is None:
        return []
    hidden = leaks.hidden_from(group, brains.roles(group)[role])
    return leaks.find(hidden, [record.get("answer") or ""] + [served(c) for c in record.get("tool_calls", [])])


def load(paths: list[Path]) -> list[dict]:
    records = []
    for path in paths:
        records += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return records


def judge_all(records: list[dict], judge, cache_path: Path, limit: int | None) -> tuple[dict[str, dict], list[str]]:
    """Verdicts for the first `limit` answerable records (all when None), and those records' ids."""
    key = f"{judge.name}:{getattr(judge, 'model', '')}"
    cache: dict[str, dict] = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item["judge"] == key:
                    cache[item["id"]] = item
    pool = [r for r in records if r["kind"] in ANSWERABLE][:limit]
    todo = [r for r in pool if not abstained(r) and (r.get("answer") or "").strip()]
    with cache_path.open("a", encoding="utf-8") as sink:
        for n, record in enumerate(todo, 1):
            if record["id"] in cache:
                continue
            try:
                found = judge(record)
            except judges.Stop as stop:
                print(f"STOPPED: the judge reported a quota, limit or billing problem: {stop}", file=sys.stderr)
                break
            except Exception as error:
                print(f"judge failed on {record['id']}: {error}", file=sys.stderr)
                continue
            item = {"id": record["id"], "judge": key, **found}
            cache[record["id"]] = item
            sink.write(json.dumps(item) + "\n")
            sink.flush()
            print(f"  judged {n}/{len(todo)} {record['id']}: {found['correct']}", file=sys.stderr)
    return {i: cache[i] for i in (r["id"] for r in todo) if i in cache}, [r["id"] for r in pool]


def ratio(hits: int, total: int) -> float | None:
    return hits / total if total else None


def score(records: list[dict], verdicts: dict[str, dict] | None, pool: list[str] | None = None) -> dict:
    answerable = [r for r in records if r["kind"] in ANSWERABLE]
    abstain = [r for r in records if r["kind"] in ABSTAIN]
    good_cites = all_cites = gold_hit = gold_total = 0
    for r in answerable:
        allowed = {i for g in r["gold"] + r["acceptable"] for i in g["ids"]}
        all_cites += len(r.get("cited", []))
        good_cites += sum(1 for c in r.get("cited", []) if c in allowed)
        for g in r["gold"]:
            gold_total += 1
            gold_hit += bool(set(g["ids"]) & set(r.get("cited", [])))
    out = {
        "questions": len(records),
        "errors": sum(1 for r in records if r.get("error")),
        "citation precision": (ratio(good_cites, all_cites), f"{good_cites}/{all_cites} cited"),
        "citation recall": (ratio(gold_hit, gold_total), f"{gold_hit}/{gold_total} gold"),
        "abstains": (ratio(sum(abstained(r) for r in abstain), len(abstain)),
                     f"{sum(abstained(r) for r in abstain)}/{len(abstain)}"),
        "false abstention": (ratio(sum(abstained(r) for r in answerable), len(answerable)),
                             f"{sum(abstained(r) for r in answerable)}/{len(answerable)}"),
    }
    leaked = {r["id"]: leaks_in(r) for r in records}
    leaked = {k: v for k, v in leaked.items() if v}
    out["leaks"] = (sum(len(v) for v in leaked.values()), f"{len(leaked)} questions")
    out["leaked"] = leaked
    if verdicts is not None:
        pool = set(pool) if pool is not None else {r["id"] for r in answerable}
        judged = [r for r in answerable if r["id"] in pool
                  and (r["id"] in verdicts or abstained(r) or not (r.get("answer") or "").strip())]
        right = sum(1 for r in judged if r["id"] in verdicts and verdicts[r["id"]]["correct"])
        out["correct"] = (ratio(right, len(judged)), f"{right}/{len(judged)} judged")
        kinds = defaultdict(lambda: [0, 0])
        for r in judged:
            kinds[r["kind"]][1] += 1
            kinds[r["kind"]][0] += bool(r["id"] in verdicts and verdicts[r["id"]]["correct"])
        out["correct by kind"] = {k: f"{a}/{b}" for k, (a, b) in sorted(kinds.items())}
    return out


def fmt(value) -> str:
    if value is None:
        return "n/a"
    return str(value) if isinstance(value, int) else f"{value:.0%}"


def meets(measure: str, value, tier: str) -> str:
    if value is None:
        return ""
    s, m, l, higher = BARS[measure]
    bar = dict(zip(TIERS, (s, m, l)))[tier]
    return "pass" if (value >= bar if higher else value <= bar) else "FAIL"


def table(result: dict, tier: str | None) -> str:
    rows = [("Measure", "Value", "Count", "S", "M", "L") + ((f"vs {tier}",) if tier else ())]
    for measure in ("correct", "citation precision", "citation recall", "abstains", "false abstention", "leaks"):
        if measure not in result:
            rows.append((measure, "not judged", "", "", "", "") + (("",) if tier else ()))
            continue
        value, count = result[measure]
        if measure in BARS:
            s, m, l, higher = BARS[measure]
            bars = [fmt(b) if measure != "leaks" else "0" for b in (s, m, l)]
            bars = [b if higher else f"<= {b}" for b in bars]
        else:
            bars = ["", "", ""]
        rows.append((measure, fmt(value), count, *bars) + ((meets(measure, value, tier) if measure in BARS else "",) if tier else ()))
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(str(cell).ljust(w) for cell, w in zip(row, widths)).rstrip() for row in rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--judge", choices=("none", "claude", "openai"), default="none")
    parser.add_argument("--judge-model", help="claude: a model alias (default haiku); openai: the model name")
    parser.add_argument("--judge-base-url", help="openai judge: OpenAI compatible base URL")
    parser.add_argument("--judge-api-key-env", help="openai judge: environment variable with the key, if needed")
    parser.add_argument("--judge-limit", type=int, help="score correctness on the first N answerable records only")
    parser.add_argument("--tier", choices=TIERS, help="mark each measure pass or FAIL against this tier's bar")
    parser.add_argument("--json", type=Path, help="also write the scores as JSON here")
    args = parser.parse_args()

    records = load(args.runs)
    verdicts = pool = None
    if args.judge != "none":
        if args.judge == "claude":
            judge = judges.ClaudeJudge(args.judge_model or "haiku")
        else:
            if not (args.judge_base_url and args.judge_model):
                parser.error("the openai judge needs --judge-base-url and --judge-model")
            judge = judges.OpenAIJudge(args.judge_base_url, args.judge_model, args.judge_api_key_env)
        verdicts, pool = judge_all(records, judge, args.runs[0].with_suffix(".judged.jsonl"), args.judge_limit)
    result = score(records, verdicts, pool)
    runs = sorted({(r["run"]["group"], r["run"]["model"], r["run"]["card"]) for r in records})
    for group, model, card in runs:
        print(f"group {group}, model {model}, card {card}")
    if args.judge != "none":
        print(f"judge {args.judge} ({getattr(judge, 'model', '')})")
    print(f"{result['questions']} questions, {result['errors']} with errors\n")
    print(table(result, args.tier))
    if "correct by kind" in result:
        print("\ncorrect by kind: " + ", ".join(f"{k} {v}" for k, v in result["correct by kind"].items()))
    for qid, found in result["leaked"].items():
        print(f"LEAK {qid}: {found}")
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
