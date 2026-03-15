import unittest
from unittest.mock import ANY, AsyncMock, patch

import bot_handlers.admin_cleanup as admin_cleanup_handlers
from tests.support import make_callback, make_message


class AdminCleanupMoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_clear_date_rejects_invalid_format(self):
        message = make_message(text="2026-03-14")
        state = AsyncMock()

        await admin_cleanup_handlers.process_clear_date(message, state)

        message.answer.assert_awaited_once_with(ANY)
        state.clear.assert_not_awaited()

    async def test_process_clear_period_end_builds_confirmation(self):
        message = make_message(text="20.03.2026")
        state = AsyncMock()
        state.get_data.return_value = {"clear_start": "10.03.2026"}

        with patch.object(admin_cleanup_handlers.keyboards, "get_confirm_clear_keyboard", return_value="kb"):
            await admin_cleanup_handlers.process_clear_period_end(message, state)

        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once_with(ANY, reply_markup="kb")

    async def test_clear_bookings_handler_shows_options_for_admin(self):
        message = make_message(user_id=1)

        with patch.object(admin_cleanup_handlers, "getenv", return_value="1"), \
             patch.object(admin_cleanup_handlers.keyboards, "get_clear_options_keyboard", return_value="kb"):
            await admin_cleanup_handlers.clear_bookings_handler(message)

        message.answer.assert_awaited_once_with(ANY, reply_markup="kb")

    async def test_confirm_clear_cb_today_uses_today_date(self):
        callback = make_callback(data="confirm_clear_today", user_id=1)

        fake_now = type("FakeNow", (), {"strftime": lambda self, fmt: "14.03.2026"})()
        fake_datetime = type("FakeDateTime", (), {"now": staticmethod(lambda: fake_now)})

        with patch.object(admin_cleanup_handlers, "getenv", return_value="1"), \
             patch.object(admin_cleanup_handlers.database, "delete_bookings_by_date", AsyncMock(return_value=3)) as delete_mock, \
             patch.object(admin_cleanup_handlers, "datetime", fake_datetime):
            await admin_cleanup_handlers.confirm_clear_cb(callback)

        delete_mock.assert_awaited_once_with("14.03.2026")
        callback.message.edit_text.assert_awaited_once_with(ANY)
