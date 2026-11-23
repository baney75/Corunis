#!/usr/bin/env python3
"""Run a local model on a question set through the real corunis-mcp server, one record per question.

    python evals/run.py --group parish --base-url http://127.0.0.1:11434/v1 \\
        --model hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M --card M --out runs/parish-M.jsonl

The group's corpus is built into a brain (under --work, else a temporary folder) and ingested
once. Each question then gets a fresh corunis-mcp process over stdio, with LOCAL_STUDIO_CALLER set
to the brain's keeper, and a fresh chat: the SKILL.md and tier card in a <skill> block, then the
question, as Local Studio sends a /brain request. The model sees only the read tools (search,
open, verify, status). A restricted question is asked as its role: the harness puts that role in
as_role on every read call, the way a member session's identity would, so the model cannot widen
it. The chat endpoint is any OpenAI compatible /chat/completions with tools.

Every record holds the answer, the tool calls with what the server returned, the cited passage
ids, the gold passages resolved to ids and text, and timing, so score.py needs no brain.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from corunis_evals import REPO, brains, questions  # noqa: E402
from corunis_evals.mcp import Client  # noqa: E402

KEEPER_CALLER = "local:corunis-evals"
READ_TOOLS = ("search", "open", "verify", "status")
SKILL = REPO / "skills" / "plugin" / "corunis"
THINK = re.compile(r"<think>.*?</think>\s*", re.S)
PID = re.compile(r"\bp[0-9a-f]{15}\b")
STOP_WORDS = ("quota", "billing", "rate limit", "usage limit", "insufficient credit", "payment required")


class Stop(Exception):
    """A quota, limit or billing reply: every run stops and the person is told."""


def request_text(question: str, card: str) -> str:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8").strip()
    tier = (SKILL / "tiers" / f"{card}.md").read_text(encoding="utf-8").strip()
    return f"<skill>\n{skill}\n\n{tier}\n</skill>\n\n{question}"


def tool_specs(client: Client) -> list[dict]:
    specs = []
    for tool in client.tools():
        if tool["name"] not in READ_TOOLS:
            continue
        schema = json.loads(json.dumps(tool["inputSchema"]))
        schema.get("properties", {}).pop("as_role", None)  # the harness sets the role, not the model
        if "required" in schema:
            schema["required"] = [r for r in schema["required"] if r != "as_role"]
        specs.append({"type": "function", "function": {
            "name": tool["name"], "description": tool.get("description", ""), "parameters": schema}})
    return specs


def chat(args, messages: list[dict], tools: list[dict]) -> dict:
    body = {"model": args.model, "messages": messages, "tools": tools, "temperature": args.temperature, "stream": False}
    body.update(args.extra_body)
    headers = {"Content-Type": "application/json"}
    key = os.environ.get(args.api_key_env) if args.api_key_env else None
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(args.base_url.rstrip("/") + "/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            reply = json.loads(response.read())
    except urllib.error.HTTPError as error:
        text = error.read().decode(errors="replace")[:500]
        if error.code in (402, 429) or any(w in text.lower() for w in STOP_WORDS):
            raise Stop(f"HTTP {error.code}: {text}") from None
        raise
    if "error" in reply:
        text = json.dumps(reply["error"])[:500]
        if any(w in text.lower() for w in STOP_WORDS):
            raise Stop(text)
        raise RuntimeError(text)
    return reply


RUN_KEYS = ("group", "model", "base_url", "card", "temperature", "max_turns")  # a resumed run must match these

def run_tool(client: Client, name: str, raw: str, as_role: str | None) -> dict:
    try:
        arguments = json.loads(raw or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("arguments are not an object")
    except ValueError as error:
        return {"name": name, "arguments": raw, "error": True, "result": f"Bad arguments: {error}", "seconds": 0.0}
    arguments.pop("as_role", None)
    if as_role is not None and name in READ_TOOLS:
        arguments["as_role"] = as_role
    started = time.perf_counter()
    if name not in READ_TOOLS:
        result, error = f"Unknown tool: {name}", True
    else:
        reply = client.call(name, arguments)
        error = bool(reply.get("isError"))
        result = reply["content"][0]["text"] if error else reply["structuredContent"]
    return {"name": name, "arguments": arguments, "error": error, "result": result,
            "seconds": round(time.perf_counter() - started, 3)}


def ask(args, home: Path, brain: Path, q: dict, out: dict) -> dict:
    """Fill `out` as the question goes, so a failure part way still records what the server returned."""
    out.update({"answer": "", "tool_calls": [], "turns": 0, "model_seconds": 0.0, "tool_seconds": 0.0,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0}, "stopped": None, "error": None})
    started = time.perf_counter()
    with Client(home, brain, KEEPER_CALLER) as client:
        tools = tool_specs(client)
        messages: list[dict] = [{"role": "user", "content": request_text(q["question"], args.card)}]
        while True:
            if out["turns"] >= args.max_turns:
                out["stopped"] = "max_turns"
                break
            out["turns"] += 1
            t = time.perf_counter()
            reply = chat(args, messages, tools)
            out["model_seconds"] += time.perf_counter() - t
            for key in out["usage"]:
                out["usage"][key] += (reply.get("usage") or {}).get(key) or 0
            message = reply["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            content = THINK.sub("", message.get("content") or "").strip()
            if not calls:
                out["answer"] = content
                break
            messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
            for call in calls:
                record = run_tool(client, call["function"]["name"], call["function"].get("arguments", ""), q["as_role"])
                out["tool_calls"].append(record)
                out["tool_seconds"] += record["seconds"]
                text = record["result"] if isinstance(record["result"], str) else json.dumps(record["result"])
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": text})
    out["seconds"] = round(time.perf_counter() - started, 3)
    out["model_seconds"] = round(out["model_seconds"], 3)
    out["tool_seconds"] = round(out["tool_seconds"], 3)
    out["cited"] = list(dict.fromkeys(PID.findall(out["answer"])))
    return out


def resolved(resolver: questions.Resolver, locators: list[dict]) -> list[dict]:
    out = []
    for locator in locators:
        found = resolver.resolve(locator)
        if not found:
            raise SystemExit(f"locator resolves to no passage: {locator}")
        out.append({**locator, "ids": [p["id"] for p in found], "texts": [p["text"] for p in found]})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--group", required=True, choices=brains.GROUPS)
    parser.add_argument("--questions", type=Path, help="a question set (default: the group's tuning set)")
    parser.add_argument("--base-url", required=True, help="OpenAI compatible base, such as http://127.0.0.1:11434/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--card", required=True, choices=("S", "M", "L"))
    parser.add_argument("--out", required=True, type=Path, help="JSON lines, one record per question (appended)")
    parser.add_argument("--work", type=Path, help="where to build the brain (default: a temporary folder)")
    parser.add_argument("--ids", nargs="*", help="only these question ids")
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--resume", action="store_true", help="skip ids already in --out")
    parser.add_argument("--max-turns", type=int, default=8, help="model replies per question (default 8)")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=600, help="seconds per model reply")
    parser.add_argument("--extra-body", type=json.loads, default={}, help="JSON merged into each chat request")
    parser.add_argument("--api-key-env", help="name of an environment variable holding the endpoint's key, if it needs one")
    args = parser.parse_args()

    items = questions.load(args.questions or questions.tuning_path(args.group))
    if args.ids:
        items = [q for q in items if q["id"] in set(args.ids)]
    if args.limit:
        items = items[: args.limit]
    done = set()
    if args.resume and args.out.exists():
        kept = [json.loads(line) for line in args.out.read_text(encoding="utf-8").splitlines() if line.strip()]
        for old in kept:
            same = {k: old["run"].get(k) for k in RUN_KEYS} == {k: getattr(args, k) for k in RUN_KEYS}
            if not same:
                raise SystemExit(f"{args.out} holds a run with other settings ({ {k: old['run'].get(k) for k in RUN_KEYS} }); "
                                 "resume it with those settings or write a new --out")
        kept = [r for r in kept if not r.get("error")]  # a question that failed is asked again
        args.out.write_text("".join(json.dumps(r) + "\n" for r in kept), encoding="utf-8")
        done = {r["id"] for r in kept}
    items = [q for q in items if q["id"] not in done]

    work = args.work or Path(tempfile.mkdtemp(prefix=f"corunis-evals-{args.group}-"))
    home = work / "home"
    brain = brains.build(args.group, home / args.group, KEEPER_CALLER)
    t = time.perf_counter()
    with Client(home, brain, KEEPER_CALLER) as client:
        report = client.tool("ingest", {})
    ingest_seconds = round(time.perf_counter() - t, 3)
    if report["failed"] or report["skipped"]:
        raise SystemExit(f"ingest did not read every file: {report['failed'] + report['skipped']}")
    resolver = questions.Resolver(brain)
    run = {"group": args.group, "model": args.model, "base_url": args.base_url, "card": args.card,
           "started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "documents": report["added"],
           "ingest_seconds": ingest_seconds, "temperature": args.temperature, "max_turns": args.max_turns}
    print(f"{args.group}: {report['added']} documents ingested in {ingest_seconds} s; {len(items)} questions", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a", encoding="utf-8") as sink:
        for n, q in enumerate(items, 1):
            record = {"id": q["id"], "kind": q["kind"], "question": q["question"], "as_role": q["as_role"],
                      "gold_answer": q["gold_answer"], "gold": resolved(resolver, q["gold"]),
                      "acceptable": resolved(resolver, q["acceptable"]),
                      "restricted": resolved(resolver, q["restricted"]), "run": run}
            partial: dict = {}
            try:
                record.update(ask(args, home, brain, q, partial))
            except Stop as stop:
                print(f"STOPPED: the endpoint reported a quota, limit or billing problem: {stop}", file=sys.stderr)
                return 3
            except Exception as error:  # one broken question must not end the run
                record.update({**partial, "answer": "", "cited": [], "error": f"{type(error).__name__}: {error}"})
                record.setdefault("tool_calls", [])
            sink.write(json.dumps(record) + "\n")
            sink.flush()
            print(f"[{n}/{len(items)}] {q['id']} {record.get('seconds', 0)} s "
                  f"{len(record['tool_calls'])} calls{' ERROR ' + record['error'] if record.get('error') else ''}",
                  file=sys.stderr)
    resolver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
