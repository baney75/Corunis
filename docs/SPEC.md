# Corunis v0 spec: a Local Studio plugin

Status: prepared 2026-11-17 by the flagship plugins lead. Nothing here is built yet. The bars below were written before any eval ran, and they do not move to fit a result.

Corunis is an organizational brain for any group, not only universities (Donovan, 2026-11-16): a family, a parish, a small business, a class, a team. It ships first as a Local Studio plugin installed from its catalog. The one bot, one chat rule in the README still holds: the brain is a chat, not a suite of dashboards. The rival study that sets the outside bar lives in [docs/rivals/STUDY.md](rivals/STUDY.md). The university plan in [STACK.md](STACK.md) (Keycloak, OpenFGA, Canvas) becomes a later edition for large institutions; v0 does not depend on it.

## Who it is for

- **The keeper**: the one person who sets the brain up and adds documents. Not technical. A parish secretary, a parent, an office manager, a teacher.
- **Members** (after v0, when the core asks under Members and roles land): everyone else in the group. They ask questions in chat, from a desktop or the Local Studio iPhone app, and see only what their role may see.

## The promise

- Answers come only from the group's own documents and notes, each claim tied to the exact passage it came from, which opens with one click.
- When the documents do not answer the question, Corunis says so and names what it looked at. It never fills the gap from the model's own knowledge.
- A member never sees, and is never told about, anything their role may not see. Roles are enforced in the index before the model reads a word, never by asking the model to keep a secret.
- It works offline on the group's own hardware with a local model. No document, question or answer leaves the host.
- The mechanism is neutral: Corunis holds no positions of its own. A parish brain answers from the parish's documents; a business brain answers from the business's.

## One-minute setup

1. In Local Studio, open Plugins, pick Corunis, press Install. Local Studio asks once for the `mcp-server` capability ("Run its own tool server for your sessions") and the keeper approves.
2. Type `/brain new "St. Brigid Parish"`. Corunis makes the brain folder and opens it.
3. Drop a folder of documents into it. Corunis reads them in the background and posts progress in chat.
4. Ask a question. The first cited answer arrives.

The test for this: with Local Studio and Fonsviva already installed, a first-time keeper goes from the catalog to a cited answer over a 50-document folder in under 60 seconds on a machine with a GPU, and under 3 minutes CPU only, timed on the recorded run.

## How it works

### The brain is a folder

```
St. Brigid Parish/
  brain.toml          name, members, roles, which roles read which space
  spaces/
    everyone/         bulletins, schedules, the handbook
    council/          minutes, budgets
    staff/            payroll notes, personnel
      notes/          what members told Corunis to remember, each with author and date, kept in a space like any file
  .corunis/           the index (SQLite), rebuilt from the files at any time
```

Spaces are plain folders, so the keeper manages access by dragging files, and backup is copying the folder. A remembered note is saved in a space's `notes/` folder: the space the member picks, or by default the narrowest space that member can read, and it is filtered like any document. The index follows the folder: a file watcher updates a moved or changed file's space before the next search, and `search` also checks each result's current path against `brain.toml` at query time, so a file dragged into a restricted space is never served from a stale index entry. `brain.toml` maps roles to spaces in a few lines; Corunis writes it and changes it through chat (`/brain role add council`), so the keeper never has to edit it by hand.

### The plugin

- `plugin.toml`: id `corunis`, capability `mcp-server`, commands `/brain` (ask, add, remember, roles) pointing at the `corunis` skill, with tier cards `tiers/S.md`, `M.md`, `L.md` like smoothstone.
- `corunis-mcp`: the plugin's MCP server, Python 3.11+ with the standard library and `sqlite3` only for tier S. Every tool that takes a passage id or returns document content (`search`, `open`, `verify` and the side panel) applies the same role filter in SQL. A restricted id gets exactly the reply a nonexistent id gets, and ids are opaque hashes, not counters, so they cannot be guessed or enumerated. Tools: `search(question)` returns passages the caller may read, each with a stable id, document, page and character range; `open(passage_id)`; `verify(answer)` checks every quoted span against its cited passage and returns the claims that fail. A quote being present is not enough: every number, date and proper name in a claim must also appear in its quote, so "the 2026 budget is $40,000" cannot stand on a quote that says "the 2025 budget was $40,000"; `remember(note)`; `ingest(path)`; `status()`.
- Index: SQLite FTS5 (BM25) for every tier. Tiers M and L add a small local embedding model through Fonsviva for hybrid ranking. Ingest reads text, Markdown, HTML, PDF text, DOCX and email exports; scanned images wait for a later slice.

