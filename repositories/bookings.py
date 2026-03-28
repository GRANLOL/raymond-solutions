from __future__ import annotations

import re
from datetime import timedelta

from .base import _slot_overlaps, _time_to_minutes, _to_iso_date, aiosqlite, db_connect, datetime
from config import salon_config
from time_utils import build_reminder_schedule, combine_salon_datetime, get_salon_now, get_salon_today


class ActiveBookingLimitReachedError(Exception):
    pass


def _normalize_phone_digits(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return digits


def _duration_from_range(start_time: str, end_time: str) -> int:
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None or end_minutes <= start_minutes:
        return 0
    return end_minutes - start_minutes


def _parse_working_hours(working_hours: str) -> tuple[int, int]:
    start_str, end_str = ("10:00", "20:00")
    if working_hours and "-" in working_hours:
        raw_start, raw_end = [part.strip() for part in working_hours.split("-", 1)]
        if ":" in raw_start and ":" in raw_end:
            start_str, end_str = raw_start[-5:], raw_end[:5]
    start_minutes = _time_to_minutes(start_str)
    end_minutes = _time_to_minutes(end_str)
    if start_minutes is None or end_minutes is None:
        return 10 * 60, 20 * 60
    return start_minutes, end_minutes


def _booking_datetime(date: str, time: str):
    booking_date = datetime.strptime(date, "%d.%m.%Y").date()
    booking_time = datetime.strptime(time, "%H:%M").time()
    return combine_salon_datetime(booking_date, booking_time)


def _build_busy_slot(
    time_value: str,
    duration: int,
    *,
    kind: str = "booking",
    label: str | None = None,
) -> dict:
    slot = {
        "time": time_value,
        "duration": int(duration or 60),
        "kind": kind,
    }
    if label:
        slot["label"] = label
    return slot


def _is_date_open_for_break(date_str: str) -> bool:
    try:
        target_date = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        return False

    js_weekday = (target_date.weekday() + 1) % 7
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    return js_weekday in working_days and date_str not in blacklisted_dates


def _get_lunch_break_slot(date_str: str) -> dict | None:
    if not bool(salon_config.get("lunch_break_enabled", False)):
        return None
    if not _is_date_open_for_break(date_str):
        return None

    start_time = str(salon_config.get("lunch_break_start", "") or "").strip()
    end_time = str(salon_config.get("lunch_break_end", "") or "").strip()
    duration = _duration_from_range(start_time, end_time)
    if duration <= 0:
        return None
    return _build_busy_slot(start_time, duration, kind="lunch", label="Обед")


def _collect_busy_slots(date_str: str, booking_rows, blocked_rows) -> list[dict]:
    busy_slots = [
        _build_busy_slot(time_value, duration if duration is not None else 60)
        for time_value, duration in booking_rows
    ]
    for start_time, end_time, reason in blocked_rows:
        duration = _duration_from_range(start_time, end_time)
        if duration > 0:
            busy_slots.append(
                _build_busy_slot(
                    start_time,
                    duration,
                    kind="break",
                    label=(reason or "Перерыв"),
                )
            )

    lunch_slot = _get_lunch_break_slot(date_str)
    if lunch_slot is not None:
        busy_slots.append(lunch_slot)

    busy_slots.sort(key=lambda item: item["time"])
    return busy_slots


async def sync_completed_bookings() -> int:
    now = get_salon_now()
    updated = 0
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT id, date, time, duration
            FROM bookings
            WHERE status = 'scheduled'
            """
        ) as cursor:
            rows = await cursor.fetchall()

        for booking_id, date_str, time_str, duration in rows:
            try:
                booking_dt = _booking_datetime(date_str, time_str)
            except ValueError:
                continue
            duration_minutes = int(duration or 60)
            if booking_dt.timestamp() + duration_minutes * 60 <= now.timestamp():
                await db.execute(
                    """
                    UPDATE bookings
                    SET status = 'completed',
                        completed_at = COALESCE(completed_at, ?)
                    WHERE id = ? AND status = 'scheduled'
                    """,
                    (now.isoformat(), booking_id),
                )
                updated += 1
        if updated:
            await db.commit()
    return updated


async def add_booking(
    user_id,
    name,
    phone,
    date,
    time,
    duration=60,
    service_name=None,
    price=0,
    *,
    source: str = "telegram",
    notes: str | None = None,
    created_by_admin: bool = False,
):
    date_iso = _to_iso_date(date)
    booking_dt = _booking_datetime(date, time)
    schedule = build_reminder_schedule(booking_dt)
    async with db_connect() as db:
        await db.execute(
            """
            INSERT INTO bookings (
                user_id, name, phone, date, date_iso, time, duration, service_name, price,
                created_at, first_reminder_due_at, second_reminder_due_at, status, source, notes, created_by_admin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?, ?)
            """,
            (
                user_id, name, phone, date, date_iso, time, duration, service_name, price,
                schedule["created_at"], schedule["first_reminder_due_at"], schedule["second_reminder_due_at"],
                source, notes, 1 if created_by_admin else 0,
            ),
        )
        await db.commit()


async def create_booking_if_available(
    user_id,
    name,
    phone,
    date,
    time,
    duration=60,
    service_name=None,
    price=0,
    *,
    source: str = "telegram",
    notes: str | None = None,
    created_by_admin: bool = False,
    enforce_active_limit: bool = True,
):
    slot_start = _time_to_minutes(time)
    date_iso = _to_iso_date(date)
    if slot_start is None:
        return False

    async with db_connect(timeout=30) as db:
        await db.execute("BEGIN IMMEDIATE")

        if enforce_active_limit:
            active_limit = max(int(salon_config.get("max_active_bookings_per_user", 3) or 3), 1)
            async with db.execute(
                "SELECT COUNT(id) FROM bookings WHERE user_id = ? AND status = 'scheduled'",
                (user_id,),
            ) as cursor:
                active_count = (await cursor.fetchone())[0]
            if active_count >= active_limit:
                await db.rollback()
                raise ActiveBookingLimitReachedError(active_limit)

        async with db.execute(
            "SELECT time, duration FROM bookings WHERE date = ? AND status = 'scheduled'",
            (date,),
        ) as cursor:
            rows = await cursor.fetchall()
        async with db.execute(
            "SELECT start_time, end_time, reason FROM blocked_slots WHERE date = ?",
            (date,),
        ) as cursor:
            blocked_rows = await cursor.fetchall()

        for busy in _collect_busy_slots(date, rows, blocked_rows):
            busy_time = busy["time"]
            busy_duration = int(busy.get("duration") or 60)
            busy_start = _time_to_minutes(busy_time)
            if busy_start is None:
                continue
            if _slot_overlaps(slot_start, int(duration or 60), busy_start, busy_duration):
                await db.rollback()
                return False

        booking_dt = _booking_datetime(date, time)
        schedule = build_reminder_schedule(booking_dt)
        await db.execute(
            """
            INSERT INTO bookings (
                user_id, name, phone, date, date_iso, time, duration, service_name, price,
                created_at, first_reminder_due_at, second_reminder_due_at, status, source, notes, created_by_admin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?, ?)
            """,
            (
                user_id, name, phone, date, date_iso, time, duration, service_name, price,
                schedule["created_at"], schedule["first_reminder_due_at"], schedule["second_reminder_due_at"],
                source, notes, 1 if created_by_admin else 0,
            ),
        )
        await db.commit()
        return True


async def create_manual_booking(
    *,
    name: str,
    phone: str | None,
    date: str,
    time: str,
    duration: int = 60,
    service_name: str | None = None,
    price: int = 0,
    source: str = "manual",
    notes: str | None = None,
) -> bool:
    linked_user_id = None
    if phone:
        linked_user_id = await get_existing_user_id_by_phone(phone)

    return await create_booking_if_available(
        user_id=linked_user_id,
        name=name,
        phone=phone,
        date=date,
        time=time,
        duration=duration,
        service_name=service_name,
        price=price,
        source=source,
        notes=notes,
        created_by_admin=True,
        enforce_active_limit=False,
    )


async def get_client_snapshot_by_phone(phone: str):
    normalized = _normalize_phone_digits(phone)
    if not normalized:
        return None

    async with db_connect() as db:
        async with db.execute(
            """
            SELECT name, phone, date, created_at
            FROM bookings
            WHERE phone IS NOT NULL AND TRIM(phone) != ''
            ORDER BY COALESCE(date_iso, date) DESC, time DESC, id DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()

        matches = [
            row
            for row in rows
            if _normalize_phone_digits(row[1]) == normalized
        ]
        if not matches:
            return None

        latest_name, raw_phone, last_date, created_at = matches[0]
        return {
            "name": latest_name,
            "phone": raw_phone,
            "last_date": last_date,
            "created_at": created_at,
            "total_bookings": len(matches),
        }


async def get_existing_user_id_by_phone(phone: str) -> int | None:
    normalized = _normalize_phone_digits(phone)
    if not normalized:
        return None

    async with db_connect() as db:
        async with db.execute(
            """
            SELECT user_id, phone
            FROM bookings
            WHERE user_id IS NOT NULL
              AND phone IS NOT NULL
              AND TRIM(phone) != ''
            ORDER BY id DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()

    for user_id, raw_phone in rows:
        if _normalize_phone_digits(raw_phone) == normalized:
            return int(user_id)
    return None


async def attach_bookings_to_user_by_phone(phone: str, user_id: int) -> int:
    normalized = _normalize_phone_digits(phone)
    if not normalized:
        return 0

    async with db_connect() as db:
        async with db.execute(
            """
            SELECT id, phone
            FROM bookings
            WHERE (user_id IS NULL OR user_id != ?)
              AND phone IS NOT NULL
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        matching_ids = [
            booking_id
            for booking_id, raw_phone in rows
            if _normalize_phone_digits(raw_phone) == normalized
        ]
        if not matching_ids:
            return 0

        placeholders = ", ".join("?" for _ in matching_ids)
        await db.execute(
            f"UPDATE bookings SET user_id = ? WHERE id IN ({placeholders})",
            (user_id, *matching_ids),
        )
        await db.commit()
        return len(matching_ids)


async def get_booked_slots(date):
    async with db_connect() as db:
        async with db.execute(
            "SELECT time FROM bookings WHERE date = ? AND status = 'scheduled'",
            (date,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_busy_slots_by_date(date: str):
    async with db_connect() as db:
        async with db.execute(
            "SELECT time, duration FROM bookings WHERE date = ? AND status = 'scheduled'",
            (date,),
        ) as cursor:
            rows = await cursor.fetchall()
        async with db.execute(
            "SELECT start_time, end_time, reason FROM blocked_slots WHERE date = ? ORDER BY start_time",
            (date,),
        ) as cursor:
            blocked_rows = await cursor.fetchall()

    return _collect_busy_slots(date, rows, blocked_rows)


async def get_all_bookings():
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT b.name, b.phone, b.date, b.time, b.price, b.status
            FROM bookings b
            WHERE b.status IN ('scheduled', 'completed')
            ORDER BY COALESCE(b.date_iso, b.date), b.time
            """
        ) as cursor:
            return await cursor.fetchall()


async def get_all_bookings_export():
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT
                b.id,
                b.name,
                b.phone,
                b.service_name,
                b.date,
                b.time,
                b.duration,
                b.price,
                b.status,
                COALESCE(b.source, 'telegram'),
                COALESCE(b.notes, ''),
                COALESCE(b.created_by_admin, 0),
                b.created_at
            FROM bookings b
            ORDER BY COALESCE(b.date_iso, b.date) DESC, b.time DESC, b.id DESC
            """
        ) as cursor:
            return await cursor.fetchall()


async def get_completed_bookings_export():
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT
                b.id,
                b.name,
                b.phone,
                b.service_name,
                b.date,
                b.time,
                b.duration,
                b.price,
                b.status,
                COALESCE(b.source, 'telegram'),
                COALESCE(b.notes, ''),
                COALESCE(b.created_by_admin, 0),
                b.completed_at
            FROM bookings b
            WHERE b.status = 'completed'
            ORDER BY COALESCE(b.date_iso, b.date) DESC, b.time DESC, b.id DESC
            """
        ) as cursor:
            return await cursor.fetchall()


async def get_client_base_export():
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT
                COALESCE(NULLIF(TRIM(phone), ''), 'Без телефона') AS phone_key,
                MAX(COALESCE(NULLIF(TRIM(name), ''), 'Без имени')) AS name,
                MAX(COALESCE(NULLIF(TRIM(phone), ''), '')) AS phone,
                COUNT(*) AS total_bookings,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_bookings,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_bookings,
                SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) AS no_show_bookings,
                SUM(CASE WHEN status = 'completed' THEN COALESCE(price, 0) ELSE 0 END) AS completed_revenue,
                MAX(COALESCE(date_iso, '')) AS last_date_iso,
                MAX(COALESCE(created_at, '')) AS last_created_at
            FROM bookings
            GROUP BY phone_key
            ORDER BY total_bookings DESC, completed_revenue DESC, name ASC
            """
        ) as cursor:
            return await cursor.fetchall()


async def get_future_bookings_outside_working_hours(working_hours: str):
    start_mins, end_mins = _parse_working_hours(working_hours)
    now = get_salon_now()

    async with db_connect() as db:
        async with db.execute(
            """
            SELECT id, name, date, time, duration
            FROM bookings
            WHERE status = 'scheduled'
            ORDER BY COALESCE(date_iso, date), time
            """
        ) as cursor:
            rows = await cursor.fetchall()

    conflicts = []
    for booking_id, name, date_str, time_str, duration in rows:
        try:
            booking_dt = _booking_datetime(date_str, time_str)
        except ValueError:
            continue
        duration_minutes = int(duration or 60)
        if booking_dt.timestamp() + duration_minutes * 60 <= now.timestamp():
            continue

        slot_start = _time_to_minutes(time_str)
        if slot_start is None:
            continue
        if slot_start < start_mins or slot_start + duration_minutes > end_mins:
            conflicts.append(
                {
                    "id": booking_id,
                    "name": name,
                    "date": date_str,
                    "time": time_str,
                    "duration": duration_minutes,
                }
            )
    return conflicts


async def get_all_bookings_detailed():
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT b.id, b.name, b.phone, b.date, b.time, b.price, b.status
            FROM bookings b
            ORDER BY COALESCE(b.date_iso, b.date), b.time
            """
        ) as cursor:
            return await cursor.fetchall()


async def get_all_bookings_detailed_filtered(source: str | None = None):
    query = """
        SELECT b.id, b.name, b.phone, b.date, b.time, b.price, b.status
        FROM bookings b
    """
    params: list = []
    if source and source != "all":
        query += " WHERE COALESCE(b.source, 'telegram') = ?"
        params.append(source)
    query += " ORDER BY COALESCE(b.date_iso, b.date), b.time"

    async with db_connect() as db:
        async with db.execute(query, tuple(params)) as cursor:
            return await cursor.fetchall()


async def clear_bookings():
    async with db_connect() as db:
        await db.execute("DELETE FROM bookings")
        await db.commit()


async def get_bookings_by_date_full(target_date: str):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT b.name, b.phone, b.date, b.time, b.price, b.service_name, COALESCE(b.source, 'telegram'), COALESCE(b.notes, ''), COALESCE(b.created_by_admin, 0)
            FROM bookings b
            WHERE b.date = ? AND b.status != 'cancelled'
            ORDER BY b.time
            """,
            (target_date,),
        ) as cursor:
            return await cursor.fetchall()


async def get_bookings_by_date_detailed(target_date: str):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT b.id, b.name, b.phone, b.date, b.time, b.price, b.status
            FROM bookings b
            WHERE b.date = ?
            ORDER BY b.time
            """,
            (target_date,),
        ) as cursor:
            return await cursor.fetchall()


async def get_bookings_by_date_detailed_filtered(target_date: str, source: str | None = None):
    query = """
        SELECT b.id, b.name, b.phone, b.date, b.time, b.price, b.status
        FROM bookings b
        WHERE b.date = ?
    """
    params: list = [target_date]
    if source and source != "all":
        query += " AND COALESCE(b.source, 'telegram') = ?"
        params.append(source)
    query += " ORDER BY b.time"

    async with db_connect() as db:
        async with db.execute(query, tuple(params)) as cursor:
            return await cursor.fetchall()


async def get_user_booking(user_id: int):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT name, phone, date, time, id
            FROM bookings
            WHERE user_id = ? AND status = 'scheduled'
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ) as cursor:
            return await cursor.fetchone()


async def get_user_bookings(user_id: int):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT id, name, phone, date, time, status
            FROM bookings
            WHERE user_id = ?
            ORDER BY
                CASE status
                    WHEN 'scheduled' THEN 0
                    WHEN 'completed' THEN 1
                    ELSE 2
                END,
                COALESCE(date_iso, date) DESC,
                time DESC,
                id DESC
            """,
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()


async def cancel_booking_by_id(booking_id: int):
    async with db_connect() as db:
        await db.execute(
            """
            UPDATE bookings
            SET status = 'cancelled',
                cancelled_at = COALESCE(cancelled_at, ?)
            WHERE id = ?
            """,
            (get_salon_now().isoformat(), booking_id),
        )
        await db.commit()


async def delete_booking_by_id(booking_id: int):
    async with db_connect() as db:
        await db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        await db.commit()


async def get_booking_record_by_id(booking_id: int):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT id, user_id, name, phone, date, time, status, duration
            FROM bookings
            WHERE id = ?
            """,
            (booking_id,),
        ) as cursor:
            return await cursor.fetchone()


async def get_booking_admin_details(booking_id: int):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT
                id,
                user_id,
                name,
                phone,
                date,
                time,
                status,
                duration,
                service_name,
                price,
                COALESCE(source, 'telegram'),
                COALESCE(notes, ''),
                COALESCE(created_by_admin, 0),
                created_at
            FROM bookings
            WHERE id = ?
            """,
            (booking_id,),
        ) as cursor:
            return await cursor.fetchone()


