from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock


_LOCK = Lock()
_LAST_SEEN: dict[str, datetime] = {}


def get_rate_limit_remaining(key: str, cooldown_seconds: int) -> int:
    now = datetime.utcnow()
    with _LOCK:
        last_seen = _LAST_SEEN.get(key)
        if last_seen is None:
            _LAST_SEEN[key] = now
            return 0

        remaining = cooldown_seconds - int((now - last_seen).total_seconds())
        if remaining > 0:
            return remaining

        _LAST_SEEN[key] = now

        # Drop stale keys opportunistically.
        stale_before = now - timedelta(hours=1)
        for old_key, old_value in list(_LAST_SEEN.items()):
            if old_value < stale_before:
                _LAST_SEEN.pop(old_key, None)
        return 0
