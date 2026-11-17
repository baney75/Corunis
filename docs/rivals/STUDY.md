# Corunis rival study

Prepared 2026-11-17 by Claude (research delegate) for the Corunis lead. Status: prepared, not reviewed. Evidence notes, cloned code and downloaded papers live in `~/.local/state/flagship/studies/corunis/evidence/` (`notes.md`, `src/`, `papers/`). No accounts were created, nothing was installed or run, and no local model was run.

Claim labels: **settled** (primary source or code read directly), **in flux** (pricing or behavior that changes often, or only third-party sources agree), **judgment** (my inference from the evidence), **unknown** (not found). Bracketed numbers point to the Sources list at the end; every source carries its read date.

## 1. Verdict

No rival does all five things Corunis promises at once: run fully offline on local models, enforce per-document role permissions for a small group, cite the exact passage, abstain by default when the sources are silent, and install without an IT person. The cloud products (Notion AI, Glean, NotebookLM, Rovo, Slite) do permission-aware answers with page or passage citations, but none runs offline, Rovo will not even turn on for a gmail.com admin [20], and Glean's default mode mixes in the model's own knowledge [8]. The open-source local tools split the features between them: Onyx has per-document ACLs in its MIT core but puts group sync behind its enterprise license and needs a heavy server stack [29]; Kotaemon has the best citations (exact spans) and an "I don't know" prompt but only private-or-shared collections [32]; AnythingLLM is the easiest install but permissions stop at the workspace and it abstains only when retrieval returns nothing [25]; Open WebUI's default prompt tells the model to answer from its own knowledge when the context lacks the answer [28]. Measured bars are low and public: on Onyx's EnterpriseRAG-Bench the best self-hostable open-source app scores 50.2 (RAGFlow), AnythingLLM 35.6 and Open WebUI 24.9 [44]; NotebookLM hallucinated in 13% of newsroom answers against 40% for ChatGPT and Gemini [36]; the best legal RAG tool was accurate 65% of the time and still hallucinated about 17% [35]. Corunis can win on offline privacy, per-document roles for non-business groups, honest abstention and price. It will not win on raw answer quality against frontier cloud models on a CPU-only box, on connector breadth, or on native mobile apps. (judgment)

## 2. Comparison tables

Mem is listed for completeness: it stops taking payments and shuts down on January 15, 2027 [17].

### 2a. Price, offline, citations, permissions, abstention

