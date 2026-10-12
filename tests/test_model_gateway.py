"""Pure-stdlib tests for Parexa's local-first provider gateway."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "code"))

from parexa_interface.services import model_gateway as gateway  # noqa: E402


def configuration(**overrides):
    values = dict(
        chat_provider="lmstudio",
        api_key="",
        chat_model="gpt-oss-120b",
        allow_cloud_model_selection=False,
        allow_remote_model_server=False,
        lmstudio_base_url="http://127.0.0.1:1234/v1",
        lmstudio_api_key="lm-studio",
        lmstudio_chat_model="",
        ollama_base_url="http://127.0.0.1:11434/v1",
        ollama_api_key="ollama",
        ollama_chat_model="",
        local_context_window=8192,
        local_max_output_tokens=768,
        local_chat_timeout_sec=90,
        local_discovery_timeout_sec=2,
        local_max_concurrent_inference=1,
        embedding_provider="lmstudio",
        embedding_model="embeddinggemma",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class ModelGatewayTests(unittest.TestCase):
    def setUp(self):
        gateway._cache.clear()

    def test_endpoint_rejects_remote_and_embedded_credentials(self):
        self.assertEqual(
            gateway.normalize_local_endpoint("http://localhost:1234"),
            "http://localhost:1234/v1",
        )
        self.assertEqual(
            gateway.normalize_local_endpoint("http://127.0.0.1:1234/v1/"),
            "http://127.0.0.1:1234/v1",
        )
        for url in (
            "http://model.example/v1",
            "http://localhost.evil/v1",
            "http://user:pass@localhost:1234/v1",
            "http://localhost:1234/v1?token=secret",
            "ftp://127.0.0.1:1234",
            "http://0.0.0.0:1234",
        ):
            with self.subTest(url=url), self.assertRaises(gateway.ModelSelectionError):
                gateway.normalize_local_endpoint(url)
        self.assertEqual(
            gateway.normalize_local_endpoint("https://model.example/v1", allow_remote=True),
            "https://model.example/v1",
        )

    def test_typed_embedding_models_are_not_exposed_as_chat(self):
        import io
        import json
        response = {
            "data": [
                {"id": "text-embedding-001", "type": "embedding"},
                {"id": "nomic-embed-v1"},
                {"id": "good-chat", "type": "llm"},
            ]
        }
        with patch.object(gateway, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
            models = gateway._request_models("http://127.0.0.1:1234/v1", "test", 1)
        self.assertEqual(models, ("good-chat",))

    def test_local_model_route_and_catalog_do_not_leak_tokens(self):
        settings = configuration(lmstudio_api_key="PRIVATE_TEST_KEY")
        with patch.object(gateway, "_request_models", return_value=("local:chat1", "local:chat2")):
            result = gateway.catalog(settings)
            route = gateway.resolve_route(
                settings, requested_provider="lmstudio", requested_model="local:chat2"
            )
        self.assertTrue(route.local)
        self.assertEqual(route.model, "local:chat2")
        self.assertEqual(route.api_base if hasattr(route, "api_base") else route.base_url, "http://127.0.0.1:1234/v1")
        self.assertEqual(route.max_concurrency, 1)
        self.assertNotIn("PRIVATE_TEST_KEY", str(result))
        self.assertNotIn("cerebras", [p["id"] for p in result["providers"]])

    def test_unknown_or_unlisted_model_is_blocked(self):
        settings = configuration()
        with patch.object(gateway, "_request_models", return_value=("model-A",)):
            with self.assertRaises(gateway.ModelSelectionError):
                gateway.resolve_route(settings, requested_provider="lmstudio", requested_model="model-B")
        with self.assertRaises(gateway.ModelSelectionError):
            gateway.resolve_route(settings, requested_provider="localhost.attacker")

    def test_model_server_failure_never_becomes_cloud_request(self):
        settings = configuration(api_key="CLOUD_KEY")
        with patch.object(gateway, "_request_models", side_effect=ConnectionRefusedError()):
            with self.assertRaises(gateway.ModelUnavailableError):
                gateway.resolve_route(settings)
            catalog = gateway.catalog(settings)
        self.assertFalse(catalog["cloud_selection_enabled"])
        self.assertNotIn("cerebras", [p["id"] for p in catalog["providers"]])
        self.assertFalse(catalog["providers"][0]["online"])

    def test_cloud_needs_explicit_enablement_or_legacy_configuration(self):
        settings = configuration(
            chat_provider="lmstudio", api_key="CLOUD_KEY", allow_cloud_model_selection=False
        )
        with self.assertRaises(gateway.ModelSelectionError):
            gateway.resolve_route(settings, requested_provider="cerebras")
        settings.allow_cloud_model_selection = True
        route = gateway.resolve_route(settings, requested_provider="cerebras")
        self.assertEqual(route.provider, "cerebras")
        self.assertFalse(route.local)
        with self.assertRaises(gateway.ModelSelectionError):
            gateway.resolve_route(settings, requested_provider="cerebras", requested_model="unauthorized-model")

    def test_switching_embedding_dimension_cannot_erase_collection(self):
        source = (
            ROOT / "src" / "code" / "parexa_interface" / "services" / "ingestion_service.py"
        ).read_text(encoding="utf-8")
        self.assertIn("EmbeddingDimensionMismatchError", source)
        self.assertNotIn("_reset_collection_safely", source)
        self.assertNotIn("recreate_collection(", source)


if __name__ == "__main__":
    unittest.main()
