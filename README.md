# Parexa Research OS & Observatory

> **Local-first research operating system** for project workspaces, original-source preservation, notebooks, hypotheses, evidence tracking, document reading, source-aware answers and optional Genesis multi-agent review.

Parexa is a Flask + vanilla JavaScript application. It provides **model routing**, not a newly trained language model. The latest runtime supports **LM Studio, Ollama, and the original Cerebras integration** for chat. Embeddings and web-grounded browsing are configured separately.

## Quick start: run local chat without cloud credentials

Install Python 3.10+ and [uv](https://docs.astral.sh/uv/). Start LM Studio's local server and load any compatible **chat** model.

```bash
git clone https://github.com/RetrixAlfariz/Parexa.git
cd Parexa
cp .env.example .env
uv sync --locked
uv run python main.py
```

Windows PowerShell: `Copy-Item .env.example .env` instead of `cp`.

Open **http://127.0.0.1:5000/research** for the new research workstation, or **http://127.0.0.1:5000** for the existing AI chat. Select a loaded LM Studio model in the chat **Models** selector in the header or composer. The model list is obtained from the configured local `/v1/models` endpoint. If no model is found, start the server and load a model, then refresh.

**Ollama alternative:** start Ollama, pull a chat model, set `CHAT_PROVIDER=ollama` in `.env`, and select the model through the UI.

No cloud API keys are needed for **text chat** with a locally running chat model. Document RAG additionally requires the separately configured **embedding model**, even when chat is local.

## Research OS workspace (new)

The **Research OS** runs at `/research` and has eight working workspaces: Observatory overview, Projects, Source Vault, Experiments, Evidence Ledger, Notebook, Research Queue, and Systems & Storage. Research projects, notes, tasks, experiments, evidence, and SHA-256 source metadata persist in a local SQLite database, separate from the Qdrant vector index. PDF/TXT/Markdown originals are stored byte-for-byte using content-addressed deduplication and are downloadable and integrity-checkable. Storage-only vault uploads work without running a local LLM or embedding model; existing chat uploads are archived before RAG parsing and marked indexed after successful ingestion.

**Important distinction:** archiving a file in the vault does not index it for chat search. For now, reattach archived files through the chat uploader to run existing RAG. The original Observatory scratchpad still uses browser localStorage; the new **Notebook** persists its notes server-side. Evidence quotations and confidence labels are written by the researcher, not automatically citation-verified.

See [Research OS architecture, API and limitations](docs/RESEARCH_OS.md).

## What Parexa supports

- Chat through locally served LM Studio or Ollama models, with selectable per-request routes.
- Legacy Cerebras chat when configured, and an explicit opt-in for selecting cloud models alongside a local default.
- Document upload and RAG for PDF, Markdown and plain text; PyMuPDF with conditional EasyOCR.
- LlamaIndex + Qdrant document vectors, optional BM25 fusion and reranking.
- Selected-file RAG now returns an explicit error if retrieval fails instead of silently answering without evidence.
- Persistent conversation records and compact summaries.
- Optional Genesis multi-agent: draft, critics and synthesis, all using the selected chat provider.
- Parexa Observatory chat UI with source inspector and a **browser-only** scratchpad, plus the separate persistent Research OS notebook.

**Not implemented:** training a new Parexa foundation model, PDF page preview, auto-indexing sources uploaded only to the vault, source-span citation verification, full workspace backup, semantic long-term memory, streaming tokens to the browser, real GPU telemetry, or measured autonomous task routing.

## Model configuration

The new `.env.example` is local-first. Existing `.env` files without `CHAT_PROVIDER` retain the previous Cerebras default for backward compatibility.

| Variable | Description |
| --- | --- |
| `CHAT_PROVIDER` | `lmstudio`, `ollama`, or `cerebras` |
| `LMSTUDIO_CHAT_MODEL` / `OLLAMA_CHAT_MODEL` | Optional pinned local model; blank chooses the first discovered model |
| `LMSTUDIO_BASE_URL` / `OLLAMA_BASE_URL` | OpenAI-compatible server URL |
| `LOCAL_CHAT_CONTEXT_WINDOW` | Configured context budget reported to LlamaIndex |
| `LOCAL_CHAT_MAX_OUTPUT_TOKENS` | Per-call completion cap |
| `LOCAL_MAX_CONCURRENT_INFERENCE` | Bounded local inference concurrency; default 1 |
| `CHAT_ALLOW_CLOUD_SELECTION` | Explicitly permit additional cloud model selection when a key is provided |
| `EMBEDDING_PROVIDER` | `lmstudio` or `google` (independent of chat provider) |
| `EMBEDDING_MODEL` | Exact local or cloud embedding model name |
| `GOOGLE_API_KEY` | Needed for Google embeddings and optional Gemini web grounding |
| `CEREBRAS_API_KEY` | Needed for Cerebras chat, not for local inference |

Cloud selection does **not** occur automatically after local failure. Web browsing is an explicit cloud-grounding path when enabled and configured; it is not part of purely local chat.

See [the Research OS guide](docs/RESEARCH_OS.md) for persistent storage and researcher workflows, [the model runtime guide](docs/MODEL_RUNTIME.md) for privacy boundaries, troubleshooting and benchmarks, and [the Observatory UI guide](docs/OBSERVATORY_UI.md) for legacy chat UI features.

## Safety and storage

- The HTTP server binds to `127.0.0.1` by default because it currently has **no authentication**. Do not expose it on an untrusted network.
- Local model server URLs default to loopback only; remote use must be deliberately enabled and use HTTPS.
- When an embedding model's dimensionality differs from an existing Qdrant collection, Parexa rejects indexing rather than deleting vectors. **Reindexing is a deliberate future migration operation, not automatic.**
- New uploads retain original PDF/TXT/Markdown source bytes in the SHA-256 Research Vault. Pre-existing uploads from older versions cannot be retroactively recovered from vector metadata alone. The manual evidence ledger has source IDs and user-provided excerpts, not validated PDF coordinate spans.
- A local application does not guarantee fully offline behavior if cloud embeddings, Cerebras, or Google browsing are configured.

## Tests

```bash
python -m unittest discover -s tests -p 'test_model_gateway.py' -v
python -m unittest discover -s tests -p 'test_local_chat_llm.py' -v
node --check website/static/model_selector.js
python -m unittest discover -s tests -p 'test_research_*.py' -v
node --check website/static/research-os.js
```

GitHub Actions run pure-stdlib routing tests and a real HTTP integration using a fake local OpenAI-compatible model server; another workflow tests the Observatory interface in Chromium. These tests do **not** measure a real model's answer quality or performance.

## Research priorities

1. Provider reliability and inference timing (now).
2. Evaluated sparse/dense retrieval and source-span evidence.
3. Measured memory/context compilation and conditional agent routing.
4. Optional compact, specialized model research **only after** repeatable baselines.

## Origin

Originally the Sanber Code Bootcamp Batch 8 final project. Continued development focuses on an evidence-first, compute-conscious research application.

## Branch consolidation and workstation controls

The archived architecture study is at [Parexa 2.0 modernization](docs/PAREXA_2_MODERNIZATION.md). The active Observatory UI keeps the previous workspace experiment's functional shortcuts without loading its conflicting purple theme: `/` focuses the composer, `Alt+N` starts a new conversation, `Alt+Shift+B` toggles the sidebar, and `Alt+Shift+P` opens activity. The runtime ribbon reflects the current reasoning mode, web toggle, embedding monitor and request state. Unexpected API failures return generic error messages while full details remain in server logs.
