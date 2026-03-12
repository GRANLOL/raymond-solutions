import aiosqlite

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
        await db.commit()

async def add_booking(user_id, name, phone, date, time, master_id=None, duration=60, service_name=None, price=0):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute(
            "INSERT INTO bookings (user_id, name, phone, date, time, master_id, duration, service_name, price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, phone, date, time, master_id, duration, service_name, price)
        )
        await db.commit()

async def get_booked_slots(date, master_id=None):
    async with aiosqlite.connect("bookings.db") as db:
        if master_id is not None:
            async with db.execute("SELECT time FROM bookings WHERE date = ? AND master_id = ?", (date, master_id)) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute("SELECT time FROM bookings WHERE date = ?", (date,)) as cursor:
                rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_all_bookings():
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT b.name, b.phone, b.date, b.time, m.name 
            FROM bookings b 
            LEFT JOIN masters m ON b.master_id = m.id 
            ORDER BY b.date, b.time
        """) as cursor:
            return await cursor.fetchall()

async def clear_bookings():
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("DELETE FROM bookings")
        await db.commit()

async def get_bookings_by_date_full(target_date: str):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT b.name, b.phone, b.date, b.time, m.name 
            FROM bookings b 
            LEFT JOIN masters m ON b.master_id = m.id 
            WHERE b.date = ? 
            ORDER BY b.time
        """, (target_date,)) as cursor:
            return await cursor.fetchall()

