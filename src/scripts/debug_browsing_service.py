from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT_DIR / "src" / "code"
for path in (str(ROOT_DIR), str(CODE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from llama_index.core.llms import ChatMessage

from parexa_interface.services.browsing_service import run_browsing_chat


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug runner for browsing (Gemini + Google Search)"
    )
    parser.add_argument(
        "--message",
        default="Who won the euro 2024?",
        help="Prompt to send to the browsing model",
    )
    parser.add_argument(
        "--history",
        default="",
        help="JSON array of history items (role/text) to include before message",
    )
    parser.add_argument(
        "--history-file",
        default="",
        help="Path to JSON file containing history items",
    )
    parser.add_argument(
        "--output-id",
        default="",
        help="Identifier for output filename (default: random uuid4)",
    )
    return parser.parse_args()


def _load_history(args: argparse.Namespace) -> List[Dict[str, str]]:
    if args.history_file:
        history_path = Path(args.history_file).expanduser().resolve()
        if history_path.exists():
            return json.loads(history_path.read_text(encoding="utf-8"))
        raise SystemExit(f"History file not found: {history_path}")
    if args.history:
        return json.loads(args.history)
    return []


def _to_chat_messages(history: List[Dict[str, str]]) -> List[ChatMessage]:
    items: List[ChatMessage] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = (entry.get("role") or "").strip().lower()
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        if role == "model":
            role = "assistant"
        if role in {"user", "assistant"}:
            items.append(ChatMessage(role=role, content=text))
    return items


def _write_output(function_name: str, output_id: str, payload: Dict[str, Any]) -> Path:
    outputs_dir = ROOT_DIR / "storage" / "test" / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / f"{function_name}_{output_id}.json"
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return output_path


def main() -> None:
    args = _parse_args()
    history_payload = _load_history(args)
    chat_history = _to_chat_messages(history_payload)
    reply = run_browsing_chat(args.message, chat_history)

    result = {
        "message": args.message,
        "reply": reply,
        "history": history_payload,
    }
    output_id = args.output_id.strip() or str(uuid.uuid4())
    output_path = _write_output("browsing_service", output_id, result)
    print(f"Saved output to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("browsing debug failed: %s", exc)
        sys.exit(1)
