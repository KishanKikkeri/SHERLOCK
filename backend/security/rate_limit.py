"""
SHERLOCK — Stage E6: Rate limiting.

Optional (`SHERLOCK_RATE_LIMIT_ENABLED`, default false — same pattern as
`SHERLOCK_AUTH_ENABLED`), so a zero-configuration dev/test run — including
this stage's own `validate_stage_e*.py` scripts, which log in many times
in quick succession — behaves exactly as before. When enabled, applied
specifically to `/auth/login` and `/auth/refresh`, the two endpoints
where brute-forcing is the actual risk; every other route is unaffected.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_ENABLED = os.getenv("SHERLOCK_RATE_LIMIT_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
LOGIN_RATE_LIMIT = os.getenv("SHERLOCK_LOGIN_RATE_LIMIT", "20/minute")
REFRESH_RATE_LIMIT = os.getenv("SHERLOCK_REFRESH_RATE_LIMIT", "60/minute")

limiter = Limiter(key_func=get_remote_address, enabled=RATE_LIMIT_ENABLED)
