from pathlib import Path
from http.server import ThreadingHTTPServer
root = Path(__file__).resolve().parents[1]
p = root / "tests" / "observatory_browser_smoke.py"
s = p.read_text(encoding="utf-8").replace("from playwright.sync_api import sync_playwright", "")
namespace = {"__file__": str(p), "__name__": "preview_fixture"}
exec(compile(s.split("\ndef main():")[0], str(p), "exec"), namespace)
ThreadingHTTPServer(("127.0.0.1", 5001), namespace["Handler"]).serve_forever()
