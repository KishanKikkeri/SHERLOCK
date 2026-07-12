"""
SHERLOCK — Logging configuration.

Stabilization pass: the codebase previously had zero server-side logging —
exceptions were either swallowed silently or only ever surfaced to the
client over the WebSocket/HTTP response, leaving operators with no record
of what actually failed. This adds one small, standard `logging` setup;
it does not change any business logic or response behaviour.

Usage: call `configure_logging()` once at process startup (done in
`backend/app/main.py`), then in any module:

    import logging
    logger = logging.getLogger(__name__)
    logger.exception("something failed")
"""

import logging
import os


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
