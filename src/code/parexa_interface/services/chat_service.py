from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import uuid
from typing import Any, Dict, List, Optional

from ..config import settings
from ..storage.conversation_store import (
    delete_conversation as delete_conversation_record,
    fetch_history as fetch_full_history,
    list_conversations,
    persist_turn,
)
from .executor_pool import run_io_bound
from .summary import build_compact_history, refresh_summary

logger = logging.getLogger(__name__)


class ChatServiceError(Exception):
    """Domain error for chat service operations."""


class ChatRetrievalUnavailable(ChatServiceError):
    """A document-based answer cannot be safely grounded."""


_HALLUCINATION_GUARDRAIL = (
    "You are a careful assistant.\n"
    "Do not present guesses, assumptions, or fabricated details as facts.\n"
    "If information is missing or uncertain, say that explicitly and ask for clarification when useful.\n"
    "Do not invent citations, file/page references, links, tool outputs, or actions you did not actually perform."
)


def _chat_message(role: str, content: str) -> Any:
    from llama_index.core.llms import ChatMessage

    return ChatMessage(role=role, content=content)


def _new_llm() -> Any:
    from llama_index.llms.cerebras import Cerebras

    return Cerebras(model=settings.chat_model, api_key=settings.api_key)


def _to_chat_messages(history: List[Dict[str, str]]) -> List[Any]:
    items: List[Any] = []
    for entry in history:
        role = (entry.get("role") or "").strip()
        text = (entry.get("text") or "").strip()
        if role in {"user", "assistant", "model"} and text:
            if role == "model":
                role = "assistant"
            items.append(_chat_message(role=role, content=text))
    return items


def _coerce_bool(value: Optional[Any]) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
            "enable",
            "enabled",
        }
    return False


def _extract_reply(response: Any) -> str:
    if response is None:
        return ""
    response_text = getattr(response, "response", None)
    if isinstance(response_text, str) and response_text:
        return response_text
    message = getattr(response, "message", None)
    if message is not None:
        content = getattr(message, "content", None)
        if content:
            return content
    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text
    return ""


def _build_system_messages(assistant_instructions: str) -> List[Any]:
    messages = [_chat_message(role="system", content=_HALLUCINATION_GUARDRAIL)]
    if assistant_instructions:
        messages.append(
            _chat_message(
                role="system",
                content=(
                    "Additional assistant instructions (follow these unless they conflict "
                    "with higher-priority system policies):\n"
                    f"{assistant_instructions}"
                ),
            )
        )
    return messages


def _collect_selected_file_ids(raw_file_ids: Any, raw_files: Any) -> List[str]:
    collected: List[str] = []
    if isinstance(raw_file_ids, list):
        for item in raw_file_ids:
            value = str(item or "").strip()
            if value:
                collected.append(value)
    if isinstance(raw_files, list):
        for item in raw_files:
            if not isinstance(item, dict):
                continue
            value = str(item.get("id") or "").strip()
            if value:
                collected.append(value)
    return list(dict.fromkeys(collected))


def _node_type_to_source_type(node_type: str) -> str:
    value = (node_type or "").strip().lower()
    if value == "image_region":
        return "image_region"
    if value in {"page_visual_summary", "image_visual_summary"}:
        return "visual"
    return "text"


