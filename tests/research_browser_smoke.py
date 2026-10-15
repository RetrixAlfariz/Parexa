"""Real browser flow for the research workstation, with a lightweight real Flask API.

Does not run LlamaIndex, OCR, Qdrant or a live model; those remain separate tests.
"""
from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from flask import Flask, jsonify, render_template
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src" / "code"))

from parexa_interface import research_api  # noqa: E402
from parexa_interface.storage.research_store import ResearchStore  # noqa: E402


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(ROOT / "website" / "static"),
        template_folder=str(ROOT / "website" / "templates")
    )
    app.register_blueprint(research_api.bp)

    @app.get("/research")
    def research_page():
        return render_template("research.html")

    @app.get("/api/models")
    def models():
        return jsonify({
            "default":{"provider":"lmstudio","model":""},
            "providers":[{"id":"lmstudio","label":"LM Studio","local":True,
                          "online":False,"models":[]}],
        })

    @app.get("/api/health/embedding")
    def embedding_health():
        return jsonify({"provider":"lmstudio","enabled":True,"healthy":False})

    return app


def main():
    with tempfile.TemporaryDirectory() as scratch:
        with patch.object(research_api,"store",ResearchStore(Path(scratch)/"research")):
            server = make_server("127.0.0.1",0,create_app(),threaded=True)
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    page = browser.new_page(viewport={"width":1440,"height":900},device_scale_factor=1)
                    errors = []
                    page.on("pageerror",lambda error: errors.append(str(error)))
                    page.goto("http://127.0.0.1:" + str(server.server_port) + "/research",wait_until="networkidle")
                    expect(page.locator("#rx-footer-status")).to_contain_text("Vault connected")
                    expect(page.locator("#rx-metrics .rx-metric")).to_have_count(4)
                    expect(page.locator("#rx-home-heading")).to_contain_text("Research needs")

                    page.locator('.rx-toolbar [data-new="project"]').click()
                    page.get_by_label("Project name").fill("Autonomous drone research")
                    page.get_by_label("Research objective").fill("Test control algorithms with clear evidence.")
                    page.get_by_role("button",name="Save record").click()
                    expect(page.locator("#rx-metrics .rx-metric-number").first).to_have_text("1")

                    page.locator('#rx-scope').select_option(label="Autonomous drone research")
                    expect(page.locator("#rx-footer-status")).to_contain_text("Vault connected")
                    page.locator('.rx-nav-item[data-view="library"]').click()
                    source = Path(scratch) / "drone-research.pdf"
                    source.write_bytes(b"%PDF-1.4\n% fake source for archive, never parsed\n%%EOF\n")
                    page.locator("#rx-vault-file").set_input_files(str(source))
                    expect(page.locator("#rx-documents")).to_contain_text("drone-research.pdf")
                    expect(page.locator("#rx-documents")).to_contain_text("stored")
                    page.locator("#rx-documents [data-verify]").click()
                    expect(page.locator("#rx-toast")).to_contain_text("SHA-256 verified")

                    page.locator('.rx-nav-item[data-view="evidence"]').click()
                    page.locator('[data-new="evidence"]').click()
                    page.get_by_label("Original source document").select_option(label="drone-research.pdf")
                    page.get_by_label("Claim supported by the source").fill("Source traceability is required")
                    page.get_by_label("Exact quotation / relevant text").fill("fake source for archive")
                    page.get_by_label("Page or section label").fill("1")
                    page.get_by_role("button",name="Save record").click()
                    expect(page.locator("#rx-evidence")).to_contain_text("Source traceability is required")
                    expect(page.locator("#rx-evidence")).to_contain_text("drone-research.pdf")

                    page.locator('.rx-nav-item[data-view="notes"]').click()
                    page.locator('[data-new="note"]').click()
                    page.get_by_label("Note title").fill("Review of flight controllers")
                    page.locator('#rx-editor textarea[name="content"]').fill("Compare numerical simulations to the real prototype.")
                    page.get_by_role("button",name="Save record").click()
                    expect(page.locator("#rx-notes")).to_contain_text("Review of flight controllers")
                    page.reload(wait_until="networkidle")
                    page.locator('.rx-nav-item[data-view="notes"]').click()
                    expect(page.locator("#rx-notes")).to_contain_text("Review of flight controllers")

                    page.locator('.rx-nav-item[data-view="system"]').click()
                    expect(page.locator("#rx-system")).to_contain_text("SHA-256")
                    expect(page.locator("#rx-system")).to_contain_text("Not implemented")
                    page.locator('.rx-nav-item[data-view="overview"]').click()
                    screenshot_dir = ROOT / "artifacts"
                    screenshot_dir.mkdir(exist_ok=True)
                    page.screenshot(path=str(screenshot_dir/"parexa-research-desktop.png"),full_page=True)

                    page.set_viewport_size({"width":390,"height":844})
                    page.locator("#rx-nav-toggle").click()
                    expect(page.locator(".rx-app")).to_have_class("rx-app rx-mobile-open")
                    page.locator('.rx-nav-item[data-view="library"]').click()
                    expect(page.locator("#rx-documents")).to_contain_text("drone-research.pdf")
                    page.screenshot(path=str(screenshot_dir/"parexa-research-mobile.png"),full_page=True)
                    assert not errors, "JavaScript page errors: " + " | ".join(errors)
                    browser.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    main()
