import aiosqlite
import re

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

    return [
        {
            "time": row[0],
            "duration": row[1] if len(row) > 1 and row[1] is not None else 60,
        }
        for row in rows
    ]

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

async def get_master_by_id(master_id: int):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT id, name, telegram_id, category_id FROM masters WHERE id = ?", (master_id,)) as cursor:
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

async def get_service_by_name(service_name: str):
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT s.id, s.name, s.price, s.duration, s.description, s.category_id, c.name
            FROM services s
            LEFT JOIN categories c ON s.category_id = c.id
            WHERE lower(trim(s.name)) = lower(trim(?))
            LIMIT 1
        """, (service_name,)) as cursor:
            row = await cursor.fetchone()

    if not row:
        return None

    price_text = row[2] or ""
    price_digits = re.sub(r"\D", "", str(price_text))
    price_value = int(price_digits) if price_digits else 0

    return {
        "id": row[0],
        "name": row[1],
        "price": row[2],
        "price_value": price_value,
        "duration": row[3],
        "description": row[4],
        "category_id": row[5],
        "category_name": row[6],
    }

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

async def update_service_duration(service_id: int, duration: int):
    async with aiosqlite.connect("bookings.db") as db:
        await db.execute("UPDATE services SET duration=? WHERE id=?", (duration, service_id))
        await db.commit()

# ==================== ANALYTICS ====================

def _period_start_date(period_days: int):
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=period_days)).date()


def _parse_booking_date(value: str):
    from datetime import datetime
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except (TypeError, ValueError):
        return None


async def _get_bookings_in_period(period_days: int):
    start_date = _period_start_date(period_days)
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("""
            SELECT date, time, price, service_name, phone
            FROM bookings
        """) as cursor:
            rows = await cursor.fetchall()

    bookings = []
    for row in rows:
        booking_date = _parse_booking_date(row[0])
        if booking_date and booking_date >= start_date:
            bookings.append({
                "date": booking_date,
                "time": row[1],
                "price": row[2],
                "service_name": row[3],
                "phone": row[4],
            })
    return bookings


async def get_revenue_stats(period_days: int) -> dict:
    bookings = await _get_bookings_in_period(period_days)
    prices = [int(float(item["price"] or 0)) for item in bookings]
    total_bookings = len(bookings)
    total_revenue = sum(prices)
    avg_price = int(total_revenue / total_bookings) if total_bookings else 0
    return {
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "avg_price": avg_price,
    }


async def get_top_services(period_days: int, limit: int = 5) -> list:
    from collections import Counter

    bookings = await _get_bookings_in_period(period_days)
    counter = Counter(
        item["service_name"]
        for item in bookings
        if item["service_name"]
    )
    return counter.most_common(limit)


async def get_bookings_by_weekday(period_days: int) -> dict:
    weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    result = {name: 0 for name in weekday_names}
    bookings = await _get_bookings_in_period(period_days)
    for item in bookings:
        result[weekday_names[item["date"].weekday()]] += 1
    return result


async def get_peak_hours(period_days: int, top_n: int = 3) -> list:
    from collections import Counter

    bookings = await _get_bookings_in_period(period_days)
    counter = Counter(item["time"] for item in bookings if item["time"])
    return counter.most_common(top_n)


async def get_client_stats(period_days: int) -> dict:
    period_bookings = await _get_bookings_in_period(period_days)
    period_phones = {item["phone"] for item in period_bookings if item["phone"]}
    period_start = _period_start_date(period_days)

    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT phone, date FROM bookings") as cursor:
            rows = await cursor.fetchall()

    returning = set()
    for phone, date_str in rows:
        if phone not in period_phones:
            continue
        booking_date = _parse_booking_date(date_str)
        if booking_date and booking_date < period_start:
            returning.add(phone)

    new_clients = len(period_phones - returning)
    returning_clients = len(returning)
    return {"new": new_clients, "returning": returning_clients}
