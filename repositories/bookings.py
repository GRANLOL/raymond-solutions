from __future__ import annotations

from .base import _slot_overlaps, _time_to_minutes, _to_iso_date, aiosqlite, datetime


def _duration_from_range(start_time: str, end_time: str) -> int:
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None or end_minutes <= start_minutes:
        return 0
    return end_minutes - start_minutes

async def add_booking(user_id, name, phone, date, time, master_id=None, duration=60, service_name=None, price=0):
    date_iso = _to_iso_date(date)
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute(
            "INSERT INTO bookings (user_id, name, phone, date, date_iso, time, master_id, duration, service_name, price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, phone, date, date_iso, time, master_id, duration, service_name, price)
        )
        await db.commit()

async def create_booking_if_available(
    user_id,
    name,
    phone,
    date,
    time,
    master_id=None,
    duration=60,
    service_name=None,
    price=0,
):
    slot_start = _time_to_minutes(time)
    date_iso = _to_iso_date(date)
    if slot_start is None:
        return False

    async with aiosqlite.connect("bookings.db", timeout=30) as db:
        await db.execute("BEGIN IMMEDIATE")

        if master_id is not None:
            query = "SELECT time, duration FROM bookings WHERE date = ? AND master_id = ?"
            params = (date, master_id)
        else:
            query = "SELECT time, duration FROM bookings WHERE date = ?"
            params = (date,)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        for busy_time, busy_duration in rows:
            busy_start = _time_to_minutes(busy_time)
            if busy_start is None:
                continue
            normalized_busy_duration = int(busy_duration or 60)
            if _slot_overlaps(slot_start, int(duration or 60), busy_start, normalized_busy_duration):
                await db.rollback()
                return False

        await db.execute(
            "INSERT INTO bookings (user_id, name, phone, date, date_iso, time, master_id, duration, service_name, price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, phone, date, date_iso, time, master_id, duration, service_name, price),
        )
        await db.commit()
        return True

async def get_booked_slots(date, master_id=None):
    async with aiosqlite.connect("bookings.db") as db:
        if master_id is not None:
            async with db.execute("SELECT time FROM bookings WHERE date = ? AND master_id = ?", (date, master_id)) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute("SELECT time FROM bookings WHERE date = ?", (date,)) as cursor:
                rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_busy_slots_by_date(date: str, master_id: int | None = None):
    async with aiosqlite.connect("bookings.db") as db:
        if master_id is not None:
            query = "SELECT time, duration FROM bookings WHERE date = ? AND master_id = ?"
            params = (date, master_id)
        else:
            query = "SELECT time, duration FROM bookings WHERE date = ?"
            params = (date,)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        async with db.execute(
            "SELECT start_time, end_time FROM blocked_slots WHERE date = ? ORDER BY start_time",
            (date,),
        ) as cursor:
            blocked_rows = await cursor.fetchall()

    busy_slots = [
        {
            "time": row[0],
            "duration": row[1] if len(row) > 1 and row[1] is not None else 60,
        }
        for row in rows
    ]
    for start_time, end_time in blocked_rows:
        duration = _duration_from_range(start_time, end_time)
        if duration > 0:
            busy_slots.append({"time": start_time, "duration": duration})
    return busy_slots

async def get_all_bookings():
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT b.name, b.phone, b.date, b.time, b.price
            FROM bookings b 
            ORDER BY COALESCE(b.date_iso, b.date), b.time
        """) as cursor:
            return await cursor.fetchall()

async def get_all_bookings_detailed():
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT b.id, b.name, b.phone, b.date, b.time, b.price
            FROM bookings b
            ORDER BY COALESCE(b.date_iso, b.date), b.time
        """) as cursor:
            return await cursor.fetchall()

async def clear_bookings():
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("DELETE FROM bookings")
        await db.commit()

async def get_bookings_by_date_full(target_date: str):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT b.name, b.phone, b.date, b.time, b.price
            FROM bookings b 
            WHERE b.date = ? 
            ORDER BY b.time
        """, (target_date,)) as cursor:
            return await cursor.fetchall()

async def get_bookings_by_date_detailed(target_date: str):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT b.id, b.name, b.phone, b.date, b.time, b.price
            FROM bookings b
            WHERE b.date = ?
            ORDER BY b.time
        """, (target_date,)) as cursor:
            return await cursor.fetchall()

