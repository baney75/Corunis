# Corunis evals

The corpora, tuning questions and harness behind the evals and tier bars in
[docs/SPEC.md](../docs/SPEC.md). Everything is invented: the groups, people, addresses, phone
numbers and amounts. No real person's records are used.

## Layout

| Path | What it holds |
| --- | --- |
| `corpora/<group>/` | One made-up group each: `family`, `parish`, `business`, `class`. 60 to 80 documents under `spaces/<space>/`, `brain.toml.in` (the brain template; `{{KEEPER_CALLER}}` is filled at build) and `corpus.toml` (the date for undated files and the restricted strings per space). |
| `questions/<group>/tuning.jsonl` | 48 tuning questions per group, 8 of each kind: single, multi, unanswerable, restricted, stale, conflicting. Field list in `corunis_evals/questions.py`. |
| `corunis_evals/` | Building a brain from a corpus, the stdio MCP client, question loading, leak detection and the judges. Standard library only. |
| `judges/correctness.md` | The blind correctness prompt every judge uses. |
| `run.py` | Runs a model on a question set through the real `corunis-mcp`. |
| `score.py` | Scores run records against the S, M and L bars. |

The leak suite and the corpus checks live in `tests/evals/`, so CI runs them on every push.

There is no held-out question set in this repo. These are tuning questions: tune skill text and
retrieval on them, and score claims only on a held-out set kept elsewhere.

The held-out set (`heldout-v1`, 24 questions per group, 4 of each kind, over the same corpora)
lives outside the repo, on chapel1 under `~/.local/state/flagship/studies/corunis/heldout-v1/`.
A separate writer who does no tuning wrote it, and nobody who tunes the tier cards or retrieval
reads it. It is run only for the final win check, one group at a time, with
`evals/run.py --group <group> --questions <path to group.jsonl>`. [`heldout-v1.sha256`](heldout-v1.sha256)
holds each file's SHA-256, so a changed question shows: run `sha256sum -c` on that file from the
held-out folder before the check.

The corpora have few disagreements and superseded facts, so held-out conflicting questions in
family, parish and business, and some stale and conflicting ones in class, use document pairs the
tuning set also uses. Each asks something the tuning set does not. Report held-out scores on those
two kinds as such, and don't tune on facts from those pairs.

### Corpus conventions

- DOCX and PDF files are written as text (`name.docx.src`, `name.pdf.src`) and converted when the
  brain is built, so every document can be reviewed in a diff. A `.docx.src` paragraph whose
  every line has ` | ` becomes a table; a `.pdf.src` line holding only a form feed starts a page.
- A built file's modified time is the date in its name (`2026-10-09` or `2026-10`), else the
  corpus default date, so passage dates match what the documents say.
- Each corpus plants single facts, facts that need two documents, a superseded fact (old and new
  document), two dated documents that disagree, and facts in spaces at least one role cannot read.
- `corpus.toml [restricted]` lists the strings that must never reach a role that cannot read their
  space. `corunis_evals/leaks.py` adds each restricted document's file name, stem and title, and
  drops any of those that also appear outside the space. `tests/evals` checks that every listed
  string sits only in its own space and in no question.

## Run

From the repo root, with `uv sync` done (pytest and pypdf come from the dev group):

```sh
# the corpus checks, the leak suite and an offline harness test (no model)
uv run python -m pytest -q tests/evals

# build and ingest one corpus, ask every tuning question through corunis-mcp
uv run python evals/run.py --group parish --card M \
  --base-url http://127.0.0.1:11434/v1 --model hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M \
  --out runs/parish-M.jsonl --resume

# score with an OpenAI compatible judge (any local model)
uv run python evals/score.py runs/parish-M.jsonl --tier M --judge openai \
  --judge-base-url http://127.0.0.1:11434/v1 --judge-model hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF:Q4_K_M

# or with the claude judge (haiku, no tools, the CLI's own sign-in; ANTHROPIC_API_KEY is removed)
uv run python evals/score.py runs/parish-M.jsonl --tier M --judge claude --judge-limit 10
```

`run.py` gives each question a fresh `corunis-mcp` process and a fresh chat. The request is the
`SKILL.md` and the chosen tier card in a `<skill>` block followed by the question, the way Local
Studio sends `/brain`. The model gets only `search`, `open`, `verify` and `status`; for a
restricted question the harness sets `as_role` to the question's role on every call, as a member
session's identity would. `--extra-body` merges JSON into each chat request (for example a
server's context length option), and `--api-key-env` names an environment variable to send as a
bearer key for an endpoint that needs one. Both scripts stop at once on a quota, limit or billing
reply.

`score.py` reports correctness (blind judge with the gold answer and gold passages; an abstention
on an answerable question counts as wrong without a judge call), citation precision and recall at
passage level, abstention on unanswerable and restricted questions, false abstention on answerable
ones, and leaks. An abstention is the abstention sentence alone, with no citation. Verdicts are
cached in `<run>.judged.jsonl`, keyed by the whole grading input, so a changed answer is judged
again. If any answer has no verdict, correctness shows n/a and the exit code is 1. `--tier` marks each measure pass or
FAIL against that tier's bar. The claude judge waits while the host's 1 minute load is 6 or more.

## Leak suite

`tests/evals/test_eval_leaks.py` runs on all four corpora, with no model:

- `open` and `verify` with every restricted passage id, for every role kept out of its space,
  answer exactly as for an id that does not exist; searches built from those passages' words
  return nothing from the space and no restricted string
- every restricted tuning question, asked as its role through `search`, `open`, `verify` and
  `status`
- a note remembered in a restricted space
- a file just moved into a restricted space, with and without the index catching up first
- a symlink and a hard link from `everyone` to a restricted file
- `ingest` of a path outside the brain, and a link that leads outside it
- `status` and `search` from a second server while a restricted space is being ingested
- a Remote session (paired device, no caller, another host user, `_meta` claiming the keeper,
  `_meta` remote, `CORUNIS_SESSION=remote`) over the real stdio server
- `as_role` set to a higher role, a member name or the keeper
- an unsupported claim attached to a real quote, and an answer with an uncited sentence

Fonsviva set up with a cloud provider is covered by `tests/server/test_fonsviva.py`, not here.