async def update_booking_name(booking_id: int, name: str):
    async with db_connect() as db:
        await db.execute("UPDATE bookings SET name = ? WHERE id = ?", (name, booking_id))
        await db.commit()


async def update_booking_phone(booking_id: int, phone: str):
    async with db_connect() as db:
        await db.execute("UPDATE bookings SET phone = ? WHERE id = ?", (phone, booking_id))
        await db.commit()


async def update_booking_source(booking_id: int, source: str):
    async with db_connect() as db:
        await db.execute("UPDATE bookings SET source = ? WHERE id = ?", (source, booking_id))
        await db.commit()


async def update_booking_notes(booking_id: int, notes: str | None):
    async with db_connect() as db:
        await db.execute("UPDATE bookings SET notes = ? WHERE id = ?", (notes, booking_id))
        await db.commit()


async def update_booking_status(booking_id: int, status: str):
    now_iso = get_salon_now().isoformat()
    async with db_connect() as db:
        if status == "completed":
            await db.execute(
                """
                UPDATE bookings
                SET status = 'completed',
                    completed_at = COALESCE(completed_at, ?),
                    cancelled_at = NULL
                WHERE id = ?
                """,
                (now_iso, booking_id),
            )
        elif status == "no_show":
            await db.execute(
                """
                UPDATE bookings
                SET status = 'no_show',
                    completed_at = NULL,
                    cancelled_at = NULL
                WHERE id = ?
                """,
                (booking_id,),
            )
        elif status == "cancelled":
            await db.execute(
                """
                UPDATE bookings
                SET status = 'cancelled',
                    cancelled_at = COALESCE(cancelled_at, ?),
                    completed_at = NULL
                WHERE id = ?
                """,
                (now_iso, booking_id),
            )
        else:
            await db.execute(
                """
                UPDATE bookings
                SET status = 'scheduled',
                    completed_at = NULL,
                    cancelled_at = NULL
                WHERE id = ?
                """,
                (booking_id,),
            )
        await db.commit()