async def get_bookings_by_master(master_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT name, phone, date, time FROM bookings WHERE master_id = ? ORDER BY COALESCE(date_iso, date), time", (master_id,)) as cursor:
            return await cursor.fetchall()

async def get_bookings_by_master_and_date(master_id: int, target_date: str):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT name, phone, date, time FROM bookings WHERE master_id = ? AND date = ? ORDER BY time", (master_id, target_date)) as cursor:
            return await cursor.fetchall()

async def get_user_booking(user_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        # Fetch the most recent booking
        async with db.execute("SELECT name, phone, date, time, id FROM bookings WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)) as cursor:
            return await cursor.fetchone()

async def get_user_bookings(user_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT id, name, phone, date, time, master_id
            FROM bookings
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,)) as cursor:
            return await cursor.fetchall()

async def delete_booking_by_id(booking_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        await db.commit()

async def get_booking_record_by_id(booking_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT id, user_id, name, phone, date, time, master_id
            FROM bookings
            WHERE id = ?
        """, (booking_id,)) as cursor:
            return await cursor.fetchone()

async def get_booking_record_with_master_by_id(booking_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute(
            """
            SELECT b.id, b.user_id, b.name, b.phone, b.date, b.time, b.master_id, m.name
            FROM bookings b
            LEFT JOIN masters m ON b.master_id = m.id
            WHERE b.id = ?
            """,
            (booking_id,),
        ) as cursor:
            return await cursor.fetchone()

async def get_bookings_for_reminders(max_level: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute(
            """
            SELECT b.id, b.user_id, b.name, b.date, b.time, m.name as master_name, b.reminder_level
            FROM bookings b 
            LEFT JOIN masters m ON b.master_id = m.id 
            WHERE b.reminder_level < ?
            """, (max_level,)
        ) as cursor:
            return await cursor.fetchall()

async def get_booking_by_id(booking_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute(
            """
            SELECT b.name, b.phone, b.date, b.time, m.name, b.user_id
            FROM bookings b 
            LEFT JOIN masters m ON b.master_id = m.id 
            WHERE b.id = ?
            """, (booking_id,)
        ) as cursor:
            return await cursor.fetchone()

async def update_reminder_level(booking_id: int, level: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE bookings SET reminder_level = ? WHERE id = ?", (level, booking_id))
        await db.commit()

async def delete_bookings_by_date(target_date: str):
    async with aiosqlite.connect("bookings.db") as db:
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

    async with aiosqlite.connect("bookings.db") as db:
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

async def delete_bookings_by_master(master_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT COUNT(id) FROM bookings WHERE master_id = ?", (master_id,)) as cursor:
            count = (await cursor.fetchone())[0]
        if count > 0:
            await db.execute("DELETE FROM bookings WHERE master_id = ?", (master_id,))
            await db.commit()
        return count

async def delete_past_bookings():
    today_iso = datetime.now().date().isoformat()
    async with aiosqlite.connect("bookings.db") as db:
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
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute(
            """
            INSERT INTO blocked_slots (date, date_iso, start_time, end_time, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (date, date_iso, start_time, end_time, reason or None),
        )
        await db.commit()

async def get_blocked_slots(date: str | None = None):
    async with aiosqlite.connect("bookings.db") as db:
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
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("DELETE FROM blocked_slots WHERE id = ?", (blocked_slot_id,))
        await db.commit()

async def get_all_busy_slots(master_id: int | None = None):
    from collections import defaultdict
    async with aiosqlite.connect("bookings.db") as db:
        if master_id is not None:
            async with db.execute("SELECT date, time, duration FROM bookings WHERE master_id = ?", (master_id,)) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute("SELECT date, time, duration FROM bookings") as cursor:
                rows = await cursor.fetchall()
        async with db.execute("SELECT date, start_time, end_time FROM blocked_slots") as cursor:
            blocked_rows = await cursor.fetchall()
        busy_slots = defaultdict(list)
        if rows:
            for r in rows:
                date = r[0]
                time_str = r[1]
                duration = r[2] if len(r) > 2 and r[2] is not None else 60
                busy_slots[date].append({"time": time_str, "duration": duration})
        if blocked_rows:
            for date, start_time, end_time in blocked_rows:
                duration = _duration_from_range(start_time, end_time)
                if duration > 0:
                    busy_slots[date].append({"time": start_time, "duration": duration})
        return dict(busy_slots)