### Answering

1. The skill calls `search`. The MCP server filters by the caller's roles in SQL first, then ranks. Restricted passages never enter the model's context.
2. The model writes an answer where every claim carries one or more passage ids, each with a short quote. A claim that combines sources (a multi-source answer, two conflicting figures) cites each passage it uses. A derived value (a sum, "three days before") is marked derived and cites the passages its inputs come from.
3. The skill calls `verify`, which splits the whole answer into sentences itself, never trusting the model to mark which ones are claims. A sentence with no valid citation is dropped, except the fixed abstention sentence. A cited sentence stands only when every quote is in its passage and every number, date and proper name in it appears in the union of its quotes (for a derived value, its inputs do). If no claim survives, or `search` found nothing above its threshold, the answer is "The documents I can see don't answer this," followed by what it searched.
4. The chat shows the answer with citations; each opens the passage in a side panel.

### Members and roles

The brain lives on one host machine: the keeper's desktop, or a small always-on box. Later, members reach it through Local Studio Remote (the phone protocol, local-studio PR #4) from the iPhone app or another desktop, which keeps one place that enforces roles, something a synced folder on every member's machine cannot do.

v0 is the keeper alone. A Remote session runs on the host with the session's tools, including bash, so it could read the brain folder directly; no plugin can close that. Member access ships only when the core provides both of these, and until then every Corunis tool refuses to serve a member:

