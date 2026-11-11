# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor and others) working in UniCerebrum.

## What this project is

A fully local, private and secure organizational brain for universities. It helps with grants, student management and institutional knowledge in a realistic way, and it is easy to extend, back up and integrate with existing campus systems.

## Ground rules

- **Local first.** Features must work with local models on the user's own hardware. Cloud or private compute providers (for example RunPod) are optional add-ons, never required.
- **Private and secure by default.** User data is encrypted at rest and in transit. Never log, print or send secrets or personal data.
- **Trusted models only.** Use safe, reputable open models. Document which models a feature was tested with.
- **Easy beats clever.** Every feature has to be usable by a non-technical person.
- **Design comes from DESIGN.md.** Follow it for all UI work. If it is empty or silent on something, ask the designer rather than inventing a style.
- **Prove it works.** Back every change with behavior tests or a recorded real run. Don't claim something works without evidence.
- **Small, reviewable changes.** One concern per pull request, with a clear description.
- **Student privacy.** Respect FERPA and institutional policy. Access control and audit logs are required for anything touching student data.
- **Backup and integration are features.** Every data store must be backed up and restorable, and integrations go through documented connectors.

## Skills

Skills live in `skills/maintainer/` (for building this project) and `skills/runtime/` (used by agents inside the app). All are original and tested; see `skills/README.md`. Load the skill that matches your task before starting, and improve it when you learn something.

## Testing and honesty

Never claim the software can do something without a passing test. Follow `TESTING.md`, keep `SUPPORTED.md` honest, and benchmark models per `BENCHMARKS.md`. Model-specific instructions live in `models/<model>/`.

## Releases

UniCerebrum ships on two channels, Stable and Dev (no nightly). See `RELEASES.md`. Never push directly to `stable`.

## Repository layout

- `AGENTS.md`: this file
- `CLAUDE.md`: Claude Code entry point, points here
- `DESIGN.md`: design system and UX rules, owned by the designer
- `RELEASES.md`: Stable and Dev channels
- `CONTRIBUTING.md`: how to contribute, including design work and coauthorship
- `TESTING.md`, `SUPPORTED.md`, `BENCHMARKS.md`: accuracy, honest scope and model benchmarks
- `skills/maintainer/`, `skills/runtime/`: original, tested skills
- `models/`: per-model instructions
- `tests/`, `benchmarks/results/`: tests and published results
- `design/`: design exports and notes
