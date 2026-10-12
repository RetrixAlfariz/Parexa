"""Integration smoke against a fake OpenAI-compatible *local* HTTP server.

Uses real LlamaIndex and OpenAI SDK components, but never downloads an AI model
or sends data to external providers.
"""
from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "code"))

from llama_index.core.llms import ChatMessage, MessageRole  # noqa: E402
from parexa_interface.services.local_chat_llm import build_local_llm  # noqa: E402
from parexa_interface.services.model_gateway import ModelRoute  # noqa: E402


class FakeOpenAIServer(BaseHTTPRequestHandler):
    last_roles: list[str] = []
    last_model = ""
    last_max_tokens = None

    def log_message(self, *_args):
        pass

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.loads(raw)
        FakeOpenAIServer.last_roles = [entry["role"] for entry in body.get("messages", [])]
        FakeOpenAIServer.last_model = body.get("model", "")
        FakeOpenAIServer.last_max_tokens = body.get("max_tokens")
        prompt = body["messages"][-1]["content"]
        output = {
            "id": "fake-local-1",
            "object": "chat.completion",
            "created": 1,
            "model": body.get("model"),
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Local: " + prompt},
                }
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
        }
        data = json.dumps(output).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class LocalChatAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenAIServer)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.route = ModelRoute(
            provider="lmstudio",
            model="test-local-model",
            local=True,
            base_url=f"http://127.0.0.1:{cls.server.server_address[1]}/v1",
            api_key="test-local",
            context_window=4096,
            max_tokens=128,
            timeout_sec=10,
            max_concurrency=1,
        )

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_real_http_chat_preserves_roles(self):
        llm = build_local_llm(self.route)
        reply = llm.chat([
            ChatMessage(role=MessageRole.SYSTEM, content="You are Parexa."),
            ChatMessage(role=MessageRole.USER, content="hello"),
        ])
        self.assertEqual(reply.message.content, "Local: hello")
        self.assertEqual(FakeOpenAIServer.last_roles, ["system", "user"])
        self.assertEqual(FakeOpenAIServer.last_model, "test-local-model")
        self.assertEqual(FakeOpenAIServer.last_max_tokens, 128)
        self.assertEqual(llm.metadata.model_name, "test-local-model")
        self.assertTrue(llm.metadata.is_chat_model)

    def test_complete_uses_chat_endpoint(self):
        llm = build_local_llm(self.route)
        reply = llm.complete("Summarize this")
        self.assertEqual(reply.text, "Local: Summarize this")


if __name__ == "__main__":
    unittest.main()
