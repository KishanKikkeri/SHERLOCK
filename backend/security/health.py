"""
SHERLOCK — Stage E6: Component health checks.

`get_component_health()` returns a status dict per subsystem the brief
names: security, database, storage, translation, voice. Each check is
cheap and side-effect-free (a `SELECT 1`, a `shutil.which`, a filesystem
write to a temp path) — this is a liveness/readiness signal, not a deep
diagnostic, and is safe to call on every `GET /health` request.
"""

import shutil
import tempfile
from pathlib import Path

from backend.database.config import SessionLocal
from backend.security.config import AUTH_ENABLED, JWT_SECRET_KEY


def _security_health() -> dict:
    # A JWT secret that was auto-generated (rather than set via
    # SHERLOCK_JWT_SECRET) works fine for a single dev process but won't
    # survive a restart or be shared across multiple instances — worth
    # surfacing as a "degraded" signal in a real deployment, not an error.
    import os
    explicit_secret = bool(os.getenv("SHERLOCK_JWT_SECRET"))
    if not AUTH_ENABLED:
        return {"status": "disabled", "auth_enabled": False}
    return {
        "status": "ok" if explicit_secret else "degraded",
        "auth_enabled": True,
        "jwt_secret_explicitly_configured": explicit_secret,
    }


def _database_health() -> dict:
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()


def _storage_health() -> dict:
    # No dedicated object-storage subsystem exists in SHERLOCK today (PDF
    # export and voice synthesis both write to short-lived temp files) —
    # this checks that the temp directory the process actually uses is
    # writable, which is the real, concrete storage dependency that
    # exists right now, rather than a check against infrastructure that
    # isn't part of this codebase.
    try:
        tmp_dir = Path(tempfile.gettempdir())
        probe = tmp_dir / ".sherlock_health_probe"
        probe.write_text("ok")
        probe.unlink()
        return {"status": "ok", "path": str(tmp_dir)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _translation_health() -> dict:
    try:
        from backend.language import SUPPORTED_LANGUAGES
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    font_path = Path(__file__).resolve().parents[1] / "reporting" / "fonts" / "NotoSansKannada-Regular.ttf"
    return {
        "status": "ok" if font_path.exists() else "degraded",
        "supported_languages": list(SUPPORTED_LANGUAGES),
        "kannada_pdf_font_available": font_path.exists(),
    }


def _voice_health() -> dict:
    import os
    provider = os.getenv("SHERLOCK_TTS_PROVIDER", "espeak")
    if provider == "espeak":
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        return {
            "status": "ok" if binary else "degraded",
            "provider": provider,
            "binary_found": bool(binary),
        }
    # google/azure/none — presence of the binary isn't relevant; assume
    # configured correctly (their own API calls would surface any real
    # problem) rather than trying to validate third-party credentials here.
    return {"status": "ok", "provider": provider}


def get_component_health() -> dict:
    return {
        "security": _security_health(),
        "database": _database_health(),
        "storage": _storage_health(),
        "translation": _translation_health(),
        "voice": _voice_health(),
    }
