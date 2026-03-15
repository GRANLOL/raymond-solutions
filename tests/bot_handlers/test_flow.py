import unittest
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

import booking_service
import bot_handlers.client as client_handlers
import bot_handlers.reminders as reminder_handlers
from tests.support import make_callback, make_message, make_state


class ClientFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_launch_booking_webapp_sends_inline_web_app_button(self):
        message = make_message(user_id=10)

        with patch.object(client_handlers.keyboards, "get_booking_launch_keyboard", return_value="webapp-kb"):
            await client_handlers.launch_booking_webapp(message)

        message.answer.assert_awaited_once_with(
            "Нажмите кнопку ниже, чтобы открыть запись.",
            reply_markup="webapp-kb",
        )

    async def test_process_web_app_data_success_calls_finalize_and_clears_state(self):
        message = make_message(
            user_id=10,
            web_app_data={
                "service": 1,
                "date": "14.03.2026",
                "time": "10:00",
                "phone": "+10000000000",
                "name": "Alice",
            },
        )
        state = make_state()
        validated = {
            "service": {"name": "Маникюр"},
            "date": "14.03.2026",
            "time": "10:00",
            "duration": 60,
            "phone": "+10000000000",
            "name": "Alice",
            "price": 2500,
        }

        with patch.object(client_handlers, "service_validate_web_booking", AsyncMock(return_value=(validated, None))), \
             patch.object(client_handlers, "finalize_web_booking", AsyncMock()) as finalize_mock:
            await client_handlers.process_web_app_data(message, state)

        finalize_mock.assert_awaited_once_with(
            message,
            service="Маникюр",
            date="14.03.2026",
            time="10:00",
            duration=60,
            phone="+10000000000",
            name="Alice",
            price=2500,
            is_admin=False,
        )
        state.clear.assert_awaited_once()

    async def test_process_web_app_data_validation_error_replies_without_finalize(self):
        message = make_message(web_app_data={"broken": True})
        state = make_state()

        with patch.object(client_handlers, "service_validate_web_booking", AsyncMock(return_value=({}, "invalid payload"))), \
             patch.object(client_handlers, "finalize_web_booking", AsyncMock()) as finalize_mock:
            await client_handlers.process_web_app_data(message, state)

        message.answer.assert_awaited_once_with("invalid payload")
        finalize_mock.assert_not_awaited()
        state.clear.assert_not_awaited()

    async def test_my_bookings_handler_sends_each_booking_with_cancel_keyboard(self):
        message = make_message(user_id=55)
        bookings = [
            (101, "Alice", "+100", "14.03.2026", "10:00", None),
            (102, "Bob", "+200", "15.03.2026", "11:00", None),
        ]

        with patch.object(client_handlers.database, "get_user_bookings", AsyncMock(return_value=bookings)), \
             patch.object(client_handlers, "format_user_booking_text", side_effect=["msg1", "msg2"]), \
             patch.object(client_handlers.keyboards, "get_cancel_keyboard", side_effect=["kb1", "kb2"]):
            await client_handlers.my_bookings_handler(message)

        self.assertEqual(message.answer.await_count, 2)
        message.answer.assert_any_await("msg1", reply_markup="kb1", parse_mode="HTML")
        message.answer.assert_any_await("msg2", reply_markup="kb2", parse_mode="HTML")


class ReminderFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_reminder_cancel_rejects_foreign_user(self):
        callback = make_callback(data="rem_canc_15", user_id=999)

        with patch.object(reminder_handlers.database, "get_booking_by_id", AsyncMock(return_value=("Name", "Phone", "14.03.2026", "10:00", "Master", 1))), \
             patch.object(reminder_handlers.database, "delete_booking_by_id", AsyncMock()) as delete_mock:
            await reminder_handlers.reminder_cancel_cb(callback)

        callback.answer.assert_awaited_once_with("Эта кнопка не относится к вашей записи.", show_alert=True)
        delete_mock.assert_not_awaited()
        callback.message.answer.assert_not_awaited()

    async def test_reminder_confirm_success_clears_markup_and_notifies_admin(self):
        callback = make_callback(data="rem_conf_21", user_id=1)
        booking = ("Alice", "+100", "14.03.2026", "10:00", "Top Master", 1)

        with patch.object(reminder_handlers.database, "get_booking_by_id", AsyncMock(return_value=booking)), \
             patch.object(reminder_handlers, "getenv", return_value="777"):
            await reminder_handlers.reminder_confirm_cb(callback)

        callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
        callback.message.answer.assert_awaited_once_with(ANY)
        callback.bot.send_message.assert_awaited_once()

    async def test_reminder_reschedule_deletes_booking_for_owner(self):
        callback = make_callback(data="rem_resched_30", user_id=1)
        booking = ("Alice", "+100", "14.03.2026", "10:00", None, 1)

        with patch.object(reminder_handlers.database, "get_booking_by_id", AsyncMock(return_value=booking)), \
             patch.object(reminder_handlers.database, "delete_booking_by_id", AsyncMock()) as delete_mock, \
             patch.object(reminder_handlers, "getenv", return_value=None):
            await reminder_handlers.reminder_resched_cb(callback)

        delete_mock.assert_awaited_once_with(30)
        callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
        callback.message.answer.assert_awaited_once_with(ANY)


class BookingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_finalize_web_booking_replies_when_slot_is_taken(self):
        message = make_message(user_id=5, full_name="Alice")

        with patch.object(booking_service.database, "create_booking_if_available", AsyncMock(return_value=False)):
            await booking_service.finalize_web_booking(
                message,
                service="Маникюр",
                date="14.03.2026",
                time="10:00",
                duration=60,
                phone="+100",
                name="Alice",
                price=2500,
                is_admin=False,
            )

        message.answer.assert_awaited_once_with(ANY)
        message.bot.send_message.assert_not_awaited()

    async def test_finalize_web_booking_sends_admin_notification_on_success(self):
        remove_message = SimpleNamespace(delete=AsyncMock())
        message = make_message(user_id=5, full_name="Alice")
        message.answer = AsyncMock(side_effect=[remove_message, None])

        with patch.object(booking_service.database, "create_booking_if_available", AsyncMock(return_value=True)), \
             patch.object(booking_service.keyboards, "get_main_menu", return_value="menu"), \
             patch.object(booking_service, "getenv", return_value="777"):
            await booking_service.finalize_web_booking(
                message,
                service="Маникюр",
                date="14.03.2026",
                time="10:00",
                duration=60,
                phone="+100",
                name="Alice",
                price=2500,
                is_admin=False,
            )

        self.assertEqual(message.answer.await_count, 2)
        remove_message.delete.assert_awaited_once()
        message.bot.send_message.assert_awaited_once()


class CancelBookingHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_booking_callback_rejects_foreign_user(self):
        callback = make_callback(data="cancel_1_55", user_id=999)

        await client_handlers.cancel_booking_callback(callback)

        callback.answer.assert_awaited_once_with("Это не ваша запись!", show_alert=True)

    async def test_cancel_booking_callback_uses_explicit_booking_and_calls_service(self):
        callback = make_callback(data="cancel_1_55", user_id=1)
        booking = (55, 1, "Alice", "+100", "14.03.2026", "10:00", None)

        with patch.object(client_handlers.database, "get_booking_record_by_id", AsyncMock(return_value=booking)), \
             patch.object(client_handlers, "cancel_booking_and_notify", AsyncMock()) as cancel_mock:
            await client_handlers.cancel_booking_callback(callback)

        cancel_mock.assert_awaited_once_with(
            callback,
            booking_id=55,
            name="Alice",
            phone="+100",
            date="14.03.2026",
            time="10:00",
        )
