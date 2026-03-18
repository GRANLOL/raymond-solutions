import unittest
import aiosqlite
import sqlite3
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from repositories.analytics import get_bookings_by_weekday, get_revenue_stats
from repositories.bookings import (
    ActiveBookingLimitReachedError,
    create_booking_if_available,
    get_all_bookings,
    reschedule_booking_if_available,
    search_bookings,
)
from repositories.categories import (
    add_category,
    delete_category,
    get_all_categories,
    update_category_parent,
)
from repositories.schema import init_db
from tests.support import RepositoryTestCase


class BookingRepositoryTests(RepositoryTestCase):
    async def test_create_booking_prevents_overlap_for_busy_slot(self):
        created = await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="14.03.2026",
            time="10:00",
            duration=60,
            service_name="Маникюр",
            price=2000,
        )
        overlapping = await create_booking_if_available(
            user_id=2,
            name="Bob",
            phone="+10000000002",
            date="14.03.2026",
            time="10:30",
            duration=60,
            service_name="Маникюр",
            price=2000,
        )
        later_slot = await create_booking_if_available(
            user_id=3,
            name="Carol",
            phone="+10000000003",
            date="14.03.2026",
            time="11:00",
            duration=60,
            service_name="Маникюр",
            price=2000,
        )

        bookings = await get_all_bookings()

        self.assertTrue(created)
        self.assertFalse(overlapping)
        self.assertTrue(later_slot)
        self.assertEqual(len(bookings), 2)

    async def test_create_booking_allows_non_overlapping_slots(self):
        first = await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="14.03.2026",
            time="10:00",
            duration=60,
        )
        second = await create_booking_if_available(
            user_id=2,
            name="Bob",
            phone="+10000000002",
            date="14.03.2026",
            time="11:00",
            duration=60,
        )

        self.assertTrue(first)
        self.assertTrue(second)

    async def test_revenue_stats_counts_bookings_in_period(self):
        await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
            service_name="Маникюр",
            price=2000,
        )

        stats = await get_revenue_stats(30)

        self.assertEqual(stats["total_bookings"], 1)
        self.assertEqual(stats["total_revenue"], 2000)

    async def test_today_stats_do_not_include_future_bookings(self):
        await create_booking_if_available(
            user_id=1,
            name="Sunday Client",
            phone="+10000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
            service_name="Маникюр",
            price=2000,
        )
        await create_booking_if_available(
            user_id=2,
            name="Monday Client",
            phone="+10000000002",
            date="16.03.2026",
            time="11:00",
            duration=60,
            service_name="Маникюр",
            price=2500,
        )

        with patch("repositories.analytics._period_start_date", return_value=date(2026, 3, 15)):
            weekday_stats = await get_bookings_by_weekday(0)

        self.assertEqual(weekday_stats["Пн"], 0)
        self.assertEqual(weekday_stats["Вс"], 1)

    async def test_reschedule_booking_moves_slot_when_new_time_is_free(self):
        await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
        )

        moved = await reschedule_booking_if_available(1, "15.03.2026", "12:00")
        bookings = await search_bookings("Alice")

        self.assertTrue(moved)
        self.assertEqual(bookings[0][4], "12:00")

    async def test_search_bookings_matches_phone_and_name(self):
        await create_booking_if_available(
            user_id=1,
            name="Alice Example",
            phone="+70000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
        )

        by_name = await search_bookings("Alice")
        by_phone = await search_bookings("0001")

        self.assertEqual(len(by_name), 1)
        self.assertEqual(len(by_phone), 1)

    async def test_create_booking_rejects_when_user_reaches_active_limit(self):
        with patch.dict("repositories.bookings.salon_config", {"max_active_bookings_per_user": 3}, clear=False):
            for index, time_value in enumerate(("10:00", "11:00", "12:00"), start=1):
                created = await create_booking_if_available(
                    user_id=77,
                    name=f"Client {index}",
                    phone=f"+7000000000{index}",
                    date="15.03.2026",
                    time=time_value,
                    duration=60,
                )
                self.assertTrue(created)

            with self.assertRaises(ActiveBookingLimitReachedError):
                await create_booking_if_available(
                    user_id=77,
                    name="Client 4",
                    phone="+70000000004",
                    date="16.03.2026",
                    time="10:00",
                    duration=60,
                )


class CategoryRepositoryTests(RepositoryTestCase):
    async def test_update_category_parent_rejects_descendant_cycle(self):
        await add_category("Root")
        await add_category("Child", parent_id=1)
        await add_category("Grandchild", parent_id=2)

        with self.assertRaises(ValueError):
            await update_category_parent(1, 3)

    async def test_delete_category_reparents_children_to_deleted_parent_parent(self):
        await add_category("Root")
        await add_category("Child", parent_id=1)
        await add_category("Grandchild", parent_id=2)

        await delete_category(2)
        categories = await get_all_categories()
        by_id = {category["id"]: category for category in categories}

        self.assertNotIn(2, by_id)
        self.assertEqual(by_id[3]["parent_id"], 1)


class SchemaMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_init_db_removes_legacy_master_and_time_slot_tables(self):
        db_path = Path.cwd() / f".test_{next(tempfile._get_candidate_names())}.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT,
                    phone TEXT,
                    date TEXT,
                    time TEXT,
                    master_id INTEGER
                );
                CREATE TABLE masters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT
                );
                CREATE TABLE time_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time_value TEXT
                );
                CREATE INDEX idx_bookings_date_master_time ON bookings(date, master_id, time);
                """
            )
            conn.commit()
        finally:
            conn.close()

        original_connect = aiosqlite.connect

        def connect_override(_path, *args, **kwargs):
            return original_connect(db_path, *args, **kwargs)

        with patch("repositories.schema.aiosqlite.connect", side_effect=connect_override):
            await init_db()

        conn = sqlite3.connect(db_path)
        try:
            objects = {
                name: object_type
                for name, object_type in conn.execute(
                    "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'index')"
                )
            }
            booking_columns = [row[1] for row in conn.execute("PRAGMA table_info(bookings)")]
        finally:
            conn.close()
            if db_path.exists():
                db_path.unlink()

        self.assertNotIn("masters", objects)
        self.assertNotIn("time_slots", objects)
        self.assertNotIn("idx_bookings_date_master_time", objects)
        self.assertNotIn("master_id", booking_columns)