async def reschedule_booking_if_available(booking_id: int, date: str, time: str) -> bool:
    slot_start = _time_to_minutes(time)
    date_iso = _to_iso_date(date)
    if slot_start is None:
        return False

    async with db_connect(timeout=30) as db:
        await db.execute("BEGIN IMMEDIATE")

        async with db.execute(
            """
            SELECT duration, status
            FROM bookings
            WHERE id = ?
            """,
            (booking_id,),
        ) as cursor:
            booking_row = await cursor.fetchone()

        if not booking_row:
            await db.rollback()
            return False

        duration, status = booking_row
        if status != "scheduled":
            await db.rollback()
            return False

        normalized_duration = int(duration or 60)

        async with db.execute(
            """
            SELECT id, time, duration
            FROM bookings
            WHERE date = ? AND status = 'scheduled' AND id != ?
            """,
            (date, booking_id),
        ) as cursor:
            rows = await cursor.fetchall()

        for _busy_booking_id, busy_time, busy_duration in rows:
            busy_start = _time_to_minutes(busy_time)
            if busy_start is None:
                continue
            if _slot_overlaps(slot_start, normalized_duration, busy_start, int(busy_duration or 60)):
                await db.rollback()
                return False

        booking_dt = _booking_datetime(date, time)
        schedule = build_reminder_schedule(booking_dt)
        await db.execute(
            """
            UPDATE bookings
            SET date = ?,
                date_iso = ?,
                time = ?,
                status = 'scheduled',
                completed_at = NULL,
                cancelled_at = NULL,
                created_at = ?,
                first_reminder_due_at = ?,
                second_reminder_due_at = ?,
                first_reminder_sent_at = NULL,
                second_reminder_sent_at = NULL
            WHERE id = ?
            """,
            (
                date,
                date_iso,
                time,
                schedule["created_at"],
                schedule["first_reminder_due_at"],
                schedule["second_reminder_due_at"],
                booking_id,
            ),
        )
        await db.commit()
        return True


