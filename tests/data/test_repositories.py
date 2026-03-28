import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import aiosqlite

import repositories.bookings as bookings_repo
from repositories.analytics import (
    get_booking_status_stats,
    get_bookings_by_weekday,
    get_client_stats,
    get_peak_hours,
    get_revenue_stats,
    get_top_services,
)
from repositories.bookings import (
    ActiveBookingLimitReachedError,
    add_blocked_slot,
    cancel_booking_by_id,
    create_manual_booking,
    create_booking_if_available,
    get_all_busy_slots,
    get_all_bookings,
    get_booking_admin_details,
    get_busy_slots_by_date,
    reschedule_booking_if_available,
    search_bookings,
    update_booking_status,
)
from repositories.categories import (
    add_category,
    delete_category,
    get_all_categories,
    update_category_parent,
)
from repositories.services import add_service, get_all_services
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
            service_name="Service A",
            price=2000,
        )
        overlapping = await create_booking_if_available(
            user_id=2,
            name="Bob",
            phone="+10000000002",
            date="14.03.2026",
            time="10:30",
            duration=60,
            service_name="Service A",
            price=2000,
        )
        later_slot = await create_booking_if_available(
            user_id=3,
            name="Carol",
            phone="+10000000003",
            date="14.03.2026",
            time="11:00",
            duration=60,
            service_name="Service A",
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

    async def test_get_busy_slots_by_date_includes_lunch_break_metadata(self):
        with patch.dict(
            bookings_repo.salon_config,
            {
                "working_days": [0, 1, 2, 3, 4, 5, 6],
                "blacklisted_dates": [],
                "lunch_break_enabled": True,
                "lunch_break_start": "13:00",
                "lunch_break_end": "14:00",
            },
            clear=False,
        ):
            busy_slots = await get_busy_slots_by_date("14.03.2026")

        self.assertTrue(any(slot["kind"] == "lunch" and slot["time"] == "13:00" for slot in busy_slots))

    async def test_create_booking_rejects_overlap_with_single_break(self):
        await add_blocked_slot("14.03.2026", "13:00", "14:00", reason="Перерыв")

        blocked = await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="14.03.2026",
            time="12:30",
            duration=60,
        )
        allowed = await create_booking_if_available(
            user_id=2,
            name="Bob",
            phone="+10000000002",
            date="14.03.2026",
            time="12:00",
            duration=60,
        )

        self.assertFalse(blocked)
        self.assertTrue(allowed)

    async def test_get_all_busy_slots_generates_lunch_for_booking_window_dates(self):
        with patch.dict(
            bookings_repo.salon_config,
            {
                "booking_window": 2,
                "working_days": [0, 1, 2, 3, 4, 5, 6],
                "blacklisted_dates": [],
                "lunch_break_enabled": True,
                "lunch_break_start": "13:00",
                "lunch_break_end": "14:00",
            },
            clear=False,
        ), patch("repositories.bookings.get_salon_today", return_value=date(2026, 3, 20)):
            busy_slots = await get_all_busy_slots()

        self.assertIn("20.03.2026", busy_slots)
        self.assertIn("21.03.2026", busy_slots)
        self.assertTrue(any(slot["kind"] == "lunch" for slot in busy_slots["20.03.2026"]))

    async def test_revenue_stats_counts_only_completed_bookings_in_period(self):
        await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
            service_name="Service A",
            price=2000,
        )
        await update_booking_status(1, "completed")

        await create_booking_if_available(
            user_id=2,
            name="Bob",
            phone="+10000000002",
            date="16.03.2026",
            time="10:00",
            duration=60,
            service_name="Service B",
            price=3000,
        )
        await update_booking_status(2, "no_show")

        await create_booking_if_available(
            user_id=3,
            name="Carol",
            phone="+10000000003",
            date="17.03.2026",
            time="10:00",
            duration=60,
            service_name="Service C",
            price=4000,
        )
        await cancel_booking_by_id(3)

        stats = await get_revenue_stats(30)

        self.assertEqual(stats["total_bookings"], 1)
        self.assertEqual(stats["total_revenue"], 2000)
        self.assertEqual(stats["avg_price"], 2000)

    async def test_booking_status_stats_counts_completed_cancelled_and_no_show(self):
        await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
            service_name="Service A",
            price=2000,
        )
        await update_booking_status(1, "completed")

        await create_booking_if_available(
            user_id=2,
            name="Bob",
            phone="+10000000002",
            date="16.03.2026",
            time="11:00",
            duration=60,
            service_name="Service B",
            price=2500,
        )
        await update_booking_status(2, "no_show")

        await create_booking_if_available(
            user_id=3,
            name="Carol",
            phone="+10000000003",
            date="17.03.2026",
            time="12:00",
            duration=60,
            service_name="Service C",
            price=3000,
        )
        await cancel_booking_by_id(3)

        await create_booking_if_available(
            user_id=4,
            name="Dana",
            phone="+10000000004",
            date="18.03.2026",
            time="13:00",
            duration=60,
            service_name="Service D",
            price=3500,
        )

        stats = await get_booking_status_stats(30)

        self.assertEqual(stats, {"completed": 1, "cancelled": 1, "no_show": 1})

    async def test_top_services_and_peak_hours_use_only_completed_bookings(self):
        await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
            service_name="Completed Service",
            price=2000,
        )
        await update_booking_status(1, "completed")

        await create_booking_if_available(
            user_id=2,
            name="Bob",
            phone="+10000000002",
            date="16.03.2026",
            time="10:00",
            duration=60,
            service_name="Completed Service",
            price=2100,
        )
        await update_booking_status(2, "completed")

        await create_booking_if_available(
            user_id=3,
            name="Carol",
            phone="+10000000003",
            date="17.03.2026",
            time="12:00",
            duration=60,
            service_name="No Show Service",
            price=2200,
        )
        await update_booking_status(3, "no_show")

        await create_booking_if_available(
            user_id=4,
            name="Dana",
            phone="+10000000004",
            date="18.03.2026",
            time="13:00",
            duration=60,
            service_name="Cancelled Service",
            price=2300,
        )
        await cancel_booking_by_id(4)

        top_services = await get_top_services(30)
        peak_hours = await get_peak_hours(30)

        self.assertEqual(top_services, [("Completed Service", 2)])
        self.assertEqual(peak_hours, [("10:00", 2)])

    async def test_weekday_and_client_stats_use_only_completed_bookings(self):
        await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="10.03.2026",
            time="10:00",
            duration=60,
            service_name="Old Service",
            price=1500,
        )
        await update_booking_status(1, "completed")

        await create_booking_if_available(
            user_id=1,
            name="Alice",
            phone="+10000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
            service_name="Return Service",
            price=2000,
        )
        await update_booking_status(2, "completed")

        await create_booking_if_available(
            user_id=2,
            name="Bob",
            phone="+10000000002",
            date="15.03.2026",
            time="11:00",
            duration=60,
            service_name="No Show Service",
            price=2100,
        )
        await update_booking_status(3, "no_show")

        await create_booking_if_available(
            user_id=3,
            name="Cara",
            phone="+10000000003",
            date="15.03.2026",
            time="12:00",
            duration=60,
            service_name="Cancelled Service",
            price=2200,
        )
        await cancel_booking_by_id(4)

        with patch("repositories.analytics._period_start_date", return_value=date(2026, 3, 15)):
            weekday_stats = await get_bookings_by_weekday(0)
            client_stats = await get_client_stats(0)

        self.assertEqual(sum(weekday_stats.values()), 1)
        self.assertEqual(weekday_stats["Вс"], 1)
        self.assertEqual(client_stats, {"new": 0, "returning": 1})

    async def test_today_stats_do_not_include_future_bookings(self):
        await create_booking_if_available(
            user_id=1,
            name="Sunday Client",
            phone="+10000000001",
            date="15.03.2026",
            time="10:00",
            duration=60,
            service_name="Service A",
            price=2000,
        )
        await update_booking_status(1, "completed")

        await create_booking_if_available(
            user_id=2,
            name="Monday Client",
            phone="+10000000002",
            date="16.03.2026",
            time="11:00",
            duration=60,
            service_name="Service B",
            price=2500,
        )
        await update_booking_status(2, "completed")

        with patch("repositories.analytics._period_start_date", return_value=date(2026, 3, 15)):
            weekday_stats = await get_bookings_by_weekday(0)

        self.assertEqual(sum(weekday_stats.values()), 1)
        self.assertEqual(max(weekday_stats.values()), 1)

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

    async def test_manual_booking_bypasses_user_active_limit_and_persists_source(self):
        with patch.dict("repositories.bookings.salon_config", {"max_active_bookings_per_user": 1}, clear=False):
            created_regular = await create_booking_if_available(
                user_id=77,
                name="Alice",
                phone="+70000000001",
                date="15.03.2026",
                time="10:00",
                duration=60,
                service_name="Service A",
                price=2000,
            )
            created_manual = await create_manual_booking(
                name="Bob",
                phone="+70000000002",
                date="15.03.2026",
                time="11:00",
                duration=60,
                service_name="Service B",
                price=3000,
                source="whatsapp",
                notes="manual note",
            )

        details = await get_booking_admin_details(2)
        self.assertTrue(created_regular)
        self.assertTrue(created_manual)
        self.assertEqual(details[10], "whatsapp")
        self.assertEqual(details[11], "manual note")
        self.assertEqual(details[12], 1)


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


class ServiceRepositoryTests(RepositoryTestCase):
    async def test_get_all_services_returns_numeric_price_value(self):
        await add_service("Test Service", "8 000", duration=30)

        services = await get_all_services()

        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]["price_value"], 8000)


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
        self.assertIn("source", booking_columns)
        self.assertIn("notes", booking_columns)
        self.assertIn("created_by_admin", booking_columns)
