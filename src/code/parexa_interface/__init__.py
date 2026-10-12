"""Parexa package.

Importing a model gateway should not initialize Flask, create Qdrant directories,
or require cloud credentials. The legacy app export remains available lazily.
"""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "app":
        from .app import app

        return app
    raise AttributeError(name)


__all__ = ["app"]
