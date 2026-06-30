"""Per-IP sliding-window rate limiter. In-memory for single-instance deploys; swap the
backing store for Redis (see note) when running multiple instances."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from .config import settings

_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


async def rate_limit(request: Request) -> None:
    # NOTE: for multi-instance production, replace _hits with a Redis sorted set.
    now = time.time()
    window = settings.rate_limit_window_seconds
    ip = _client_ip(request)
    q = _hits[ip]
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) >= settings.rate_limit_requests:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Rate limit exceeded. Slow down and try again shortly.")
    q.append(now)
