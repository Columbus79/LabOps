"""Small, dependency-free request and Agent telemetry without prompt contents."""

import json
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request


logger = logging.getLogger("uvicorn.error")


def trace_event(event: str, **fields):
    logger.info("labops_trace %s", json.dumps({"event": event, **fields}, ensure_ascii=False))


async def request_trace(request: Request, call_next):
    trace_id = uuid4().hex
    request.state.trace_id = trace_id
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        trace_event("http_error", trace_id=trace_id, path=request.url.path,
                    duration_ms=round((perf_counter() - started) * 1000, 2))
        raise
    response.headers["X-Request-ID"] = trace_id
    if not request.url.path.startswith("/health/"):
        trace_event("http_response", trace_id=trace_id, method=request.method,
                    path=request.url.path, status=response.status_code,
                    response_start_ms=round((perf_counter() - started) * 1000, 2))
    return response
