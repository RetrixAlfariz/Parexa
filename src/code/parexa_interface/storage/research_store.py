"""Persistent, local-first research records and byte-exact source vault.

No model dependency: storing research must work even when inference is offline.
SQLite is the authoritative metadata store; Qdrant remains a derived RAG index.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator

_ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt"}
_COLLECTIONS: dict[str, tuple[str, ...]] = {
    "notes": ("title", "content", "project_id"),
    "experiments": ("title", "hypothesis", "method", "result", "status", "project_id"),
    "evidence": ("claim", "quote", "page_label", "confidence", "document_id", "project_id"),
    "tasks": ("title", "description", "priority", "status", "project_id"),
}
_STATUSES = {
    "projects": {"active", "paused", "archived"},
    "experiments": {"planned", "running", "completed", "paused"},
    "tasks": {"todo", "doing", "done"},
}
_LIMITS = {
    "title": 200,
    "name": 250,
    "description": 5000,
    "hypothesis": 15000,
    "method": 30000,
    "result": 30000,
    "content": 250000,
    "claim": 10000,
    "quote": 50000,
    "page_label": 100,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, field: str, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required.")
    if len(value) > _LIMITS.get(field, 500):
        raise ValueError(f"{field} exceeds its length limit.")
    return value


def _project(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError("Invalid project ID.")
    return value


def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class ResearchStore:
    """A self-contained workspace store. Instantiate once per runtime directory."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects = self.root / "objects"
        self.objects.mkdir(exist_ok=True)
        self.db_path = self.root / "research.sqlite3"
        self._initialize()

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._db() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    name TEXT NOT NULL, mime_type TEXT NOT NULL, sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL, index_status TEXT NOT NULL DEFAULT 'stored',
                    chunks INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS documents_sha ON documents(sha256);
                CREATE INDEX IF NOT EXISTS documents_project ON documents(project_id);
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    title TEXT NOT NULL, hypothesis TEXT NOT NULL DEFAULT '',
                    method TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'planned', created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
                    claim TEXT NOT NULL, quote TEXT NOT NULL, page_label TEXT NOT NULL DEFAULT '',
                    confidence TEXT NOT NULL DEFAULT 'unreviewed', created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS evidence_document ON evidence(document_id);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                    title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'todo', priority TEXT NOT NULL DEFAULT 'normal',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
            """)

    @staticmethod
    def _exists(db: sqlite3.Connection, table: str, record_id: str) -> bool:
        if table not in (*_COLLECTIONS, "projects", "documents"):
            raise ValueError("Unknown resource type.")
        return db.execute(f"SELECT 1 FROM {table} WHERE id = ?", (record_id,)).fetchone() is not None

    def _assert_project(self, db: sqlite3.Connection, project_id: str | None) -> None:
        if project_id and not self._exists(db, "projects", project_id):
            raise ValueError("Project not found.")

    def project(self, title: str, description: str = "") -> dict[str, Any]:
        payload = {
            "id": str(uuid.uuid4()), "title": _text(title, "title", required=True),
            "description": _text(description, "description"),
            "status": "active", "created_at": _now(), "updated_at": _now()
        }
        with self._db() as db:
            db.execute(
                "INSERT INTO projects (id,title,description,status,created_at,updated_at)"
                " VALUES (:id,:title,:description,:status,:created_at,:updated_at)", payload
            )
        return payload

    def list(self, kind: str, *, project_id: str | None = None,
             query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        if kind not in (*_COLLECTIONS, "projects", "documents"):
            raise ValueError("Unknown resource type.")
        project_id = _project(project_id)
        limit = min(max(int(limit), 1), 250)
        where: list[str] = []
        params: list[Any] = []
        if project_id:
            where.append("id = ?" if kind == "projects" else "project_id = ?")
            params.append(project_id)
        if query.strip():
            query_col = "name" if kind == "documents" else "title"
            if kind == "evidence":
                query_col = "claim"
            where.append(f"{query_col} LIKE ? ESCAPE '\\'")
            safe_query = query.strip()[:150].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{safe_query}%")
        sql = f"SELECT * FROM {kind}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY " + ("created_at" if kind in ("documents", "evidence") else "updated_at") + " DESC LIMIT ?"
        with self._db() as db:
            return [dict(row) for row in db.execute(sql, [*params, limit]).fetchall()]

    def get(self, kind: str, record_id: str) -> dict[str, Any] | None:
        if kind not in (*_COLLECTIONS, "projects", "documents"):
            raise ValueError("Unknown resource type.")
        with self._db() as db:
            return _dict(db.execute(f"SELECT * FROM {kind} WHERE id = ?", (record_id,)).fetchone())

    def _validate(self, kind: str, values: dict[str, Any], *, creating: bool) -> dict[str, Any]:
        allowed = (*_COLLECTIONS.get(kind, ()),) if kind in _COLLECTIONS else (
            "title", "description", "status"
        )
        if kind not in (*_COLLECTIONS, "projects"):
            raise ValueError("Unknown resource type.")
        if any(key not in allowed for key in values):
            raise ValueError("Unsupported field.")
        clean: dict[str, Any] = {}
        for key, value in values.items():
            if key == "project_id":
                clean[key] = _project(value)
            elif key == "document_id":
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("Evidence requires a source document.")
                clean[key] = value
            elif key == "status":
                if value not in _STATUSES.get(kind, set()):
                    raise ValueError("Invalid status.")
                clean[key] = value
            elif key == "confidence":
                if value not in ("unreviewed", "low", "medium", "high"):
                    raise ValueError("Invalid confidence.")
                clean[key] = value
            elif key == "priority":
                if value not in ("low", "normal", "high"):
                    raise ValueError("Invalid priority.")
                clean[key] = value
            else:
                clean[key] = _text(value, key, required=key in ("title", "claim", "quote"))
        if creating and kind in ("projects", "notes", "experiments", "tasks"):
            if not clean.get("title"):
                raise ValueError("title is required.")
        if creating and kind == "evidence":
            if not clean.get("document_id") or not clean.get("claim") or not clean.get("quote"):
                raise ValueError("Evidence requires document_id, claim and quote.")
        return clean

    def create(self, kind: str, values: dict[str, Any]) -> dict[str, Any]:
        if kind not in _COLLECTIONS:
            raise ValueError("Unsupported resource.")
        clean = self._validate(kind, values, creating=True)
        defaults = {
            "notes": {"title": "", "content": "", "project_id": None},
            "experiments": {"title": "", "hypothesis": "", "method": "", "result": "",
                            "status": "planned", "project_id": None},
            "evidence": {"document_id": "", "claim": "", "quote": "", "page_label": "",
                         "confidence": "unreviewed", "project_id": None},
            "tasks": {"title": "", "description": "", "status": "todo",
                      "priority": "normal", "project_id": None},
        }
        data = {**defaults[kind], **clean, "id": str(uuid.uuid4()),
                "created_at": _now(), "updated_at": _now()}
        with self._db() as db:
            self._assert_project(db, data["project_id"])
            if kind == "evidence":
                document = db.execute(
                    "SELECT project_id FROM documents WHERE id=?", (data["document_id"],)
                ).fetchone()
                if document is None:
                    raise ValueError("Source document not found.")
                if document["project_id"] and data["project_id"] != document["project_id"]:
                    raise ValueError("Evidence must belong to its source document's project.")
            cols = ",".join(data)
            bind = ",".join(":" + column for column in data)
            db.execute(f"INSERT INTO {kind} ({cols}) VALUES ({bind})", data)
        return data

    def update(self, kind: str, record_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        if kind not in (*_COLLECTIONS, "projects"):
            raise ValueError("Unknown resource.")
        clean = self._validate(kind, values, creating=False)
        if not clean:
            raise ValueError("No fields to update.")
        with self._db() as db:
            if not self._exists(db, kind, record_id):
                return None
            if "project_id" in clean:
                self._assert_project(db, clean["project_id"])
            if kind == "evidence" and ("project_id" in clean or "document_id" in clean):
                current = db.execute(
                    "SELECT document_id,project_id FROM evidence WHERE id=?", (record_id,)
                ).fetchone()
                doc_id = clean.get("document_id", current["document_id"])
                project_id = clean.get("project_id", current["project_id"])
                source = db.execute("SELECT project_id FROM documents WHERE id=?", (doc_id,)).fetchone()
                if source is None or (source["project_id"] and project_id != source["project_id"]):
                    raise ValueError("Evidence must match an existing source and its project.")
            clean["updated_at"] = _now()
            assignments = ", ".join(f"{key} = :{key}" for key in clean)
            db.execute(f"UPDATE {kind} SET {assignments} WHERE id = :id", {**clean, "id": record_id})
            return _dict(db.execute(f"SELECT * FROM {kind} WHERE id = ?", (record_id,)).fetchone())

    def delete(self, kind: str, record_id: str) -> bool:
        if kind not in _COLLECTIONS:
            raise ValueError("This resource cannot be deleted.")
        with self._db() as db:
            return db.execute(f"DELETE FROM {kind} WHERE id = ?", (record_id,)).rowcount > 0

    def archive_stream(self, stream: BinaryIO, *, filename: str, project_id: str | None = None,
                       document_id: str | None = None, source: str = "vault",
                       max_bytes: int = 25 * 1024 * 1024) -> dict[str, Any]:
        """Stream into a SHA-256 addressed object; never trust the uploaded filename as a path."""
        from werkzeug.utils import secure_filename

        name = secure_filename(filename)[:250]
        extension = Path(name).suffix.lower()
        if not name or extension not in _ALLOWED_EXTENSIONS:
            raise ValueError("Only PDF, Markdown and plain-text sources are supported.")
        if source not in ("vault", "chat"):
            raise ValueError("Invalid import source.")
        project_id = _project(project_id)
        with self._db() as db:
            self._assert_project(db, project_id)
        digest = hashlib.sha256()
        size = 0
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix=".import-", delete=False) as tmp:
                temp_path = Path(tmp.name)
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        break
                    size += len(block)
                    if size > max_bytes:
                        raise ValueError("File exceeds the configured upload limit.")
                    digest.update(block)
                    tmp.write(block)
                tmp.flush()
                os.fsync(tmp.fileno())
            if size == 0:
                raise ValueError("Empty source files cannot be archived.")
            checksum = digest.hexdigest()
            target = self.objects / checksum[:2] / checksum
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                os.replace(temp_path, target)
                temp_path = None
            mime_type = {".pdf": "application/pdf", ".md": "text/markdown",
                         ".txt": "text/plain"}[extension]
            data = {
                "id": document_id or str(uuid.uuid4()), "project_id": project_id,
                "name": name, "mime_type": mime_type, "sha256": checksum,
                "size_bytes": size, "index_status": "stored", "chunks": 0,
                "source": source, "created_at": _now()
            }
            with self._db() as db:
                db.execute(
                    "INSERT INTO documents (id,project_id,name,mime_type,sha256,"
                    "size_bytes,index_status,chunks,source,created_at) VALUES "
                    "(:id,:project_id,:name,:mime_type,:sha256,:size_bytes,"
                    ":index_status,:chunks,:source,:created_at)", data
                )
            return data
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def mark_indexed(self, document_id: str, chunks: int) -> None:
        if chunks <= 0:
            raise ValueError("An indexed document needs retrievable chunks.")
        with self._db() as db:
            updated = db.execute(
                "UPDATE documents SET index_status = 'indexed', chunks = ? WHERE id = ?",
                (chunks, document_id)
            ).rowcount
            if not updated:
                raise ValueError("Archived source not found for indexing.")

    def source_path(self, document_id: str) -> Path | None:
        document = self.get("documents", document_id)
        if not document:
            return None
        digest = document["sha256"]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid stored source digest.")
        path = (self.objects / digest[:2] / digest).resolve()
        if not path.is_relative_to(self.objects.resolve()):
            raise ValueError("Invalid source path.")
        return path if path.is_file() else None

    def verify(self, document_id: str) -> dict[str, Any] | None:
        document = self.get("documents", document_id)
        if document is None:
            return None
        path = self.source_path(document_id)
        if path is None:
            return {"id": document_id, "valid": False, "reason": "source_missing"}
        digest = hashlib.sha256()
        with path.open("rb") as reader:
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                digest.update(chunk)
        return {"id": document_id, "valid": digest.hexdigest() == document["sha256"],
                "sha256": digest.hexdigest()}

    def overview(self, *, project_id: str | None = None) -> dict[str, Any]:
        project_id = _project(project_id)
        with self._db() as db:
            counts = {}
            for kind in ("projects", "documents", "notes", "experiments", "evidence", "tasks"):
                clause = (" WHERE id = ?" if kind == "projects" else " WHERE project_id = ?") if project_id else ""
                params = (project_id,) if project_id else ()
                counts[kind] = db.execute(f"SELECT COUNT(*) FROM {kind}{clause}", params).fetchone()[0]
            scope = " WHERE project_id = ?" if project_id else ""
            args = (project_id,) if project_id else ()
            counts["indexed"] = db.execute(
                f"SELECT COUNT(*) FROM documents{scope + (' AND' if scope else ' WHERE')}"
                " index_status = 'indexed'", args
            ).fetchone()[0]
            counts["open_tasks"] = db.execute(
                f"SELECT COUNT(*) FROM tasks{scope + (' AND' if scope else ' WHERE')}"
                " status != 'done'", args
            ).fetchone()[0]
            counts["storage_bytes"] = db.execute(
                f"SELECT COALESCE(SUM(size_bytes),0) FROM "
                f"(SELECT MAX(size_bytes) AS size_bytes FROM documents{scope} GROUP BY sha256)", args
            ).fetchone()[0]
        return {"counts": counts,
                "projects": self.list("projects", project_id=project_id, limit=5),
                "documents": self.list("documents", project_id=project_id, limit=5),
                "tasks": self.list("tasks", project_id=project_id, limit=8)}

    def search(self, query: str, *, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        value = _text(query, "query")
        if not value:
            return {"projects": [], "documents": [], "notes": [], "experiments": [], "evidence": []}
        return {kind: self.list(kind, query=value, limit=limit)
                for kind in ("projects", "documents", "notes", "experiments", "evidence")}

    def system(self) -> dict[str, Any]:
        usage = shutil.disk_usage(self.root)
        counts = self.overview()["counts"]
        return {
            "storage": {
                "documents_bytes": counts["storage_bytes"],
                "metadata_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
                "free_bytes": usage.free, "volume_total_bytes": usage.total,
                "documents": counts["documents"], "indexed_documents": counts["indexed"],
                "hash_algorithm": "sha256",
                "metadata_engine": "sqlite",
                "object_engine": "content_addressed_files",
            },
            "capabilities": {
                "source_preservation": True, "integrity_verification": True,
                "retrieval": "existing Qdrant index (independent)",
                "gpu_telemetry": False, "automated_reindex": False, "workspace_backup": False,
            },
        }
