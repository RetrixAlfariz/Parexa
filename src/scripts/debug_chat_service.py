from __future__ import annotations

import asyncio
import argparse
import json
import logging
import sys
import uuid
from typing import Any, Dict, List

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT_DIR / "src" / "code"
for path in (str(ROOT_DIR), str(CODE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from parexa_interface.services.chat_service import handle_chat, handle_chat_async


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _load_json(value: str, *, label: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {label} JSON: {exc}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug runner for chat_service.handle_chat"
    )
    parser.add_argument("--message", required=True, help="User message to send")
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Existing conversation id (optional)",
    )
    parser.add_argument(
        "--history-json",
        default="",
        help="History JSON array (e.g. '[{""role"": ""user"", ""text"": ""hi""}]')",
    )
    parser.add_argument(
        "--file-ids",
        default="",
        help="Comma-separated file_ids to trigger RAG (optional)",
    )
    parser.add_argument(
        "--attach-file-ids",
        default="",
        help="Comma-separated file_ids converted into files payload objects (optional)",
    )
    parser.add_argument(
        "--files-json",
        default="",
        help="Files JSON array (optional, attaches to persistence)",
    )
    parser.add_argument(
        "--output-id",
        default="",
        help="Identifier for output filename (default: random uuid4)",
    )
    parser.add_argument(
        "--use-browsing",
        action="store_true",
        help="Set use_browsing=true in payload (useful to verify RAG override when files are attached)",
    )
    parser.add_argument(
        "--print-payload",
        action="store_true",
        help="Print final payload before execution",
    )
    parser.add_argument(
        "--use-async",
        action="store_true",
        help="Run handle_chat_async instead of handle_chat",
    )
    return parser.parse_args()


def _write_output(function_name: str, output_id: str, payload: Dict[str, Any]) -> Path:
    outputs_dir = ROOT_DIR / "storage" / "test" / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / f"{function_name}_{output_id}.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return output_path


def main() -> None:
    args = _parse_args()

    payload: Dict[str, Any] = {"message": args.message}

    if args.conversation_id:
        payload["conversation_id"] = args.conversation_id

    if args.history_json:
        payload["history"] = _load_json(args.history_json, label="history")

    if args.file_ids:
        payload["file_ids"] = [item.strip() for item in args.file_ids.split(",") if item.strip()]

    if args.attach_file_ids:
        attached = [
            {"id": item.strip(), "name": f"file-{item.strip()}"}
            for item in args.attach_file_ids.split(",")
            if item.strip()
        ]
        payload["files"] = attached
        if "file_ids" not in payload:
            payload["file_ids"] = [item["id"] for item in attached]

    if args.files_json:
        payload["files"] = _load_json(args.files_json, label="files")

    if args.use_browsing:
        payload["use_browsing"] = True

    if args.print_payload:
        print("Payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=True))

    if args.use_async:
        result = asyncio.run(handle_chat_async(payload))
    else:
        result = handle_chat(payload)
    output_id = args.output_id.strip() or str(uuid.uuid4())
    output_path = _write_output("chat_service", output_id, result)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    print(f"Saved output to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("chat_service debug failed: %s", exc)
        sys.exit(1)
