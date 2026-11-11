# Testing: honest claims only

UniCerebrum must never claim it can do something it can't. Every claim in the README, the docs or the app has a test behind it, and the results are public in this repo.

## Answer accuracy standard

Every task has golden cases built from realistic university data (synthetic, never real student records): questions with known answers from institutional documents, grant requirements and deadlines, and student-management workflows.

- Answers must cite the source document. An answer without a source is a failure.
- Access-control tests prove a user never sees data they aren't allowed to.
- When the answer isn't in the university's data, the system says so instead of guessing.

## Rules

- **No unknown error.** Any output that differs from the expected result fails the test, field by field. "Close enough" is a failure.
- **Known limits are declared.** Anything UniCerebrum doesn't support yet is listed in `SUPPORTED.md`. The app detects those situations and tells the user plainly instead of guessing.
- **Every model is tested separately.** A model is only offered for a task after it passes that task's suite (see `BENCHMARKS.md`).
- **Real behavior, not mocks.** Tests run the real skills against real local models and check real outputs.
- **Regressions block release.** A drop in any pass rate blocks promotion from Dev to Stable.

## Layout

- `tests/golden/`: cases with known-correct expected outputs and their sources.
- `tests/skills/<skill-name>/`: tests for each skill.
- `benchmarks/results/`: published pass rates per model and hardware.
