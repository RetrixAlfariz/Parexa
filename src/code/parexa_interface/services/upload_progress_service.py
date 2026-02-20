from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

_TTL_SECONDS = 60 * 30
_progress_lock = threading.RLock()
_progress_map: Dict[str, Dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def _prune_locked() -> None:
    cutoff = _now() - _TTL_SECONDS
    stale_ids = [
        upload_id
        for upload_id, payload in _progress_map.items()
        if float(payload.get("updated_at", 0.0)) < cutoff
    ]
    for upload_id in stale_ids:
        _progress_map.pop(upload_id, None)


def init_upload_progress(
    upload_id: str,
    *,
    filename: str,
    mime_type: str,
) -> Dict[str, Any]:
    now = _now()
    payload = {
        "upload_id": upload_id,
        "state": "running",
        "stage": "queued",
        "percent": 1,
        "message": "Queued",
        "filename": filename,
        "mime_type": mime_type,
        "details": {},
        "created_at": now,
        "updated_at": now,
    }
    with _progress_lock:
        _prune_locked()
        _progress_map[upload_id] = payload
        return dict(payload)


def update_upload_progress(
    upload_id: str,
    *,
    state: Optional[str] = None,
    stage: Optional[str] = None,
    percent: Optional[int] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    with _progress_lock:
        _prune_locked()
        entry = _progress_map.get(upload_id)
        if entry is None:
            return None
        if state:
            entry["state"] = state
        if stage:
            entry["stage"] = stage
        if percent is not None:
            value = max(1, min(100, int(percent)))
            entry["percent"] = value
        if message is not None:
            entry["message"] = message
        if details:
            current_details = dict(entry.get("details") or {})
            current_details.update(details)
            entry["details"] = current_details
        entry["updated_at"] = _now()
        return dict(entry)


def complete_upload_progress(
    upload_id: str, *, message: str = "Completed", details: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    return update_upload_progress(
        upload_id,
        state="completed",
        stage="completed",
        percent=100,
        message=message,
        details=details,
    )


def fail_upload_progress(
    upload_id: str, *, message: str = "Failed", details: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    return update_upload_progress(
        upload_id,
        state="failed",
        stage="failed",
        message=message,
        details=details,
    )


def get_upload_progress(upload_id: str) -> Optional[Dict[str, Any]]:
    with _progress_lock:
        _prune_locked()
        entry = _progress_map.get(upload_id)
        if entry is None:
            return None
        return dict(entry)


__all__ = [
    "init_upload_progress",
    "update_upload_progress",
    "complete_upload_progress",
    "fail_upload_progress",
    "get_upload_progress",
]

