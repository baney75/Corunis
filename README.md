# Corunis

Formerly UniCerebrum. The name is Latin *cor* + *unus*, "of one heart" (Acts 4:32).

Corunis is an open-source organizational brain for universities. It is completely local, private, safe and secure: the AI runs on the university's own hardware, and its data never leaves campus.

## What it will do (planned)

Nothing below is built yet. See [SUPPORTED.md](SUPPORTED.md) for what works today.


Corunis will help a university with day-to-day work:

- **Grants:** finding opportunities, organizing requirements and deadlines, and drafting materials from the institution's own records.
- **Students:** helping staff manage student records, advising and communication.
- **Institutional knowledge:** answering questions from the university's own documents, policies and systems, so knowledge doesn't live only in a few people's heads.

## Principles

- **All local AI.** No student or institutional data goes to an outside AI provider.
- **Private and secure by design.** Access controls, auditing, and respect for student privacy law such as FERPA.
- **Easily expandable.** New skills and workflows can be added without rebuilding the system.
- **Easy to back up.** The whole brain can be backed up and restored.
- **Easy to integrate.** It connects to the systems a university already uses.

## Prior work

Corunis will learn from open work on organizational AI and cite it here as we use it. What sets it apart is that it is fully local.

## First version (planned)

The first version is sign-in with roles and a role-aware assistant that answers from the school's own documents with citations, and it works on a phone as an installable PWA (the same app), built while we find a pilot school. Then come an audit log, memory, Canvas and Moodle connectors, grants and student support workspaces, and backup. The pilot school picks what matters most after that. The first Dev release is planned for Feb 1, 2027.

The parts and licenses are in [docs/STACK.md](docs/STACK.md).

## Setup

Corunis runs on [Fonsviva](https://github.com/baney75/Fonsviva), the shared local compute layer. If Fonsviva is already installed, Corunis uses it and you pick models inside the app. If not, the app installs it for you and walks you through setup. Cloud providers are set up only in Fonsviva, for personal use only.

Agents setting this up for someone: start at [docs/agents.md](docs/agents.md) or [llms.txt](llms.txt). Site: https://baney75.github.io/Corunis/

## Status

Early planning. Contributions and ideas are welcome.

## License

MIT