| Rival | Price per seat or group | Offline and local models | Citation granularity | Roles and per-document permissions | Unanswerable handling |
|---|---|---|---|---|---|
| Notion AI | Business $20/seat/mo with AI; Plus $10 has AI trial only [1] (in flux) | Pages offline on desktop and mobile; AI runs via cloud LLM subprocessors, no local model [1] (settled) | Cites referenced pages [2] (settled) | Permission groups, private teamspaces, row-level database permissions on Business; Q&A uses only pages the asker can access [1][2] (settled) | Says it cannot find an answer instead of guessing [2] (settled) |
| Glean | Not published; third-party estimates $45 to $75/user/mo with ~100-seat minimums [10] (in flux) | No; cloud SaaS [8] (settled) | Inline markers; deep-linked passage citations since Q4 2025, falling back to document level when unsure [9] (settled) | Company knowledge limited to what the user can access in source apps [8] (settled) | Default "All Knowledge" mode may use LLM and web knowledge [8] (settled) |
| NotebookLM (Gemini Notebook) | Free; higher limits via Google AI Plus, Pro, Ultra; org via Workspace [3] (in flux) | No; cloud only [3] (settled) | Direct quotes from sources, hover shows quoted text [4] (settled) | Viewer or Editor per notebook; no per-source roles inside a notebook found [6] (settled for roles, unknown for per-source) | Will not answer if the answer is not in the sources [5] (settled) |
| Obsidian + Smart Connections | Obsidian free, Sync $4/user/mo annual [12]; Smart Connections Pro price unknown [15] | Yes; local embeddings [16] (settled) | Related notes and passages, not cited Q&A [15][16] (settled) | None inside a shared vault found (unknown) | unknown |
| Obsidian + Copilot for Obsidian | Free with own key or local model; Plus $14.99/mo [13] (in flux) | Yes with local model or BYOK [14] (settled) | unknown | unknown | unknown |
| Mem | No new paid plans; shutting down Jan 15, 2027 [17] (settled) | unknown | unknown | unknown | unknown |
| Capacities | Basic free; Pro $9.99/mo; Believer from $12.49/mo [18] (in flux) | Notes offline [18]; AI is cloud budget [18][19] (settled) | Web sources summary when it searches online; note citation depth unknown [19] | View-only sharing of notes [18] (settled) | unknown |
| Confluence + Rovo | Rovo credits included: 25, 70, 150 per user/mo on Standard, Premium, Enterprise; pay-as-you-go from Dec 3, 2026 [20]; seat price unknown after Oct 13, 2026 list change [21] | No; cloud [20] (settled) | unknown | unknown | unknown |
| Guru | Quote only; last public $25/seat/mo is third-party [22] (in flux) | No (judgment from SaaS model [22]) | unknown | unknown | unknown |
| Slab | Startup about $6.67/user/mo annual, free up to 10 users, per third parties [23] (in flux) | unknown | unknown | unknown | unknown |
| Slite | Basic $10, Pro $20/user/mo yearly; Ask AI in Basic [24] (in flux) | unknown | unknown | unknown | unknown |
| AnythingLLM | Desktop free; self-host Docker free; Cloud $50 or $99/mo per instance [26] (in flux) | Yes; air-gap capable with local LLM and vector DB [25] (settled) | Retrieved chunks per document with similarity score, not tied to claims [25] (settled) | Roles admin, manager, default; access per workspace; no per-document ACL found [25] (settled) | Refusal only when zero chunks retrieved in query mode; default prompt has no abstain rule [25] (settled) |
| Khoj | Self-host free; cloud and teams pricing unknown [27] | Yes, self-hosted with local models [27] (settled) | Inline markdown links to documents [27] (settled) | Per-user content; agents public, private or protected; no group ACL found [27] (settled) | No abstain rule in base prompt read [27] (settled) |
| Open WebUI | Free; enterprise license for rebranding over 50 users [28] (settled) | Yes; "built to run entirely offline" [28] (settled) | Inline [id] per source chunk [28] (settled) | Read or write grants per knowledge base and per file to user, group or anyone; checked at retrieval; admin sees all [28] (settled) | Default prompt says answer from own knowledge if context lacks it [28] (settled) |
| Onyx | Self-host free; Cloud Business $20/user/mo [30] (in flux) | Yes when self-hosted with local models (judgment from [29]) | Inline [1] per document [29] (settled) | Per-document ACL in MIT core (user email, public); groups and source permission sync are enterprise [29] (settled) | No abstain rule; last cycle answers "to the best of your ability" [29] (settled) |
| PrivateGPT | Free API layer; Zylon is the commercial product [31] (settled) | Yes; needs a separate OpenAI-compatible model server [31] (settled) | unknown | Optional basic auth only [31] (settled) | unknown |
| Kotaemon | Free [32] (settled) | Yes via Ollama or llama-cpp-python [32] (settled) | Exact span (start and end phrases copied from context) [32] (settled) | Private or shared file collections only [32] (settled) | "Just say that you don't know" prompt [32] (settled) |
| Reor | Free [33] (settled) | Yes via Ollama [33] (settled) | unknown | Single-user desktop [33] (settled) | unknown |
| RAGFlow | Free open source; enterprise build exists [34] (settled) | Yes; DeepDoc OCR on CPU [34] (settled) | unknown | Dataset visible to creator ("me") or whole team ("team") [34] (settled) | Configurable empty response [34] (settled) |

### 2b. Ingest, sharing, platforms, setup, measured accuracy

| Rival | Ingest formats | Group sharing and sync | Platforms | One-time admin setup | Measured accuracy |
|---|---|---|---|---|---|
| Notion AI | Notion pages; Q&A cannot read embedded PDFs or video [2] (settled) | Cloud workspace, ~1 hour indexing lag for new content [2] (settled) | Web, desktop and mobile apps [1]; Linux unknown | Sign up, buy Business, invite members [1] (settled) | unknown |
| Glean | Connected company apps; count unknown [8] (settled) | Cloud index of source apps [8] (settled) | Web, browser extension, desktop macOS and Windows, mobile [11] (settled) | Sales-led deployment with connectors [10] (in flux) | unknown |
| NotebookLM | PDF, Google Docs and Slides, web, YouTube, audio with speech, pasted text [7] (in flux) | Share notebook by email or public link [6] (settled) | Web and mobile [3] (settled) | Google account, upload, share [6] (settled) | 13% of answers had a hallucination vs 40% for ChatGPT and Gemini [36] (settled for that study) |
| Obsidian + plugins | Markdown vault (judgment from [12]) | Obsidian Sync shared vaults, E2E encrypted [12] (settled) | Desktop; Copilot agent is desktop only, Quick Chat on mobile [14] (settled) | Install app, plugin, then key or Ollama [13][14] (settled) | unknown |
| Mem | unknown | Shutting down [17] (settled) | unknown | unknown | unknown |
| Capacities | unknown | Cloud sync, view-only sharing [18] (settled) | unknown | Sign up [18] (settled) | unknown |
| Confluence + Rovo | unknown | Cloud, credits pooled per org [20] (settled) | unknown | Verified business domain required [20] (settled) | unknown |
| Guru | unknown | unknown | unknown | unknown | unknown |
| Slab | unknown | unknown | unknown | unknown | unknown |
| Slite | Search across connected tools on Pro [24] (settled) | Cloud [24] (settled) | unknown | Sign up [24] (settled) | unknown |
| AnythingLLM | PDF, Office, ODF, CSV, MD, HTML, EPUB, mbox, images, audio, video [25] (settled) | Multi-user only in the Docker server [25] (settled) | Desktop Mac, Windows, Linux; Docker [25] (settled) | Desktop installer for one user; Docker server for a group [25] (settled) | EnterpriseRAG-Bench 35.6 [44] (settled, vendor-run) |
| Khoj | unknown | Self-host or cloud [27] (settled) | Web, desktop, Obsidian, Emacs, phone, WhatsApp [27] (settled) | Self-host per docs or cloud signup [27] (settled) | unknown |
| Open WebUI | unknown | Self-hosted server [28] (settled) | Web; desktop app for macOS, Windows, Linux [28] (settled) | pip or one docker run plus a model server [28] (settled) | EnterpriseRAG-Bench 24.9 [44] (settled, vendor-run) |
| Onyx | 40+ app connectors [30] (in flux) | Self-hosted or cloud [29][30] (settled) | Web, Chrome extension, Slack [29][30] (settled) | Docker, Kubernetes or Helm; Lite mode cannot index documents [29] (settled) | unknown (not in page text read [44]) |
| PrivateGPT | File and artifact ingestion [31] (settled) | API server [31] (settled) | Server API plus test UI [31] (settled) | Run model server, then PrivateGPT [31] (settled) | unknown |
| Kotaemon | PDF, HTML, MHTML, XLSX; Office types need full image [32] (settled) | Multi-user web UI [32] (settled) | Web via Docker [32] (settled) | docker run; Ollama image available [32] (settled) | unknown |
| Reor | Markdown notes [33] (settled) | None (single user) [33] (settled) | Desktop Mac, Linux, Windows [33] (settled) | Installer plus Ollama model download [33] (settled) | unknown |
| RAGFlow | Deep document parsing with OCR [34] (settled) | Team datasets [34] (settled) | Web via Docker [34] (settled) | Docker; 4 CPU, 16 GB RAM, 50 GB disk recommended [34] (settled) | EnterpriseRAG-Bench 50.2 [44] (settled, vendor-run) |

