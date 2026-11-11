# Open-source stack (planned)

Nothing here is built yet. This is the list of existing projects Corunis v0 plans to assemble, in build order, with each license and how Corunis uses it. Corunis's own code stays MIT.

| Build | Part | License | How Corunis uses it |
|---|---|---|---|
| 1 | [t3code](https://github.com/pingdotgg/t3code) | MIT | Forked for the app, threads and provider layer, the same way as Gantrel. |
| 1, 9 | [Keycloak](https://github.com/keycloak/keycloak) | Apache-2.0 | Sign-in (OpenID Connect), roles, the admin console, and later the link to the school's own sign-in (SAML or OIDC). |
| 1 | [OpenFGA](https://github.com/openfga/openfga) | Apache-2.0 | Who can read which documents. |
| 2 | [Docling](https://github.com/docling-project/docling) | MIT | Reading PDF, Word and web documents. |
| 2, 5 | [LanceDB](https://github.com/lancedb/lancedb) | Apache-2.0 | Embedded local vector store and memories. |
| 2 | [pgvector](https://github.com/pgvector/pgvector) | PostgreSQL License | Option for larger installs on Postgres. |
| 3 | [Local AI registry](https://github.com/sybil-solutions/local-ai-registry) | MIT | Picking local models that pass on the school's hardware. |
| 4 | [OpenTelemetry](https://github.com/open-telemetry/opentelemetry-collector) | Apache-2.0 | Debug traces, kept apart from the hash-chained audit log. |
| 5 | [Hermes Agent](https://github.com/NousResearch/hermes-agent) | MIT | Reference for how an agent saves and recalls memories. |
| 6 | Canvas LMS REST API | Canvas is AGPL-3.0 | API calls only. |
| 6 | Moodle Web Services API | Moodle is GPL-3.0 | API calls only. |
| 6 | 1EdTech OneRoster 1.2 | Open standard | Rosters from student information systems. Blackboard's REST API comes after v0. |
| 7 | Grants.gov search API | Public API | Finding open grant opportunities. |
| 9 | [restic](https://github.com/restic/restic) | BSD-2-Clause | Encrypted backup and restore. |
| 10 | electron-builder, Docker Compose | MIT, Apache-2.0 | Packaging for a pilot install. |

## Rules

- All AI runs locally through [Fonsviva](https://github.com/baney75/Fonsviva). Corunis's Fonsviva key can never reach a cloud provider.
- Corunis links only to MIT, Apache, BSD, PostgreSQL and LGPL code. GPL and AGPL systems such as Canvas and Moodle are reached only through their APIs.
- Student records follow FERPA: only assigned staff see a student, and every view is logged.

## After v0

These come after the first Dev release (planned for Feb 1, 2027): Blackboard and other SIS connectors, the school's own sign-in, agent-made themes, and whatever the pilot school asks for next.
