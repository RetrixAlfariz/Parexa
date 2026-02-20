from __future__ import annotations

import logging
from typing import List, Optional

from google.genai import types
from llama_index.core.llms import ChatMessage
from llama_index.llms.google_genai import GoogleGenAI

from ..config import settings

logger = logging.getLogger(__name__)

_BROWSING_LLM: Optional[GoogleGenAI] = None


def get_browsing_llm() -> GoogleGenAI:
    global _BROWSING_LLM
    if _BROWSING_LLM is None:
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        _BROWSING_LLM = GoogleGenAI(
            model=settings.browsing_model,
            api_key=settings.google_api_key,
            built_in_tool=grounding_tool,
        )
    return _BROWSING_LLM


def _extract_text(response: object) -> str:
    if response is None:
        return ""
    message = getattr(response, "message", None)
    if message is not None:
        content = getattr(message, "content", None)
        if content:
            return content
    response_text = getattr(response, "response", None)
    if isinstance(response_text, str) and response_text:
        return response_text
    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text
    return str(response)


def run_browsing_chat(message: str, history: Optional[List[ChatMessage]] = None) -> str:
    if not message:
        return ""

    llm = get_browsing_llm()
    history = history or []
    if history:
        try:
            response = llm.chat([*history, ChatMessage(role="user", content=message)])
            return _extract_text(response).strip()
        except Exception as exc:
            logger.warning(
                "Browsing chat failed, falling back to completion: %s", exc
            )

    response = llm.complete(message)
    return _extract_text(response).strip()


__all__ = ["get_browsing_llm", "run_browsing_chat"]
