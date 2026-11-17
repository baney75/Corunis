# Testing: honest claims only

Corunis must never claim it can do something it can't. Every claim in the README, the docs or the app has a test behind it, and the results are public in this repo.

## Answer accuracy standard

Every task has golden cases built from realistic university data (synthetic, never real student records): questions with known answers from institutional documents, grant requirements and deadlines, and student-management workflows.

- Answers must cite the source document. An answer without a source is a failure.
- Access-control tests prove a user never sees data they aren't allowed to.
- When the answer isn't in the university's data, the system says so instead of guessing.

## Rules

- **No unknown error.** Any output that differs from the expected result fails the test, field by field. "Close enough" is a failure.
- **Known limits are declared.** Anything Corunis doesn't support yet is listed in `SUPPORTED.md`. The app detects those situations and tells the user plainly instead of guessing.
- **Every model is tested separately.** A model is only offered for a task after it passes that task's suite (see `BENCHMARKS.md`).
- **Real behavior, not mocks.** Tests run the real skills against real local models and check real outputs.
- **Regressions block release.** A drop in any pass rate blocks promotion from Dev to Stable.

## Layout

- `tests/golden/`: cases with known-correct expected outputs and their sources.
- `tests/skills/<skill-name>/`: tests for each skill.
- `benchmarks/results/`: published pass rates per model and hardware.

## Brain server and plugin checks

These run on every pull request, on Linux, macOS and Windows (`.github/workflows/plugin.yml`):

- `uv run pytest -q` (or `python -m pytest -q` with `pytest` and `pypdf` installed): the server tests in `tests/server/` over a synthetic parish brain with 3 spaces and 3 roles. They cover every format, re-ingest, calibration of the `answerable` flag, `verify`, the MCP protocol, a check that no server module imports a network library and no socket opens while serving, and the leak tests: every role and space pair through `search`, `open` and `verify`, restricted notes, moved and linked files, ingest outside the brain, `status` during a restricted ingest, refused non-keeper sessions, "ask as" a higher role, and a Fonsviva reply that ran in the cloud.
- `tests/plugin/check.sh`: the manifest, no em or en dashes, an MCP smoke test of `bin/corunis-mcp` over stdio, and `local-studio plugin validate` when a Local Studio binary with the plugin command is present.
- `CORUNIS_SPEED=1 uv run pytest -q tests/server/test_speed.py` or `uv run python benchmarks/search_latency.py`: the SPEC's speed bar, search p95 under 200 ms over 50,000 passages. It runs only while the 1-minute load is under 8 and writes the load with its result to `benchmarks/results/`.
