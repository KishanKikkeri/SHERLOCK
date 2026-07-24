"""
Tests for backend/language/resources.py — mainly guarding against en/kn
key drift now that the bundle has been expanded for the frontend i18n
integration (navigation, common, dashboard, board, analytics, voice,
admin, audit, graph, errors, notifications, dialogs sections).
"""

from backend.language.resources import RESOURCES, SUPPORTED_LANGUAGES, get_resources


def test_en_and_kn_have_identical_section_and_key_structure():
    en, kn = RESOURCES["en"], RESOURCES["kn"]
    assert set(en.keys()) == set(kn.keys())
    for section in en:
        assert set(en[section].keys()) == set(kn[section].keys()), f"key drift in section '{section}'"


def test_get_resources_returns_expected_new_sections():
    en = get_resources("en")
    for section in (
        "navigation", "common", "dashboard", "board", "analytics",
        "voice", "admin", "audit", "graph", "errors", "notifications", "dialogs",
    ):
        assert section in en

    kn = get_resources("kn")
    assert kn["navigation"]["dashboard"] == "ಡ್ಯಾಶ್\u200cಬೋರ್ಡ್"


def test_get_resources_rejects_unsupported_language():
    import pytest
    with pytest.raises(ValueError):
        get_resources("fr")


def test_supported_languages_unchanged():
    assert SUPPORTED_LANGUAGES == ("en", "kn")