## 3. Per-rival notes

**Notion AI.** AI sits in the Business plan at $20 per seat per month, with Standard and Select credits per seat and paid top-ups [1]. Q&A searches only pages the asker can open and says so when it cannot answer [2]. That is retrieval-time filtering done right. Offline covers reading pages, not AI [1]. Enterprise gets zero data retention with LLM providers; Business keeps 30 days [1]. For a family or parish, $20 per member per month is the real barrier. (settled for facts, judgment for the barrier)

**Glean.** Enterprise search and assistant over connected company apps [8]; no public price [10]. It answers from company knowledge the user may see, but its default "All Knowledge" mode also draws on web and LLM knowledge, so "I don't know" is not the default path [8]. Deep-linked citations reach the passage when the match is confident and drop to document level otherwise [9]. Not a fit for small groups on price or setup. (settled; fit is judgment)

**NotebookLM, now Gemini Notebook.** Renamed in July 2026 [3]. Free with 50 sources per notebook, rising to 600 on Ultra [3]. Citations are direct quotes you can hover [4], and it declines when the answer is not in the sources [5]. In the one independent audit found, 13% of its answers held at least one hallucination, about a third of ChatGPT's and Gemini's rate, and most errors were overconfident characterizations rather than invented facts [36]. Sharing is per notebook (Viewer or Editor), and "chat only" public sharing does not fully revoke underlying access [6]. This is the quality bar a family or class will compare Corunis to, and its weakness is that everything goes to Google and roles stop at the notebook. (settled; comparison is judgment)

**Obsidian with AI plugins.** Obsidian is free and local with optional $4 Sync and shared vaults [12]. Smart Connections finds related notes and passages with local embeddings; it is discovery, not cited Q&A, and its license bars building a competing general product on it [15][16]. Copilot for Obsidian (AGPL-3.0) runs with your own key or a local model for free, $14.99 a month for hosted models [13][14]. Neither has group roles; a shared vault is all or nothing (judgment from [12]).

**Mem.** Winding down: notes go read-only December 18, 2026, and the service ends January 15, 2027 [17]. Its users need a new home, which is a small, real opening. (settled; opening is judgment)

**Capacities.** Object-based personal notes, free core, Pro $9.99 a month with an AI budget [18]. AI can take notes as context and lists web sources when it searches [19]. Single-user with view-only sharing [18]. Not a group tool. (settled)

**Confluence with Rovo.** Rovo credits come with paid Confluence plans and go pay-as-you-go by default on December 3, 2026 [20]. Rovo will not enable for an org registered on gmail.com or outlook.com [20], which rules out most families and parishes outright. Seat prices changed October 13, 2026 and current figures were not confirmed [21]. (settled; seat price unknown)

**Guru, Slab, Slite.** Guru is quote-only now [22]. Slab's price is unconfirmed and no AI answer feature was confirmed [23]. Slite puts Ask (AI search and answers) in its $10 Basic plan and an agent plus connected-tool search in $20 Pro [24]. Citation and abstention behavior for all three: unknown.

