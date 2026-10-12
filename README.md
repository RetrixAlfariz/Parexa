# Parexa

> **An evidence-first AI research workspace in development.** The current application is the v1 chat/RAG foundation, originally created for Sanber Code Bootcamp Batch 8. Parexa 2.0 is a staged modernization plan, not a completed rewrite.

## What works today

- Chat with Cerebras-hosted models, optional Google-grounded web browsing, and conversation persistence.
- Upload and retrieve from PDF, Markdown, and plain-text files. PDF pages use PyMuPDF text extraction with EasyOCR fallback.
- LlamaIndex retrieval backed by **Qdrant**. Google GenAI embeddings are supported; LM Studio can serve an optional local embedding model.
- Genesis optional draft -> parallel critics -> synthesis workflow.
- Flask API with a vanilla JavaScript/CSS client and optional upload progress reporting.

**Not yet implemented:** generalized image understanding, high-confidence source-span citation, persistent semantic/episodic memory, full local chat inference, and per-workspace context governance. These are proposals, not current features.

## Requirements

- Python 3.10 or newer. `uv` is recommended for lockfile-based installation.
- `CEREBRAS_API_KEY` and `GOOGLE_API_KEY`. The v1 application validates both at startup, including configurations that would not otherwise use both providers.
- GPU is optional, but EasyOCR and local embedding models can be resource intensive.

## Quick start

```bash
git clone https://github.com/RetrixAlfariz/Parexa.git
cd Parexa
cp .env.example .env  # Windows PowerShell: Copy-Item .env.example .env
# Edit .env and add the required API keys.
uv sync --locked
uv run python main.py
```

Open `http://127.0.0.1:5000`. Alternatively install the dependencies with `pip install -r requirements.txt` and run `python main.py`.

### Local and network safety

Parexa binds to `127.0.0.1` by default and runs without Flask debug mode. Set `PAREXA_HOST` or `FLASK_DEBUG=true` only when you understand the implications. **The HTTP API currently has no authentication or multiuser separation. Do not expose it directly to the internet or an untrusted LAN.**

Set `PAREXA_MAX_UPLOAD_MB` (default 25) to cap incoming requests. Your model credentials stay in `.env`, which should not be committed.

## Configuration

| Environment variable | Purpose | Default |
| --- | --- | --- |
| `CHAT_MODEL` | Cerebras chat model | `gpt-oss-120b` |
| `EMBEDDING_PROVIDER` | `google` or `lmstudio` | `google` |
| `EMBEDDING_MODEL` | Provider-specific embedding model | depends on provider |
| `LMSTUDIO_BASE_URL` | Local embedding API | `http://127.0.0.1:1234/v1` |
| `PAREXA_DATA_DIR` | Persistent runtime data directory | `storage/db` |
| `QDRANT_DB_PATH` | Embedded Qdrant data directory | within runtime directory |
| `QDRANT_URL` | Optional external Qdrant server | local embedded |
| `PAREXA_MAX_UPLOAD_MB` | Request-size limit in MiB | `25` |
| `PAREXA_HOST` | HTTP bind address | `127.0.0.1` |
| `FLASK_DEBUG` | Explicit debug flag | `false` |
| `INGEST_OCR_SPARSE_THRESHOLD` | Page text length below which OCR is attempted | `120` |
| `GENESIS_PARALLEL_CRITICS` | Critic worker limit | `3` |

See `.env.example` for health-check and worker-pool options.

## Evidence and data-safety behavior

- When a request selects uploaded files, document retrieval takes precedence over browsing.
- If retrieval errors out or yields no source nodes, Parexa reports a retrieval error (**HTTP 503**) instead of silently answering as a generic chat model.
- If the active embedding model's dimension is incompatible with an existing Qdrant collection, ingestion is blocked (**HTTP 409**) and the existing vectors are preserved.
- Oversized uploads return **HTTP 413** with a JSON error.
- PDF source files are currently deleted after indexing; their original bytes are **not** preserved for source replay. A provenance-preserving source store is a planned capability.

Changing an embedding model requires an explicit reindex/migration strategy. Do **not** delete your Qdrant storage to resolve a dimension mismatch without backing it up.

## Testing

```bash
uv sync --locked
uv run python -m unittest discover -s tests -v
python -m compileall -q main.py src/code/parexa_interface tests
```

These tests are baseline regression checks, not end-to-end retrieval or OCR benchmarks. Full offline and provider-backed evaluation remains future work.

## Research roadmap

Read [Parexa 2.0 modernization architecture](docs/PAREXA_2_MODERNIZATION.md) for the evidence contract, cross-project integration principles, phased implementation, evaluations, and UI direction.

## Known limitations

- Provider-specific configuration is loaded at startup; inference providers are not yet pluggable end to end.
- Full-corpus BM25 is not guaranteed with the current vector-store-backed LlamaIndex docstore, and hybrid retrieval must be measured rather than assumed.
- The current PDF ingestion does not preserve tables, layout boxes, diagrams, or original PDF bytes as reusable evidence objects.
- Genesis critics receive the draft and source labels, not verified source passages. It is an answer-refinement tool, not a proven fact-checker.
- No rate limits, authentication, or workspace-level isolation are implemented. Keep deployments local and trusted.

## License

A license file is not currently provided in this repository. Do not assume redistribution terms without establishing them.
