"""Regression tests forward-ported from the original safety-foundation branch.

Run with the lightweight runtime integrations installed, no model/API connection.
"""
from __future__ import annotations

import io
import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "code"))

from parexa_interface.services import chat_service, ingestion_service  # noqa: E402
from parexa_interface.services.model_gateway import ModelRoute  # noqa: E402

app_module = importlib.import_module("parexa_interface.app")
app = app_module.app


class TestEmbeddingSafety(unittest.TestCase):
    def test_dimension_mismatch_preserves_existing_vectors(self):
        with (
            patch.object(ingestion_service, "_resolve_embedding_dimension", return_value=768),
            patch.object(ingestion_service, "_get_collection_vector_size", return_value=3072),
        ):
            with self.assertRaises(ingestion_service.EmbeddingDimensionMismatchError) as error:
                ingestion_service._ensure_collection_dimension("uploaded_files", object())
        self.assertIn("preserved", str(error.exception).lower())
        self.assertIn("3072", str(error.exception))

    def test_compatible_or_uninitialized_collection(self):
        for old_size in (768, None):
            with (
                patch.object(ingestion_service, "_resolve_embedding_dimension", return_value=768),
                patch.object(ingestion_service, "_get_collection_vector_size", return_value=old_size),
            ):
                self.assertIsNone(
                    ingestion_service._ensure_collection_dimension("uploaded_files", object())
                )


class TestRetrievalSafety(unittest.TestCase):
    def test_retrieval_outage_does_not_invoke_ungrounded_chat(self):
        class DummyLLM:
            calls = 0

            def chat(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("Untrusted plain-chat fallback must never execute")

        model = DummyLLM()
        route = ModelRoute(
            provider="lmstudio",
            model="fake-local-model",
            local=True,
            base_url="http://127.0.0.1:1234/v1",
        )
        with (
            patch.object(chat_service, "resolve_route", return_value=route),
            patch.object(chat_service, "_new_llm", return_value=model),
            patch.object(chat_service, "build_compact_history", return_value=[]),
            patch.object(chat_service, "persist_turn") as persist,
            patch.object(
                ingestion_service, "get_index_for_collection",
                side_effect=RuntimeError("Qdrant index unavailable")
            ),
        ):
            with self.assertRaises(chat_service.ChatRetrievalUnavailable):
                chat_service.handle_chat({
                    "message": "Explain section 4 of my paper",
                    "file_ids": ["fixture-file-id"],
                })
            persist.assert_not_called()
            self.assertEqual(model.calls, 0)


class TestHTTPErrorHandling(unittest.TestCase):
    def test_upload_request_limit_is_json_413(self):
        with app.test_client() as client, patch.dict(app.config, {"MAX_CONTENT_LENGTH": 1}):
            response = client.post(
                "/api/upload",
                data={"file": (io.BytesIO(b"example" * 90), "fixture.pdf")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.get_json().get("code"), "request_too_large")

    def test_non_object_chat_body_is_a_client_error(self):
        with app.test_client() as client:
            response = client.post("/api/chat", json=["not", "an", "object"])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json().get("code"), "invalid_payload")

    def test_unexpected_errors_are_not_sent_to_clients(self):
        async def internal_failure(_payload):
            raise RuntimeError("TEST_PRIVATE_INTERNAL_DETAIL")

        with app.test_client() as client, patch.object(
            app_module, "handle_chat_async", internal_failure
        ):
            response = client.post("/api/chat", json={"message": "Hello"})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("TEST_PRIVATE_INTERNAL_DETAIL", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
