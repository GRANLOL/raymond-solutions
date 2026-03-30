from html import escape
import logging
import secrets
from os import getenv

from aiogram import types

from config import salon_config
import database
import keyboards
from runtime_state import get_runtime_value, set_runtime_value

logger = logging.getLogger(__name__)


def _store_pending_start_notification(*, token: str, booking_id: int, user_id: int) -> None:
    payload = get_runtime_value("pending_start_notifications", {}) or {}
    payload[token] = {
        "booking_id": int(booking_id),
        "user_id": int(user_id),
    }
    set_runtime_value("pending_start_notifications", payload)


def build_booking_start_payload(*, booking_id: int, user_id: int) -> str:
    token = secrets.token_urlsafe(8)
    _store_pending_start_notification(token=token, booking_id=booking_id, user_id=user_id)
    return f"booking_{token}"


def consume_booking_start_payload(payload: str, *, user_id: int) -> int | None:
    if not payload.startswith("booking_"):
        return None

    token = payload.split("booking_", 1)[1].strip()
    if not token:
        return None

    stored = get_runtime_value("pending_start_notifications", {}) or {}
    entry = stored.get(token)
    if not entry:
        return None

    if int(entry.get("user_id") or 0) != int(user_id):
        return None

    booking_id = int(entry.get("booking_id") or 0)
    stored.pop(token, None)
    set_runtime_value("pending_start_notifications", stored)
    return booking_id or None


def get_booking_status_label(status: str) -> str:
    return {
        "scheduled": "Активна",
        "completed": "Выполнена",
        "no_show": "Не пришел",
        "cancelled": "Отменена",
    }.get(status, status)


async def create_booking_and_notify(
    *,
    bot,
    user_id: int,
    user_full_name: str,
    service: str,
    date: str,
    time: str,
    duration: int,
    phone: str,
    name: str,
    price: int,
) -> tuple[bool, str, dict]:
    full_name_service = f"{name} ({service})" if name else f"{user_full_name} ({service})"

    try:
        booking_created = await database.create_booking_if_available(
            user_id=user_id,
            name=full_name_service,
            phone=phone,
            date=date,
            time=time,
            duration=duration,
            service_name=service,
            price=price,
        )
    except database.ActiveBookingLimitReachedError:
        active_limit = max(int(salon_config.get("max_active_bookings_per_user", 3) or 3), 1)
        return False, (
            f"У вас уже {active_limit} активные записи.\n\n"
            "Отмените одну из текущих записей, чтобы оформить новую."
        ), {}

    if not booking_created:
        return False, "Этот слот уже занят.\n\nОбновите форму записи и выберите другое время.", {}

    try:
        await database.attach_bookings_to_user_by_phone(phone, user_id)
    except Exception:
        logger.exception("Failed to attach bookings to Telegram user by phone", extra={"user_id": user_id})

    admin_text = (
        "🔔 <b>Новая запись</b>\n\n"
        f"<b>Клиент:</b> {escape(full_name_service)}\n"
        f"<b>Телефон:</b> {escape(phone)}\n"
        f"<b>Дата:</b> {escape(date)}\n"
        f"<b>Время:</b> {escape(time)}"
    )
    admin_id = getenv("ADMIN_ID")
    if admin_id and bot is not None:
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send booking notification to admin", extra={"admin_id": admin_id})

    success_text = (
        "✨ <b>Запись подтверждена</b>\n\n"
        f"<b>Услуга:</b> {escape(service)}\n"
        f"<b>Дата:</b> {escape(date)}\n"
        f"<b>Время:</b> {escape(time)}\n"
        f"<b>Телефон:</b> {escape(phone)}\n\n"
        "Ждём вас!"
    )
    client_notified = False
    if bot is not None:
        try:
            await bot.send_message(user_id, success_text, parse_mode="HTML")
            client_notified = True
        except Exception:
            logger.exception("Failed to send booking confirmation to client", extra={"user_id": user_id})

    meta = {
        "booking_id": int(booking_created),
        "client_notified": client_notified,
        "start_payload": None if client_notified else build_booking_start_payload(booking_id=int(booking_created), user_id=int(user_id)),
    }
    return True, success_text, meta


async def finalize_web_booking(
    message: types.Message,
    *,
    service: str,
    date: str,
    time: str,
    duration: int,
    phone: str,
    name: str,
    price: int,
    is_admin: bool,
) -> None:
    success, result_text, _meta = await create_booking_and_notify(
        bot=message.bot,
        user_id=message.from_user.id,
        user_full_name=message.from_user.full_name,
        service=service,
        date=date,
        time=time,
        duration=duration,
        phone=phone,
        name=name,
        price=price,
    )
    if not success:
        await message.answer(result_text)
        return

    remove_msg = await message.answer("Загрузка...", reply_markup=types.ReplyKeyboardRemove())
    await remove_msg.delete()

    await message.answer(result_text, parse_mode="HTML", reply_markup=keyboards.get_main_menu(is_admin=is_admin))


def format_user_booking_text(name: str, phone: str, date: str, time: str, status: str = "scheduled") -> str:
    safe_name = escape(name)
    safe_phone = escape(phone)
    safe_date = escape(date)
    safe_time = escape(time)
    safe_status = escape(get_booking_status_label(status))
    return (
        "🗓 <b>Актуальная запись</b>\n\n"
        f"🏷 <b>Статус:</b> {safe_status}\n"
        f"👤 <b>Запись:</b> {safe_name}\n"
        f"📅 <b>Дата:</b> {safe_date}\n"
        f"⏰ <b>Время:</b> {safe_time}\n"
        f"📞 <b>Телефон:</b> {safe_phone}"
    )


def format_booking_history_text(bookings: list[tuple[str, str, str, str, str]]) -> str:
    lines = [
        "🕰 <b>История записей</b>",
        "",
        "<i>Ваши прошедшие и отменённые визиты:</i>",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for index, (name, date, time, status, phone) in enumerate(bookings, start=1):
        safe_name = escape(name)
        safe_date = escape(date)
        safe_time = escape(time)
        safe_phone = escape(phone)
        safe_status = escape(get_booking_status_label(status))
        lines.extend(
            [
                f"🔹 <b>{index}. {safe_name}</b>",
                f"   🏷 <b>Статус:</b> {safe_status}",
                f"   📅 <b>Дата:</b> {safe_date} в {safe_time}",
                f"   📞 <b>Телефон:</b> {safe_phone}",
                "",
            ]
        )

    return "\n".join(lines).rstrip()


async def cancel_booking_and_notify(
    callback: types.CallbackQuery,
    *,
    booking_id: int,
    name: str,
    phone: str,
    date: str,
    time: str,
) -> None:
    await database.cancel_booking_by_id(booking_id)
    await callback.message.edit_text(
        "❌ <b>Запись отменена</b>\n\nЕсли захотите, можно записаться заново.",
        parse_mode="HTML",
    )

    msg_text = (
        "⚠️ <b>Отмена записи</b>\n\n"
        f"<b>Клиент:</b> {escape(name)}\n"
        f"<b>Дата:</b> {escape(date)}\n"
        f"<b>Время:</b> {escape(time)}\n"
        f"<b>Телефон:</b> {escape(phone)}"
    )
    admin_id = getenv("ADMIN_ID")
    if admin_id:
        try:
            await callback.bot.send_message(admin_id, msg_text, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send cancellation notification to admin", extra={"admin_id": admin_id})
