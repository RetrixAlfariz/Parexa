# Parexa Research OS v1

**Implementation status:** Working local-first research-management foundation introduced on the \`feat/research-operating-system-v1\` branch. This is an additive product surface, not a replacement for the existing chat/Genesis and RAG components.

## Design principle

**Preserve evidence before inference.** A research source is first a byte-exact object, then a parsed/indexed representation, then a possible citation. Research notes, hypotheses, and source metadata must remain usable when LM Studio, Ollama, embedding services, or cloud connectors are unavailable.

## Navigate the application

- **\`/research\`**: new researcher workstation, accessible from the old chat sidebar and command palette.
- **\`/\`**: unchanged conversation-focused Observatory/Genesis experience.
- Open \`/research\` and create a project. Choose a project scope in the left rail. All projects is a global view; scoped records have project IDs.
- **Source vault** uploads PDF, TXT, MD as preserved, content-addressed originals without requiring an embedding model.
- **Experiment registry** maintains hypotheses, methods, results, and stage labels.
- **Evidence ledger** requires an existing archived source, an explicit claim, and a supporting excerpt. Page labels and confidence are user-provided, **not independently verified**.
- **Notebook** persists notes in SQLite. "Import old browser scratchpad" copies, rather than removes, the existing \`localStorage\` scratchpad.
- **Research queue** tracks tasks, priorities, and progress.
- **Systems & storage** reports SQLite-backed counts and local disk space and checks configured models and embedding status using the existing APIs.

The main header search queries locally persisted projects, notes, document titles, experiments, and evidence claims. It is a metadata/title search, not a new fulltext/semantic search backend.

## Component boundaries

\`\`\`mermaid
flowchart LR
    UI["Research OS UI /research"] --> API["Research Flask Blueprint /api/research"]
    Chat["Existing chat & upload /"] --> Archive["Source Vault"]
    API --> Archive
    Archive --> DB["SQLite research.sqlite3"]
    Archive --> Store["Immutable SHA-256 objects"]
    Chat --> Parse["Existing PyMuPDF/OCR ingestion"]
    Parse --> Vector["Existing Qdrant RAG index"]
    Chat --> Model["LM Studio / Ollama / optional cloud"]
    UI --> Monitor["/api/models + /api/health/embedding"]
\`\`\`

### Metadata tables

| Table | Scope | Key contents |
| --- | --- | --- |
| \`projects\` | root | title, objective, status |
| \`documents\` | project/global | UUID, filename, MIME, SHA-256, byte size, indexing status, chunk count |
| \`notes\` | project/global | title and full note text |
| \`experiments\` | project/global | hypothesis, method, outcome, stage |
| \`evidence\` | source-bound, project/global | source UUID, claim, excerpt, location, reviewed confidence |
| \`tasks\` | project/global | description, priority, status |

SQLite uses WAL and foreign-key enforcement. The metadata database is \`<PAREXA_DATA_DIR>/research/research.sqlite3\`. Source objects are placed at \`<PAREXA_DATA_DIR>/research/objects/<first-2-sha-chars>/<sha256>\`. Names never determine local object paths. Multiple source records with identical bytes share the same immutable object. The storage counter counts distinct archived digests, not duplicated metadata rows.

### Two distinct source ingestion paths

1. **Research vault:** \`POST /api/research/documents\` streams and hashes a source, creates metadata with \`index_status=stored\`, and **does not** claim the source is searchable by RAG.
2. **Existing chat upload:** \`POST /api/upload\` archives an original before parsing or indexing. If parsing or embeddings fail, the original remains stored. After successful Qdrant ingestion, the corresponding source metadata changes to \`index_status=indexed\` and records the produced chunk count.

The first path is intentionally decoupled from AI inference. Automatic re-indexing of already archived source objects is **not** shipped in this version. To use a research-vault source with the current chat RAG, reattach it using the chat upload flow. **Do not delete original sources simply because a vector index exists.**

### Source integrity and provenance

Every original source has a SHA-256 digest. The \`Verify\` action rehashes the original object on disk and compares it to recorded metadata. The \`Download\` action returns preserved bytes as an attachment, not inline content.

Evidence entries cannot point to nonexistent documents and cannot be filed into another project when the source has a project assignment. However, the quote text and page label are currently manually authored. No claim has yet been verified against a parsed source span, so user-assigned confidence must not be mistaken for a cryptographic proof or AI confidence probability.

### Explicitly outside v1 scope

- PDF page rendering and coordinate-precise citations
- Automatically indexed vault sources, source/version migrations, or Qdrant index repair
- Structured table/figure/formula extraction
- True semantic knowledge graph or autonomous research agent orchestration
- Automatic citation correctness verification
- Reproducible experiment execution and real GPU telemetry
- Dataset versioning and notebook execution
- Portable research-workspace export/import and automated backup
- User authentication, collaborative permissions, or network exposure

## API

| HTTP | Endpoint | Action |
| --- | --- | --- |
| GET | \`/api/research/overview\` | live counts, recent work |
| GET/POST | \`/api/research/projects\` | list/create projects |
| GET/PATCH | \`/api/research/projects/<id>\` | inspect/edit project |
| GET/POST | \`/api/research/documents\` | list/archive original sources |
| GET | \`/api/research/documents/<id>/download\` | retrieve original bytes |
| GET | \`/api/research/documents/<id>/verify\` | SHA-256 verification |
| GET/POST | \`/api/research/notes\` | notebook |
| GET/POST | \`/api/research/experiments\` | experiment registry |
| GET/POST | \`/api/research/evidence\` | evidence ledger |
| GET/POST | \`/api/research/tasks\` | tasks |
| GET/PATCH/DELETE | \`/api/research/{notes,experiments,evidence,tasks}/<id>\` | inspect/change/remove |
| GET | \`/api/research/search?q=\` | title/claim search |
| GET | \`/api/research/system\` | real local storage counters and declared capabilities |

Accepts \`project_id\` on list endpoints (except project list), and as optional scope on create. A source upload is multipart \`file\` and optional \`project_id\`. All limits reuse \`PAREXA_MAX_UPLOAD_MB\` (default 25 MiB). All JSON mutation endpoints reject unknown fields and foreign-project references. Errors have non-200 statuses with stable \`code\` identifiers.

## Local launch and verification

\`\`\`bash
uv sync --locked
uv run python main.py
# Open http://127.0.0.1:5000/research
\`\`\`

Lightweight backend/API tests do not require LlamaIndex, Qdrant, or a real model server:

\`\`\`bash
python -m pip install flask python-dotenv
python -m unittest discover -s tests -p 'test_research_*.py' -v
node --check website/static/research-os.js
\`\`\`

The \`Research OS validation\` GitHub Actions workflow runs these checks on Python 3.10 and 3.12. Full model quality and performance evaluations remain separate and cannot be inferred from these tests.

## Security and reliability notes

1. Keep Parexa bound to loopback: the current Flask server **does not authenticate users**. Do not expose it publicly. Another machine on the LAN should not be granted access simply by widening \`PAREXA_HOST\`.
2. The source vault does not execute uploaded content. File extensions are limited to .pdf, .md, .txt; downloads force attachment mode. A file extension check is **not** an antivirus or PDF parser sandbox.
3. Server-side metadata and content-addressed objects are permanent until manually cleaned. The UI does not expose destructive removal of projects or archived sources. No automated garbage collection runs.
4. SQLite and SHA-256 protect metadata consistency and *detect* changed object bytes; they do not replace real backups.
5. Vault uploads never silently fall back to a cloud provider. The separate chat and embedding integrations can use externally hosted providers only according to the configured runtime.
6. Researchers should verify quoted passages and interpretations before publication. The evidence ledger captures accountability, not a proof of scientific truth.

## Subsequent milestones

**M1 (this implementation):** Persistent project schema, archival vault, notes, tasks, experiments, manual evidence ledger, real system/status panel, responsive UI.

**M2 (next):** Indexed source lifecycle, reindex queue and explicit model selection, PDF page viewer, parsed span provenance, searchable source text, backup/export tool, storage quota.

**M3:** Typed evidence graph, citation extraction/validation, experiment datasets and reproducibility, cross-document claim synthesis, context scoping.

**M4:** Optional local worker orchestration, evaluation harness, measured model routing, performance dashboards, revisioned research packages, collaboration/authentication if networked usage is ever needed.
