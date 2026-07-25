"""
Tests for backend/language/context.py and backend/language/prompting.py —
the Priority 26/27 global language context and shared LLM-prompt helper
introduced to make AI-generated output (not just UI chrome) respect the
active application language end-to-end.
"""

import pytest

from backend.language.context import (
    resolve_language, get_current_language, set_current_language, LanguageContextMiddleware,
)
from backend.language.prompting import language_directive, localize_template_fallback


# -- resolve_language / context plumbing ------------------------------------

def test_get_current_language_defaults_to_english():
    set_current_language(None)
    assert get_current_language() == "en"


def test_set_and_get_current_language_round_trips():
    set_current_language("kn")
    try:
        assert get_current_language() == "kn"
    finally:
        set_current_language(None)


def test_set_current_language_rejects_unsupported_code():
    set_current_language("fr")
    try:
        assert get_current_language() == "en"
    finally:
        set_current_language(None)


def test_resolve_language_explicit_argument_wins_over_context():
    set_current_language("kn")
    try:
        assert resolve_language("en") == "en"
    finally:
        set_current_language(None)


def test_resolve_language_falls_back_to_context_when_no_explicit_argument():
    set_current_language("kn")
    try:
        assert resolve_language(None) == "kn"
        assert resolve_language() == "kn"
    finally:
        set_current_language(None)


def test_resolve_language_defaults_to_english_with_no_context_or_argument():
    set_current_language(None)
    assert resolve_language(None) == "en"


def test_resolve_language_ignores_unsupported_explicit_argument():
    set_current_language("kn")
    try:
        # An unsupported explicit code isn't silently accepted — falls
        # back to English (normalize()'s behavior), NOT to the ambient
        # context, since resolve_language treats "explicit but invalid"
        # differently from "not given at all".
        assert resolve_language("fr") == "en"
    finally:
        set_current_language(None)


# -- LanguageContextMiddleware (end-to-end via a real request) --------------

def test_language_context_middleware_sets_and_resets_language(api_client):
    r = api_client.get("/health", headers={"X-App-Language": "kn"})
    assert r.status_code == 200
    assert r.headers.get("x-app-language") == "kn"
    # Context doesn't leak across requests.
    assert get_current_language() == "en"


def test_language_context_middleware_defaults_to_english_without_header(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-app-language") == "en"


def test_language_context_middleware_rejects_unsupported_header_value(api_client):
    r = api_client.get("/health", headers={"X-App-Language": "fr"})
    assert r.status_code == 200
    assert r.headers.get("x-app-language") == "en"


# -- language_directive -------------------------------------------------

def test_language_directive_empty_for_english():
    assert language_directive("en") == ""


def test_language_directive_mentions_target_language_by_name():
    directive = language_directive("kn")
    assert "Kannada" in directive
    assert directive.strip() != ""


def test_language_directive_empty_for_unsupported_language():
    assert language_directive("fr") == ""


# -- localize_template_fallback ------------------------------------------

def test_localize_template_fallback_passthrough_for_english():
    assert localize_template_fallback("hello", "en") == "hello"


def test_localize_template_fallback_passthrough_for_empty_text():
    assert localize_template_fallback("", "kn") == ""


def test_localize_template_fallback_never_raises_without_llm_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # No ANTHROPIC_API_KEY in the test suite (see conftest.py) — this
    # degrades to TranslationService's own passthrough behavior rather
    # than raising, same contract as every other translation call site.
    result = localize_template_fallback("Investigation summary.", "kn")
    assert isinstance(result, str)
