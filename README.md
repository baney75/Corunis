# UniCerebrum

UniCerebrum is an open-source organizational brain for universities. It is completely local, private, safe and secure: the AI runs on the university's own hardware, and its data never leaves campus.

## What it does

UniCerebrum helps a university with real, day-to-day work, in a realistic way:

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

Universities are already building organizational brains, and UniCerebrum learns from them and from open work on organizational AI. What sets it apart is that it is fully local.

## Setup

UniCerebrum runs on [Fonsviva](https://github.com/baney75/Fonsviva), the shared local compute layer. If Fonsviva is already installed, UniCerebrum uses it and you pick models inside the app. If not, the app installs it for you and walks you through setup. Cloud providers are set up only in Fonsviva, for personal use only.

Agents setting this up for someone: start at [docs/agents.md](docs/agents.md) or [llms.txt](llms.txt). Site: https://baney75.github.io/UniCerebrum/

## Status

Early planning. The name may change. Contributions and ideas are welcome.

## License

MIT