**AnythingLLM (MIT).** The easiest local install: a free desktop app for Mac, Windows and Linux, but multi-user only in the Docker server [25]. Roles are admin, manager and default, and access is granted per workspace; I found no per-document ACL in `server/` [25]. In query mode it returns "There is no relevant information in this workspace to answer your query." only when zero chunks come back (`server/utils/chats/stream.js:111,244`); otherwise the default system prompt carries no abstain rule [25]. Citations are the retrieved chunks with similarity scores, not claims tied to passages [25]. Scored 35.6 on EnterpriseRAG-Bench [44]. (settled)

**Khoj (AGPL-3.0).** Personal AI first, with web, desktop, Obsidian, Emacs, phone and WhatsApp clients [27]. Content is per user; agents have public, private or protected privacy levels; no group ACL over documents found [27]. Prompt asks for inline citations as markdown links, with no abstain rule in the base prompt [27]. Last commit August 1, 2026. (settled)

**Open WebUI (custom license).** BSD-3 plus a clause that forbids removing the Open WebUI brand above 50 users in 30 days without permission or an enterprise license [28]; that matters for any white-labeled Corunis fork. Access grants are read or write per knowledge base or file to a user, group or everyone, and retrieval checks them at query time (`backend/open_webui/retrieval/utils.py` get_sources_from_items) [28]. The default RAG template says "If you don't know the answer, clearly state that" and then "If the answer isn't present in the context but you possess the knowledge, ... provide the answer using your own understanding" (`config.py:1075`), and the relevance threshold defaults to 0.0 [28]. Lowest listed score on EnterpriseRAG-Bench at 24.9 [44]. (settled)

**Onyx, formerly Danswer (MIT core, enterprise `ee/`).** The strongest permission model in open source: every indexed document carries an ACL, and a user matches on their email, prior emails or public (`backend/onyx/access/access.py`) [29]. User groups, post-query censoring and permission sync from Drive, Confluence, SharePoint, Canvas and others live in `ee/` under the Onyx Enterprise License [29]. Prompts demand inline [1] citations to documents but contain no abstain rule [29]. Standard mode runs a vector and keyword index, background workers, model servers, Redis and MinIO; Lite mode cannot index documents [29]. Onyx publishes EnterpriseRAG-Bench and its prompts are tuned on it [29][44]. Cloud Business is $20 per user per month [30]. (settled)

**PrivateGPT (Apache-2.0).** Now an API layer, not an app: it does not run models and needs an OpenAI-compatible server; the UI at `/ui` is for testing [31]. Auth is optional basic auth [31]. Not a direct rival for non-technical groups. (settled)

**Kotaemon (Apache-2.0).** The citation leader: the prompt makes the model copy roughly six-word start and end phrases exactly from the context to mark the supporting span, shown in a PDF preview with a relevance score [32]. It tells the model to say it doesn't know [32]. Permissions are only private or shared collections [32]. Last commit May 30, 2026, so momentum is slowing. (settled; momentum is judgment)

**Reor (AGPL-3.0).** Single-user desktop notes with local models through Ollama [33]. Last commit May 13, 2025; treat as dormant. (settled)

**RAGFlow (Apache-2.0).** Found while surveying; a strong document parser with OCR on CPU, now a Go backend [34]. Datasets are visible to the creator or the whole team, nothing finer [34]. Best open-source self-hostable app on EnterpriseRAG-Bench at 50.2 [44]. Needs 16 GB RAM to start [34]. (settled)

**Others found, not studied:** GPT4All LocalDocs, Msty, Dify, Quivr, LibreChat, h2oGPT. (unknown beyond names)

## 4. Published evidence

**Legal research RAG (Magesh et al., JELS 2025).** Preregistered, 202 queries. Lexis+ AI accurate 65%, Westlaw AI-Assisted Research 41 to 42%, Ask Practical Law AI 19%; incomplete answers 18%, 25% and 62%; each tool hallucinated between 17% and 33% of the time [35]. Lesson: "RAG with citations" vendors overstate; refusals are scored as incomplete, not correct, so a tool can look safe by refusing. (settled)

**NotebookLM newsroom audit (Hagar et al., 2025).** 300-document corpus; 30% of outputs had at least one hallucination overall, ChatGPT and Gemini 40%, NotebookLM 13%; errors were mostly interpretive overconfidence [36]. (settled; per-tool sample size unknown)

**CRAG (Meta, 2024).** 4,409 questions; LLMs alone at most 34%, simple RAG 44%, state-of-the-art industry RAG answers 63% of questions without hallucination [37]. Data is CC BY-NC 4.0 [37]. (settled)

**RGB (2023).** Negative rejection with only noise documents: ChatGPT rejects 24.67% by exact match and 45% by judge in English; the best rejection rate was only 45% [41]. (settled)

**Sufficient Context (Google, ICLR 2025).** Large models answer wrongly instead of abstaining when context is insufficient; small models hallucinate or abstain even when context suffices [40]. Directly relevant because Corunis runs small local models. (settled; relevance is judgment)

**ALCE (2023).** Defines citation recall and precision with an entailment model; even the best models lacked complete citation support 50% of the time on ELI5 [42]. (settled)

