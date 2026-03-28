from __future__ import annotations

import asyncio
import random
from typing import Any, Awaitable, Callable, Iterable, Optional, Type


async def async_retry(
    operation: Callable[[], Awaitable[Any]],
    *,
    attempts: int,
    base_delay_seconds: float,
    jitter_seconds: float,
    retry_on: Iterable[Type[BaseException]],
) -> Any:
    retryable = tuple(retry_on)
    last_error: Optional[BaseException] = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return await operation()
        except retryable as exc:
            last_error = exc
            if attempt >= max(1, attempts):
                raise
            delay = base_delay_seconds * (2 ** (attempt - 1))
            if jitter_seconds > 0:
                delay += random.uniform(0, jitter_seconds)
            await asyncio.sleep(delay)
    if last_error is not None:
        raise last_error
