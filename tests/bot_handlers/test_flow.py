import unittest
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

import booking_service
import bot_handlers.client as client_handlers
import bot_handlers.reminders as reminder_handlers
from tests.support import make_callback, make_message, make_state


class ClientFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_portfolio_sends_media_group_and_gallery_button(self):
        message = make_message(user_id=10)
        portfolio_config = {
            "portfolio_url": "https://t.me/example",
            "portfolio_items": [
                {"media": "file_1", "caption": "Первая работа"},
                {"media": "file_2", "caption": "Вторая работа"},
            ],
        }

        with patch.object(client_handlers, "salon_config", portfolio_config), \
             patch.object(client_handlers.keyboards, "get_portfolio_keyboard", return_value="gallery-kb"):
            await client_handlers.handle_portfolio(message)

        message.bot.send_media_group.assert_awaited_once()
        media = message.bot.send_media_group.await_args.kwargs["media"]
        self.assertEqual(len(media), 2)
        self.assertEqual(media[0].media, "file_1")
        self.assertIn("Примеры работ", media[0].caption)
        message.answer.assert_awaited_once_with(
            "✨ Больше примеров доступно в полной галерее.",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup="gallery-kb",
        )

    async def test_handle_portfolio_falls_back_to_gallery_link(self):
        message = make_message(user_id=10)
        portfolio_config = {
            "portfolio_url": "https://t.me/example",
            "portfolio_items": [],
        }

        with patch.object(client_handlers, "salon_config", portfolio_config), \
             patch.object(client_handlers.keyboards, "get_portfolio_keyboard", return_value="gallery-kb"):
            await client_handlers.handle_portfolio(message)

        message.bot.send_media_group.assert_not_awaited()
        message.answer.assert_awaited_once_with(
            ANY,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup="gallery-kb",
        )

    async def test_launch_booking_webapp_sends_inline_web_app_button(self):
        message = make_message(user_id=10)

        with patch.object(client_handlers.keyboards, "get_booking_launch_keyboard", return_value="webapp-kb"):
            await client_handlers.launch_booking_webapp(message)

        message.answer.assert_awaited_once_with(ANY, parse_mode="HTML", reply_markup="webapp-kb")

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

    async def test_my_bookings_handler_sends_summary_and_active_cards_only(self):
        message = make_message(user_id=55)
        bookings = [
            (101, "Alice", "+100", "14.03.2026", "10:00", "scheduled"),
            (102, "Bob", "+200", "15.03.2026", "11:00", "completed"),
            (103, "Cara", "+300", "16.03.2026", "12:00", "cancelled"),
        ]

        with patch.object(client_handlers.database, "sync_completed_bookings", AsyncMock()), \
             patch.object(client_handlers.database, "get_user_bookings", AsyncMock(return_value=bookings)), \
             patch.object(client_handlers, "format_user_booking_text", return_value="active-card"), \
             patch.object(client_handlers.keyboards, "get_cancel_keyboard", return_value="kb1"):
            await client_handlers.my_bookings_handler(message)

        self.assertEqual(message.answer.await_count, 2)
        first_call = message.answer.await_args_list[0]
        self.assertIn("Мои записи", first_call.args[0])
        self.assertIn("Активные", first_call.args[0])
        self.assertIn("В истории", first_call.args[0])
        message.answer.assert_any_await("active-card", reply_markup="kb1", parse_mode="HTML")

    async def test_my_bookings_handler_shows_empty_state_when_user_has_no_active_bookings(self):
        message = make_message(user_id=55)

        with patch.object(client_handlers.database, "sync_completed_bookings", AsyncMock()), \
             patch.object(client_handlers.database, "get_user_bookings", AsyncMock(return_value=[])):
            await client_handlers.my_bookings_handler(message)

        message.answer.assert_awaited_once_with(ANY, parse_mode="HTML")

    async def test_booking_history_handler_sends_history_block(self):
        message = make_message(user_id=55)
        bookings = [
            (101, "Alice", "+100", "14.03.2026", "10:00", "scheduled"),
            (102, "Bob", "+200", "15.03.2026", "11:00", "completed"),
            (103, "Cara", "+300", "16.03.2026", "12:00", "cancelled"),
        ]

        with patch.object(client_handlers.database, "sync_completed_bookings", AsyncMock()), \
             patch.object(client_handlers.database, "get_user_bookings", AsyncMock(return_value=bookings)), \
             patch.object(client_handlers, "format_booking_history_text", return_value="history-block"):
            await client_handlers.booking_history_handler(message)

        message.answer.assert_awaited_once_with("history-block", parse_mode="HTML")

    async def test_booking_history_handler_appends_history_limit_note(self):
        message = make_message(user_id=55)
        bookings = [
            (101, "Alice", "+100", "14.03.2026", "10:00", "scheduled"),
            (102, "Bob", "+200", "15.03.2026", "11:00", "completed"),
            (103, "Cara", "+300", "16.03.2026", "12:00", "cancelled"),
            (104, "Dana", "+400", "17.03.2026", "13:00", "completed"),
            (105, "Ella", "+500", "18.03.2026", "14:00", "cancelled"),
            (106, "Faye", "+600", "19.03.2026", "15:00", "completed"),
            (107, "Gina", "+700", "20.03.2026", "16:00", "cancelled"),
        ]

        with patch.object(client_handlers.database, "sync_completed_bookings", AsyncMock()), \
             patch.object(client_handlers.database, "get_user_bookings", AsyncMock(return_value=bookings)), \
             patch.object(client_handlers, "format_booking_history_text", return_value="history-block"):
            await client_handlers.booking_history_handler(message)

        message.answer.assert_awaited_once()
        self.assertIn("Показаны последние 5 записей.", message.answer.await_args.args[0])

    async def test_booking_history_handler_shows_empty_state_when_history_missing(self):
        message = make_message(user_id=55)
        bookings = [
            (101, "Alice", "+100", "14.03.2026", "10:00", "scheduled"),
        ]

        with patch.object(client_handlers.database, "sync_completed_bookings", AsyncMock()), \
             patch.object(client_handlers.database, "get_user_bookings", AsyncMock(return_value=bookings)):
            await client_handlers.booking_history_handler(message)

        message.answer.assert_awaited_once_with(ANY, parse_mode="HTML")


class ReminderFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_reminder_cancel_rejects_foreign_user(self):
        callback = make_callback(data="rem_canc_15", user_id=999)

        with patch.object(reminder_handlers.database, "get_booking_by_id", AsyncMock(return_value=("Name", "Phone", "14.03.2026", "10:00", 1, "scheduled"))), \
             patch.object(reminder_handlers.database, "cancel_booking_by_id", AsyncMock()) as cancel_mock:
            await reminder_handlers.reminder_cancel_cb(callback)

        callback.answer.assert_awaited_once_with(ANY, show_alert=True)
        cancel_mock.assert_not_awaited()
        callback.message.answer.assert_not_awaited()

    async def test_reminder_confirm_success_clears_markup_and_notifies_admin(self):
        callback = make_callback(data="rem_conf_21", user_id=1)
        booking = ("Alice", "+100", "14.03.2026", "10:00", 1, "scheduled")

        with patch.object(reminder_handlers.database, "get_booking_by_id", AsyncMock(return_value=booking)), \
             patch.object(reminder_handlers, "getenv", return_value="777"):
            await reminder_handlers.reminder_confirm_cb(callback)

        callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
        callback.message.answer.assert_awaited_once_with(ANY)
        callback.bot.send_message.assert_awaited_once()

    async def test_reminder_reschedule_cancels_booking_for_owner(self):
        callback = make_callback(data="rem_resched_30", user_id=1)
        booking = ("Alice", "+100", "14.03.2026", "10:00", 1, "scheduled")

        with patch.object(reminder_handlers.database, "get_booking_by_id", AsyncMock(return_value=booking)), \
             patch.object(reminder_handlers.database, "cancel_booking_by_id", AsyncMock()) as cancel_mock, \
             patch.object(reminder_handlers, "getenv", return_value=None):
            await reminder_handlers.reminder_resched_cb(callback)

        cancel_mock.assert_awaited_once_with(30)
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

        callback.answer.assert_awaited_once_with(ANY, show_alert=True)

    async def test_cancel_booking_callback_uses_explicit_booking_and_calls_service(self):
        callback = make_callback(data="cancel_1_55", user_id=1)
        booking = (55, 1, "Alice", "+100", "14.03.2026", "10:00", "scheduled", 60)

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

    async def test_cancel_booking_callback_blocks_completed_booking(self):
        callback = make_callback(data="cancel_1_55", user_id=1)
        booking = (55, 1, "Alice", "+100", "14.03.2026", "10:00", "completed", 60)

        with patch.object(client_handlers.database, "get_booking_record_by_id", AsyncMock(return_value=booking)), \
             patch.object(client_handlers, "cancel_booking_and_notify", AsyncMock()) as cancel_mock:
            await client_handlers.cancel_booking_callback(callback)

        callback.answer.assert_awaited_once_with(ANY, show_alert=True)
        cancel_mock.assert_not_awaited()