async def get_bookings_by_master(master_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT name, phone, date, time FROM bookings WHERE master_id = ? ORDER BY date, time", (master_id,)) as cursor:
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

async def cancel_booking(user_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        # Removed the most recent booking for this user
        # Note: we can also target specific IDs, but following instructions directly
        # If we need to delete just the latest, we could do WHERE id = (SELECT max(id) FROM bookings WHERE user_id = ?)
        # But deleting all bookings by user_id or the active one works if they only have 1 active booking.
        await db.execute("DELETE FROM bookings WHERE id = (SELECT id FROM bookings WHERE user_id = ? ORDER BY id DESC LIMIT 1)", (user_id,))
        await db.commit()

async def delete_booking_by_id(booking_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        await db.commit()

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
            SELECT b.name, b.phone, b.date, b.time, m.name 
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

from datetime import datetime

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
        start = datetime.strptime(start_date, "%d.%m.%Y").date()
        end = datetime.strptime(end_date, "%d.%m.%Y").date()
    except ValueError:
        return 0

    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT id, date FROM bookings") as cursor:
            rows = await cursor.fetchall()
            
        ids_to_delete = []
        for r_id, r_date in rows:
            try:
                d = datetime.strptime(r_date, "%d.%m.%Y").date()
                if start <= d <= end:
                    ids_to_delete.append(r_id)
            except ValueError:
                pass
                
        if ids_to_delete:
            placeholders = ",".join("?" for _ in ids_to_delete)
            await db.execute(f"DELETE FROM bookings WHERE id IN ({placeholders})", ids_to_delete)
            await db.commit()
        return len(ids_to_delete)

async def delete_bookings_by_master(master_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT COUNT(id) FROM bookings WHERE master_id = ?", (master_id,)) as cursor:
            count = (await cursor.fetchone())[0]
        if count > 0:
            await db.execute("DELETE FROM bookings WHERE master_id = ?", (master_id,))
            await db.commit()
        return count

async def delete_past_bookings():
    today = datetime.now().date()
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT id, date FROM bookings") as cursor:
            rows = await cursor.fetchall()
            
        ids_to_delete = []
        for r_id, r_date in rows:
            try:
                d = datetime.strptime(r_date, "%d.%m.%Y").date()
                if d < today:
                    ids_to_delete.append(r_id)
            except ValueError:
                pass
                
        if ids_to_delete:
            placeholders = ",".join("?" for _ in ids_to_delete)
            await db.execute(f"DELETE FROM bookings WHERE id IN ({placeholders})", ids_to_delete)
            await db.commit()
        return len(ids_to_delete)

async def get_all_busy_slots(master_id: int | None = None):
    from collections import defaultdict
    async with aiosqlite.connect("bookings.db") as db:
        if master_id is not None:
            async with db.execute("SELECT date, time, duration FROM bookings WHERE master_id = ?", (master_id,)) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute("SELECT date, time, duration FROM bookings") as cursor:
                rows = await cursor.fetchall()
        busy_slots = defaultdict(list)
        if rows:
            for r in rows:
                date = r[0]
                time_str = r[1]
                duration = r[2] if len(r) > 2 and r[2] is not None else 60
                busy_slots[date].append({"time": time_str, "duration": duration})
        return dict(busy_slots)

# --- CRUD for Masters ---
async def add_master(name: str, telegram_id: str, category_id: int | None = None):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("INSERT INTO masters (name, telegram_id, category_id) VALUES (?, ?, ?)", (name, telegram_id, category_id))
        await db.commit()

async def get_all_masters():
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT id, name, telegram_id, category_id FROM masters") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "telegram_id": r[2], "category_id": r[3]} for r in rows]

async def delete_master(master_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("DELETE FROM masters WHERE id = ?", (master_id,))
        await db.commit()

async def get_master_by_telegram_id(telegram_id: str):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT id, name, telegram_id, category_id FROM masters WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "name": row[1], "telegram_id": row[2], "category_id": row[3]}
            return None

# --- CRUD for Services ---
async def add_service(name: str, price: str, duration: int = 60, description: str = "", category_id: int | None = None):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("INSERT INTO services (name, price, duration, description, category_id) VALUES (?, ?, ?, ?, ?)", (name, price, duration, description, category_id))
        await db.commit()

async def update_service_category(service_id: int, category_id: int | None):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE services SET category_id = ? WHERE id = ?", (category_id, service_id))
        await db.commit()

async def update_service_name(service_id: int, name: str):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE services SET name = ? WHERE id = ?", (name, service_id))
        await db.commit()

async def update_service_price(service_id: int, price: str):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE services SET price = ? WHERE id = ?", (price, service_id))
        await db.commit()

async def get_service_by_id(service_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT s.id, s.name, s.price, s.duration, s.description, s.category_id, c.name
            FROM services s
            LEFT JOIN categories c ON s.category_id = c.id
            WHERE s.id = ?
        """, (service_id,)) as cursor:
            r = await cursor.fetchone()
            if r:
                return {"id": r[0], "name": r[1], "price": r[2], "duration": r[3], "description": r[4], "category_id": r[5], "category_name": r[6]}
            return None

async def get_all_services():
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT s.id, s.name, s.price, s.duration, s.description, s.category_id, c.name
            FROM services s
            LEFT JOIN categories c ON s.category_id = c.id
        """) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2], "duration": r[3], "description": r[4], "category_id": r[5], "category_name": r[6]} for r in rows]

async def delete_service(service_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("DELETE FROM services WHERE id = ?", (service_id,))
        await db.commit()

# --- CRUD for Time Slots ---
async def add_time_slot(time_value: str):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("INSERT INTO time_slots (time_value) VALUES (?)", (time_value,))
        await db.commit()

async def get_all_time_slots():
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT id, time_value FROM time_slots ORDER BY time_value") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "time_value": r[1]} for r in rows]

async def delete_time_slot(slot_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("DELETE FROM time_slots WHERE id = ?", (slot_id,))
        await db.commit()

# --- CRUD for Categories ---
async def add_category(name: str, parent_id: int | None = None):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
        await db.commit()

async def get_all_categories():
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT id, name, parent_id FROM categories") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "parent_id": r[2]} for r in rows]

async def get_category_by_id(category_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT id, name, parent_id FROM categories WHERE id = ?", (category_id,)) as cursor:
            r = await cursor.fetchone()
            if r:
                return {"id": r[0], "name": r[1], "parent_id": r[2]}
            return None

async def update_category_name(category_id: int, name: str):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        await db.commit()

async def update_category_parent(category_id: int, parent_id: int | None):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE categories SET parent_id = ? WHERE id = ?", (parent_id, category_id))
        await db.commit()

async def delete_category(category_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        # Also let's set category_id to NULL for services that belonged to this category
        await db.execute("UPDATE services SET category_id = NULL WHERE category_id = ?", (category_id,))
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()

async def update_service_name(service_id: int, name: str):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE services SET name=? WHERE id=?", (name, service_id))
        await db.commit()

async def update_service_price(service_id: int, price: str):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE services SET price=? WHERE id=?", (price, service_id))
        await db.commit()

async def update_service_duration(service_id: int, duration: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE services SET duration=? WHERE id=?", (duration, service_id))
        await db.commit()

async def update_service_category(service_id: int, category_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE services SET category_id=? WHERE id=?", (category_id, service_id))
        await db.commit()

# ==================== ANALYTICS ====================

def _date_from_period(period_days: int) -> str:
    """Returns a date string (DD.MM.YYYY) that is `period_days` ago from today."""
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=period_days)).strftime("%d.%m.%Y")

async def get_revenue_stats(period_days: int) -> dict:
    """Returns total revenue (sum of price), number of bookings, and average price for the period."""
    from_date = _date_from_period(period_days)
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT 
                COUNT(*) as total_bookings,
                COALESCE(SUM(CAST(price AS REAL)), 0) as total_revenue,
                COALESCE(AVG(CAST(price AS REAL)), 0) as avg_price
            FROM bookings
            WHERE date >= ?
        """, (from_date,)) as cursor:
            row = await cursor.fetchone()
            return {
                "total_bookings": row[0] or 0,
                "total_revenue": int(row[1] or 0),
                "avg_price": int(row[2] or 0)
            }

async def get_top_services(period_days: int, limit: int = 5) -> list:
    """Returns the most booked services by name for the period."""
    from_date = _date_from_period(period_days)
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT service_name, COUNT(*) as cnt
            FROM bookings
            WHERE date >= ? AND service_name IS NOT NULL AND service_name != ''
            GROUP BY service_name
            ORDER BY cnt DESC
            LIMIT ?
        """, (from_date, limit)) as cursor:
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]

async def get_bookings_by_weekday(period_days: int) -> dict:
    """Returns booking count per day of week (Mon=0...Sun=6)."""
    from_date = _date_from_period(period_days)
    from datetime import datetime
    weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    result = {name: 0 for name in weekday_names}
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT date FROM bookings WHERE date >= ?", (from_date,)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                try:
                    dt = datetime.strptime(row[0], "%d.%m.%Y")
                    result[weekday_names[dt.weekday()] ] += 1
                except (ValueError, IndexError):
                    pass
    return result

async def get_peak_hours(period_days: int, top_n: int = 3) -> list:
    """Returns the top N booking hours for the period."""
    from_date = _date_from_period(period_days)
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT time, COUNT(*) as cnt
            FROM bookings
            WHERE date >= ? AND time IS NOT NULL
            GROUP BY time
            ORDER BY cnt DESC
            LIMIT ?
        """, (from_date, top_n)) as cursor:
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]

async def get_client_stats(period_days: int) -> dict:
    """Returns counts of new vs. returning clients by phone number."""
    from_date = _date_from_period(period_days)
    async with aiosqlite.connect("bookings.db") as db:
        # All unique phones in this period
        async with db.execute("""
            SELECT DISTINCT phone FROM bookings WHERE date >= ?
        """, (from_date,)) as cursor:
            period_phones = {row[0] for row in await cursor.fetchall()}

        # Of these, which also had bookings BEFORE the period
        returning = set()
        for phone in period_phones:
            async with db.execute("""
                SELECT 1 FROM bookings WHERE phone = ? AND date < ? LIMIT 1
            """, (phone, from_date)) as cursor:
                if await cursor.fetchone():
                    returning.add(phone)

        new_clients = len(period_phones - returning)
        returning_clients = len(returning)
        return {"new": new_clients, "returning": returning_clients}