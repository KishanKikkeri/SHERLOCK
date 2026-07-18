"""
SHERLOCK — Stage E6: Operational Security — request/correlation IDs,
security headers, and structured logging.

Everything here is ASGI middleware, wrapping the existing app rather
than touching any route (Golden Rule 3). All of it is always-on and
side-effect-free for existing behavior: it only adds response headers
and log fields, never changes a response body or status code.
"""

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class RequestIdLogFilter(logging.Filter):
    """Attaches the current request's request_id/correlation_id to every
    log record emitted while handling it, so `LOG_LEVEL=INFO` output can
    be correlated across the several log lines one request usually
    produces (route handler, audit write, DB warnings, ...) without
    threading an id through every function signature by hand."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.correlation_id = correlation_id_var.get()
        return True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generates (or forwards) an `X-Request-ID` and `X-Correlation-ID`
    per request. A request_id is always fresh per request; a
    correlation_id is forwarded as-is if the caller supplied one
    (letting a frontend or upstream gateway tie multiple backend calls
    for one user action together), or defaults to the request_id if not."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        correlation_id = request.headers.get("x-correlation-id") or request_id

        req_token = request_id_var.set(request_id)
        corr_token = correlation_id_var.set(correlation_id)

        start = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(req_token)
            correlation_id_var.reset(corr_token)

        duration_ms = (time.monotonic() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Standard defensive response headers. None of these change what
    data a response contains — only how a browser is told to treat it."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        # HSTS only makes sense over an actual TLS connection; asserting
        # it over plain HTTP (e.g. local dev) is actively misleading, so
        # it's only added when the request itself arrived over https —
        # true in any real deployment sitting behind a TLS-terminating
        # proxy that forwards this correctly.
        if request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response


def configure_structured_logging() -> None:
    """Adds request_id/correlation_id to every log record's available
    fields (via the filter above) and, if SHERLOCK_LOG_FORMAT=json, sets
    a JSON formatter — both purely a logging-output concern, applied to
    the root logger's existing handlers rather than replacing Python's
    logging setup wholesale."""
    import os

    log_filter = RequestIdLogFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(log_filter)

    if os.getenv("SHERLOCK_LOG_FORMAT", "").lower() == "json":
        import json as _json

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "request_id": getattr(record, "request_id", "-"),
                    "correlation_id": getattr(record, "correlation_id", "-"),
                }
                if record.exc_info:
                    payload["exc_info"] = self.formatException(record.exc_info)
                return _json.dumps(payload)

        for handler in root_logger.handlers:
            handler.setFormatter(JsonFormatter())
