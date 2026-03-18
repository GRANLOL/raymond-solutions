from __future__ import annotations

from datetime import datetime, timedelta

from config import salon_config
from .base import aiosqlite, db_connect
from time_utils import build_reminder_schedule, combine_salon_datetime, get_salon_now


async def _table_columns(db, table_name: str) -> set[str]:
    async with db.execute(f"PRAGMA table_info({table_name})") as cursor:
        rows = await cursor.fetchall()
    return {row[1] for row in rows}


async def _cleanup_legacy_master_schema(db) -> None:
    await db.execute("DROP INDEX IF EXISTS idx_bookings_date_master_time")
    await db.execute("DROP TABLE IF EXISTS masters")

    booking_columns = await _table_columns(db, "bookings")
    if "master_id" not in booking_columns:
        return

    await db.execute("ALTER TABLE bookings RENAME TO bookings_legacy_master_cleanup")
    await db.execute("""
        CREATE TABLE bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            phone TEXT,
            date TEXT,
            time TEXT,
            reminder_level INTEGER DEFAULT 0,
            duration INTEGER DEFAULT 60,
            service_name TEXT,
            price INTEGER DEFAULT 0,
            date_iso TEXT,
            created_at TEXT,
            first_reminder_due_at TEXT,
            second_reminder_due_at TEXT,
            first_reminder_sent_at TEXT,
            second_reminder_sent_at TEXT,
            status TEXT DEFAULT 'scheduled',
            completed_at TEXT,
            cancelled_at TEXT
        )
    """)
    await db.execute("""
        INSERT INTO bookings (
            id, user_id, name, phone, date, time, reminder_level, duration, service_name, price,
            date_iso, created_at, first_reminder_due_at, second_reminder_due_at,
            first_reminder_sent_at, second_reminder_sent_at, status, completed_at, cancelled_at
        )
        SELECT
            id, user_id, name, phone, date, time, reminder_level, duration, service_name, price,
            date_iso, created_at, first_reminder_due_at, second_reminder_due_at,
            first_reminder_sent_at, second_reminder_sent_at, status, completed_at, cancelled_at
        FROM bookings_legacy_master_cleanup
    """)
    await db.execute("DROP TABLE bookings_legacy_master_cleanup")


async def init_db():
    async with db_connect() as db:
        # Создаем таблицу, если её нет
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                phone TEXT,
                date TEXT,
                date_iso TEXT,
                time TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price TEXT,
                description TEXT,
                category_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                parent_id INTEGER
            )
        """)
        try:
            await db.execute("ALTER TABLE services ADD COLUMN category_id INTEGER")
        except aiosqlite.OperationalError:
            # Column already exists
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN date_iso TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN reminder_level INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN created_at TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN first_reminder_due_at TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN second_reminder_due_at TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN first_reminder_sent_at TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN second_reminder_sent_at TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE services ADD COLUMN duration INTEGER DEFAULT 60")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN duration INTEGER DEFAULT 60")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN service_name TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN price INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT 'scheduled'")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN completed_at TEXT")
        except aiosqlite.OperationalError:
            pass
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN cancelled_at TEXT")
        except aiosqlite.OperationalError:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                date_iso TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                reason TEXT
            )
        """)
        await _cleanup_legacy_master_schema(db)
        await db.execute("DROP TABLE IF EXISTS time_slots")
        await db.execute("""
            UPDATE bookings
            SET date_iso = substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)
            WHERE date_iso IS NULL
              AND length(date) = 10
              AND substr(date, 3, 1) = '.'
              AND substr(date, 6, 1) = '.'
        """)
        await db.execute("UPDATE bookings SET status = 'scheduled' WHERE status IS NULL OR trim(status) = ''")
        async with db.execute("""
            SELECT id, date, time, reminder_level, created_at, first_reminder_due_at,
                   second_reminder_due_at, first_reminder_sent_at, second_reminder_sent_at
            FROM bookings
        """) as cursor:
            rows = await cursor.fetchall()

        now = get_salon_now()
        for row in rows:
            (
                booking_id,
                date_str,
                time_str,
                reminder_level,
                created_at,
                first_due_at,
                second_due_at,
                first_sent_at,
                second_sent_at,
            ) = row
            try:
                booking_date = datetime.strptime(date_str, "%d.%m.%Y").date()
                booking_time = datetime.strptime(time_str, "%H:%M").time()
                booking_dt = combine_salon_datetime(booking_date, booking_time)
            except ValueError:
                continue

            created_dt = now
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=now.tzinfo)
                except ValueError:
                    created_dt = now

            schedule = build_reminder_schedule(booking_dt, created_dt)
            normalized_first_due = first_due_at or schedule["first_reminder_due_at"]
            normalized_second_due = second_due_at or schedule["second_reminder_due_at"]
            normalized_first_sent = first_sent_at
            normalized_second_sent = second_sent_at

            if reminder_level >= 1 and not normalized_first_sent:
                normalized_first_sent = now.isoformat()
                normalized_first_due = normalized_first_due or (booking_dt - timedelta(hours=24)).isoformat()
            if reminder_level >= 2 and not normalized_second_sent:
                normalized_second_sent = now.isoformat()
                second_hours = int(salon_config.get("reminder_2_hours", 3) or 3)
                normalized_second_due = normalized_second_due or (booking_dt - timedelta(hours=second_hours)).isoformat()

            await db.execute(
                """
                UPDATE bookings
                SET created_at = COALESCE(created_at, ?),
                    first_reminder_due_at = ?,
                    second_reminder_due_at = ?,
                    first_reminder_sent_at = ?,
                    second_reminder_sent_at = ?
                WHERE id = ?
                """,
                (
                    schedule["created_at"],
                    normalized_first_due,
                    normalized_second_due,
                    normalized_first_sent,
                    normalized_second_sent,
                    booking_id,
                ),
            )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date_iso_time ON bookings(date_iso, time)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bookings_first_due ON bookings(first_reminder_due_at, first_reminder_sent_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bookings_second_due ON bookings(second_reminder_due_at, second_reminder_sent_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_blocked_slots_date_time ON blocked_slots(date, start_time, end_time)")
        await db.commit()