async def get_due_first_reminders(now_iso: str):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT id, user_id, name, date, time, first_reminder_due_at
            FROM bookings
            WHERE status = 'scheduled'
              AND first_reminder_due_at IS NOT NULL
              AND first_reminder_sent_at IS NULL
              AND first_reminder_due_at <= ?
            """,
            (now_iso,),
        ) as cursor:
            return await cursor.fetchall()


async def get_due_second_reminders(now_iso: str):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT id, user_id, name, date, time, second_reminder_due_at
            FROM bookings
            WHERE status = 'scheduled'
              AND second_reminder_due_at IS NOT NULL
              AND second_reminder_sent_at IS NULL
              AND second_reminder_due_at <= ?
            """,
            (now_iso,),
        ) as cursor:
            return await cursor.fetchall()


async def get_booking_by_id(booking_id: int):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT name, phone, date, time, user_id, status
            FROM bookings
            WHERE id = ?
            """,
            (booking_id,),
        ) as cursor:
            return await cursor.fetchone()


async def search_bookings(query: str, limit: int = 10):
    like_query = f"%{query.strip()}%"
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT id, name, phone, date, time, status
            FROM bookings
            WHERE name LIKE ?
               OR phone LIKE ?
               OR date LIKE ?
               OR time LIKE ?
               OR COALESCE(service_name, '') LIKE ?
               OR COALESCE(source, 'telegram') LIKE ?
               OR COALESCE(notes, '') LIKE ?
            ORDER BY COALESCE(date_iso, date) DESC, time DESC, id DESC
            LIMIT ?
            """,
            (like_query, like_query, like_query, like_query, like_query, like_query, like_query, int(limit)),
        ) as cursor:
            return await cursor.fetchall()


