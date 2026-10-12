# Parexa model runtime — implementation and research plan

**Status:** the provider gateway and LlamaIndex-compatible local text adapter are implemented on the model-runtime branch. A newly trained Parexa LLM is **not** included.

## 1. Runtime architecture

```text
Observatory UI
    |
    | GET /api/models  -> enumerate configured LM Studio / Ollama models
    | POST /api/chat   -> model_provider + model (validated server-side)
    v
ModelGateway (explicit provider policy + capabilities + URL validation)
    |                     |
    | local               | cloud, configured and authorized
    v                     v
OpenAI-compatible         Cerebras LlamaIndex integration
LlamaIndex adapter        (legacy)
    |
    +-- LM Studio /v1/chat/completions
    +-- Ollama    /v1/chat/completions

        -> ordinary chat
        -> document RAG synthesis (Qdrant + LlamaIndex)
        -> Genesis draft / critics / synthesis

Separate:
    Embedding provider -> Google OR LM Studio embeddings
    Web grounding      -> Google GenAI (opt-in, cloud)
    Stored documents   -> Qdrant vectors and extracted text
```

The adapter preserves system/user/assistant roles rather than collapsing the entire conversation into a single prompt. It wraps the already-required Python OpenAI client and LlamaIndex `CustomLLM`. No new third-party Python dependencies were needed; `uv.lock` remains unchanged.

### Model discovery

`GET /api/models` returns identifiers, location (local/cloud), availability as reported by the selected server, and default route. It **never** returns API keys or model server URLs.

The gateway restricts local endpoints to loopback by default. A user may configure a trusted HTTPS remote model server with `PAREXA_ALLOW_REMOTE_MODEL_SERVER=true`. URLs cannot be supplied in browser requests. A malformed or unlisted model ID is rejected.

Cloud routes remain unavailable when `CHAT_ALLOW_CLOUD_SELECTION=false` and the legacy `CHAT_PROVIDER` is not Cerebras. This avoids automatic network egress on an otherwise local setup.

### Model parameters

The current text-only local adapter supports:

- Configurable model identifier, context window, maximum generated tokens, and inference timeout.
- A shared semaphore to bound local model calls; default concurrency one so Genesis critic fan-out does not overwhelm a consumer GPU.
- Chat completions, LlamaIndex completion wrappers, and a streaming adapter that is available to future server transport integration. Browser chat is **not** streaming yet.
- Per-request provider/model choice from the browser, with validated IDs.
- Explicit error returns on model outage. No silent fallbacks to a cloud LLM.

Model availability is not the same as inference success; some loaded local models can fail under memory pressure, context mismatch or unsupported options.

## 2. Fully local setup

1. Start the LM Studio model server (`http://127.0.0.1:1234/v1`) and load a chat model from the application's own model manager.
2. Copy `.env.example` to `.env`, select `CHAT_PROVIDER=lmstudio`, and leave `LMSTUDIO_CHAT_MODEL=` empty to discover a model.
3. For document RAG, also load an **embedding** model in LM Studio and set `EMBEDDING_PROVIDER=lmstudio` plus its exact `EMBEDDING_MODEL` identifier.
4. Run `uv sync --locked` and `uv run python main.py`.
5. Choose the local chat model from Parexa's new Model picker. No cloud credentials are required for local text-only chat and local-vector ingestion.

For Ollama chat, use `CHAT_PROVIDER=ollama`, pull a model using the Ollama CLI, and select it in the UI. The current RAG embedding adapter uses LM Studio or Google, **not Ollama embedding APIs**. That separate interface can be added later.

**If you only want to chat**, embeddings are not needed. If no local embedding model is loaded, PDF upload and RAG will fail, rather than magically generating vectors from the chat model.

## 3. Legacy cloud support

Existing installations that omit `CHAT_PROVIDER` continue with Cerebras. The cloud key is only checked when attempting cloud inference; it is no longer required simply to start a locally configured server.

To enable Cerebras alongside local models, set `CHAT_ALLOW_CLOUD_SELECTION=true` and `CEREBRAS_API_KEY`. This is an opt-in to external API traffic. Google web grounding remains a separate mode using `GOOGLE_API_KEY`. Avoid passing private documents to cloud providers without reviewing their data policies.

## 4. Known correctness limitations

- The LlamaIndex BM25 path may not engage if the reconstructed vector index lacks a populated docstore. Dense/lexical/hybrid retrieval quality still requires proper evaluation.
- PDF inputs retain extracted page references but not a high-fidelity byte-exact document registry. Citation navigation to physical pages is not implemented.
- Genesis critics now receive limited document excerpts, but this does not make their critiques deterministic factual verification.
- Local chat still uses ordinary response JSON; browser-visible token streaming is not yet implemented.
- The context-window setting reports the selected budget to LlamaIndex. It does not reconfigure the underlying model server. Set the correct context on the server.
- For a low-memory GPU, start with a model that your local server can actually load. Do not assume model size directly predicts answer accuracy or throughput.
- Embedding dimension mismatch blocks ingestion, without deleting existing collection points. A staged explicit reindex/migration workflow remains to be built.

## 5. Quantitative evaluation protocol

Before designing a custom Parexa model, benchmark baseline routes against a fixed test corpus.

Define end-to-end latency:

\[
T_{\rm answer}=T_{\rm parse}+T_{\rm embed}+T_{\rm retrieve}
               +T_{\rm rerank}+T_{\rm prefill}+T_{\rm decode}
               +T_{\rm orchestration}.
\]

Terms are stage costs and may be zero for ordinary chat. The terms are *measurement targets*, not measured values.

For local LLMs, record:
- Time to first token (TTFT), prefill tokens/second, decode tokens/second.
- Peak RAM/VRAM, context length, quantization, model ID/version, batch size.
- p50/p95 request latency, errors, energy if measured, and accuracy on frozen prompts.
- Separate 1-agent versus Genesis mode, and simple chat versus RAG.

For document tasks, record Recall@5, nDCG@10, exact source/page precision, supported versus unsupported answer detection, and token/call costs. Compare unchanged corpus and prompts across models.

Only claim one runtime/model is faster or better once these are actually measured on equivalent hardware.

## 6. Research directions after the gateway

1. **Context compiler:** keep chat history, retrieved passages, and user-approved persistent memory separate, with explicit budgets.
2. **Conditional compute:** route simple tasks to compact models and enable verification only when retrieval confidence or task complexity warrants it; measure routing errors.
3. **Retrieval model:** benchmark sparse/dense hybrid retrieval, reranking, domain-specialized embeddings, and Matryoshka dimensions if the training/model supports it.
4. **Multimodal parsing:** integrate typed document blocks from Ortheon-compatible perception only after anchored bbox/page evidence tests.
5. **Future proprietary Parexa models:** feasible only after a dataset license audit, training objective, baseline, test split and hardware budget. A custom model is not synonymous with a better model.

## Reference APIs

- [LM Studio OpenAI-compatible endpoints](https://lmstudio.ai/docs/developer/openai-compat)
- [Ollama OpenAI-compatible endpoints](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx)
- [LlamaIndex CustomLLM](https://developers.llamaindex.ai/python/framework-api-reference/llms/custom_llm/)
