from __future__ import annotations

import logging
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

if __package__ is None or __package__ == "":
    # Allow running as `python src/code/parexa_interface/app.py`
    PACKAGE_DIR = Path(__file__).resolve().parent
    PARENT_DIR = PACKAGE_DIR.parent
    if str(PARENT_DIR) not in sys.path:
        sys.path.insert(0, str(PARENT_DIR))

    from parexa_interface.services.chat_service import (  # type: ignore[import-not-found]
        ChatServiceError,
        delete_conversation,
        get_conversation_history,
        get_conversation_list,
        handle_chat_async,
    )
    from parexa_interface.config import settings  # type: ignore[import-not-found]
    from parexa_interface.services import (  # type: ignore[import-not-found]
        ingestion_service,
    )
    from parexa_interface.services.upload_progress_service import (  # type: ignore[import-not-found]
        complete_upload_progress,
        fail_upload_progress,
        get_upload_progress,
        init_upload_progress,
        update_upload_progress,
    )
else:
    from .services.chat_service import (
        ChatServiceError,
        delete_conversation,
        get_conversation_history,
        get_conversation_list,
        handle_chat_async,
    )
    from .config import settings
    from .services import ingestion_service
    from .services.upload_progress_service import (
        complete_upload_progress,
        fail_upload_progress,
        get_upload_progress,
        init_upload_progress,
        update_upload_progress,
    )


app = Flask(
    __name__,
    static_folder=str(settings.website_dir / "static"),
    template_folder=str(settings.website_dir / "templates"),
)

logger = logging.getLogger(__name__)


# Global file mapping to store file metadata
file_mapping = {}
_ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".pdf", ".md"}


@app.route("/", methods=["GET"])
def index() -> str:
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
async def chat() -> Any:
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    try:
        result = await handle_chat_async(payload)
        return jsonify(result)
    except ChatServiceError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Kesalahan tidak terduga saat memproses chat")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/upload", methods=["POST"])
