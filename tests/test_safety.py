"""Regression tests for data safety and evidence-first retrieval."""
from __future__ import annotations

import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "code"))
os.environ.setdefault("CEREBRAS_API_KEY", "test-cerebras-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")

from parexa_interface.services import chat_service, ingestion_service  # noqa: E402
from parexa_interface.app import app  # noqa: E402


class TestEmbeddingSafety(unittest.TestCase):
    def test_dimension_mismatch_does_not_reset_collection(self) -> None:
        with (
            patch.object(ingestion_service, "_resolve_embedding_dimension", return_value=768),
            patch.object(ingestion_service, "_get_collection_vector_size", return_value=3072),
        ):
            with self.assertRaises(ingestion_service.EmbeddingDimensionMismatchError) as ctx:
                ingestion_service._ensure_collection_dimension("uploaded_files", object())
        self.assertIn("preserved", str(ctx.exception))
        self.assertIn("3072", str(ctx.exception))

    def test_compatible_and_new_collection(self) -> None:
        for size in (768, None):
            with (
                patch.object(ingestion_service, "_resolve_embedding_dimension", return_value=768),
                patch.object(ingestion_service, "_get_collection_vector_size", return_value=size),
            ):
                self.assertIsNone(ingestion_service._ensure_collection_dimension("uploaded_files", object()))


class TestRetrievalSafety(unittest.TestCase):
    def test_rag_error_never_falls_back_to_chat(self) -> None:
        class DummyLLM:
            calls = 0
            def chat(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("Ungrounded fallback called")
        dummy = DummyLLM()
        with (
            patch.object(chat_service, "_new_llm", return_value=dummy),
            patch.object(chat_service, "build_compact_history", return_value=[]),
            patch.object(chat_service, "persist_turn") as persist,
            patch.object(ingestion_service, "get_index_for_collection", side_effect=RuntimeError("Qdrant unavailable")),
        ):
            with self.assertRaises(chat_service.ChatRetrievalUnavailable):
                chat_service.handle_chat({"message": "What does the paper say?", "file_ids": ["file-123"]})
            self.assertEqual(dummy.calls, 0)
            persist.assert_not_called()


class TestHTTPBasics(unittest.TestCase):
    def test_oversized_upload_is_413_json(self) -> None:
        with app.test_client() as client, patch.dict(app.config, {"MAX_CONTENT_LENGTH": 1}):
            result = client.post(
                "/api/upload",
                data={"file": (io.BytesIO(b"example" * 90), "sample.pdf")},
                content_type="multipart/form-data",
            )
        self.assertEqual(result.status_code, 413)
        self.assertIn("error", result.get_json())


if __name__ == "__main__":
    unittest.main()