async def mark_first_reminder_sent(booking_id: int, sent_at: str):
    async with db_connect() as db:
        await db.execute(
            """
            UPDATE bookings
            SET first_reminder_sent_at = COALESCE(first_reminder_sent_at, ?)
            WHERE id = ?
            """,
            (sent_at, booking_id),
        )
        await db.commit()


async def mark_second_reminder_sent(booking_id: int, sent_at: str):
    async with db_connect() as db:
        await db.execute(
            """
            UPDATE bookings
            SET second_reminder_sent_at = COALESCE(second_reminder_sent_at, ?)
            WHERE id = ?
            """,
            (sent_at, booking_id),
        )
        await db.commit()


async def delete_bookings_by_date(target_date: str):
    async with db_connect() as db:
        async with db.execute("SELECT COUNT(id) FROM bookings WHERE date = ?", (target_date,)) as cursor:
            count = (await cursor.fetchone())[0]
        if count > 0:
            await db.execute("DELETE FROM bookings WHERE date = ?", (target_date,))
            await db.commit()
        return count


async def delete_bookings_by_period(start_date: str, end_date: str):
    try:
        start_iso = datetime.strptime(start_date, "%d.%m.%Y").date().isoformat()
        end_iso = datetime.strptime(end_date, "%d.%m.%Y").date().isoformat()
    except ValueError:
        return 0

    async with db_connect() as db:
        async with db.execute(
            "SELECT COUNT(id) FROM bookings WHERE date_iso IS NOT NULL AND date_iso BETWEEN ? AND ?",
            (start_iso, end_iso),
        ) as cursor:
            count = (await cursor.fetchone())[0]
        if count > 0:
            await db.execute(
                "DELETE FROM bookings WHERE date_iso IS NOT NULL AND date_iso BETWEEN ? AND ?",
                (start_iso, end_iso),
            )
            await db.commit()
        return count


