---
name: corunis
description: Answer only from the group's own documents in a Corunis brain, with an exact quote for every claim, and add files, notes and roles. Use for /brain or any question about the group's documents.
---

# corunis

The person's request is the text after `</skill>` at the end of this message.

Corunis keeps a group's documents (a family, a parish, a small business, a class) in a brain
folder on this computer and answers only from them. Its tools come from the `corunis` server
(Local Studio lists it as `plugin-corunis`): `search`, `open`, `verify`, `remember`, `ingest`,
`status`, `brain_new`, `brain_open`, `role_add`, `role_grant`, `role_revoke`, `member_set`.

## Rules that never bend

- Answer only from passages that `search` or `open` returned in this conversation. Never answer
  from your own knowledge, not even a fact you are sure of.
- Every sentence of an answer cites a passage: `[p0123456789abcde "exact words from it"]`.
- Call `verify` with the whole answer, then show the person only the `answer` that `verify`
  returned. Never add a sentence after it.
- If `search` says `answerable: false`, or `verify` keeps nothing, say exactly:
  The documents I can see don't answer this.
  Then say what was searched, from `searched`.
- Never say or hint whether a document you were not shown exists. A restricted document and a
  missing one get the same reply.

## Pick your tier and follow that card

- Tier S, about 3B parameters and under: tiers/S.md
- Tier M, about 4B to 30B: tiers/M.md
- Tier L, the largest local models: tiers/L.md

## /brain

- `/brain <question>` or a plain question: ask, by your tier card.
- `/brain add`: the keeper puts files in a space folder under `spaces/` (shown by `status`),
  then call `ingest`. Report what it added, skipped and failed.
- `/brain remember <note>`: call `remember` with the note. Say which space it went to.
- `/brain roles`: `status` shows roles; change them with `role_add`, `role_grant`,
  `role_revoke` and `member_set`. "Ask as" a role (`as_role` on `search`, `open`, `verify`,
  `status`) shows what that role would see; it can only lower what you see.
- No brain yet: ask the person for the group's name, then call `brain_new`.

## What v0 does not do yet

- Corunis v0 answers only the keeper, in a session on the brain's own computer. Every tool
  refuses any other caller, and refuses everyone while Local Studio Remote is serving. Members
  wait for a signed caller identity from the core.
- Corunis does not yet block cloud sessions. Use it only with a local model: in a session on a
  cloud model, the question and the passages reach that provider.
