import unittest
from unittest.mock import ANY, patch

import bot_handlers.catalog as catalog_handlers
import bot_handlers.settings as settings_handlers
from tests.support import make_callback, make_message, make_state


class CatalogHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_edit_service_duration_callback_starts_duration_flow(self):
        callback = make_callback(data="eds_dur_7", user_id=1)
        state = make_state()

        with patch.object(catalog_handlers.keyboards, "get_cancel_admin_action_keyboard", return_value="kb"):
            await catalog_handlers.eds_duration_callback(callback, state)

        state.update_data.assert_awaited_once_with(service_id=7)
        state.set_state.assert_awaited_once()
        callback.message.answer.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup="kb")
        callback.answer.assert_awaited_once()

    async def test_process_edit_service_duration_updates_service(self):
        message = make_message(text="90")
        state = make_state(data={"service_id": 7})
        service = {"id": 7, "name": "Маникюр", "price": "2500", "duration": 90, "category_name": None}

        with patch.object(catalog_handlers.database, "update_service_duration") as update_mock, \
             patch.object(catalog_handlers.database, "get_service_by_id", return_value=service), \
             patch.object(catalog_handlers.keyboards, "get_service_edit_keyboard", return_value="kb"):
            await catalog_handlers.process_edit_service_duration(message, state)

        update_mock.assert_awaited_once_with(7, 90)
        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once_with(ANY, reply_markup="kb")

    async def test_move_category_callback_filters_invalid_targets(self):
        callback = make_callback(data="move_cat_2", user_id=1)
        state = make_state()
        categories = [
            {"id": 1, "name": "Root", "parent_id": None},
            {"id": 2, "name": "Child", "parent_id": 1},
            {"id": 3, "name": "Grandchild", "parent_id": 2},
            {"id": 4, "name": "Other", "parent_id": None},
        ]

        with patch.object(catalog_handlers, "getenv", return_value="1"), \
             patch.object(catalog_handlers.database, "get_all_categories", return_value=categories), \
             patch.object(catalog_handlers.database, "get_category_descendant_ids", return_value={3}), \
             patch.object(catalog_handlers.keyboards, "get_parent_category_keyboard", return_value="kb"):
            await catalog_handlers.move_category_callback(callback, state)

        state.update_data.assert_awaited_once_with(category_id=2)
        state.set_state.assert_awaited_once()
        callback.message.edit_text.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup="kb")

    async def test_process_service_duration_retries_on_invalid_number(self):
        message = make_message(text="abc")
        state = make_state(data={"name": "Маникюр", "category_id": 1, "price": "2500"})

        await catalog_handlers.process_service_duration(message, state)

        message.answer.assert_awaited_once_with(ANY)

    async def test_finish_service_selection_updates_categories_and_clears_state(self):
        callback = make_callback(data="finish_service_selection", user_id=1)
        state = make_state(data={"new_category_id": 9, "selected_services": [1, 2]})
        categories = [{"id": 9, "name": "New", "parent_id": None}]

        with patch.object(catalog_handlers.database, "update_service_category") as update_mock, \
             patch.object(catalog_handlers.database, "get_all_categories", return_value=categories), \
             patch.object(catalog_handlers.keyboards, "build_category_tree", return_value=[(categories[0], 0)]), \
             patch.object(catalog_handlers.keyboards, "get_categories_keyboard", return_value="kb"):
            await catalog_handlers.finish_service_selection(callback, state)

        self.assertEqual(update_mock.await_count, 2)
        state.clear.assert_awaited_once()
        callback.message.edit_text.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup="kb")

    async def test_back_to_services_callback_restores_requested_page(self):
        callback = make_callback(data="back_to_services", user_id=1)
        state = make_state(data={"services_page": 1})
        services = [
            {"id": index, "name": f"Service {index}", "price": str(index), "category_name": None}
            for index in range(25)
        ]

        with patch.object(catalog_handlers.database, "get_all_services", return_value=services), \
             patch.object(catalog_handlers.keyboards, "get_services_keyboard", return_value="kb"):
            await catalog_handlers.back_to_services_callback(callback, state)

        state.clear.assert_awaited_once()
        callback.message.edit_text.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup="kb")


class SettingsHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_rem_time_2_rejects_invalid_hours(self):
        message = make_message(text="0")
        state = make_state()

        with patch.object(settings_handlers.keyboards, "get_cancel_admin_action_keyboard", return_value="kb"):
            await settings_handlers.process_rem_time_2(message, state)

        message.answer.assert_awaited_once_with(ANY, reply_markup="kb")
        state.clear.assert_not_awaited()

    async def test_process_timezone_offset_saves_valid_offset(self):
        message = make_message(text="+5")
        state = make_state()

        with patch.object(settings_handlers, "update_config") as update_mock, \
             patch.object(settings_handlers.keyboards, "get_system_settings_keyboard", return_value="kb"):
            await settings_handlers.process_timezone_offset(message, state)

        update_mock.assert_called_once_with("timezone_offset", 5)
        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once_with(ANY, reply_markup="kb")

    async def test_process_blacklist_date_adds_date_and_returns_schedule_keyboard(self):
        message = make_message(text="31.12.2026")
        state = make_state()

        with patch.dict(settings_handlers.salon_config, {"blacklisted_dates": [], "working_days": [1, 2, 3]}, clear=False), \
             patch.object(settings_handlers, "update_config") as update_mock, \
             patch.object(settings_handlers.keyboards, "get_working_days_keyboard", return_value="kb"):
            await settings_handlers.process_blacklist_date(message, state)

        update_mock.assert_called_once()
        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup="kb")

    async def test_process_booking_window_rejects_invalid_value(self):
        message = make_message(text="0")
        state = make_state()

        with patch.object(settings_handlers.keyboards, "get_cancel_admin_action_keyboard", return_value="kb"):
            await settings_handlers.process_booking_window(message, state)

        message.answer.assert_awaited_once_with(ANY, reply_markup="kb")
        state.clear.assert_not_awaited()

    async def test_toggle_service_duration_visibility_updates_config_and_rerenders_menu(self):
        callback = make_callback(data="toggle_service_duration_visibility", user_id=1)

        with patch.object(settings_handlers, "getenv", return_value="1"), \
             patch.object(settings_handlers, "update_config") as update_mock, \
             patch.object(settings_handlers.keyboards, "get_system_settings_keyboard", return_value="kb"), \
             patch.dict(settings_handlers.salon_config, {"show_service_duration": True}, clear=False):
            await settings_handlers.toggle_service_duration_visibility_callback(callback)

        update_mock.assert_called_once_with("show_service_duration", False)
        callback.message.edit_text.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup="kb")
        callback.answer.assert_awaited_once()

    async def test_process_working_hours_rejects_invalid_format(self):
        message = make_message(text="10-20")
        state = make_state()

        with patch.object(settings_handlers.keyboards, "get_cancel_admin_action_keyboard", return_value="kb"):
            await settings_handlers.process_working_hours(message, state)

        message.answer.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup="kb")
        state.clear.assert_not_awaited()

    async def test_process_working_hours_rejects_when_future_bookings_conflict(self):
        message = make_message(text="10:00-18:00")
        state = make_state()
        conflicts = [{"date": "20.03.2026", "time": "19:00", "name": "Alice"}]

        with patch.object(settings_handlers.database, "get_future_bookings_outside_working_hours", return_value=conflicts), \
             patch.object(settings_handlers.keyboards, "get_cancel_admin_action_keyboard", return_value="kb"):
            await settings_handlers.process_working_hours(message, state)

        message.answer.assert_awaited_once_with(ANY, reply_markup="kb")
        state.clear.assert_not_awaited()
