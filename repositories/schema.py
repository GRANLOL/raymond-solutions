from __future__ import annotations

from .base import aiosqlite

async def init_db():
    async with aiosqlite.connect("bookings.db") as db:
        # Создаем таблицу, если её нет
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                phone TEXT,
                date TEXT,
                date_iso TEXT,
                time TEXT,
                master_id INTEGER
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
            await db.execute("ALTER TABLE bookings ADD COLUMN master_id INTEGER")
        except aiosqlite.OperationalError:
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS time_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time_value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                telegram_id TEXT,
                category_id INTEGER
            )
        """)
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
        await db.execute("""
            UPDATE bookings
            SET date_iso = substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)
            WHERE date_iso IS NULL
              AND length(date) = 10
              AND substr(date, 3, 1) = '.'
              AND substr(date, 6, 1) = '.'
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date_master_time ON bookings(date, master_id, time)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date_iso_time ON bookings(date_iso, time)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_blocked_slots_date_time ON blocked_slots(date, start_time, end_time)")
        await db.commit()
