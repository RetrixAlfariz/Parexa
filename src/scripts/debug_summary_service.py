from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT_DIR / "src" / "code"
for path in (str(ROOT_DIR), str(CODE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from llama_index.llms.cerebras import Cerebras

from parexa_interface.config import settings
from parexa_interface.services.summary import refresh_summary
from parexa_interface.storage.conversation_store import (
    get_summary_state,
    persist_turn,
)


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug runner for summary refresh flow"
    )
    parser.add_argument(
        "--conversation-id",
        default="",
        help="Existing conversation id (optional)",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=3,
        help="Number of user/model turns to add before refreshing",
    )
    parser.add_argument(
        "--message",
        default="Debug message",
        help="Base text to store in conversation",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Skip calling the LLM summary refresh",
    )
    parser.add_argument(
        "--output-id",
        default="",
        help="Identifier for output filename (default: random uuid4)",
    )
    return parser.parse_args()


def _write_output(function_name: str, output_id: str, payload: dict) -> Path:
    outputs_dir = ROOT_DIR / "storage" / "test" / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / f"{function_name}_{output_id}.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return output_path


def main() -> None:
    args = _parse_args()

    conversation_id = args.conversation_id.strip() or str(uuid.uuid4())
    turns = max(1, args.turns)

    for idx in range(1, turns + 1):
        user_text = f"{args.message} (user {idx})"
        model_text = f"{args.message} (model {idx})"
        persist_turn(
            conversation_id,
            (("user", user_text), ("model", model_text)),
            paired=(user_text, model_text),
            files=None,
        )

    print(f"Seeded {turns} turn(s) into {conversation_id}")

    if args.no_refresh:
        result = {
            "conversation_id": conversation_id,
            "turns_seeded": turns,
            "summary_refreshed": False,
        }
        output_id = args.output_id.strip() or str(uuid.uuid4())
        output_path = _write_output("summary_service", output_id, result)
        print(f"Saved output to {output_path}")
        return

    llm = Cerebras(model=settings.summary.model, api_key=settings.api_key)
    refresh_summary(llm, conversation_id)

    summary_text, last_turn_id = get_summary_state(conversation_id)
    print("Summary state:")
    print(f"- last_processed_turn_id: {last_turn_id}")
    print(f"- summary: {summary_text}")
    result = {
        "conversation_id": conversation_id,
        "turns_seeded": turns,
        "summary_refreshed": True,
        "last_processed_turn_id": last_turn_id,
        "summary": summary_text,
    }
    output_id = args.output_id.strip() or str(uuid.uuid4())
    output_path = _write_output("summary_service", output_id, result)
    print(f"Saved output to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("summary debug failed: %s", exc)
        sys.exit(1)