async def upload_file() -> Any:
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_id = str(uuid.uuid4())
    original_name = file.filename or "uploaded_file"
    safe_name = secure_filename(original_name) or f"uploaded_{file_id}.txt"
    suffix = Path(safe_name).suffix.lower()
    guessed_mime = (file.mimetype or "").strip() or (
        mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    )
    raw_upload_id = str(request.headers.get("X-Upload-ID", "")).strip()
    upload_tracking_id = (raw_upload_id[:128] if raw_upload_id else "") or file_id
    init_upload_progress(
        upload_tracking_id,
        filename=safe_name,
        mime_type=guessed_mime,
    )

    if guessed_mime.startswith("image/"):
        fail_upload_progress(upload_tracking_id, message="Image upload is disabled")
        return jsonify({"error": "Image upload is disabled"}), 415
    if suffix not in _ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_UPLOAD_EXTENSIONS))
        fail_upload_progress(
            upload_tracking_id,
            message=f"Unsupported file type. Allowed: {allowed}",
        )
        return jsonify({"error": f"Unsupported file type. Allowed: {allowed}"}), 415

    temp_dir = settings.runtime_dir / "temp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    file_path = temp_dir / f"{file_id}_{safe_name}"

    try:
        file.save(str(file_path))
        update_upload_progress(
            upload_tracking_id,
            stage="saving",
            percent=12,
            message="File saved",
        )
        health = ingestion_service.get_embedding_health_status()
        if bool(health.get("enabled")) and not bool(health.get("healthy")):
            recovered = ingestion_service.check_embedding_health(force_reload=True)
            if not recovered:
                health = ingestion_service.get_embedding_health_status()
                details = (
                    "LM Studio embedding unavailable. "
                    f"Error: {health.get('last_error') or 'model not loaded'}"
                )
                fail_upload_progress(upload_tracking_id, message=details)
                return jsonify({"error": details}), 503

        def _on_parse_progress(payload: Dict[str, Any]) -> None:
            total = max(1, int(payload.get("pages_total") or 1))
            processed = max(0, min(total, int(payload.get("pages_processed") or 0)))
            ocr_pages = max(0, int(payload.get("ocr_pages") or 0))
            parse_percent = 15 + int((processed / total) * 55)
            update_upload_progress(
                upload_tracking_id,
                stage="parsing",
                percent=parse_percent,
                message=f"Parsing pages {processed}/{total}",
                details={
                    "pages_total": total,
                    "pages_processed": processed,
                    "ocr_pages": ocr_pages,
                },
            )

        parse_result = await ingestion_service.parse_file_async(
            file_path,
            mime_type=guessed_mime,
            progress_callback=_on_parse_progress,
        )
        docs = parse_result.get("documents", [])
        warnings = parse_result.get("warnings", [])
        ingestion_stats = parse_result.get("stats", {})

        if not docs:
            details = (
                "No extractable text found in the uploaded document. "
                "Try another PDF or ensure the document is not empty."
            )
            if warnings:
                details = f"{details} Warnings: {' | '.join(str(item) for item in warnings[:3])}"
            fail_upload_progress(
                upload_tracking_id,
                message=details,
                details={
                    "warnings": warnings if isinstance(warnings, list) else [],
                    "ingestion": (
                        ingestion_stats if isinstance(ingestion_stats, dict) else {}
                    ),
                },
            )
            return jsonify({"error": details}), 422

        update_upload_progress(
            upload_tracking_id,
            stage="preparing",
            percent=72,
            message="Preparing document metadata",
        )
        for doc in docs:
            metadata = doc.metadata or {}
            metadata["file_id"] = file_id
            metadata["file_name"] = safe_name
            metadata.setdefault("mime_type", guessed_mime)
            metadata.setdefault("page_label", str(metadata.get("page_number", 1) or 1))
            metadata.setdefault("node_type", "page_text")
            doc.metadata = metadata

        def _on_ingest_progress(payload: Dict[str, Any]) -> None:
            stage = str(payload.get("stage") or "indexing")
            nodes_total = max(0, int(payload.get("nodes_total") or 0))
            nodes_indexed = max(0, int(payload.get("nodes_indexed") or 0))
            if stage == "indexing_prepare":
                percent = 75
                message = "Preparing index"
            elif stage == "indexing_complete":
                percent = 99
                message = "Finalizing index"
            else:
                ratio = (nodes_indexed / nodes_total) if nodes_total > 0 else 0.0
                percent = 76 + int(ratio * 22)
                message = f"Indexing chunks {nodes_indexed}/{nodes_total}"
            update_upload_progress(
                upload_tracking_id,
                stage="indexing",
                percent=percent,
                message=message,
                details={
                    "nodes_total": nodes_total,
                    "nodes_indexed": nodes_indexed,
                },
            )

        nodes_created = await ingestion_service.ingest_documents_async(
            docs, progress_callback=_on_ingest_progress
        )
        if nodes_created <= 0:
            fail_upload_progress(
                upload_tracking_id,
                message=(
                    "Document parsed but produced no retrievable chunks. "
                    "Please upload a document with readable text content."
                ),
            )
            return jsonify(
                {
                    "error": (
                        "Document parsed but produced no retrievable chunks. "
                        "Please upload a document with readable text content."
                    )
                }
            ), 422
        if isinstance(ingestion_stats, dict):
            ingestion_stats["nodes_created"] = nodes_created

        file_mapping[file_id] = {
            "filename": safe_name,
            "file_id": file_id,
            "mime_type": guessed_mime,
            "uploaded_at": str(file_path.stat().st_mtime),
        }
        complete_upload_progress(
            upload_tracking_id,
            message="Upload completed",
            details={
                "file_id": file_id,
                "ingestion": (
                    ingestion_stats if isinstance(ingestion_stats, dict) else {}
                ),
                "warnings": warnings if isinstance(warnings, list) else [],
            },
        )

        return jsonify(
            {
                "message": "File processed successfully",
                "filename": safe_name,
                "file_id": file_id,
                "upload_id": upload_tracking_id,
                "warnings": warnings if isinstance(warnings, list) else [],
                "ingestion": (
                    ingestion_stats if isinstance(ingestion_stats, dict) else {}
                ),
            }
        )
    except ingestion_service.EmbeddingServiceUnavailableError as exc:
        message = (
            "LM Studio embedding unavailable. "
            f"Error: {str(exc) or 'model not loaded'}"
        )
        fail_upload_progress(upload_tracking_id, message=message)
        return jsonify({"error": message}), 503
    except Exception as exc:
        logger.exception("Error processing file")
        fail_upload_progress(
            upload_tracking_id,
            message=str(exc) or "Error processing upload",
        )
        return jsonify({"error": str(exc)}), 500
    finally:
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as cleanup_exc:  # pragma: no cover - defensive
            logger.warning("Failed to cleanup temp file %s: %s", file_path, cleanup_exc)


@app.route("/api/upload/progress/<upload_id>", methods=["GET"])
def upload_progress(upload_id: str) -> Any:
    key = upload_id.strip()[:128]
    if not key:
        return jsonify({"error": "Invalid upload id"}), 400
    payload = get_upload_progress(key)
    if payload is None:
        return jsonify({"error": "Upload progress not found"}), 404
    return jsonify(payload)


@app.route("/api/health/embedding", methods=["GET"])
def embedding_health() -> Any:
    try:
        return jsonify(ingestion_service.get_embedding_health_status())
    except Exception as exc:
        logger.exception("Failed to resolve embedding health status")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/conversations/<conversation_id>", methods=["GET"])
def conversation(conversation_id: str) -> Any:
    try:
        result = get_conversation_history(conversation_id)
        return jsonify(result)
    except ChatServiceError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
def delete_conversation_route(conversation_id: str) -> Any:
    try:
        result = delete_conversation(conversation_id)
        return jsonify(result)
    except ChatServiceError as exc:
        message = str(exc)
        status = 404 if "tidak ditemukan" in message.lower() else 400
        return jsonify({"error": message}), status


@app.route("/api/conversations", methods=["GET"])
def conversations_list() -> Any:
    limit = request.args.get("limit", type=int) or 50
    result = get_conversation_list(limit)
    return jsonify(result)


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        threaded=True,
    )
