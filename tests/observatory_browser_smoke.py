"""Browser smoke test for the real Parexa HTML/CSS/JS with a tiny fake API.

This validates interface wiring without requiring cloud model credentials, OCR,
Qdrant, or importing the production Flask backend. It is not an LLM/RAG test.
"""
from __future__ import annotations

import json
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"


class Handler(SimpleHTTPRequestHandler):
    last_chat_payload: dict = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEBSITE), **kwargs)

    def log_message(self, *args):
        pass

    def send_json(self, status: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            text = (WEBSITE / "templates" / "index.html").read_text(encoding="utf-8")
            text = re.sub(
                r"\{\{\s*url_for\('static', filename='([^']+)'(?:, v='([^']*)')?\)\s*\}\}",
                lambda match: "/static/" + match.group(1) + ("?v=" + match.group(2) if match.group(2) else ""),
                text,
            )
            data = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/conversations":
            self.send_json(200, {"conversations": [
                {"conversation_id": "fixture-history-1", "title": "From idea to first steps", "preview": "A practical plan"},
                {"conversation_id": "fixture-history-2", "title": "Compare research approaches", "preview": "Two perspectives"}
            ]})
            return
        if path.startswith("/api/conversations/fixture-history-"):
            self.send_json(200, {"history": [
                {"role": "user", "text": "Help me turn a rough idea into a practical plan."},
                {"role": "model", "text": "The most useful starting point is to get clear on the problem you're solving, who it's for, and what success looks like. From there, we can structure a plan that moves from validation to execution.\n\nHere's a simple framework to get started:\n\n1. **Clarify the opportunity**\n\n   Define the problem, the audience, and the value you want to deliver. Be specific about the need you're addressing and how you'll know it matters.\n\n2. **Validate and refine**\n\n   Gather evidence through research, conversations, or lightweight tests. Use what you learn to refine assumptions and identify risks.\n\n3. **Plan your next steps**\n\n   Outline focused actions, set priorities, and define early milestones. Keep it lean, test as you go, and adapt based on feedback.\n\nTell me a bit more about your idea, or choose a specific area you'd like to dig into first."}
            ]})
            return
        if path == "/api/health/embedding":
            self.send_json(200, {"provider": "lmstudio", "enabled": True, "healthy": True, "status": "ok"})
            return
        if path == "/api/models":
            self.send_json(200, {
                "providers": [{
                    "id": "lmstudio", "label": "LM Studio", "local": True,
                    "online": True, "models": [{"id": "fixture-local-chat", "label": "fixture-local-chat"}],
                    "configured_model": "fixture-local-chat", "error": ""
                }],
                "default": {"provider": "lmstudio", "model": "fixture-local-chat"},
                "embedding": {"provider": "lmstudio", "model": "fixture-embedding"},
                "cloud_selection_enabled": False
            })
            return
        if path.startswith("/api/upload/progress/"):
            self.send_json(200, {"state": "completed", "percent": 100})
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        count = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(count)
        if path == "/api/upload":
            self.send_json(200, {
                "message": "File processed",
                "filename": "sample.txt",
                "file_id": "fixture-file-1",
                "ingestion": {"pages_total": 1, "pages_processed": 1, "nodes_created": 1}
            })
            return
        if path == "/api/chat":
            Handler.last_chat_payload = json.loads(data)
            self.send_json(200, {
                "reply": "The provided document discusses several practical applications.",
                "conversation_id": "fixture-conversation-1",
                "sources": [{"file": "sample.txt", "page": "1", "type": "text"}],
                "meta": {"execution": {"mode": "rag", "provider": "lmstudio", "model": "fixture-local-chat", "local": True}}
            })
            return
        self.send_json(404, {"error": "Not found"})


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 950}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(url, wait_until="domcontentloaded")
            page.locator("#ob-home").wait_for(state="visible", timeout=15000)
            assert page.locator(".ob-action-card").count() == 4
            assert not page.locator("#ob-inspector").is_visible()
            assert page.locator("#workspace-mode").inner_text() == "STANDARD"
            assert page.locator(".new-chat-btn").is_visible()
            assert page.locator("#user-input").is_visible()
            page.wait_for_function(
                "window.parexaChatModelSelection?.model === 'fixture-local-chat'",
                timeout=15000,
            )
            assert "fixture-local-chat" in page.locator("#ob-composer-model").inner_text()
            assert "Upgrade to Pro" not in page.locator("body").inner_text()
            page.keyboard.press("Control+k")
            page.locator("#px-command-dialog").wait_for(state="visible")
            page.get_by_label("Search commands", exact=True).fill("notes")
            page.keyboard.press("Enter")
            assert not page.locator("#px-command-dialog").is_visible()
            assert page.evaluate("document.activeElement.id") == "ob-scratchpad"
            page.locator("#ob-inspector-close").click()
            page.keyboard.press("Control+k")
            page.get_by_label("Search commands", exact=True).fill("no-such-command")
            assert page.locator(".px-command-empty").is_visible()
            page.keyboard.press("Escape")
            assert not page.locator("#px-command-dialog").is_visible()
            page.keyboard.press("/")
            assert page.evaluate("document.activeElement.id") == "user-input"
            page.locator("#agent-genesis").click()
            page.wait_for_function("document.querySelector('#workspace-mode')?.textContent === 'GENESIS'")
            page.locator("#agent-default").click()
            page.wait_for_function("document.querySelector('#workspace-mode')?.textContent === 'STANDARD'")
            page.locator(".conversation-item", has_text="From idea to first steps").click()
            page.locator(".message.model").wait_for(state="visible")
            assert page.locator("#studio-conversation-title").inner_text() == "From idea to first steps"
            page.reload()
            page.locator(".conversation-item", has_text="From idea to first steps").click()
            page.locator(".message.model").wait_for(state="visible")
            page.locator(".new-chat-btn").click()
            page.locator("#ob-model-button").click()
            assert page.locator("#ob-inspector").is_visible()
            page.locator("#ob-chat-model-select").select_option("-1")
            assert page.locator("#studio-model-state").inner_text() == "No model connected"
            page.locator("#ob-chat-model-select").select_option("0")
            page.locator("#ob-inspector-close").click()
            page.locator("#sidebar-settings-btn").click()
            page.get_by_role("button", name="Dark", exact=True).click()
            assert page.locator("html").get_attribute("data-theme") == "dark"
            page.get_by_role("button", name="Light", exact=True).click()
            page.keyboard.press("Escape")
            assert not page.locator("#settings-drawer").is_visible()
            assert "OBSERVATORY" not in page.locator(".sidebar-brand").inner_text()
            page.locator("#chat-folder-new").click()
            page.locator("#modal-input").fill("Research")
            page.get_by_role("button", name="Create", exact=True).click()
            page.get_by_label("Move From idea to first steps to folder", exact=True).select_option(label="Research")
            page.get_by_role("button", name="Research", exact=True).click()
            page.reload()
            assert page.get_by_role("button", name="Research", exact=True).get_attribute("aria-expanded") == "false"
            page.get_by_role("button", name="Rename Research", exact=True).click()
            assert page.locator("#modal-input").input_value() == "Research"
            page.locator("#modal-input").fill("Research notes")
            page.get_by_role("button", name="Rename", exact=True).click()
            page.get_by_role("button", name="Research notes", exact=True).click()
            assert page.locator(".chat-folder .conversation-item").count() == 1
            page.get_by_role("button", name="Remove Research notes", exact=True).click()
            page.get_by_role("button", name="Remove folder", exact=True).click()
            assert page.locator(".chat-folder").count() == 0
            assert page.locator(".conversation-item").count() == 2
            page.screenshot(path=str(artifacts / "parexa-observatory-desktop.png"), full_page=True)

            page.locator('[data-ob-action="notes"]').click()
            pad = page.locator("#ob-scratchpad")
            pad.fill("Browser-local note")
            page.reload()
            page.locator("#ob-home").wait_for(state="visible")
            page.locator('[data-ob-action="notes"]').click()
            assert page.locator("#ob-scratchpad").input_value() == "Browser-local note"
            page.wait_for_function(
                "window.parexaChatModelSelection?.model === 'fixture-local-chat'",
                timeout=15000,
            )

            page.locator('[data-ob-action="sources"]').click()
            page.locator("#file-upload").set_input_files({
                "name": "sample.txt",
                "mimeType": "text/plain",
                "buffer": b"Parexa evidence test."
            })
            page.locator(".ob-source-name", has_text="sample.txt").wait_for(timeout=15000)
            page.locator("#user-input").fill("Explain the sample document")
            page.locator(".send-btn").click()
            page.locator(".source-chip").wait_for(timeout=15000)
            assert page.locator(".ob-evidence-item").count() == 1
            assert Handler.last_chat_payload.get("model_provider") == "lmstudio"
            assert Handler.last_chat_payload.get("model") == "fixture-local-chat"
            assert "lmstudio / fixture-local-chat" in page.locator("#ob-provider").inner_text().lower()
            page.locator("#ob-inspector-close").click()
            assert not page.locator("#ob-inspector").is_visible()
            page.locator(".source-chip").click()
            assert page.locator("#ob-inspector").is_visible()
            page.screenshot(path=str(artifacts / "parexa-observatory-chat.png"), full_page=True)

            page.locator(".new-chat-btn").click()
            page.locator("#ob-home").wait_for(state="visible", timeout=5000)
            page.locator('[data-ob-action="explain"]').click()
            assert "step by step" in page.locator("#user-input").input_value()

            page.set_viewport_size({"width": 390, "height": 844})
            page.reload()
            page.locator("#ob-home").wait_for(state="visible", timeout=15000)
            assert not page.locator("#ob-inspector").is_visible()
            assert not page.locator(".sidebar").is_visible()
            page.locator("#sidebar-toggle-btn").click()
            assert page.locator(".sidebar").is_visible()
            page.keyboard.press("Escape")
            assert not page.locator(".sidebar").is_visible()
            page.locator("#ob-inspector-toggle").click()
            assert "ob-inspector-open" in (page.locator(".app-shell").get_attribute("class") or "")
            page.locator("#ob-inspector-close").click()
            assert "ob-inspector-open" not in (page.locator(".app-shell").get_attribute("class") or "")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator("#chat-form").bounding_box()["y"] + page.locator("#chat-form").bounding_box()["height"] <= 844
            page.screenshot(path=str(artifacts / "parexa-observatory-mobile.png"), full_page=True)

            assert not errors, f"Uncaught browser JavaScript errors: {errors}"
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