async def delete_past_bookings():
    today_iso = get_salon_today().isoformat()
    async with db_connect() as db:
        async with db.execute(
            "SELECT COUNT(id) FROM bookings WHERE date_iso IS NOT NULL AND date_iso < ?",
            (today_iso,),
        ) as cursor:
            count = (await cursor.fetchone())[0]
        if count > 0:
            await db.execute("DELETE FROM bookings WHERE date_iso IS NOT NULL AND date_iso < ?", (today_iso,))
            await db.commit()
        return count


async def add_blocked_slot(date: str, start_time: str, end_time: str, reason: str | None = None):
    date_iso = _to_iso_date(date)
    async with db_connect() as db:
        await db.execute(
            """
            INSERT INTO blocked_slots (date, date_iso, start_time, end_time, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (date, date_iso, start_time, end_time, reason or None),
        )
        await db.commit()


async def get_blocked_slots(date: str | None = None):
    async with db_connect() as db:
        if date is None:
            query = """
                SELECT id, date, start_time, end_time, reason
                FROM blocked_slots
                ORDER BY COALESCE(date_iso, date), start_time
            """
            params = ()
        else:
            query = """
                SELECT id, date, start_time, end_time, reason
                FROM blocked_slots
                WHERE date = ?
                ORDER BY start_time
            """
            params = (date,)
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()


async def delete_blocked_slot(blocked_slot_id: int):
    async with db_connect() as db:
        await db.execute("DELETE FROM blocked_slots WHERE id = ?", (blocked_slot_id,))
        await db.commit()


async def get_all_busy_slots():
    from collections import defaultdict

    async with db_connect() as db:
        async with db.execute(
            "SELECT date, time, duration FROM bookings WHERE status = 'scheduled'"
        ) as cursor:
            rows = await cursor.fetchall()
        async with db.execute("SELECT date, start_time, end_time, reason FROM blocked_slots") as cursor:
            blocked_rows = await cursor.fetchall()

    busy_slots = defaultdict(list)
    bookings_by_date = defaultdict(list)
    breaks_by_date = defaultdict(list)

    for date, time_str, duration in rows:
        bookings_by_date[date].append((time_str, duration))
    for date, start_time, end_time, reason in blocked_rows:
        breaks_by_date[date].append((start_time, end_time, reason))

    all_dates = set(bookings_by_date.keys()) | set(breaks_by_date.keys())
    booking_window = max(int(salon_config.get("booking_window", 7) or 7), 1)
    today = get_salon_today()
    for offset in range(booking_window):
        all_dates.add((today + timedelta(days=offset)).strftime("%d.%m.%Y"))

    for date_str in sorted(all_dates, key=lambda value: _to_iso_date(value) or value):
        collected = _collect_busy_slots(
            date_str,
            bookings_by_date.get(date_str, []),
            breaks_by_date.get(date_str, []),
        )
        if collected:
            busy_slots[date_str].extend(collected)

    return dict(busy_slots)