**RAGTruth (2024).** About 18,000 RAG responses with word-level hallucination labels [38]. Useful to calibrate a hallucination judge. (settled)

**FRAMES (Google, 2024).** 824 multi-hop questions; 0.40 accuracy with no retrieval, 0.66 with multi-step retrieval [39]. (settled)

**UAEval4RAG (2024).** Six-category taxonomy of unanswerable questions with unanswered-ratio and acceptable-ratio metrics; finds trade-offs between answering and rejecting [43]. (settled)

**EnterpriseRAG-Bench (Onyx, 2026).** 511,962 synthetic company documents across nine sources, 500 questions in ten categories including Conflicting Info and Not Found, MIT licensed [44]. Leaderboard on Onyx's page: OpenClaw 68.2, OpenAI File Search 61.0, RAGFlow 50.2, Amazon Q 49.0, Azure AI Search 48.4, Vertex AI Search 41.9, NVIDIA Blueprints 37.7, AnythingLLM 35.6, Weaviate Verba 34.5, LlamaIndex 27.2, LangChain 25.0, Open WebUI 24.9 [44]. Run by a competitor of those systems, with Onyx's prompts validated on it [29], so treat as a floor, not a fair race. (settled numbers; fairness is judgment)

**Vectara hallucination leaderboard.** Summarization hallucination rates for models Corunis might run locally: Qwen3-4B 5.7%, Qwen3-8B 4.8%, Gemma-3-12B 4.4%, Llama-3.3-70B 4.1%; best listed 1.8% [51]. Summarization of a given document, not retrieval QA. (in flux)

**Permission leaks in enterprise AI.** Gartner surveyed 132 IT leaders in June 2024: 40% delayed Microsoft 365 Copilot rollouts by three months or more over oversharing, and Copilot had surfaced payroll data, confidential legal files and strategy documents in some organizations because the underlying permissions were too broad [52]. EchoLeak (CVE-2025-32711, CVSS 9.3) let one crafted email make M365 Copilot exfiltrate data with no click; patched server-side in 2025 [53]. OrgAccess shows frontier LLMs fail to follow role rules reliably when asked to enforce them in the prompt [45], and a 2025 position paper demonstrates RAG exfiltration and argues only deterministic access control works [46]. Lesson: filter before retrieval, never ask the model to keep secrets. (settled facts; lesson is judgment)

## 5. Eval design

### 5.1 Principles

- Same synthetic corpus, same questions, same scoring for every system. No real member data.
- For local tools, the same model where the tool allows it (for example one 8B instruct model through Ollama or llama.cpp), plus each tool's defaults. Report both "default" and "best config" rows.
- A tool that cannot express a role rule is not given a pass on the leak test. Either the admin works around it (separate workspaces per role, which we record as setup cost) or every role-restricted question counts as a leak if the restricted fact appears.
- Cloud rivals run only on the synthetic corpus, only under accounts Donovan approves later. This study created none.

### 5.2 Corpus shapes (synthetic, fixed seed, 300 to 1,500 documents each)

| Group | Documents | Roles | Sensitive slice |
|---|---|---|---|
| Family | Insurance policies, medical visit notes, school letters, recipes, budgets, warranties, scanned receipts | Parent, teen, child, grandparent | Medical notes, finances, gift plans |
| Parish | Bulletins, council minutes, policies, volunteer schedules, safe-environment records, donor list, sacramental register | Pastor, staff, ministry lead, volunteer, parishioner | Donor amounts, pastoral counseling notes, background checks |
| Small business | SOPs, price sheets, contracts, HR handbook, payroll, customer emails, invoices | Owner, manager, employee, contractor | Payroll, contracts, HR cases |
| Class or team | Syllabus, assignments, rubrics, grades, roster, meeting notes, playbook | Teacher or coach, assistant, student or player, parent | Grades, accommodations, discipline notes |

Mix formats as real groups do: digital PDF, scanned PDF, DOCX, XLSX, Markdown, email (mbox), photos of paper. Include near-duplicates and superseded versions with effective dates. EnterpriseRAG-Bench's generation framework (MIT) can be adapted to produce these [44].

### 5.3 Question kinds (200 per group, 800 total)

| Kind | Count per group | Right answer |
|---|---|---|
| Answerable, one source | 60 | Correct answer citing the one gold passage |
| Multi-source | 40 | Correct synthesis citing every gold passage (2 to 4 documents, as in MultiHop-RAG [47] and FRAMES [39]) |
| Unanswerable | 40 | Abstain plainly; spread across the six UAEval4RAG categories [43], with SQuAD 2.0 style near-miss distractors [48] |
| Role-restricted | 40 | Asked by a low-privilege role: refusal that reveals nothing, not even that the document exists |
| Stale versus current | 20 | Answer from the current version, cite it, and say it replaced the old one when asked |

Each restricted document carries unique canary strings (a fake donor amount, a fake diagnosis code) so leaks are machine-detectable.

### 5.4 Scoring rules