def handle_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    message = (payload.get("message") or "").strip()
    if not message:
        raise ChatServiceError("Message is required.")

    raw_history = payload.get("history")
    history_payload: List[Dict[str, str]] = (
        raw_history if isinstance(raw_history, list) else []
    )
    conversation_id = (payload.get("conversation_id") or "").strip()
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    history_for_model = build_compact_history(conversation_id, history_payload)

    file_ids = payload.get("file_ids", [])
    files = payload.get("files", [])
    selected_file_ids = _collect_selected_file_ids(file_ids, files)

    use_browsing_value = payload.get("use_browsing")
    if use_browsing_value is None:
        use_browsing_value = payload.get("browsing")
    if use_browsing_value is None:
        use_browsing_value = payload.get("web")
    use_browsing = _coerce_bool(use_browsing_value)

    assistant_instructions = (payload.get("assistant_instructions") or "").strip()
    if len(assistant_instructions) > 2000:
        assistant_instructions = assistant_instructions[:2000]

    raw_agent = payload.get("agent")
    if raw_agent is None:
        raw_agent = payload.get("agent_mode")
    if raw_agent is None:
        raw_agent = payload.get("mode")
    agent = str(raw_agent or "").strip().lower()
    is_genesis = agent in {"genesis", "multi-agent", "multi_agent", "multi"}

    include_trace_value = payload.get("include_trace")
    if include_trace_value is None:
        include_trace_value = payload.get("trace")
    if include_trace_value is None:
        include_trace_value = payload.get("thinking")
    include_trace = _coerce_bool(include_trace_value)

    base_history = _to_chat_messages(history_for_model)
    system_messages = _build_system_messages(assistant_instructions)
    chat_history = [*system_messages, *base_history]

    use_browsing_requested = use_browsing
    execution_mode = "chat"
    if selected_file_ids:
        execution_mode = "rag"
        if use_browsing_requested:
            logger.info(
                "RAG override: uploaded files attached, browsing disabled for this request."
            )
        use_browsing = False
    elif use_browsing_requested:
        execution_mode = "browsing"

    logger.info(
        "Chat execution mode=%s selected_file_ids_count=%s use_browsing_requested=%s",
        execution_mode,
        len(selected_file_ids),
        use_browsing_requested,
    )
    execution_meta: Dict[str, Any] = {
        "mode": execution_mode,
        "requested_browsing": use_browsing_requested,
        "effective_browsing": execution_mode == "browsing",
        "provider": "",
        "model": "",
    }

    sources: List[Dict[str, str]] = []
    reply = ""
    llm: Any = None
    activity: Dict[str, Any] | None = None
    trace: list[dict[str, str]] | None = None

    if execution_mode == "rag":
        execution_meta["provider"] = "cerebras"
        execution_meta["model"] = settings.chat_model
        llm = _new_llm()
        from llama_index.core.postprocessor import SentenceTransformerRerank
        from llama_index.core.query_engine import RetrieverQueryEngine
        from llama_index.core.retrievers import QueryFusionRetriever, VectorIndexRetriever
        from llama_index.core.vector_stores.types import (
            FilterCondition,
            MetadataFilter,
            MetadataFilters,
        )
        from llama_index.retrievers.bm25 import BM25Retriever

        from .ingestion_service import get_index_for_collection

        try:
            index = get_index_for_collection("uploaded_files")
            metadata_filters = MetadataFilters(
                filters=[
                    MetadataFilter(key="file_id", value=file_id)
                    for file_id in selected_file_ids
                ],
                condition=FilterCondition.OR,
            )
            vector_retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=10,
                filters=metadata_filters,
            )
            retriever = vector_retriever
            doc_count = (
                len(index.docstore.docs) if hasattr(index.docstore, "docs") else 0
            )

            if doc_count > 0:
                try:
                    filtered_nodes = []
                    if hasattr(index.docstore, "docs"):
                        for node in index.docstore.docs.values():
                            metadata = getattr(node, "metadata", {}) or {}
                            node_file_id = str(metadata.get("file_id") or "").strip()
                            if node_file_id in selected_file_ids:
                                filtered_nodes.append(node)

                    if filtered_nodes:
                        bm25_retriever = BM25Retriever.from_defaults(
                            nodes=filtered_nodes,
                            similarity_top_k=10,
                        )
                    else:
                        bm25_retriever = BM25Retriever.from_defaults(
                            docstore=index.docstore,
                            similarity_top_k=10,
                            filters=metadata_filters,
                        )

                    retriever = QueryFusionRetriever(
                        [vector_retriever, bm25_retriever],
                        similarity_top_k=20,
                        num_queries=1,
                        mode="reciprocal_rerank",
                        use_async=False,
                        verbose=False,
                    )
                except Exception as bm25_err:
                    logger.warning(
                        "Failed to initialize BM25, falling back to vector-only: %s",
                        bm25_err,
                    )

            try:
                reranker = SentenceTransformerRerank(
                    model="cross-encoder/ms-marco-MiniLM-L-6-v2",
                    top_n=5,
                )
                postprocessors = [reranker]
            except Exception as rerank_err:
                logger.warning("Failed to initialize reranker: %s", rerank_err)
                postprocessors = []

            system_prompt = (
                f"{_HALLUCINATION_GUARDRAIL}\n\n"
                "Use ONLY the provided context from uploaded files to answer. "
                "If context is insufficient, explicitly say the answer is not available in the provided files. "
                "When you cite, use this format: [Source: file_name p.X | type]. "
                "Type must be one of text, visual, image_region. "
                "If the answer is not in the context, say so."
            )
            if assistant_instructions:
                system_prompt = (
                    f"{system_prompt}\n\nAdditional assistant instructions:\n{assistant_instructions}"
                )
            query_engine = RetrieverQueryEngine.from_args(
                retriever=retriever,
                node_postprocessors=postprocessors,
                llm=llm,
                system_prompt=system_prompt,
            )
            response = query_engine.query(message)
            if not getattr(response, "source_nodes", None):
                raise ChatRetrievalUnavailable(
                    "No verifiable passages were retrieved from the selected documents. "
                    "No document-based answer was generated."
                )

            if hasattr(response, "source_nodes") and response.source_nodes:
                seen_sources: set[tuple[str, str, str]] = set()
                for node in response.source_nodes:
                    metadata = node.metadata or {}
                    file_name = str(metadata.get("file_name", "Unknown"))
                    page_num = str(metadata.get("page_label", "") or "")
                    source_type = _node_type_to_source_type(
                        str(metadata.get("node_type", ""))
                    )
                    source_key = (file_name, page_num, source_type)
                    if source_key in seen_sources:
                        continue
                    seen_sources.add(source_key)
                    source_info: Dict[str, str] = {"file": file_name, "type": source_type}
                    if page_num:
                        source_info["page"] = page_num
                    sources.append(source_info)
            reply = _extract_reply(response)
        except ChatRetrievalUnavailable:
            raise
        except Exception as exc:
            logger.exception("RAG retrieval failed; refusing ungrounded fallback")
            raise ChatRetrievalUnavailable(
                "Document retrieval is unavailable. The selected files were not used "
                "to generate an answer. Check the embedding and retrieval configuration."
            ) from exc
    elif execution_mode == "browsing":
        execution_meta["provider"] = "gemini"
        execution_meta["model"] = settings.browsing_model
        from .browsing_service import run_browsing_chat

        try:
            reply = run_browsing_chat(message, chat_history)
        except Exception as exc:
            logger.error(
                "Browsing failed, falling back to standard chat: %s", exc, exc_info=True
            )
            llm = _new_llm()
            chat_history.append(_chat_message(role="user", content=message))
            response = llm.chat(chat_history)
            reply = _extract_reply(response)
            execution_meta["fallback"] = {
                "reason": "browsing_error",
                "from_provider": "gemini",
                "from_model": settings.browsing_model,
                "to_provider": "cerebras",
                "to_model": settings.chat_model,
            }
            execution_meta["provider"] = "cerebras"
            execution_meta["model"] = settings.chat_model
    else:
        execution_meta["provider"] = "cerebras"
        execution_meta["model"] = settings.chat_model
        llm = _new_llm()
        chat_history.append(_chat_message(role="user", content=message))
        response = llm.chat(chat_history)
        reply = _extract_reply(response)

    if is_genesis:
        draft_reply = (reply or "").strip()
        if draft_reply:
            raw_genesis_config = payload.get("genesis_config") or {}
            critics_config: list[dict[str, str]] = []
            synthesizer_instructions = ""

            if isinstance(raw_genesis_config, dict):
                raw_critics = raw_genesis_config.get("critics")
                if isinstance(raw_critics, list):
                    for item in raw_critics:
                        if not isinstance(item, dict):
                            continue
                        name = str(item.get("name") or "").strip()
                        if not name:
                            name = f"Critic {len(critics_config) + 1}"
                        instructions = str(item.get("instructions") or "").strip()
                        critics_config.append(
                            {"name": name[:60], "instructions": instructions[:2000]}
                        )
                raw_synth = raw_genesis_config.get("synthesizer")
                if isinstance(raw_synth, dict):
                    synthesizer_instructions = str(
                        raw_synth.get("instructions") or ""
                    ).strip()[:2000]

            if not critics_config:
                critics_config = [
                    {
                        "name": "Critic",
                        "instructions": (
                            "Critique the draft for correctness and completeness. "
                            "Point out missing assumptions, edge cases, and unclear parts. "
                            "Keep it concise and actionable."
                        ),
                    }
                ]
            critics_config = critics_config[:5]
            if not synthesizer_instructions:
                synthesizer_instructions = (
                    "Rewrite the draft into a clear final answer. Apply the critique. "
                    "Keep important details and be concise."
                )

            sources_lines = []
            for source in sources:
                if not isinstance(source, dict):
                    continue
                file_name = source.get("file") or "Unknown"
                page = source.get("page")
                if page:
                    sources_lines.append(f"{file_name} (p.{page})")
                else:
                    sources_lines.append(str(file_name))
            sources_text = "\n".join(sources_lines) if sources_lines else "(none)"
            draft_for_prompt = draft_reply[:8000]

            def _system_with_instructions(prefix: str, extra: str = "") -> str:
                parts = [_HALLUCINATION_GUARDRAIL, prefix]
                if assistant_instructions:
                    parts.append(
                        f"Additional assistant instructions:\n{assistant_instructions}"
                    )
                if extra:
                    parts.append(f"Agent-specific instructions:\n{extra}")
                return "\n\n".join(parts)

            def _run_critic(critic: dict[str, str]) -> tuple[str, str]:
                critic_name = (critic.get("name") or "Critic").strip()[:60]
                critic_instructions = (
                    critic.get("instructions") or ""
                ).strip()[:2000]
                critic_messages = [
                    _chat_message(
                        role="system",
                        content=_system_with_instructions(
                            f"You are {critic_name} (Critic), part of a multi-agent system. "
                            "Critique the draft answer for correctness, completeness, and alignment with the user's request. "
                            "Output a concise bullet list of improvements. Do NOT rewrite the full answer.",
                            critic_instructions,
                        ),
                    ),
                    *base_history,
                    _chat_message(
                        role="user",
                        content=(
                            f"User request:\n{message}\n\n"
                            f"Draft answer:\n{draft_for_prompt}\n\n"
                            f"Sources:\n{sources_text}\n\n"
                            "Give critique and concrete improvements."
                        ),
                    ),
                ]
                critic_llm = _new_llm()
                critique = _extract_reply(critic_llm.chat(critic_messages)).strip()
                return critic_name, critique

            try:
                critiques: list[tuple[str, str]] = []
                activity_steps: list[dict[str, str]] = [
                    {
                        "title": "Genesis • Draft",
                        "detail": draft_reply[:700],
                        "status": "success",
                    }
                ]
                if include_trace:
                    trace = [
                        {"title": "Genesis • Draft", "content": draft_reply[:12000]}
                    ]

                critic_workers = max(
                    1,
                    min(
                        len(critics_config),
                        settings.genesis_parallel_critics,
                    ),
                )
                with ThreadPoolExecutor(max_workers=critic_workers) as pool:
                    futures = [pool.submit(_run_critic, critic) for critic in critics_config]
                    for future in futures:
                        critic_name, critique = future.result()
                        critiques.append((critic_name, critique))
                        activity_steps.append(
                            {
                                "title": f"Genesis • Critic • {critic_name}",
                                "detail": (critique or "(no critique)")[:900],
                                "status": "warn" if critique else "success",
                            }
                        )
                        if trace is not None:
                            trace.append(
                                {
                                    "title": f"Genesis • Critic • {critic_name}",
                                    "content": (critique or "(no critique)")[:12000],
                                }
                            )

                combined_critique = "\n\n".join(
                    [
                        f"{name}:\n{critique[:1200] if critique else '(no critique)'}"
                        for name, critique in critiques
                    ]
                )[:8000]

                synth_messages = [
                    _chat_message(
                        role="system",
                        content=_system_with_instructions(
                            "You are Genesis (Synthesizer), part of a multi-agent system. "
                            "Rewrite the draft into the best possible final answer using the critique. "
                            "Output the final answer only.",
                            synthesizer_instructions,
                        ),
                    ),
                    *base_history,
                    _chat_message(
                        role="user",
                        content=(
                            f"User request:\n{message}\n\n"
                            f"Draft answer:\n{draft_for_prompt}\n\n"
                            f"Critique:\n{combined_critique or '(none)'}\n\n"
                            f"Sources:\n{sources_text}\n\n"
                            "Now write the final answer. If sources are present, keep citations in [Source: Filename] style."
                        ),
                    ),
                ]
                synth_llm = _new_llm()
                refined = _extract_reply(synth_llm.chat(synth_messages)).strip()
                if refined:
                    reply = refined

                activity_steps.append(
                    {
                        "title": "Genesis • Final",
                        "detail": "Refined answer generated.",
                        "status": "success",
                    }
                )
                llm = synth_llm
                activity = {"status": "Ready", "steps": activity_steps}
            except Exception as exc:
                logger.warning(
                    "Genesis multi-agent refinement failed: %s", exc, exc_info=True
                )
                trace = None
                activity = {
                    "status": "Error",
                    "steps": [
                        {
                            "title": "Genesis • Error",
                            "detail": str(exc),
                            "status": "error",
                        }
                    ],
                }

    reply = reply.strip() or "Model tidak memberikan jawaban."
    persist_turn(
        conversation_id,
        (("user", message), ("model", reply)),
        paired=(message, reply),
        files=files,
    )

    summary_llm = llm or _new_llm()
    try:
        refresh_summary(summary_llm, conversation_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "Gagal menjalankan pembaruan ringkasan %s: %s", conversation_id, exc
        )

    response_payload: Dict[str, Any] = {
        "reply": reply,
        "conversation_id": conversation_id,
        "sources": sources,
        "meta": {"execution": execution_meta},
    }
    if activity:
        response_payload["activity"] = activity
    if trace:
        response_payload["trace"] = trace
    if agent:
        response_payload["agent"] = agent
    return response_payload


async def handle_chat_async(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await run_io_bound(handle_chat, payload)


def get_conversation_history(conversation_id: str) -> Dict[str, Any]:
    conversation_id = conversation_id.strip()
    if not conversation_id:
        raise ChatServiceError("Conversation ID is required.")
    history = fetch_full_history(conversation_id)
    return {"conversation_id": conversation_id, "history": history}


def get_conversation_list(limit: int) -> Dict[str, Any]:
    items = list_conversations(limit)
    return {"conversations": items}


def delete_conversation(conversation_id: str) -> Dict[str, Any]:
    conversation_id = conversation_id.strip()
    if not conversation_id:
        raise ChatServiceError("Conversation ID is required.")

    deleted = delete_conversation_record(conversation_id)
    if not deleted:
        raise ChatServiceError("Conversation tidak ditemukan.")
    return {"deleted": True, "conversation_id": conversation_id}


__all__ = [
    "ChatServiceError",
    "ChatRetrievalUnavailable",
    "handle_chat",
    "handle_chat_async",
    "get_conversation_history",
    "get_conversation_list",
    "delete_conversation",
]
