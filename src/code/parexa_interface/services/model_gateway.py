"""Model selection and discovery for local-first Parexa.

This module uses only Python's standard library so model discovery and selection
can be tested without installing PyTorch, LlamaIndex or a model runtime.
No request payload can supply a server URL or API key.
"""
from __future__ import annotations

import ipaddress
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


class ModelSelectionError(ValueError):
    """The requested provider/model is not allowed by server configuration."""


class ModelUnavailableError(RuntimeError):
    """A selected model cannot currently be reached or is not configured."""


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    local: bool
    base_url: Optional[str] = None
    api_key: str = ""
    context_window: int = 8192
    max_tokens: int = 2048
    timeout_sec: float = 120.0
    max_concurrency: int = 1


_LOCAL = {
    "lmstudio": ("LM Studio", "http://127.0.0.1:1234/v1", "lmstudio_base_url", "lmstudio_api_key", "lmstudio_chat_model"),
    "ollama": ("Ollama", "http://127.0.0.1:11434/v1", "ollama_base_url", "ollama_api_key", "ollama_chat_model"),
}
_cache: dict[tuple[str, str], tuple[float, tuple[str, ...]]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL_SEC = 8.0


def normalize_local_endpoint(value: str, *, allow_remote: bool = False) -> str:
    """Accept loopback HTTP by default; explicitly trusted remote hosts need TLS."""
    raw = str(value or "").strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ModelSelectionError("Model server URL must start with http:// or https://.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ModelSelectionError("Model server URL must not contain credentials, query or fragment.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ModelSelectionError("Invalid model server port.") from exc
    hostname = parsed.hostname.lower()
    try:
        loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        loopback = hostname == "localhost"
    if not loopback and not allow_remote:
        raise ModelSelectionError(
            "Remote model servers are disabled. Configure PAREXA_ALLOW_REMOTE_MODEL_SERVER explicitly."
        )
    if not loopback and parsed.scheme != "https":
        raise ModelSelectionError("Remote model servers must use HTTPS.")
    path = (parsed.path or "").rstrip("/")
    if path and not path.endswith("/v1"):
        path += "/v1"
    elif not path:
        path = "/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _configuration_for(provider: str, settings: Any) -> tuple[str, str, str]:
    if provider not in _LOCAL:
        raise ModelSelectionError("Unsupported local model provider.")
    _, default_url, url_field, key_field, model_field = _LOCAL[provider]
    raw = getattr(settings, url_field, "") or default_url
    url = normalize_local_endpoint(
        str(raw),
        allow_remote=bool(getattr(settings, "allow_remote_model_server", False)),
    )
    api_key = str(getattr(settings, key_field, "") or provider)
    pinned = str(getattr(settings, model_field, "") or "").strip()
    return url, api_key, pinned


def _request_models(url: str, api_key: str, timeout: float) -> tuple[str, ...]:
    req = Request(
        url.rstrip("/") + "/models",
        headers={"Accept": "application/json", "Authorization": "Bearer " + api_key},
        method="GET",
    )
    with urlopen(req, timeout=timeout) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ModelUnavailableError("Local model server returned an oversized model catalog.")
    body = json.loads(raw)
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ModelUnavailableError("Local model server returned an invalid /v1/models response.")
    models: list[str] = []
    for item in body["data"][:256]:
        if isinstance(item, dict):
            model_id = item.get("id")
            if isinstance(model_id, str) and 0 < len(model_id) <= 200:
                models.append(model_id)
    return tuple(dict.fromkeys(models))


def available_local_models(provider: str, settings: Any, *, force: bool = False) -> tuple[str, ...]:
    url, api_key, _ = _configuration_for(provider, settings)
    key = (provider, url)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and not force and now - cached[0] < _CACHE_TTL_SEC:
            return cached[1]
    timeout = max(0.5, min(5.0, float(getattr(settings, "local_discovery_timeout_sec", 2.0))))
    try:
        models = _request_models(url, api_key, timeout)
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError(
            f"{_LOCAL[provider][0]} is unavailable. Start the local model server and load a chat model."
        ) from exc
    with _cache_lock:
        _cache[key] = (time.monotonic(), models)
    return models


def cloud_allowed(settings: Any) -> bool:
    return bool(getattr(settings, "api_key", "")) and (
        getattr(settings, "chat_provider", "") == "cerebras"
        or bool(getattr(settings, "allow_cloud_model_selection", False))
    )


def catalog(settings: Any) -> dict[str, Any]:
    """List callable providers. Failures are visible, never substituted with cloud."""
    providers: list[dict[str, Any]] = []
    for provider, (label, _, _, _, model_field) in _LOCAL.items():
        available: tuple[str, ...] = ()
        error = ""
        try:
            available = available_local_models(provider, settings)
        except (ModelSelectionError, ModelUnavailableError) as exc:
            error = str(exc)
        providers.append(
            {
                "id": provider,
                "label": label,
                "local": True,
                "online": bool(available),
                "models": [{"id": item, "label": item} for item in available],
                "configured_model": str(getattr(settings, model_field, "") or ""),
                "error": error,
            }
        )
    if cloud_allowed(settings):
        providers.append(
            {
                "id": "cerebras",
                "label": "Cerebras (cloud)",
                "local": False,
                "online": True,  # Configured, not a live availability guarantee.
                "models": [{"id": settings.chat_model, "label": settings.chat_model}],
                "configured_model": settings.chat_model,
                "error": "",
            }
        )

    default_provider = str(getattr(settings, "chat_provider", "cerebras") or "cerebras").lower()
    default_model = ""
    for provider in providers:
        if provider["id"] != default_provider:
            continue
        available_ids = [item["id"] for item in provider["models"]]
        pinned = provider["configured_model"]
        default_model = pinned if pinned in available_ids else (available_ids[0] if available_ids else "")
        break
    return {
        "providers": providers,
        "default": {"provider": default_provider, "model": default_model},
        "embedding": {
            "provider": str(getattr(settings, "embedding_provider", "") or ""),
            "model": str(getattr(settings, "embedding_model", "") or ""),
        },
        "cloud_selection_enabled": cloud_allowed(settings),
    }


def resolve_route(
    settings: Any, *, requested_provider: Optional[str] = None,
    requested_model: Optional[str] = None,
) -> ModelRoute:
    """Validate a requested route against server-controlled capabilities."""
    if requested_provider is not None and not isinstance(requested_provider, str):
        raise ModelSelectionError("Model provider must be a string.")
    if requested_model is not None and not isinstance(requested_model, str):
        raise ModelSelectionError("Model identifier must be a string.")
    if isinstance(requested_model, str) and len(requested_model) > 200:
        raise ModelSelectionError("Model identifier is too long.")
    provider = (requested_provider or getattr(settings, "chat_provider", "cerebras")).strip().lower()
    model = (requested_model or "").strip()

    if provider == "cerebras":
        if not cloud_allowed(settings):
            raise ModelSelectionError(
                "Cloud inference is not enabled. Choose LM Studio/Ollama or enable cloud selection explicitly."
            )
        if model and model != settings.chat_model:
            raise ModelSelectionError("Requested cloud model is not configured.")
        return ModelRoute(provider="cerebras", model=settings.chat_model, local=False, api_key=settings.api_key)

    if provider not in _LOCAL:
        raise ModelSelectionError("Unknown model provider. Select an available server model.")

    url, api_key, pinned = _configuration_for(provider, settings)
    available = available_local_models(provider, settings)
    if not available:
        raise ModelUnavailableError(
            f"No chat models were found on {_LOCAL[provider][0]}. Load a model first."
        )
    selected = model or pinned or available[0]
    if selected not in available:
        raise ModelSelectionError(
            "Selected local model is not listed by the model server. Refresh the model list."
        )
    return ModelRoute(
        provider=provider,
        model=selected,
        local=True,
        base_url=url,
        api_key=api_key,
        context_window=int(getattr(settings, "local_context_window", 8192)),
        max_tokens=int(getattr(settings, "local_max_output_tokens", 2048)),
        timeout_sec=float(getattr(settings, "local_chat_timeout_sec", 120)),
        max_concurrency=max(1, int(getattr(settings, "local_max_concurrent_inference", 1))),
    )