- **Answer correctness:** gold answer per question; LLM judge with a three-level scale (correct, partial, wrong) calibrated on RAGTruth labels [38]; a human checks a 10% random sample plus every disagreement. Refusals on answerable questions score wrong, as in the Stanford study [35].
- **Citation precision and recall, passage level:** gold passage IDs per question. Recall = share of required gold passages cited. Precision = share of cited passages that entail the sentence they support, judged by an entailment check as in ALCE [42]. Whole-document citations count only if the document has exactly one passage.
- **Abstention accuracy:** precision and recall of "abstain" against the unanswerable set, reported with answer rate on answerable questions so a tool cannot win by refusing everything.
- **Leak count:** any canary string, restricted document title or ID, or paraphrase of a restricted fact (judge plus human confirm) in a low-privilege answer, its citations, its suggested follow-ups or its error messages. An answer like "I can't show you the payroll file" is a leak of existence. Target is zero; report raw counts, not rates.
- **Staleness:** correct only if the current version is used and cited.
- **Cost and speed:** median and p95 seconds to first token and to full answer on each host; setup minutes and number of admin steps, timed from a written script.

### 5.5 Seed datasets and licenses

| Dataset | Use | License |
|---|---|---|
| EnterpriseRAG-Bench [44] | Corpus generator, Not Found and conflict categories | MIT |
| SQuAD 2.0 [48] | Unanswerable question patterns | CC BY-SA 4.0 |
| UAEval4RAG [43] | Unanswerable taxonomy and metrics | unknown |
| MultiHop-RAG [47] | Multi-source question patterns | ODC-BY |
| FRAMES [39] | Multi-hop question patterns | Apache-2.0 |
| ALCE [42] | Citation precision and recall method | MIT |
| RAGTruth [38] | Judge calibration | MIT |
| RAGBench [49] | Industry-domain examples | CC BY 4.0 |
| CRAG [37] | Dynamic and stale fact patterns | CC BY-NC 4.0 (non-commercial only) |
| Vectara Open RAG Benchmark [50] | Scanned and table-heavy PDF cases | CC BY-NC 4.0 (non-commercial only) |
| OrgAccess [45] | Role and permission taxonomy | unknown |

## 6. Running the open-source rivals (plan only, nothing installed)

All of these need a model server for generation; on chapel1 (8 CPU cores, no GPU, shared) that means llama.cpp or Ollama with a small quantized model, pinned to a few cores and run off-hours so other work is not starved. Throughput on chapel1 is unknown until measured. On a GPU host the same harness swaps in a larger model. The harness should drive each tool through its HTTP API so runs repeat exactly.

| Tool | License | Install | CPU-only chapel1 | GPU host | Harness path |
|---|---|---|---|---|---|
| AnythingLLM | MIT [25] | Docker server for multi-user [25] | Feasible; built-in LanceDB, local embedder (judgment) | Same with bigger model | Developer API (verify endpoints before use) |
| Open WebUI | Open WebUI License [28] | pip or docker run [28] | Feasible; set hybrid search and threshold explicitly since defaults are off and 0.0 [28] | Same | REST API (verify) |
| Onyx | MIT core, EE separate [29] | docker compose, Helm [29] | Heavy: Standard needs index, model server, Redis, MinIO; RAM unknown (judgment) | Recommended host | REST API; run community and note EE-only features |
| Kotaemon | Apache-2.0 [32] | docker run; full image for Office files [32] | Feasible with Ollama image [32] | Same | Python libraries or Gradio client (judgment) |
| RAGFlow | Apache-2.0 [34] | Docker [34] | Feasible but needs 16 GB RAM and CPU OCR [34] | Better parsing speed | HTTP API and Python SDK (`sdk/`) [34] |
| PrivateGPT | Apache-2.0 [31] | Server plus separate model server [31] | Feasible | Same | Its API is the product [31] |
| Khoj | AGPL-3.0 [27] | docker compose (`docker-compose.yml`) [27] | Feasible; per-user only, so leak tests run as separate users | Same | API (verify) |
| Reor | AGPL-3.0 [33] | Desktop installer [33] | GUI only; Linux hosts have no GUI driver, so manual or skip | Manual | None |
| Obsidian plugins | Copilot AGPL-3.0 [14]; Smart Connections custom [16] | Inside Obsidian desktop [12] | GUI only, manual | Manual | None |

## 7. Where the bar is

### 7.1 Numbers Corunis must beat

