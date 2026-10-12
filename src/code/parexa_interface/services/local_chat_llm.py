"""LlamaIndex-compatible text chat via LM Studio or Ollama /v1/chat/completions.

No framework or model downloads: the existing installed OpenAI SDK speaks to
an independently running local server. The provider URL is validated upstream.
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from llama_index.core.llms import (
    ChatMessage,
    ChatResponse,
    ChatResponseGen,
    CompletionResponse,
    CompletionResponseGen,
    CustomLLM,
    LLMMetadata,
    MessageRole,
)
from llama_index.core.llms.callbacks import llm_chat_callback, llm_completion_callback
from pydantic import Field, PrivateAttr

from .model_gateway import ModelUnavailableError, ModelRoute

logger = logging.getLogger(__name__)

# A single shared semaphore protects small consumer GPUs from Genesis fan-out.
# Can be raised explicitly by the user after measuring local inference load.
_semaphore_lock = threading.Lock()
_semaphores: dict[int, threading.BoundedSemaphore] = {}


@contextmanager
def _inference_slot(max_concurrency: int, timeout: float) -> Iterator[None]:
    count = max(1, min(16, int(max_concurrency)))
    with _semaphore_lock:
        semaphore = _semaphores.get(count)
        if semaphore is None:
            semaphore = threading.BoundedSemaphore(count)
            _semaphores[count] = semaphore
    if not semaphore.acquire(timeout=max(1.0, timeout)):
        raise ModelUnavailableError(
            "The local model is busy. Retry after the current request finishes."
        )
    try:
        yield
    finally:
        semaphore.release()


class LocalChatLLM(CustomLLM):
    """Text-only LlamaIndex adapter retaining system/user/assistant chat roles."""

    model_name: str = Field(default="local")
    api_base: str = Field(default="http://127.0.0.1:1234/v1")
    api_key: str = Field(default="lm-studio", exclude=True, repr=False)
    context_window: int = Field(default=8192, gt=512)
    num_output: int = Field(default=2048, gt=0)
    request_timeout: float = Field(default=120.0, gt=0)
    concurrency_limit: int = Field(default=1, ge=1, le=16)
    _client: Any = PrivateAttr(default=None)

    @classmethod
    def class_name(cls) -> str:
        return "parexa_local_chat"

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            model_name=self.model_name,
            context_window=self.context_window,
            num_output=self.num_output,
            is_chat_model=True,
            is_function_calling_model=False,
        )

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=self.api_base,
                api_key=self.api_key,
                timeout=self.request_timeout,
                max_retries=0,
            )
        return self._client

    @staticmethod
    def _message_payload(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
        payload: list[dict[str, str]] = []
        for item in messages:
            role = getattr(item.role, "value", item.role)
            normalized = "assistant" if role in {"model", "assistant"} else str(role).lower()
            if normalized not in {"system", "user", "assistant"}:
                continue
            content = item.content
            # This adapter is intentionally text only. Never serialize image blocks
            # into str() and pretend that the model understood visual evidence.
            if not isinstance(content, str):
                raise ModelUnavailableError("This local chat adapter supports text input only.")
            payload.append({"role": normalized, "content": content})
        return payload

    def _run(self, messages: Sequence[ChatMessage], *, stream: bool = False) -> Any:
        payload = self._message_payload(messages)
        if not payload:
            raise ModelUnavailableError("Cannot send an empty conversation to a local model.")
        try:
            return self._get_client().chat.completions.create(
                model=self.model_name,
                messages=payload,
                max_tokens=self.num_output,
                stream=stream,
            )
        except Exception as exc:
            logger.warning("Local inference failed for %s", self.model_name, exc_info=True)
            raise ModelUnavailableError(
                "Local model inference failed. Confirm the selected model is loaded and the server is running."
            ) from exc

    @llm_chat_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        with _inference_slot(self.concurrency_limit, self.request_timeout):
            result = self._run(messages)
            content = result.choices[0].message.content or ""
        if not isinstance(content, str) or not content.strip():
            raise ModelUnavailableError("The selected local model returned no textual answer.")
        return ChatResponse(
            message=ChatMessage(role=MessageRole.ASSISTANT, content=content),
            raw=result,
        )

    @llm_chat_callback()
    def stream_chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponseGen:
        def generator() -> ChatResponseGen:
            total = ""
            with _inference_slot(self.concurrency_limit, self.request_timeout):
                response = self._run(messages, stream=True)
                try:
                    for item in response:
                        delta = item.choices[0].delta.content or ""
                        if not isinstance(delta, str) or not delta:
                            continue
                        total += delta
                        yield ChatResponse(
                            message=ChatMessage(role=MessageRole.ASSISTANT, content=total),
                            delta=delta,
                        )
                finally:
                    close = getattr(response, "close", None)
                    if callable(close):
                        close()
        return generator()

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        answer = self.chat([ChatMessage(role=MessageRole.USER, content=prompt)], **kwargs)
        return CompletionResponse(text=answer.message.content or "")

    @llm_completion_callback()
    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        def generator() -> CompletionResponseGen:
            for item in self.stream_chat([ChatMessage(role=MessageRole.USER, content=prompt)], **kwargs):
                yield CompletionResponse(text=item.message.content or "", delta=item.delta)
        return generator()

    # Compatibility with CustomLLM versions that declare these hooks abstract.
    def _complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        return self.complete(prompt, **kwargs)

    def _stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        return self.stream_complete(prompt, **kwargs)


def build_local_llm(route: ModelRoute) -> LocalChatLLM:
    if not route.local or route.provider not in {"lmstudio", "ollama"} or not route.base_url:
        raise ModelUnavailableError("This route is not a configured local chat provider.")
    return LocalChatLLM(
        model_name=route.model,
        api_base=route.base_url,
        api_key=route.api_key,
        context_window=route.context_window,
        num_output=route.max_tokens,
        request_timeout=route.timeout_sec,
        concurrency_limit=route.max_concurrency,
    )
