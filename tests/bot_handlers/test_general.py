import unittest
from unittest.mock import ANY, AsyncMock, patch

import bot_handlers.general as general_handlers
from tests.support import make_callback, make_message, make_state


class GeneralHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_handler_opens_admin_panel_for_admin(self):
        message = make_message(user_id=1)

        with patch.object(general_handlers, "getenv", return_value="1"):
            await general_handlers.start_handler(message)

        message.answer.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup=general_handlers.keyboards.admin_menu)

    async def test_start_handler_uses_client_menu_for_regular_user(self):
        message = make_message(user_id=10)

        with patch.object(general_handlers, "getenv", return_value=None), \
             patch.dict(general_handlers.salon_config, {"welcome_text": "hello"}, clear=False), \
             patch.object(general_handlers.keyboards, "get_main_menu", return_value="menu"), \
             patch.object(general_handlers.keyboards, "get_booking_launch_keyboard", return_value="launch"):
            await general_handlers.start_handler(message)

        self.assertEqual(message.answer.await_count, 2)
        message.answer.assert_any_await("hello", parse_mode="HTML", reply_markup="launch")
        message.answer.assert_any_await(ANY, parse_mode="HTML", reply_markup="menu")

    async def test_client_menu_handler_refreshes_launch_and_reply_keyboards(self):
        message = make_message(user_id=1, text="Меню клиента")

        with patch.object(general_handlers, "getenv", return_value="1"), \
             patch.object(general_handlers.keyboards, "get_main_menu", return_value="menu"), \
             patch.object(general_handlers.keyboards, "get_booking_launch_keyboard", return_value="launch"):
            await general_handlers.client_menu_handler(message)

        self.assertEqual(message.answer.await_count, 2)
        message.answer.assert_any_await(ANY, parse_mode="HTML", reply_markup="launch")
        message.answer.assert_any_await(ANY, parse_mode="HTML", reply_markup="menu")

    async def test_export_excel_handler_sends_document_for_admin(self):
        message = make_message(user_id=1)

        with patch.object(general_handlers, "getenv", return_value="1"), \
             patch.object(general_handlers.database, "get_all_bookings", return_value=[("A", "B", "01.01.2026", "10:00", 2500)]), \
             patch.object(general_handlers, "_build_bookings_workbook") as build_mock, \
             patch.object(general_handlers, "FSInputFile", return_value="excel-file"), \
             patch.object(general_handlers.os, "remove") as remove_mock:
            await general_handlers.export_excel_handler(message)

        build_mock.assert_called_once_with("bookings_export.xlsx", [("A", "B", "01.01.2026", "10:00", 2500)])
        message.answer_document.assert_awaited_once_with("excel-file", caption=ANY, parse_mode="HTML")
        remove_mock.assert_called_once_with("bookings_export.xlsx")

    async def test_booking_actions_callback_renders_status_controls(self):
        callback = make_callback(data="booking_actions_all_0_15", user_id=1)
        booking = (15, 12345, "Alice", "+100", "14.03.2026", "10:00", "scheduled", 60)

        with patch.object(general_handlers, "getenv", return_value="1"), \
             patch.object(general_handlers.database, "get_booking_record_by_id", AsyncMock(return_value=booking)), \
             patch.object(general_handlers.keyboards, "get_admin_booking_actions_keyboard", return_value="actions-kb"):
            await general_handlers.booking_actions_callback(callback)

        callback.message.edit_text.assert_awaited_once_with(
            ANY,
            parse_mode="HTML",
            reply_markup="actions-kb",
        )

    async def test_admin_booking_status_callback_updates_status_and_refreshes_page(self):
        callback = make_callback(data="admin_booking_status_15_completed_today_0", user_id=1)

        with patch.object(general_handlers, "getenv", return_value="1"), \
             patch.object(general_handlers.database, "update_booking_status", AsyncMock()) as update_mock, \
             patch.object(general_handlers, "_show_booking_list", AsyncMock()) as show_mock:
            await general_handlers.admin_booking_status_callback(callback)

        update_mock.assert_awaited_once_with(15, "completed")
        callback.answer.assert_awaited_once_with(ANY)
        show_mock.assert_awaited_once_with(callback, context="today", page=0)

    async def test_admin_booking_status_callback_handles_no_show_status(self):
        callback = make_callback(data="admin_booking_status_15_no_show_all_0", user_id=1)

        with patch.object(general_handlers, "getenv", return_value="1"), \
             patch.object(general_handlers.database, "update_booking_status", AsyncMock()) as update_mock, \
             patch.object(general_handlers, "_show_booking_list", AsyncMock()) as show_mock:
            await general_handlers.admin_booking_status_callback(callback)

        update_mock.assert_awaited_once_with(15, "no_show")
        show_mock.assert_awaited_once_with(callback, context="all", page=0)

    async def test_back_to_admin_menu_clears_state(self):
        callback = make_callback(data="back_to_admin_menu", user_id=1)
        state = make_state()

        with patch.object(general_handlers, "getenv", return_value="1"):
            await general_handlers.back_to_admin_menu_callback(callback, state)

        state.clear.assert_awaited_once()

    async def test_search_bookings_handler_sets_state_for_admin(self):
        message = make_message(user_id=1, text="🔎 Поиск")
        state = make_state()

        with patch.object(general_handlers, "getenv", return_value="1"):
            await general_handlers.search_bookings_handler(message, state)

        state.set_state.assert_awaited_once()
        message.answer.assert_awaited_once_with(ANY, parse_mode="HTML")

    async def test_process_booking_search_renders_results(self):
        message = make_message(user_id=1, text="Alice")
        state = make_state()
        results = [(15, "Alice", "+100", "14.03.2026", "10:00", "no_show")]

        with patch.object(general_handlers, "getenv", return_value="1"), \
             patch.object(general_handlers.database, "search_bookings", AsyncMock(return_value=results)):
            await general_handlers.process_booking_search(message, state)

        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once_with(ANY, parse_mode="HTML")
