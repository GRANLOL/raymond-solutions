from __future__ import annotations

import re
from datetime import datetime, timedelta

import aiosqlite
from config import DATABASE_PATH
from time_utils import get_salon_today


def db_connect(**kwargs):
    return aiosqlite.connect(str(DATABASE_PATH), **kwargs)


def _slot_overlaps(slot_start: int, slot_duration: int, busy_start: int, busy_duration: int) -> bool:
    slot_end = slot_start + slot_duration
    busy_end = busy_start + busy_duration
    return slot_start < busy_end and slot_end > busy_start


def _time_to_minutes(value: str) -> int | None:
    try:
        hours, minutes = map(int, value.split(":"))
    except (AttributeError, TypeError, ValueError):
        return None
    return hours * 60 + minutes


def _period_start_date(period_days: int):
    today = get_salon_today()
    return today if period_days <= 0 else today - timedelta(days=period_days - 1)


def _parse_booking_date(value: str):
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None


def _to_iso_date(value: str) -> str | None:
    parsed = _parse_booking_date(value)
    return parsed.isoformat() if parsed else None
