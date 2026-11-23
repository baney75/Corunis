"""Blind correctness judges for answerable questions.

A judge sees the question, the gold answer, the gold passages and the answer with its citation
brackets removed. It never sees the model, the tier card or the run. Two judges:

    claude   `claude -p` on Donovan's own sign-in (ANTHROPIC_API_KEY removed), no tools, model haiku
             by default. Runs only on chapel1, one call at a time, and waits while the 1 minute
             load is 6 or more.
    openai   any OpenAI compatible /chat/completions endpoint, such as Ollama.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from corunis_evals import EVALS

PROMPT = EVALS / "judges" / "correctness.md"
BRACKET = re.compile(r"\s*\[[^\[\]]*\]")
STOP_WORDS = ("quota", "billing", "usage limit", "rate limit", "credit balance", "payment required", "upgrade")
MAX_LOAD = 6.0

RULES = {
    "single": "Correct if it states the fact in the gold answer. Extra true detail is fine.",
    "multi": "Correct only if it states every part of the gold answer. Extra true detail is fine.",
    "stale": ("Correct if it gives the current value from the newest document. Naming the older value is fine "
              "only when the answer says it was replaced; giving the older value as current is incorrect."),
    "conflicting": ("Correct only if it gives both values and says the documents disagree, naming each source "
                    "(with its date where the gold answer has one). Picking one value without the other is incorrect."),
}


class Stop(Exception):
    """A quota, limit or billing reply: judging stops and the person is told."""


def prompt_for(record: dict) -> str:
    passages = "\n\n".join(f"({g['file']})\n{text}" for g in record["gold"] for text in g["texts"])
    return PROMPT.read_text(encoding="utf-8").format(
        rule=RULES[record["kind"]], question=record["question"], gold_answer=record["gold_answer"],
        passages=passages, answer=BRACKET.sub("", record["answer"]).strip() or "(empty)",
    )


def verdict(text: str) -> dict:
    for line in reversed(text.strip().splitlines()):
        line = line.strip().strip("`")
        if line.startswith("{"):
            try:
                found = json.loads(line)
            except ValueError:
                continue
            if isinstance(found.get("correct"), bool):
                return {"correct": found["correct"], "reason": str(found.get("reason", ""))}
    match = re.search(r'"correct"\s*:\s*(true|false)', text)
    if match:
        return {"correct": match[1] == "true", "reason": "parsed from a malformed reply"}
    raise ValueError(f"no verdict in judge reply: {text[:300]!r}")


class ClaudeJudge:
    name = "claude"

    def __init__(self, model: str = "haiku") -> None:
        if not shutil.which("claude"):
            raise SystemExit("the claude judge needs the claude CLI on this host (chapel1)")
        self.model = model

    def __call__(self, record: dict) -> dict:
        while hasattr(os, "getloadavg") and os.getloadavg()[0] >= MAX_LOAD:
            time.sleep(30)
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        result = subprocess.run(
            ["claude", "-p", "--model", self.model, "--tools", "", "--strict-mcp-config",
             "--no-session-persistence", "--output-format", "text",
             "--system-prompt", "You are a strict, fair grader. You reply with one line of JSON."],
            input=prompt_for(record), capture_output=True, text=True, env=env, timeout=300,
        )
        text = result.stdout + result.stderr
        if any(w in text.lower() for w in STOP_WORDS) and not result.stdout.strip().startswith("{"):
            raise Stop(text.strip()[:300])
        if result.returncode != 0:
            raise RuntimeError(f"claude exited {result.returncode}: {text.strip()[:300]}")
        return verdict(result.stdout)


class OpenAIJudge:
    name = "openai"

    def __init__(self, base_url: str, model: str, api_key_env: str | None = None, timeout: float = 600) -> None:
        self.base_url, self.model, self.api_key_env, self.timeout = base_url, model, api_key_env, timeout

    def __call__(self, record: dict) -> dict:
        body = {"model": self.model, "temperature": 0, "stream": False, "messages": [
            {"role": "system", "content": "You are a strict, fair grader. You reply with one line of JSON."},
            {"role": "user", "content": prompt_for(record)}]}
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.api_key_env) if self.api_key_env else None
        if key:
            headers["Authorization"] = f"Bearer {key}"
        request = urllib.request.Request(self.base_url.rstrip("/") + "/chat/completions",
                                         data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                reply = json.loads(response.read())
        except urllib.error.HTTPError as error:
            text = error.read().decode(errors="replace")[:300]
            if error.code in (402, 429) or any(w in text.lower() for w in STOP_WORDS):
                raise Stop(f"HTTP {error.code}: {text}") from None
            raise
        content = reply["choices"][0]["message"].get("content") or ""
        return verdict(re.sub(r"<think>.*?</think>", "", content, flags=re.S))
