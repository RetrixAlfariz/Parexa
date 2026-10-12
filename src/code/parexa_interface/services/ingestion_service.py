from __future__ import annotations

import logging
import mimetypes
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from ..config import settings
from ..storage.qdrant_db import (
    get_client,
    get_vector_store,
)
from .executor_pool import run_cpu_bound

try:
    import numpy as np
except Exception:  # pragma: no cover - optional import safety
    np = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from llama_index.core import Document, VectorStoreIndex
    from llama_index.core.base.embeddings.base import BaseEmbedding
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[Dict[str, Any]], None]


class EmbeddingServiceUnavailableError(RuntimeError):
    """Raised when LM Studio embedding service is not reachable/ready."""


class EmbeddingDimensionMismatchError(RuntimeError):
    """No automatic destructive migration of incompatible vectors."""

_reader: Any = None
_reader_lock = threading.Lock()
_google_embedding_model_name: str | None = None
_embedding_lock = threading.Lock()
_embedding_warmup_done = False
_embedding_warmup_lock = threading.Lock()
_embedding_dimension: int | None = None
_embedding_dimension_lock = threading.Lock()
_embedding_health_lock = threading.Lock()
_embedding_health_start_lock = threading.Lock()
_embedding_health_stop_event = threading.Event()
_embedding_health_thread: threading.Thread | None = None
_embedding_health_state: Dict[str, Any] = {
    "provider": "google",
    "enabled": False,
    "healthy": False,
    "status": "disabled",
    "model": "",
    "base_url": None,
    "last_check_ts": None,
    "last_success_ts": None,
    "failure_count": 0,
    "last_error": None,
    "next_retry_ts": None,
}


def _empty_stats() -> Dict[str, Any]:
    return {
        "pages_total": 0,
        "pages_processed": 0,
        "vlm_pages": 0,
        "ocr_pages": 0,
        "nodes_created": 0,
        "economy_mode": False,
    }


def _emit_progress(
    progress_callback: Optional[ProgressCallback], **payload: Any
) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(payload)
    except Exception:  # pragma: no cover - progress sink should never break ingest
        logger.debug("Progress callback failed", exc_info=True)


def _utc_now_ts() -> float:
    return time.time()


