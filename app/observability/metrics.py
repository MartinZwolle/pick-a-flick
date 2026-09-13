from __future__ import annotations

import time

from fastapi import Request
from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "pickaflick_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "pickaflick_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)


async def metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    # Avoid unbounded-cardinality labels from numeric IDs.
    if path.startswith("/profiles/"):
        path = "/profiles/:id"
    elapsed = time.perf_counter() - started
    HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    HTTP_LATENCY.labels(request.method, path).observe(elapsed)
    return response
