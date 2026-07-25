"""
SHERLOCK — Priority 26: Global Language Context.

Before this module, "what language should this response be in" was
answered differently by every caller: `stream_investigation` detected it
from the query text, `ConversationManager` took an explicit parameter,
and everything else (sociological insights, discussion engine,
conversation summarization) had no concept of language at all and
always produced English. That's exactly the "no service should
independently decide its output language" problem this priority calls
out.

This module gives every AI-generating service in the backend ONE place
to ask "what language is this session using right now" —
`resolve_language()` — instead of re-deriving an answer locally. It
mirrors `backend/security/request_context.py`'s ContextVar + ASGI
middleware pattern exactly, for the same reason that module gives every
log line a request_id without threading one through every function
signature by hand.

Wiring:
    frontend (LanguageProvider) -> `X-App-Language` header on every
    apiFetch call (see frontend/src/lib/api-client.ts) -> this
    middleware -> ContextVar -> `resolve_language()` calls throughout
    the backend (ChiefAgent, DiscussionEngine, SociologicalInsightsService,
    ConversationMemoryService, ...).

An explicit `language` argument a caller already has (e.g. a per-turn
language ConversationManager was given directly, or one detected from
spoken/typed query text) still takes priority over the ambient
header — see `resolve_language`'s own docstring for why.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from contextvars import ContextVar

from backend.language.resources import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"
LANGUAGE_HEADER = "X-App-Language"

_current_language: ContextVar[str] = ContextVar("current_language", default=DEFAULT_LANGUAGE)


def _normalize(language: str | None) -> str:
    """Unsupported/missing codes fall back to English rather than
    raising — matches every other language boundary in this codebase
    (`get_resources`, `TranslationService`, `detect_language`)."""
    if language and language in SUPPORTED_LANGUAGES:
        return language
    return DEFAULT_LANGUAGE


def get_current_language() -> str:
    """The ambient language for whatever request is currently being
    handled — "en" outside of a request (e.g. a script, a test, a
    background job) or when no `X-App-Language` header was sent."""
    return _current_language.get()


def set_current_language(language: str | None) -> None:
    """Mainly for tests and one-off scripts that want to exercise
    language-aware code without going through a real HTTP request —
    real requests get this from `LanguageContextMiddleware` instead."""
    _current_language.set(_normalize(language))


def resolve_language(explicit: str | None = None) -> str:
    """THE call every AI-generating service in the backend should make
    to find out what language to answer in.

    `explicit` wins when given, because it usually carries more
    specific information than the ambient request-wide header — e.g.
    `stream_investigation` may fall back to detecting the language of
    the query text itself (someone typed a Kannada question under an
    English-toggled UI); that specific signal should win over the
    session-wide default. Omit `explicit` (or pass `None`/an
    unsupported code) to just use the current global language context.
    """
    if explicit:
        return _normalize(explicit)
    return get_current_language()


class LanguageContextMiddleware(BaseHTTPMiddleware):
    """Reads `X-App-Language` off the incoming request and makes it
    available for the lifetime of that request via
    `get_current_language()`/`resolve_language()`, then resets it —
    same lifecycle as `RequestContextMiddleware`'s request_id.

    This is additive: it does not replace the explicit `language`
    keyword-argument that already flows through
    `ConversationManager`/`run_investigation_once`/`stream_investigation`
    today. It exists for the many services that had no such argument at
    all before Priority 26 and would otherwise always default to
    English regardless of what's selected in the UI.
    """

    async def dispatch(self, request: Request, call_next):
        language = _normalize(request.headers.get(LANGUAGE_HEADER))
        token = _current_language.set(language)
        try:
            response = await call_next(request)
        finally:
            _current_language.reset(token)
        response.headers.setdefault(LANGUAGE_HEADER, language)
        return response
