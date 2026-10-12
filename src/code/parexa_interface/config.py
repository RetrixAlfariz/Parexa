from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _int_from_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def _bool_from_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"", "0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    return default


BASE_DIR = Path(__file__).resolve().parent
CODE_ROOT = BASE_DIR.parent
SRC_ROOT = CODE_ROOT.parent
PROJECT_ROOT = SRC_ROOT.parent
load_dotenv(PROJECT_ROOT / ".env")
LOGGER = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} harus di-set.")
    return value


@dataclass(frozen=True)
class SummarySettings:
    model: str
    context_turn_limit: int
    context_message_limit: int
    trigger_turns: int
    min_new_turns: int
    max_chars: int
    intro_prefix: str


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    project_root: Path
    website_dir: Path
    runtime_dir: Path
    db_path: Path
    qdrant_db_path: Path
    qdrant_url: Optional[str]
    qdrant_api_key: Optional[str]
    api_key: str
    google_api_key: str
    chat_model: str
    browsing_model: str
    embedding_provider: str
    embedding_model: str
    lmstudio_base_url: str
    lmstudio_api_key: str
    embedding_healthcheck_enabled: bool
    embedding_healthcheck_interval_sec: int
    embedding_healthcheck_timeout_sec: int
    embedding_healthcheck_retry_backoff_sec: int
    ingest_ocr_sparse_threshold: int
    executor_io_workers: int
    executor_cpu_workers: int
    genesis_parallel_critics: int
    summary: SummarySettings


def _build_settings() -> Settings:
    default_model = os.getenv("CHAT_MODEL", "gpt-oss-120b")
    summary_model = os.getenv("SUMMARY_MODEL", default_model)
    browsing_model = os.getenv("BROWSING_MODEL", "gemini-flash-latest")
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "google").strip().lower()
    raw_embedding_model = os.getenv("EMBEDDING_MODEL", "").strip()
    if raw_embedding_model:
        embedding_model = raw_embedding_model
    elif embedding_provider == "lmstudio":
        embedding_model = "text-embedding-embeddinggemma-300m-qat"
    else:
        embedding_model = "models/gemini-embedding-001"
    lmstudio_base_url = (
        os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").strip()
        or "http://127.0.0.1:1234/v1"
    )
    lmstudio_api_key = (
        os.getenv("LMSTUDIO_API_KEY", "lm-studio").strip() or "lm-studio"
    )

    context_turn_limit = _int_from_env("CONTEXT_TURN_LIMIT", 6)
    context_message_limit = _int_from_env(
        "CONTEXT_MESSAGE_LIMIT", context_turn_limit * 2
    )
    if context_message_limit <= 0:
        context_message_limit = max(2, context_turn_limit * 2)

    summary_settings = SummarySettings(
        model=summary_model,
        context_turn_limit=context_turn_limit,
        context_message_limit=context_message_limit,
        trigger_turns=_int_from_env("SUMMARY_TRIGGER_TURNS", 8),
        min_new_turns=_int_from_env("SUMMARY_MIN_NEW_TURNS", 1),
        max_chars=_int_from_env("SUMMARY_MAX_CHARS", 1800, minimum=200),
        intro_prefix="Ringkasan konteks (informasi, tidak perlu dibalas langsung):",
    )

    raw_runtime_dir = os.getenv("PAREXA_DATA_DIR", "").strip()
    if raw_runtime_dir:
        runtime_dir = Path(raw_runtime_dir).expanduser()
        if not runtime_dir.is_absolute():
            runtime_dir = PROJECT_ROOT / runtime_dir
    else:
        runtime_dir = PROJECT_ROOT / "storage" / "db"
        legacy_runtime_dir = PROJECT_ROOT / "runtime"
        if not runtime_dir.exists() and legacy_runtime_dir.exists():
            runtime_dir = legacy_runtime_dir
            LOGGER.warning(
                "PAREXA_DATA_DIR tidak diset; fallback ke legacy runtime (%s)",
                runtime_dir,
            )
    runtime_dir = runtime_dir.resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    raw_qdrant_dir = os.getenv("QDRANT_DB_PATH", "").strip()
    if raw_qdrant_dir:
        qdrant_db_path = Path(raw_qdrant_dir).expanduser()
        if not qdrant_db_path.is_absolute():
            qdrant_db_path = PROJECT_ROOT / qdrant_db_path
    else:
        qdrant_db_path = runtime_dir / "qdrant_db"
    qdrant_db_path = qdrant_db_path.resolve()
    qdrant_db_path.mkdir(parents=True, exist_ok=True)
    qdrant_url = os.getenv("QDRANT_URL", "").strip() or None
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip() or None

    cpu_count = max(1, os.cpu_count() or 4)
    default_cpu_workers = max(2, min(8, cpu_count))
    default_io_workers = max(4, default_cpu_workers)

    return Settings(
        base_dir=BASE_DIR,
        project_root=PROJECT_ROOT,
        website_dir=PROJECT_ROOT / "website",
        runtime_dir=runtime_dir,
        db_path=runtime_dir / "chat_history.db",
        qdrant_db_path=qdrant_db_path,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        api_key=_require_env("CEREBRAS_API_KEY"),
        google_api_key=(
            _require_env("GOOGLE_API_KEY")
            if embedding_provider != "lmstudio"
            else os.getenv("GOOGLE_API_KEY", "")
        ),
        chat_model=default_model,
        browsing_model=browsing_model,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        lmstudio_base_url=lmstudio_base_url,
        lmstudio_api_key=lmstudio_api_key,
        embedding_healthcheck_enabled=_bool_from_env(
            "EMBEDDING_HEALTHCHECK_ENABLED", True
        ),
        embedding_healthcheck_interval_sec=_int_from_env(
            "EMBEDDING_HEALTHCHECK_INTERVAL_SEC", 30
        ),
        embedding_healthcheck_timeout_sec=_int_from_env(
            "EMBEDDING_HEALTHCHECK_TIMEOUT_SEC", 10
        ),
        embedding_healthcheck_retry_backoff_sec=_int_from_env(
            "EMBEDDING_HEALTHCHECK_RETRY_BACKOFF_SEC", 5
        ),
        ingest_ocr_sparse_threshold=_int_from_env(
            "INGEST_OCR_SPARSE_THRESHOLD", 120
        ),
        executor_io_workers=_int_from_env(
            "PAREXA_IO_WORKERS", default_io_workers
        ),
        executor_cpu_workers=_int_from_env(
            "PAREXA_CPU_WORKERS", default_cpu_workers
        ),
        genesis_parallel_critics=_int_from_env("GENESIS_PARALLEL_CRITICS", 3),
        summary=summary_settings,
    )


settings = _build_settings()


__all__ = [
    "settings",
    "Settings",
    "SummarySettings",
]