def _ts_to_iso(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _is_lmstudio_healthcheck_enabled() -> bool:
    return (
        _resolve_embedding_provider() == "lmstudio"
        and settings.embedding_healthcheck_enabled
    )


def _compute_health_status(*, enabled: bool, healthy: bool, failure_count: int) -> str:
    if not enabled:
        return "disabled"
    if healthy:
        return "degraded" if failure_count > 0 else "ok"
    return "degraded" if failure_count <= 1 else "down"


def _refresh_health_static_fields_locked() -> None:
    provider = _resolve_embedding_provider()
    enabled = _is_lmstudio_healthcheck_enabled()
    _embedding_health_state["provider"] = provider
    _embedding_health_state["enabled"] = enabled
    _embedding_health_state["model"] = (settings.embedding_model or "").strip()
    _embedding_health_state["base_url"] = (
        _normalize_lmstudio_api_base() if provider == "lmstudio" else None
    )
    _embedding_health_state["status"] = _compute_health_status(
        enabled=enabled,
        healthy=bool(_embedding_health_state.get("healthy")),
        failure_count=int(_embedding_health_state.get("failure_count") or 0),
    )


def _set_health_state_locked(**updates: Any) -> tuple[str, str]:
    prev_status = str(_embedding_health_state.get("status") or "disabled")
    _embedding_health_state.update(updates)
    _refresh_health_static_fields_locked()
    new_status = str(_embedding_health_state.get("status") or "disabled")
    return prev_status, new_status


def _log_health_transition(
    previous_status: str, new_status: str, *, detail: Optional[str] = None
) -> None:
    if previous_status == new_status:
        return
    if new_status in {"down", "degraded"}:
        logger.warning(
            "Embedding health status changed: %s -> %s%s",
            previous_status,
            new_status,
            f" ({detail})" if detail else "",
        )
    else:
        logger.info(
            "Embedding health status changed: %s -> %s%s",
            previous_status,
            new_status,
            f" ({detail})" if detail else "",
        )


def clean_text(text: str) -> str:
    text = text.encode("utf-8", "ignore").decode("utf-8")
    return re.sub(r"\s+", " ", text).strip()


def _serialize_methods(methods: List[str]) -> str:
    return ",".join(methods)


def _base_metadata(
    file_name: str, mime_type: str, page_number: int, total_pages: int
) -> Dict[str, Any]:
    return {
        "file_name": file_name,
        "mime_type": mime_type,
        "page_label": str(page_number),
        "page_number": page_number,
        "total_pages": total_pages,
    }


def _build_doc(text: str, metadata: Dict[str, Any]) -> Optional["Document"]:
    from llama_index.core import Document

    cleaned = clean_text(text)
    if not cleaned:
        return None
    return Document(text=cleaned, metadata=metadata)


def get_ocr_reader() -> Any:
    global _reader
    if _reader is None:
        with _reader_lock:
            if _reader is None:
                import easyocr

                logger.info("Initializing EasyOCR reader...")
                _reader = easyocr.Reader(["en", "id"], gpu=False, verbose=False)
    return _reader


def _resolve_embedding_provider() -> str:
    provider = (settings.embedding_provider or "google").strip().lower()
    if provider in {"google", "lmstudio"}:
        return provider
    logger.warning(
        "Unknown EMBEDDING_PROVIDER '%s'; defaulting to 'google'.",
        settings.embedding_provider,
    )
    return "google"


def _normalize_lmstudio_api_base() -> str:
    base = (settings.lmstudio_base_url or "http://127.0.0.1:1234/v1").strip()
    if not base:
        base = "http://127.0.0.1:1234/v1"
    trimmed = base.rstrip("/")
    if trimmed.lower().endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


def _build_lmstudio_embedding(timeout_override: Optional[float] = None) -> "BaseEmbedding":
    from .lmstudio_embedding import LMStudioEmbedding

    model_name = (
        (settings.embedding_model or "").strip()
        or "text-embedding-embeddinggemma-300m-qat"
    )
    timeout = float(timeout_override) if timeout_override is not None else 90.0
    return LMStudioEmbedding(
        model_name=model_name,
        embed_batch_size=100,
        api_base=_normalize_lmstudio_api_base(),
        api_key=settings.lmstudio_api_key,
        timeout=max(1.0, timeout),
    )


def _resolve_google_embedding_model_name() -> str:
    global _google_embedding_model_name
    with _embedding_lock:
        if _google_embedding_model_name:
            return _google_embedding_model_name

        requested = (settings.embedding_model or "").strip()
        candidates: List[str] = []
        if requested:
            candidates.append(requested)
            if requested.startswith("models/"):
                candidates.append(requested.replace("models/", "", 1))
            else:
                candidates.append(f"models/{requested}")
        candidates.extend(["models/gemini-embedding-001", "gemini-embedding-001"])
        candidates = list(dict.fromkeys(item for item in candidates if item))

        from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

        failures: List[str] = []
        for candidate in candidates:
            try:
                probe = GoogleGenAIEmbedding(
                    model_name=candidate,
                    embed_batch_size=1,
                    api_key=settings.google_api_key,
                )
                probe.get_text_embedding("healthcheck")
                _google_embedding_model_name = candidate
                if requested and candidate != requested:
                    logger.warning(
                        "Requested embedding model '%s' unavailable; falling back to '%s'.",
                        requested,
                        candidate,
                    )
                return candidate
            except Exception as exc:  # pragma: no cover - remote API variability
                failures.append(f"{candidate}: {exc}")

        raise RuntimeError(
            "No usable embedding model found. "
            f"Requested={requested or '(empty)'}; failures={'; '.join(failures[:3])}"
        )


def get_embedding_model() -> "BaseEmbedding":
    provider = _resolve_embedding_provider()
    if provider == "lmstudio":
        return _build_lmstudio_embedding()

    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

    return GoogleGenAIEmbedding(
        model_name=_resolve_google_embedding_model_name(),
        embed_batch_size=100,
        api_key=settings.google_api_key,
    )


def warmup_embedding_model(force_reload: bool = False) -> None:
    """Preload embedding backend at startup (LM Studio only)."""
    global _embedding_warmup_done
    if _resolve_embedding_provider() != "lmstudio":
        return
    if _embedding_warmup_done and not force_reload:
        return

    with _embedding_warmup_lock:
        if _embedding_warmup_done and not force_reload:
            return
        model = _build_lmstudio_embedding()
        model_name = str(getattr(model, "model_name", settings.embedding_model))
        logger.info("Warming up LM Studio embedding model '%s'...", model_name)
        # Triggers LM Studio lazy model load so first user upload is not blocked.
        model.get_text_embedding("startup warmup")
        _embedding_warmup_done = True
        logger.info("LM Studio embedding model '%s' is ready.", model_name)


def get_embedding_health_status() -> Dict[str, Any]:
    with _embedding_health_lock:
        _refresh_health_static_fields_locked()
        state = dict(_embedding_health_state)
    return {
        "provider": state.get("provider"),
        "enabled": bool(state.get("enabled")),
        "healthy": bool(state.get("healthy")),
        "status": str(state.get("status") or "disabled"),
        "model": str(state.get("model") or ""),
        "base_url": state.get("base_url"),
        "last_check_at": _ts_to_iso(state.get("last_check_ts")),
        "last_success_at": _ts_to_iso(state.get("last_success_ts")),
        "failure_count": int(state.get("failure_count") or 0),
        "last_error": state.get("last_error"),
        "next_retry_at": _ts_to_iso(state.get("next_retry_ts")),
    }


def check_embedding_health(force_reload: bool = False) -> bool:
    if not _is_lmstudio_healthcheck_enabled():
        with _embedding_health_lock:
            previous, current = _set_health_state_locked(
                enabled=False,
                healthy=False,
                failure_count=0,
                last_error=None,
                next_retry_ts=None,
            )
        _log_health_transition(previous, current, detail="healthcheck disabled")
        return True

    now = _utc_now_ts()
    previous_status = "disabled"
    try:
        timeout = float(settings.embedding_healthcheck_timeout_sec)
        model = _build_lmstudio_embedding(timeout_override=timeout)
        vector = model.get_text_embedding("health probe")
        if not vector:
            raise RuntimeError("Empty embedding vector from LM Studio")

        with _embedding_health_lock:
            previous_status, current_status = _set_health_state_locked(
                enabled=True,
                healthy=True,
                failure_count=0,
                last_error=None,
                last_check_ts=now,
                last_success_ts=now,
                next_retry_ts=None,
            )
        _log_health_transition(previous_status, current_status, detail="probe success")
        return True
    except Exception as exc:
        error_text = str(exc)
        backoff_sec = max(1, int(settings.embedding_healthcheck_retry_backoff_sec))
        next_retry = now + backoff_sec
        with _embedding_health_lock:
            previous_count = int(_embedding_health_state.get("failure_count") or 0)
            previous_status, current_status = _set_health_state_locked(
                enabled=True,
                healthy=False,
                failure_count=previous_count + 1,
                last_error=error_text,
                last_check_ts=now,
                next_retry_ts=next_retry,
            )
        _log_health_transition(previous_status, current_status, detail=error_text)

        if not force_reload:
            # One immediate forced retry to trigger lazy reload in LM Studio.
            return check_embedding_health(force_reload=True)
        return False


def _embedding_health_monitor_loop() -> None:
    logger.info(
        "Embedding health monitor started (interval=%ss, retry_backoff=%ss).",
        settings.embedding_healthcheck_interval_sec,
        settings.embedding_healthcheck_retry_backoff_sec,
    )
    interval = max(1, int(settings.embedding_healthcheck_interval_sec))
    while not _embedding_health_stop_event.is_set():
        with _embedding_health_lock:
            _refresh_health_static_fields_locked()
            next_retry_ts = _embedding_health_state.get("next_retry_ts")
            healthy = bool(_embedding_health_state.get("healthy"))
            enabled = bool(_embedding_health_state.get("enabled"))
        if not enabled:
            sleep_for = interval
        else:
            now = _utc_now_ts()
            if (not healthy) and isinstance(next_retry_ts, (int, float)) and now < next_retry_ts:
                sleep_for = max(1.0, float(next_retry_ts - now))
            else:
                check_embedding_health(force_reload=False)
                sleep_for = interval
        if _embedding_health_stop_event.wait(float(sleep_for)):
            break
    logger.info("Embedding health monitor stopped.")


def start_embedding_health_monitor() -> None:
    global _embedding_health_thread
    with _embedding_health_start_lock:
        if _embedding_health_thread and _embedding_health_thread.is_alive():
            return
        _embedding_health_stop_event.clear()
        if not _is_lmstudio_healthcheck_enabled():
            with _embedding_health_lock:
                previous, current = _set_health_state_locked(
                    enabled=False,
                    healthy=False,
                    failure_count=0,
                    last_error=None,
                    next_retry_ts=None,
                )
            _log_health_transition(previous, current, detail="monitor disabled")
            return
        _embedding_health_thread = threading.Thread(
            target=_embedding_health_monitor_loop,
            name="parexa-embedding-health",
            daemon=True,
        )
        _embedding_health_thread.start()


def stop_embedding_health_monitor() -> None:
    global _embedding_health_thread
    with _embedding_health_start_lock:
        thread = _embedding_health_thread
        if thread is None:
            return
        _embedding_health_stop_event.set()
        if thread.is_alive():
            thread.join(timeout=3.0)
        _embedding_health_thread = None


def _resolve_embedding_dimension(embed_model: "BaseEmbedding") -> Optional[int]:
    global _embedding_dimension
    if _embedding_dimension is not None:
        return _embedding_dimension

    with _embedding_dimension_lock:
        if _embedding_dimension is not None:
            return _embedding_dimension
        try:
            vector = embed_model.get_text_embedding("dimension probe")
            size = len(vector or [])
            if size > 0:
                _embedding_dimension = size
                return size
        except Exception as exc:
            logger.debug("Unable to resolve embedding dimension: %s", exc)
        return None


def _get_collection_vector_size(collection_name: str) -> Optional[int]:
    try:
        client = get_client()
        if not client.collection_exists(collection_name):
            return None
        info = client.get_collection(collection_name)
        vectors = getattr(info.config.params, "vectors", None)
        if vectors is None:
            return None
        size = getattr(vectors, "size", None)
        if isinstance(size, int) and size > 0:
            return size
        if isinstance(vectors, dict):
            for value in vectors.values():
                named_size = getattr(value, "size", None)
                if isinstance(named_size, int) and named_size > 0:
                    return named_size
    except Exception as exc:
        logger.debug(
            "Failed to inspect collection '%s' vector size: %s",
            collection_name,
            exc,
        )
    return None


def _ensure_collection_dimension(
    collection_name: str, embed_model: "BaseEmbedding"
) -> None:
    """Validate embedding compatibility without modifying stored data."""
    expected = _resolve_embedding_dimension(embed_model)
    if expected is None:
        return
    actual = _get_collection_vector_size(collection_name)
    if actual is None or actual == expected:
        return
    raise EmbeddingDimensionMismatchError(
        f"Collection '{collection_name}' has {actual}-dimensional embeddings, "
        f"but the active model produces {expected}. Existing vectors are preserved. "
        "Restore the original embedding model or explicitly reindex the collection."
    )


def _ocr_from_page(page: Any) -> str:
    try:
        reader = get_ocr_reader()
        pix = page.get_pixmap(dpi=200, alpha=False)
        results: List[str]
        if np is not None:
            channels = max(1, int(getattr(pix, "n", 1) or 1))
            width = int(getattr(pix, "w", 0) or 0)
            height = int(getattr(pix, "h", 0) or 0)
            raw = np.frombuffer(pix.samples, dtype=np.uint8)
            expected = width * height * channels
            if width > 0 and height > 0 and raw.size == expected:
                if channels == 1:
                    img_input = raw.reshape((height, width))
                else:
                    img_input = raw.reshape((height, width, channels))
                    if channels > 3:
                        img_input = img_input[:, :, :3]
                results = reader.readtext(img_input, detail=0)
            else:
                # Safety fallback for unexpected pixmap layout.
                img_bytes = pix.tobytes("png")
                results = reader.readtext(img_bytes, detail=0)
        else:
            img_bytes = pix.tobytes("png")
            results = reader.readtext(img_bytes, detail=0)
        return clean_text(" ".join(results))
    except Exception as exc:
        logger.warning("OCR failed for page %s: %s", page.number + 1, exc)
        return ""


def _extract_pdf_documents(
    file_path: Path, progress_callback: Optional[ProgressCallback] = None
) -> Dict[str, Any]:
    warnings: List[str] = []
    stats = _empty_stats()
    documents: List["Document"] = []

    import fitz

    try:
        pdf = fitz.open(file_path)
    except Exception as exc:
        logger.error("Failed to open PDF %s: %s", file_path.name, exc)
        return {
            "documents": documents,
            "warnings": [f"Failed to open PDF: {exc}"],
            "stats": stats,
        }

    try:
        stats["pages_total"] = pdf.page_count
        _emit_progress(
            progress_callback,
            stage="parsing",
            pages_total=pdf.page_count,
            pages_processed=0,
            ocr_pages=0,
        )
        for page_num, page in enumerate(pdf, start=1):
            stats["pages_processed"] += 1
            native_text = clean_text(page.get_text("text") or "")
            methods: List[str] = []
            combined_text = native_text
            if native_text:
                methods.append("native_text")

            if len(native_text) < settings.ingest_ocr_sparse_threshold:
                ocr_text = _ocr_from_page(page)
                stats["ocr_pages"] += 1
                if ocr_text:
                    methods.append("ocr")
                    combined_text = (
                        f"{combined_text}\n{ocr_text}" if combined_text else ocr_text
                    )

            text_doc = _build_doc(
                combined_text,
                {
                    **_base_metadata(
                        file_name=file_path.name,
                        mime_type="application/pdf",
                        page_number=page_num,
                        total_pages=pdf.page_count,
                    ),
                    "node_type": "page_text",
                    "modality": "text",
                    "source_methods": _serialize_methods(methods or ["native_text"]),
                },
            )
            if text_doc is not None:
                documents.append(text_doc)

            _emit_progress(
                progress_callback,
                stage="parsing",
                pages_total=pdf.page_count,
                pages_processed=stats["pages_processed"],
                ocr_pages=stats["ocr_pages"],
            )

        stats["nodes_created"] = len(documents)
        return {"documents": documents, "warnings": warnings, "stats": stats}
    finally:
        pdf.close()


def _extract_generic_documents(
    file_path: Path,
    mime_type: str,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    from llama_index.core import SimpleDirectoryReader

    warnings: List[str] = []
    stats = _empty_stats()
    documents: List["Document"] = []

    try:
        _emit_progress(
            progress_callback,
            stage="parsing",
            pages_total=1,
            pages_processed=0,
            ocr_pages=0,
        )
        reader = SimpleDirectoryReader(input_files=[str(file_path)])
        loaded = reader.load_data()
        for doc in loaded:
            metadata = doc.metadata or {}
            metadata["file_name"] = file_path.name
            metadata["mime_type"] = mime_type
            metadata.setdefault("page_number", 1)
            metadata.setdefault("total_pages", 1)
            metadata.setdefault("page_label", str(metadata.get("page_number", 1)))
            metadata["node_type"] = "page_text"
            metadata["modality"] = "text"
            metadata["source_methods"] = _serialize_methods(["native_text"])
            doc.metadata = metadata
            documents.append(doc)
            _emit_progress(
                progress_callback,
                stage="parsing",
                pages_total=max(1, len(loaded)),
                pages_processed=len(documents),
                ocr_pages=0,
            )
    except Exception as exc:
        logger.error("Error parsing file %s: %s", file_path.name, exc)
        warnings.append(f"Failed to parse file {file_path.name}: {exc}")

    stats["pages_total"] = len(documents)
    stats["pages_processed"] = len(documents)
    stats["nodes_created"] = len(documents)
    return {"documents": documents, "warnings": warnings, "stats": stats}


def parse_file(
    file_path: Path,
    mime_type: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "unknown"

    if mime_type.startswith("image/"):
        stats = _empty_stats()
        stats["pages_total"] = 1
        _emit_progress(
            progress_callback,
            stage="parsing",
            pages_total=1,
            pages_processed=1,
            ocr_pages=0,
        )
        return {
            "documents": [],
            "warnings": [f"Image upload disabled: {file_path.name}"],
            "stats": stats,
        }
    if mime_type == "application/pdf":
        return _extract_pdf_documents(file_path, progress_callback=progress_callback)
    return _extract_generic_documents(
        file_path, mime_type, progress_callback=progress_callback
    )


def ingest_documents(
    documents: List["Document"],
    collection_name: str = "uploaded_files",
    progress_callback: Optional[ProgressCallback] = None,
) -> int:
    if not documents:
        return 0

    from llama_index.core import Document, StorageContext, VectorStoreIndex
    from llama_index.core.node_parser import SentenceSplitter

    _emit_progress(progress_callback, stage="indexing_prepare", nodes_total=0, nodes_indexed=0)

    normalized_docs: List[Document] = []
    for doc in documents:
        cleaned_text = clean_text(doc.text or "")
        if not cleaned_text:
            continue
        metadata = dict(doc.metadata or {})
        metadata.setdefault("file_name", "unknown")
        metadata.setdefault("mime_type", "unknown")
        metadata.setdefault("page_label", str(metadata.get("page_number", 1) or 1))
        metadata.setdefault("node_type", "page_text")
        rebuilt = Document(text=cleaned_text, metadata=metadata)
        rebuilt.id_ = doc.id_
        normalized_docs.append(rebuilt)

    if not normalized_docs:
        _emit_progress(
            progress_callback, stage="indexing_complete", nodes_total=0, nodes_indexed=0
        )
        return 0

    splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=200)
    nodes = splitter.get_nodes_from_documents(normalized_docs)
    if not nodes:
        _emit_progress(
            progress_callback, stage="indexing_complete", nodes_total=0, nodes_indexed=0
        )
        return 0

    total_nodes = len(nodes)
    _emit_progress(
        progress_callback,
        stage="indexing",
        nodes_total=total_nodes,
        nodes_indexed=0,
    )

    if _is_lmstudio_healthcheck_enabled() and not check_embedding_health(
        force_reload=False
    ):
        health = get_embedding_health_status()
        reason = str(health.get("last_error") or "LM Studio embedding unavailable")
        raise EmbeddingServiceUnavailableError(reason)

    embed_model = get_embedding_model()
    _ensure_collection_dimension(collection_name, embed_model)
    vector_store = get_vector_store(collection_name)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    embed_batch_size = int(getattr(embed_model, "embed_batch_size", 100) or 100)
    batch_size = max(64, min(256, embed_batch_size * 2))
    supports_insert_nodes = hasattr(VectorStoreIndex, "insert_nodes")

    def _index_in_batches() -> None:
        indexed = 0
        index_obj: Optional[VectorStoreIndex] = None
        for start in range(0, total_nodes, batch_size):
            batch = nodes[start : start + batch_size]
            if index_obj is None:
                index_obj = VectorStoreIndex(
                    batch,
                    storage_context=storage_context,
                    embed_model=embed_model,
                    show_progress=False,
                )
            elif supports_insert_nodes:
                index_obj.insert_nodes(batch)  # type: ignore[attr-defined]
            else:
                VectorStoreIndex(
                    batch,
                    storage_context=storage_context,
                    embed_model=embed_model,
                    show_progress=False,
                )
            indexed += len(batch)
            _emit_progress(
                progress_callback,
                stage="indexing",
                nodes_total=total_nodes,
                nodes_indexed=indexed,
            )

    try:
        _index_in_batches()
    except Exception as exc:
        if _is_dimension_mismatch_error(exc):
            expected = _resolve_embedding_dimension(embed_model)
            actual = _get_collection_vector_size(collection_name)
            raise EmbeddingDimensionMismatchError(
                f"Cannot index '{collection_name}': stored dimension={actual}, "
                f"active dimension={expected}. Existing vectors are preserved. "
                "Restore the previous embedding model or explicitly reindex."
            ) from exc
        if _is_lmstudio_healthcheck_enabled() and _is_embedding_service_unavailable_error(exc):
            raise EmbeddingServiceUnavailableError(str(exc)) from exc
        raise

    _emit_progress(
        progress_callback,
        stage="indexing_complete",
        nodes_total=total_nodes,
        nodes_indexed=total_nodes,
    )

    logger.info(
        "Ingested %s nodes (from %s docs) into %s",
        len(nodes),
        len(normalized_docs),
        collection_name,
    )
    return len(nodes)


def _is_dimension_mismatch_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if "dimension" in text and "embedding" in text:
        return True
    if "vector" in text and "size" in text and "mismatch" in text:
        return True
    # Local Qdrant frequently raises numpy broadcast shape errors for vector-size mismatch,
    # e.g. "could not broadcast input array from shape (768,) into shape (3072,)".
    if "could not broadcast input array from shape" in text and "into shape" in text:
        return True
    # Other numpy variants may not include the "vector" keyword.
    if "shape (" in text and "into shape" in text and "array" in text:
        return True
    if "input array from shape" in text and "into shape" in text:
        return True
    return False


def _is_embedding_service_unavailable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "connection refused",
        "api connection error",
        "connecterror",
        "connection error",
        "max retries exceeded",
        "timed out",
        "timeout",
        "failed to establish a new connection",
        "temporary failure in name resolution",
        "name or service not known",
        "connection reset by peer",
    )
    return any(marker in text for marker in markers)


def get_index_for_collection(collection_name: str = "uploaded_files") -> "VectorStoreIndex":
    from llama_index.core import VectorStoreIndex

    embed_model = get_embedding_model()
    _ensure_collection_dimension(collection_name, embed_model)
    vector_store = get_vector_store(collection_name)
    return VectorStoreIndex.from_vector_store(
        vector_store,
        embed_model=embed_model,
    )


async def parse_file_async(
    file_path: Path,
    mime_type: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    return await run_cpu_bound(parse_file, file_path, mime_type, progress_callback)


async def ingest_documents_async(
    documents: List["Document"],
    collection_name: str = "uploaded_files",
    progress_callback: Optional[ProgressCallback] = None,
) -> int:
    return await run_cpu_bound(
        ingest_documents, documents, collection_name, progress_callback
    )


__all__ = [
    "parse_file",
    "parse_file_async",
    "ingest_documents",
    "ingest_documents_async",
    "get_index_for_collection",
    "warmup_embedding_model",
    "check_embedding_health",
    "get_embedding_health_status",
    "start_embedding_health_monitor",
    "stop_embedding_health_monitor",
    "EmbeddingServiceUnavailableError",
    "clean_text",
]
