from __future__ import annotations

import asyncio
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

from llama_index.core import Document

from parexa_interface.services.ingestion_service import (
    ingest_documents,
    ingest_documents_async,
    parse_file,
    parse_file_async,
)


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug runner for ingestion_service.parse_file/ingest_documents"
    )
    parser.add_argument("--file", required=True, help="Path to file to ingest")
    parser.add_argument(
        "--collection",
        default="uploaded_files",
        help="Vector collection name (default: uploaded_files)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Parse only; do not write to Qdrant",
    )
    parser.add_argument(
        "--show-docs",
        action="store_true",
        help="Print doc metadata and text length",
    )
    parser.add_argument(
        "--output-id",
        default="",
        help="Identifier for output filename (default: random uuid4)",
    )
    parser.add_argument(
        "--use-async",
        action="store_true",
        help="Run parse/ingest via async wrappers",
    )
    parser.add_argument(
        "--file-id",
        default="",
        help="Inject file_id into parsed document metadata before ingest (for RAG debugging)",
    )
    return parser.parse_args()


def _summarize_docs(docs: List[Document]) -> None:
    for idx, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        text_len = len(doc.text or "")
        print(f"[{idx}] chars={text_len} meta={meta}")


def _write_output(function_name: str, output_id: str, payload: Dict[str, Any]) -> Path:
    outputs_dir = ROOT_DIR / "storage" / "test" / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / f"{function_name}_{output_id}.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return output_path


def main() -> None:
    args = _parse_args()

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    if args.use_async:
        parse_result = asyncio.run(parse_file_async(file_path))
    else:
        parse_result = parse_file(file_path)
    docs = parse_result.get("documents", [])
    warnings = parse_result.get("warnings", [])
    stats = parse_result.get("stats", {})

    injected_file_id = args.file_id.strip()
    if injected_file_id:
        for doc in docs:
            meta = doc.metadata or {}
            meta["file_id"] = injected_file_id
            doc.metadata = meta

    print(f"Parsed {len(docs)} document(s) from {file_path.name}")
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"- {item}")
    if stats:
        print(f"Stats: {json.dumps(stats, ensure_ascii=True)}")

    if args.show_docs and docs:
        _summarize_docs(docs)

    if args.skip_ingest:
        result: Dict[str, Any] = {
            "file": str(file_path),
            "collection": args.collection,
            "documents": len(docs),
            "ingested": False,
            "warnings": warnings,
            "stats": stats,
            "doc_metadata_brief": [
                {
                    "file_name": (doc.metadata or {}).get("file_name"),
                    "file_id": (doc.metadata or {}).get("file_id"),
                    "page_label": (doc.metadata or {}).get("page_label"),
                    "node_type": (doc.metadata or {}).get("node_type"),
                }
                for doc in docs[:10]
            ],
        }
        if args.show_docs:
            result["doc_metadata"] = [doc.metadata or {} for doc in docs]
        output_id = args.output_id.strip() or str(uuid.uuid4())
        output_path = _write_output("ingestion_service", output_id, result)
        print(f"Saved output to {output_path}")
        return

    if args.use_async:
        node_count = asyncio.run(
            ingest_documents_async(docs, collection_name=args.collection)
        )
    else:
        node_count = ingest_documents(docs, collection_name=args.collection)
    print(f"Ingested {node_count} nodes into collection '{args.collection}'")
    result = {
        "file": str(file_path),
        "collection": args.collection,
        "documents": len(docs),
        "warnings": warnings,
        "stats": {**stats, "nodes_created": node_count},
        "ingested": True,
        "doc_metadata_brief": [
            {
                "file_name": (doc.metadata or {}).get("file_name"),
                "file_id": (doc.metadata or {}).get("file_id"),
                "page_label": (doc.metadata or {}).get("page_label"),
                "node_type": (doc.metadata or {}).get("node_type"),
            }
            for doc in docs[:10]
        ],
    }
    if args.show_docs:
        result["doc_metadata"] = [doc.metadata or {} for doc in docs]
    output_id = args.output_id.strip() or str(uuid.uuid4())
    output_path = _write_output("ingestion_service", output_id, result)
    print(f"Saved output to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("ingestion_service debug failed: %s", exc)
        sys.exit(1)
