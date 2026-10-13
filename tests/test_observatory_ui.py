"""Dependency-free structural regression tests for Parexa Observatory."""
from __future__ import annotations

import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "website" / "templates" / "index.html"
STATIC = ROOT / "website" / "static"


class InspectMarkup(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.tabs: list[str] = []
        self.panels: list[str] = []
        self.buttons = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        properties = dict(attrs)
        if properties.get("id"):
            self.ids.append(properties["id"])
        if properties.get("data-ob-tab"):
            self.tabs.append(properties["data-ob-tab"])
        if properties.get("data-ob-panel"):
            self.panels.append(properties["data-ob-panel"])
        if tag == "button":
            self.buttons += 1


class ObservatoryStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = TEMPLATE.read_text(encoding="utf-8")
        cls.css = (STATIC / "css" / "observatory.css").read_text(encoding="utf-8")
        cls.javascript = (STATIC / "observatory.js").read_text(encoding="utf-8")
        cls.original_javascript = (STATIC / "script.js").read_text(encoding="utf-8")
        cls.parser = InspectMarkup()
        cls.parser.feed(cls.html)

    def test_core_chat_controls_are_retained(self) -> None:
        for identifier in (
            "chat-log", "chat-form", "user-input", "file-upload",
            "browse-toggle", "file-display-area", "agent-default",
            "agent-genesis", "settings-drawer", "activity-drawer",
            "sidebar-toggle-btn", "panel-toggle-btn",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, self.parser.ids)

    def test_observatory_has_unique_ids_and_mapped_tabs(self) -> None:
        duplicate_ids = {key for key, count in Counter(self.parser.ids).items() if count != 1}
        self.assertEqual(duplicate_ids, set())
        self.assertEqual(set(self.parser.tabs), {"sources", "context", "notes"})
        self.assertEqual(set(self.parser.panels), set(self.parser.tabs))
        for identifier in ("ob-home", "ob-recent-list", "ob-inspector", "ob-source-list",
                           "ob-evidence-list", "ob-scratchpad", "ob-inspector-toggle"):
            self.assertIn(identifier, self.parser.ids)

    def test_uses_uploaded_mark_and_not_proprietary_tiers(self) -> None:
        self.assertIn("images/parexa-mark.svg", self.html)
        self.assertTrue((STATIC / "images" / "parexa-mark.svg").is_file())
        self.assertNotIn("Upgrade to Pro", self.html)
        self.assertNotIn("Subscription", self.html)

    def test_styles_and_script_are_connected(self) -> None:
        self.assertIn("css/observatory.css", (STATIC / "styles.css").read_text(encoding="utf-8"))
        self.assertIn("filename='observatory.js'", self.html)
        self.assertIn('window.addEventListener("parexa:response"', self.javascript)
        self.assertIn('new CustomEvent("parexa:response"', self.original_javascript)
        self.assertIn("MutationObserver", self.javascript)
        self.assertEqual(self.css.count("{"), self.css.count("}"))

    def test_workspace_live_status_and_keyboard_shortcuts(self) -> None:
        for identifier in (
            "workspace-mode", "workspace-browsing", "workspace-embedding",
            "workspace-run-status",
        ):
            self.assertIn(identifier, self.parser.ids)
        self.assertIn("filename='workspace.js'", self.html)
        workspace = (STATIC / "workspace.js").read_text(encoding="utf-8")
        self.assertIn("Alt", workspace)
        self.assertIn('key === "/"', workspace)
        self.assertIn("MutationObserver", workspace)
        self.assertIn("css/workspace-status.css", (STATIC / "styles.css").read_text(encoding="utf-8"))

    def test_starters_use_actual_handlers_not_dead_links(self) -> None:
        actions = set(re.findall(r'data-ob-action="([^"]+)"', self.html))
        for action in ("home", "sources", "notes", "activity",
                       "analyze", "synthesize", "explain", "plan"):
            self.assertIn(action, actions)
            self.assertIn('case "' + action + '":', self.javascript)

    def test_source_scope_is_not_misrepresented_as_persistent_memory(self) -> None:
        self.assertIn("Used in last request; not attached to the next one", self.javascript)
        self.assertIn("stored in this browser, not sent to the model", self.html.lower())
        self.assertIn("AI providers may connect to external services", self.html)


if __name__ == "__main__":
    unittest.main()
