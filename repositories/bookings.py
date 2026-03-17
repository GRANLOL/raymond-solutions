from __future__ import annotations

from .base import _slot_overlaps, _time_to_minutes, _to_iso_date, aiosqlite, db_connect, datetime
from time_utils import build_reminder_schedule, combine_salon_datetime, get_salon_now, get_salon_today


def _duration_from_range(start_time: str, end_time: str) -> int:
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None or end_minutes <= start_minutes:
        return 0
    return end_minutes - start_minutes


def _booking_datetime(date: str, time: str):
    booking_date = datetime.strptime(date, "%d.%m.%Y").date()
    booking_time = datetime.strptime(time, "%H:%M").time()
    return combine_salon_datetime(booking_date, booking_time)


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


async def add_booking(user_id, name, phone, date, time, duration=60, service_name=None, price=0):
    date_iso = _to_iso_date(date)
    booking_dt = _booking_datetime(date, time)
    schedule = build_reminder_schedule(booking_dt)
    async with db_connect() as db:
        await db.execute(
            """
            INSERT INTO bookings (
                user_id, name, phone, date, date_iso, time, duration, service_name, price,
                created_at, first_reminder_due_at, second_reminder_due_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')
            """,
            (
                user_id, name, phone, date, date_iso, time, duration, service_name, price,
                schedule["created_at"], schedule["first_reminder_due_at"], schedule["second_reminder_due_at"],
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
):
    slot_start = _time_to_minutes(time)
    date_iso = _to_iso_date(date)
    if slot_start is None:
        return False

    async with db_connect(timeout=30) as db:
        await db.execute("BEGIN IMMEDIATE")

        async with db.execute(
            "SELECT time, duration FROM bookings WHERE date = ? AND status = 'scheduled'",
            (date,),
        ) as cursor:
            rows = await cursor.fetchall()

        for busy_time, busy_duration in rows:
            busy_start = _time_to_minutes(busy_time)
            if busy_start is None:
                continue
            normalized_busy_duration = int(busy_duration or 60)
            if _slot_overlaps(slot_start, int(duration or 60), busy_start, normalized_busy_duration):
                await db.rollback()
                return False

        booking_dt = _booking_datetime(date, time)
        schedule = build_reminder_schedule(booking_dt)
        await db.execute(
            """
            INSERT INTO bookings (
                user_id, name, phone, date, date_iso, time, duration, service_name, price,
                created_at, first_reminder_due_at, second_reminder_due_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')
            """,
            (
                user_id, name, phone, date, date_iso, time, duration, service_name, price,
                schedule["created_at"], schedule["first_reminder_due_at"], schedule["second_reminder_due_at"],
            ),
        )
        await db.commit()
        return True


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
            "SELECT start_time, end_time FROM blocked_slots WHERE date = ? ORDER BY start_time",
            (date,),
        ) as cursor:
            blocked_rows = await cursor.fetchall()

    busy_slots = [
        {"time": time_value, "duration": duration if duration is not None else 60}
        for time_value, duration in rows
    ]
    for start_time, end_time in blocked_rows:
        duration = _duration_from_range(start_time, end_time)
        if duration > 0:
            busy_slots.append({"time": start_time, "duration": duration})
    return busy_slots


async def get_all_bookings():
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT b.name, b.phone, b.date, b.time, b.price
            FROM bookings b
            WHERE b.status != 'cancelled'
            ORDER BY COALESCE(b.date_iso, b.date), b.time
            """
        ) as cursor:
            return await cursor.fetchall()


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


async def clear_bookings():
    async with db_connect() as db:
        await db.execute("DELETE FROM bookings")
        await db.commit()


async def get_bookings_by_date_full(target_date: str):
    async with db_connect() as db:
        async with db.execute(
            """
            SELECT b.name, b.phone, b.date, b.time, b.price
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
            ORDER BY COALESCE(date_iso, date) DESC, time DESC, id DESC
            LIMIT ?
            """,
            (like_query, like_query, like_query, like_query, int(limit)),
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
        async with db.execute("SELECT date, start_time, end_time FROM blocked_slots") as cursor:
            blocked_rows = await cursor.fetchall()

    busy_slots = defaultdict(list)
    if rows:
        for date, time_str, duration in rows:
            busy_slots[date].append({"time": time_str, "duration": duration or 60})
    if blocked_rows:
        for date, start_time, end_time in blocked_rows:
            duration = _duration_from_range(start_time, end_time)
            if duration > 0:
                busy_slots[date].append({"time": start_time, "duration": duration})
    return dict(busy_slots)
