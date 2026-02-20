from __future__ import annotations

import atexit
import os
from pathlib import Path
import sys
import logging

SRC_PATH = Path(__file__).resolve().parent / "src" / "code"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from parexa_interface.app import app
from parexa_interface.services.ingestion_service import (
    start_embedding_health_monitor,
    stop_embedding_health_monitor,
    warmup_embedding_model,
)


logger = logging.getLogger(__name__)


def _get_debug() -> bool:
    value = os.getenv("FLASK_DEBUG")
    if value is None:
        value = os.getenv("FLASK_ENV", "")
    value = value.strip().lower()
    return value in {"1", "true", "yes", "on", "development", "dev"}


def main() -> None:
    port = int(os.getenv("PORT", 5000))
    warmup_enabled = (
        os.getenv("EMBEDDING_WARMUP_ON_START", "true").strip().lower()
        not in {"0", "false", "no", "off"}
    )
    if warmup_enabled:
        try:
            warmup_embedding_model()
        except Exception as exc:
            logger.warning("Embedding warmup failed at startup: %s", exc)
    start_embedding_health_monitor()
    atexit.register(stop_embedding_health_monitor)
    app.run(debug=_get_debug(), host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()
