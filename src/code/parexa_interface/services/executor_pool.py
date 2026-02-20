from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

from ..config import settings

T = TypeVar("T")

_io_executor = ThreadPoolExecutor(
    max_workers=settings.executor_io_workers,
    thread_name_prefix="parexa-io",
)
_cpu_executor = ThreadPoolExecutor(
    max_workers=settings.executor_cpu_workers,
    thread_name_prefix="parexa-cpu",
)


async def run_io_bound(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    loop = asyncio.get_running_loop()
    bound = partial(func, *args, **kwargs)
    return await loop.run_in_executor(_io_executor, bound)


async def run_cpu_bound(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    loop = asyncio.get_running_loop()
    bound = partial(func, *args, **kwargs)
    return await loop.run_in_executor(_cpu_executor, bound)


__all__ = ["run_io_bound", "run_cpu_bound"]