| Measure | Rival bar | Corunis target |
|---|---|---|
| Leaks of role-restricted facts | Copilot leaked through broad permissions [52]; prompt-only enforcement fails [45][46] | Zero across all 160 role-restricted questions, enforced before retrieval (judgment) |
| Hallucination rate, sentence-level audit | NotebookLM 13% [36]; legal RAG 17% to 33% [35] | Under 13% on the same audit style with a local model (judgment) |
| EnterpriseRAG-Bench overall | RAGFlow 50.2 best self-hostable OSS app; AnythingLLM 35.6; Open WebUI 24.9; OpenAI File Search 61.0 [44] | Above 50.2 on a GPU host; report chapel1 separately (judgment) |
| Abstention on unanswerables | Best RGB rejection 45% [41]; AnythingLLM refuses only on empty retrieval [25]; Open WebUI told to use own knowledge [28] | 90% correct abstention with no more than 5 points lost on answerable questions (judgment) |
| Citation support | Best ALCE systems lack full support 50% of the time [42] | Passage-level citation recall and precision both at or above 0.9 on the synthetic corpus (judgment) |
| Accuracy without hallucination | CRAG industry best 63% [37]; Lexis+ AI 65% [35] | 65% or better on answerable questions with zero restricted leaks (judgment) |

### 7.2 Where Corunis can win

- Fully offline on the group's own machine. Every cloud rival sends content to a provider [1][3][8][20]. (settled facts, judgment on the win)
- Per-document roles for groups that are not businesses. Rovo refuses gmail.com admins [20]; NotebookLM roles stop at the notebook [6]; local tools stop at workspace or collection [25][32][34], and Onyx's group features are enterprise-licensed [29]. (judgment)
- Honest "I don't know" by default. Only NotebookLM, Notion and Kotaemon make it the default path [2][5][32]. (judgment)
- Price: $0 software against $20 per seat for Notion AI [1] or Onyx Cloud [30]. (judgment)
- Mem refugees need a home before January 15, 2027 [17]. (judgment)

### 7.3 Where Corunis cannot win yet

- Raw answer quality on CPU-only hardware against Gemini or frontier models; small models abstain or hallucinate more [40]. (judgment)
- Connector breadth: Onyx connects 40+ apps [30] and Glean indexes the company's apps [8]. (judgment)
- Native mobile and media features (NotebookLM audio and video overviews, mobile apps) [3]; Corunis plans a PWA only [54]. (judgment)
- Note-taking itself: Obsidian and Capacities are editors, Corunis is a chat over documents [12][18][54]. (judgment)

## 8. Sources (all read 2026-11-17)

"Read directly" means the page, PDF or code was read in full or in the relevant part. "Via search summary" means only a search tool's summary of the page was read; those claims are weaker.

