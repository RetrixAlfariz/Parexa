from __future__ import annotations

import asyncio
from typing import Any, List, Sequence

from llama_index.core.base.embeddings.base import BaseEmbedding
from pydantic import Field, PrivateAttr


class LMStudioEmbedding(BaseEmbedding):
    """Embedding adapter for LM Studio's OpenAI-compatible /v1/embeddings API."""

    api_base: str = Field(default="http://127.0.0.1:1234/v1")
    api_key: str = Field(default="lm-studio", exclude=True)
    timeout: float = Field(default=90.0, gt=0.0)
    _client: Any = PrivateAttr(default=None)

    @classmethod
    def class_name(cls) -> str:
        return "LMStudioEmbedding"

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    def _embed_many(self, inputs: Sequence[str]) -> List[List[float]]:
        payload = [str(item or "") for item in inputs]
        if not payload:
            return []

        response = self._get_client().embeddings.create(
            model=self.model_name,
            input=payload,
        )
        data = sorted(
            list(getattr(response, "data", []) or []),
            key=lambda item: int(getattr(item, "index", 0)),
        )
        embeddings = [list(getattr(item, "embedding", []) or []) for item in data]
        if len(embeddings) != len(payload):
            raise RuntimeError(
                "LM Studio embedding response length mismatch: "
                f"expected {len(payload)}, got {len(embeddings)}"
            )
        return embeddings

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed_many([query])[0]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return await asyncio.to_thread(self._get_query_embedding, query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed_many([text])[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        batch_size = max(1, int(self.embed_batch_size or 100))
        vectors: List[List[float]] = []
        for start in range(0, len(texts), batch_size):
            vectors.extend(self._embed_many(texts[start : start + batch_size]))
        return vectors

