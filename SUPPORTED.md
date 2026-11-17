# What Corunis supports

This file is the honest list of what Corunis can and cannot do today. Only a situation with a passing test suite in `tests/golden/` may be listed as supported.

## Supported

Nothing yet. The tier S brain server and plugin are built and tested (see TESTING.md), but no golden answer suite with a local model has passed, so nothing is listed here.

## Not supported yet

- Answering anyone but the keeper. Every tool refuses any other caller, and refuses everyone while Local Studio Remote serves on the host, until the core signs caller identity (baney75/local-studio issue #8).
- Blocking cloud sessions. A session on a cloud model sends the question and passages to that provider; this waits for the core's `local_only` (issue #7). Corunis ships on the dev channel only until then.
- A file watcher. The index catches up with added, moved and changed files at the start of every tool call instead.
- Scanned PDFs and images (no OCR). PDF text needs the optional `pypdf` package; without it a PDF is reported as skipped.
- Tiers M and L hybrid ranking. The Fonsviva embedding client is a stub that nothing calls yet.
- Starting the server on Windows from the manifest. `bin/corunis-mcp` is a Python script with a shebang; Windows runs it only through `python bin/corunis-mcp`.