1. Notion pricing, https://www.notion.com/pricing (read 2026-11-17, read directly)
2. Notion help, Understanding how Q&A finds answers, https://www.notion.com/en-gb/help/guides/understanding-how-q-and-a-finds-answers-can-help-you-get-better-results (read 2026-11-17, via search summary)
3. Gemini Notebook plans and FAQ, https://notebooklm.google/plans (read 2026-11-17, read directly)
4. NotebookLM help, Use chat, https://support.google.com/notebooklm/answer/16179559 (read 2026-11-17, via search summary)
5. NotebookLM help, FAQ, https://support.google.com/notebooklm/answer/16269187 (read 2026-11-17, via search summary)
6. NotebookLM help, public and shared notebooks, https://support.google.com/notebooklm/answer/16322204 (read 2026-11-17, via search summary)
7. Google blog, NotebookLM audio and YouTube sources, https://blog.google/innovation-and-ai/products/notebooklm-audio-video-sources/ (read 2026-11-17, via search summary)
8. Glean docs, How Glean accesses information, https://docs.glean.com/user-guide/assistant/how-glean-accesses-info (read 2026-11-17, read directly)
9. Glean docs, Deep linked citations, https://docs.glean.com/user-guide/assistant/glean-chat/glean-chat-citations/deep-linked-citations and https://developers.glean.com/guides/chat/deep-linked-citations (read 2026-11-17, via search summary)
10. Glean pricing estimates, https://www.gosearch.ai/blog/glean-pricing-explained and https://www.eesel.ai/blog/glean-pricing (read 2026-11-17, via search summary, third party)
11. Glean apps, https://docs.glean.com/administration/management/apps/mobile and https://glean.com/blog/glean-desktop-nov-drop-2025 (read 2026-11-17, via search summary)
12. Obsidian pricing, https://obsidian.md/pricing (read 2026-11-17, read directly)
13. Copilot for Obsidian pricing, https://www.obsidiancopilot.com/en/pricing (read 2026-11-17, read directly)
14. Copilot for Obsidian code and README, https://github.com/logancyang/obsidian-copilot at d93ac2d (read 2026-11-17, read directly)
15. Smart Connections Pro, https://smartconnections.app/pro-plugins/ (read 2026-11-17, read directly, partial page)
16. Smart Connections code, README and LICENSE, https://github.com/brianpetro/obsidian-smart-connections at 3bfe2b2 (read 2026-11-17, read directly)
17. Mem pricing and wind-down notice, https://get.mem.ai/pricing (read 2026-11-17, read directly)
18. Capacities pricing, https://capacities.io/pricing (read 2026-11-17, read directly, partial page)
19. Capacities AI assistant docs, https://docs.capacities.io/reference/ai-assistant (read 2026-11-17, via search summary)
20. Atlassian, How Rovo credits work, https://support.atlassian.com/rovo/docs/rovo-usage-limits/ (read 2026-11-17, read directly)
21. Atlassian future pricing list, https://www.atlassian.com/licensing/future-pricing/cloud/list, and https://www.eesel.ai/blog/confluence-ai-pricing (read 2026-11-17, via search summary)
22. Guru pricing, https://www.getguru.com/pricing and https://www.gosearch.ai/faqs/?p=1090 (read 2026-11-17, via search summary)
23. Slab pricing, https://www.capterra.co.uk/software/184289/slab and https://costbench.com/software/knowledge-management/slab/ (read 2026-11-17, via search summary, third party)
24. Slite pricing, https://slite.com/pricing (read 2026-11-17, read directly, partial page)
25. AnythingLLM code, README and TERMS_SELF_HOSTED.md, https://github.com/Mintplex-Labs/anything-llm at 160afa0 (read 2026-11-17, read directly)
26. AnythingLLM pricing, https://anythingllm.com/pricing (read 2026-11-17, read directly)
27. Khoj code and README, https://github.com/khoj-ai/khoj at ae229ca (read 2026-11-17, read directly)
28. Open WebUI code, README and LICENSE, https://github.com/open-webui/open-webui at 0666e59 (read 2026-11-17, read directly)
29. Onyx code, README and LICENSE, https://github.com/onyx-dot-app/onyx at 97bf924 (read 2026-11-17, read directly)
30. Onyx pricing, https://onyx.app/pricing (read 2026-11-17, read directly)
31. PrivateGPT code and README, https://github.com/zylon-ai/private-gpt at cfbd09b (read 2026-11-17, read directly)
32. Kotaemon code and README, https://github.com/Cinnamon/kotaemon at 9ad3e4e (read 2026-11-17, read directly)
33. Reor README, https://github.com/reorproject/reor at 9b47fca (read 2026-11-17, read directly)
34. RAGFlow code and README, https://github.com/infiniflow/ragflow at fe8201d (read 2026-11-17, read directly)
35. Magesh et al., Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools, JELS 2025, https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf (read 2026-11-17, read directly)
36. Hagar et al., Not Wrong, But Untrue, https://arxiv.org/abs/2509.25498 (read 2026-11-17, abstract read directly)
37. CRAG, https://arxiv.org/abs/2406.04744 (abstract read directly) and license https://github.com/facebookresearch/CRAG/blob/main/LICENSE (read 2026-11-17, read directly)
38. RAGTruth, https://arxiv.org/abs/2401.00396 (abstract) and https://github.com/ParticleMedia/RAGTruth (read 2026-11-17; license read directly)
39. FRAMES, https://arxiv.org/abs/2409.12941 (abstract) and https://huggingface.co/datasets/google/frames-benchmark (read 2026-11-17; card read directly)
40. Sufficient Context, https://arxiv.org/abs/2411.06037 (read 2026-11-17, abstract read directly)
41. RGB, https://arxiv.org/abs/2309.01431 (read 2026-11-17; PDF Table 3 read directly)
42. ALCE, https://arxiv.org/abs/2305.14627 (abstract) and https://github.com/princeton-nlp/ALCE (read 2026-11-17; license read directly)
43. UAEval4RAG, https://arxiv.org/abs/2412.12300 (read 2026-11-17, abstract read directly)
44. EnterpriseRAG-Bench, https://arxiv.org/abs/2605.05253 (abstract), https://onyx.app/enterpriserag-bench (read 2026-11-17, read directly) and https://huggingface.co/datasets/onyx-dot-app/EnterpriseRAG-Bench (card read directly)
45. OrgAccess, https://arxiv.org/abs/2505.19165 (read 2026-11-17, abstract read directly)
46. Enterprise AI Must Enforce Participant-Aware Access Control, https://arxiv.org/abs/2509.14608 (read 2026-11-17, abstract read directly)
47. MultiHop-RAG, https://huggingface.co/datasets/yixuantt/MultiHopRAG (read 2026-11-17; card read directly)
48. SQuAD 2.0, https://huggingface.co/datasets/rajpurkar/squad_v2 (read 2026-11-17; card read directly)
49. RAGBench, https://huggingface.co/datasets/galileo-ai/ragbench (read 2026-11-17; card read directly)
50. Vectara Open RAG Benchmark, https://huggingface.co/datasets/vectara/open_ragbench (read 2026-11-17; card read directly)
51. Vectara hallucination leaderboard README, https://github.com/vectara/hallucination-leaderboard (read 2026-11-17, read directly)
52. Computerworld, Microsoft moves to stop M365 Copilot from oversharing data, Dec 4, 2024, https://www.computerworld.com/article/3616459/microsoft-moves-to-stop-m365-copilot-from-oversharing-data.html (read 2026-11-17, read directly)
53. The Hacker News, Zero-click AI vulnerability exposes Microsoft 365 Copilot data, June 2025, https://thehackernews.com/2025/06/zero-click-ai-vulnerability-exposes.html (read 2026-11-17, via search summary)
54. Corunis README.md and docs/STACK.md, ~/Projects/Corunis (read 2026-11-17, read directly)