1. a caller identity the core signs (issue #8), including whether the session is local to the host or Remote;
2. member sessions that the core limits to Corunis's own tools, with no bash, file or web tools (added to issue #8).

Rules that hold from v0 on, enforced in `corunis-mcp`, not in the skill:

- Admin tools (`ingest`, `/brain add`, `/brain roles`, `role_add`, `role_grant`, `member_set`) answer only the keeper. `ingest` resolves every path to its real path and refuses anything outside the brain folder.
- "Ask as" can only lower privilege, never raise it.
- Every file is indexed under its real path; a file reachable through a symlink, alias or hard link in another space gets the most restrictive space of all its paths.
- `status()` and every progress message report only counts and names from spaces the caller may read, and progress goes only to the session that started the ingest.
- When members arrive, a note a member writes goes to a space only that member and the keeper can read, enters a shared space only after the keeper approves it, and is cited as "member note" with its author, never as a document.

## Capabilities it asks for

`mcp-server` only.

What the plugin API lacks, filed as issues on baney75/local-studio:

1. **Caller identity and member sessions**: the MCP server needs the member identity of the session that calls it, signed by the core, including whether it is local or Remote; and member sessions limited to the plugin's own tools.
2. **`local_only`**, the same ask as UntoCaesar: refuse to run the plugin in a session whose provider is not local, and turn off web tools in that session.
3. **Background work**: a way for the MCP server to post progress into chat while ingest runs.

## What runs locally

Everything. The MCP server talks over stdio and opens one other connection at most: a loopback client to Fonsviva's embedding endpoint for tiers M and L, in a single module that refuses any address that is not 127.0.0.1 or ::1. A CI check fails the build if any other module imports a networking library.

Loopback is not enough, because Fonsviva can route a job to a cloud provider. Every embedding call, at ingest and at question time, asks Fonsviva for local hardware only and requires its reply to say where the job ran; a reply that is missing that or names anything but the host stops the ingest or the answer (asked of the Fonsviva lead in an issue on baney75/Fonsviva).

A skill cannot stop a session on a cloud model: by the time it runs, the question has already reached that provider. So Corunis cannot keep its no-cloud promise until the core's `local_only` (issue #7) lands. Until then it ships on the dev channel only, never nightly or stable, and the catalog listing says it does not yet block cloud sessions.

## Evals

Every corpus is synthetic: four made-up groups (a family, a parish, a small business, a class), each with 60 to 200 documents of the kinds that group really keeps, written for the eval. No real person's records are used.

Each group has a question set:

| Kind | What a right answer is |
| --- | --- |
| Single source | The fact, cited to the passage that states it |
| Multi source | The combined answer, cited to every passage it needs |
| Unanswerable | "The documents don't answer this," with no invented fact |
| Restricted | For a member whose role cannot read the source: the same reply as unanswerable, with no hint the document exists |
| Stale versus current | The answer from the newest document, citing it |
| Conflicting | Both sources named, with their dates |

Scores: answer correctness (judged against the gold answer by a blind judge model with the gold passages), citation precision and recall at passage level, abstention accuracy on unanswerable and restricted questions, and leak count. A leak is any restricted fact, quote, title or file name in an answer, a citation or a tool result shown to that member.

### Bars per tier

| Measure | S (about 3B and under) | M (about 4B to 30B) | L (the largest local models, over 30B) |
| --- | --- | --- | --- |
| Correct on answerable questions | 70% | 85% | 92% |
| Citation precision | 90% | 95% | 97% |
| Abstains on unanswerable and restricted | 90% | 95% | 97% |
| Abstains when it should have answered | 15% or less | 10% or less | 5% or less |
| Leaks | 0 | 0 | 0 |

Leaks are 0 at every tier because roles are enforced before the model runs; the leak eval proves that structure holds. It includes cases that call `open` and `verify` directly with restricted ids, a remembered note made in a restricted space, a file just moved into a restricted space, a restricted file reached through a symlink, `ingest` of a path outside the brain, `status()` during a restricted ingest, a Remote session with no identity or one that claims to be the keeper, "ask as" set to a higher role, Fonsviva set up with a cloud provider, an unsupported claim attached to a real quote, and an answer with an uncited sentence.

Speed, measured on chapel1 (8 cores, no GPU): ingest of 500 mixed documents in under 5 minutes; `search` at the 95th percentile under 200 ms over 50,000 passages.

These results go in the catalog entry for each tier, with the model, hardware, date and log hash.

## The check that says it wins

On the same four corpora and question sets, with the same local model:

1. Against the strongest open-source local rivals the study names (RAGFlow, Onyx, Kotaemon, AnythingLLM and Open WebUI), Corunis wins if its correctness is at least 5 points higher than the best of them, its abstention accuracy is higher, and its leak count is 0 where theirs is measured with the same roles.
2. On the public EnterpriseRAG-Bench, where those rivals already have published scores (best self-hostable open-source app: RAGFlow at 50.2), Corunis on a GPU host with a tier M model scores above 50.2. That leaderboard is run by Onyx, a rival, so it is a floor, not the whole proof.
3. Against cloud rivals (NotebookLM, Notion AI, Glean, Mem, Capacities): the study compares price, offline use, citation depth, roles and published accuracy. A hands-on run with the synthetic corpus needs an account, so it waits for Donovan's yes and is otherwise marked not measured.

A blind council scores the final dev build in chat with one corpus: answer quality, honesty when the answer is missing, and how it feels to use.

## Channels

Stable, nightly and dev, on the family scheme in local-studio `docs/channels.md` (local-studio PR #5; Donovan, 2026-11-17). As a plugin that ships as a git tree, its channel is a git ref: stable is the newest `vX.Y.Z` tag on the `stable` branch, nightly is the rolling `nightly` tag, dev is `main`. A Local Studio install on a channel installs this plugin from the same channel. RELEASES.md follows that file.

## Not decided here

- The look of the chat cards and the passage panel: Gil designs them, using the shared Local Studio theme format.
- The university edition (sign-in with a school's identity provider, Canvas, FERPA auditing): after v0.
