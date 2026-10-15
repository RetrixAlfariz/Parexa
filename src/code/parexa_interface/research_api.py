"""Flask JSON API for Parexa Research OS.

The research vault is local-only. Its storage never depends on AI model uptime.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from flask import Blueprint, jsonify, request, send_file

from .config import settings
from .storage.research_store import ResearchStore

bp = Blueprint("research_os", __name__, url_prefix="/api/research")
store = ResearchStore(settings.runtime_dir / "research")


def _body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object.")
    return payload


def _scope() -> str | None:
    return request.args.get("project_id") or None


def _missing() -> tuple[Any, int]:
    return jsonify({"error": "Record not found.", "code": "not_found"}), 404


@bp.errorhandler(ValueError)
def invalid_research_request(exc: ValueError) -> tuple[Any, int]:
    return jsonify({"error": str(exc), "code": "invalid_research_request"}), 400


@bp.errorhandler(sqlite3.IntegrityError)
def integrity_error(_exc: sqlite3.IntegrityError) -> tuple[Any, int]:
    return jsonify({"error": "Conflicting or invalid research record.", "code": "integrity_error"}), 409


@bp.get("/overview")
def overview() -> Any:
    return jsonify(store.overview(project_id=_scope()))


@bp.get("/system")
def system() -> Any:
    payload = store.system()
    payload["runtime"] = {
        "chat_provider": settings.chat_provider,
        "embedding_provider": settings.embedding_provider,
        "local_only_http": True,
        "cloud_model_selection_enabled": settings.allow_cloud_model_selection,
        "note": "Provider health and actual inference usage are not implied by configuration."
    }
    return jsonify(payload)


@bp.get("/search")
def search() -> Any:
    return jsonify(store.search(request.args.get("q", "")[:200]))


@bp.route("/projects", methods=["GET", "POST"])
def projects() -> Any:
    if request.method == "GET":
        return jsonify({"items": store.list("projects", limit=request.args.get("limit", 100, type=int))})
    values = _body()
    if any(key not in ("title", "description") for key in values):
        raise ValueError("Unsupported project field.")
    return jsonify(store.project(values.get("title"), values.get("description", ""))), 201


@bp.route("/projects/<record_id>", methods=["GET", "PATCH"])
def project_detail(record_id: str) -> Any:
    if request.method == "GET":
        record = store.get("projects", record_id)
    else:
        record = store.update("projects", record_id, _body())
    return jsonify(record) if record is not None else _missing()


@bp.route("/documents", methods=["GET", "POST"])
def documents() -> Any:
    if request.method == "GET":
        return jsonify({"items": store.list(
            "documents", project_id=_scope(), query=request.args.get("q", ""),
            limit=request.args.get("limit", 100, type=int)
        )})
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        raise ValueError("Attach a PDF, TXT or Markdown file.")
    record = store.archive_stream(
        uploaded.stream, filename=uploaded.filename,
        project_id=request.form.get("project_id") or None,
        source="vault", max_bytes=settings.max_upload_mb * 1024 * 1024
    )
    return jsonify(record), 201


@bp.get("/documents/<document_id>")
def document_detail(document_id: str) -> Any:
    record = store.get("documents", document_id)
    return jsonify(record) if record else _missing()


@bp.get("/documents/<document_id>/download")
def document_download(document_id: str) -> Any:
    record = store.get("documents", document_id)
    if record is None:
        return _missing()
    path = store.source_path(document_id)
    if path is None:
        return jsonify({"error": "Original source bytes are missing.", "code": "source_missing"}), 410
    # Force download: untrusted PDF/HTML should never be served inline as application UI.
    return send_file(path, as_attachment=True, download_name=record["name"],
                     mimetype="application/octet-stream", conditional=True)


@bp.get("/documents/<document_id>/verify")
def document_verify(document_id: str) -> Any:
    result = store.verify(document_id)
    return jsonify(result) if result is not None else _missing()


@bp.route("/<kind>", methods=["GET", "POST"])
def records(kind: str) -> Any:
    if kind not in ("notes", "experiments", "evidence", "tasks"):
        return _missing()
    if request.method == "GET":
        return jsonify({"items": store.list(
            kind, project_id=_scope(), query=request.args.get("q", ""),
            limit=request.args.get("limit", 100, type=int)
        )})
    return jsonify(store.create(kind, _body())), 201


@bp.route("/<kind>/<record_id>", methods=["GET", "PATCH", "DELETE"])
def record_detail(kind: str, record_id: str) -> Any:
    if kind not in ("notes", "experiments", "evidence", "tasks"):
        return _missing()
    if request.method == "GET":
        record = store.get(kind, record_id)
        return jsonify(record) if record else _missing()
    if request.method == "DELETE":
        return (jsonify({"deleted": True}) if store.delete(kind, record_id)
                else _missing())
    record = store.update(kind, record_id, _body())
    return jsonify(record) if record is not None else _missing()
