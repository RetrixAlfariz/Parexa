from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List

from ..config import settings
from ..storage.conversation_store import (
    count_turns,
    fetch_recent_turns,
    get_summary_state,
    load_unsummarized_turns,
    save_summary_state,
)


logger = logging.getLogger(__name__)


def normalize_history(
    history: Iterable[Dict[str, str]],
    *,
    message_limit: int,
    summary_intro_prefix: str,
) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = (entry.get("role") or "").strip().lower()
        if role not in {"user", "model", "assistant"}:
            continue
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        if role == "user" and text.startswith(summary_intro_prefix):
            continue
        items.append({"role": role, "text": text})

    if message_limit > 0 and len(items) > message_limit:
        items = items[-message_limit:]
    return items


def build_compact_history(
    conversation_id: str,
    history: Iterable[Dict[str, str]],
) -> List[Dict[str, str]]:
    summary_settings = settings.summary
    cleaned = normalize_history(
        history,
        message_limit=summary_settings.context_message_limit
        or (summary_settings.context_turn_limit * 2),
        summary_intro_prefix=summary_settings.intro_prefix,
    )

    if not cleaned and conversation_id:
        cleaned = fetch_recent_turns(
            conversation_id, summary_settings.context_turn_limit
        )

    summary_text, _ = get_summary_state(conversation_id)
    if summary_text:
        intro = f"{summary_settings.intro_prefix}\n{summary_text}"
        cleaned = [{"role": "user", "text": intro}, *cleaned]

    return cleaned


def _chat_message(role: str, content: str) -> Any:
    from llama_index.core.llms import ChatMessage

    return ChatMessage(role=role, content=content)


def refresh_summary(llm: Any, conversation_id: str) -> None:
    if not conversation_id:
        return

    summary_text, last_turn_id = get_summary_state(conversation_id)
    pending_turns = load_unsummarized_turns(conversation_id, last_turn_id)
    if not pending_turns:
        return

    summary_settings = settings.summary
    total_turns = count_turns(conversation_id)

    should_update = False
    if summary_text:
        should_update = len(pending_turns) >= summary_settings.min_new_turns
    else:
        if (
            total_turns >= summary_settings.trigger_turns
            and len(pending_turns) >= summary_settings.min_new_turns
        ):
            should_update = True

    if not should_update:
        return

    prompt_lines: List[str] = []
    if summary_text:
        prompt_lines.append("Ringkasan percakapan saat ini:")
        prompt_lines.append(summary_text)
        prompt_lines.append("")
    prompt_lines.append("Pesan terbaru:")
    for _, user_text, ai_text in pending_turns:
        user_text = (user_text or "").strip()
        ai_text = (ai_text or "").strip()
        if user_text:
            prompt_lines.append(f"Pengguna: {user_text}")
        if ai_text:
            prompt_lines.append(f"AI: {ai_text}")
    prompt_lines.append(
        "\nPerbarui ringkasan agar mencakup fakta penting, keputusan, dan konteks yang dibutuhkan di percakapan selanjutnya. Gunakan bahasa Indonesia, maksimal 8 bullet atau 120 kata."
    )

    try:
        messages = [
            _chat_message(
                role="user",
                content="\n".join(prompt_lines),
            )
        ]
        
        response = llm.chat(messages)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Gagal memperbarui ringkasan %s: %s", conversation_id, exc)
        return

    new_summary = (response.message.content or "").strip()
    if not new_summary:
        return

    save_summary_state(
        conversation_id,
        new_summary,
        pending_turns[-1][0],
        max_chars=settings.summary.max_chars,
    )


__all__ = ["build_compact_history", "normalize_history", "refresh_summary"]
