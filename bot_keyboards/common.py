from __future__ import annotations

import re

from .base import InlineKeyboardButton, InlineKeyboardMarkup, WEBAPP_URL, WebAppInfo


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return digits


def get_cancel_keyboard(user_id: int, booking_id: int | None = None):
    callback_data = f"cancel_{user_id}_{booking_id}" if booking_id is not None else f"cancel_{user_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data=callback_data)]
        ]
    )


def get_booking_launch_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌸 Открыть запись", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]
    )


def get_back_to_admin_menu_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_admin_menu"))
    return builder.as_markup()


def get_cancel_admin_action_keyboard(back_callback: str | None = None, back_text: str = "◀️ Назад"):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    if back_callback:
        builder.row(InlineKeyboardButton(text=back_text, callback_data=back_callback))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_client_price_keyboard(page: int, total_pages: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    if total_pages <= 1:
        return None

    builder = InlineKeyboardBuilder()
    nav_buttons = []

    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"client_price_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"client_price_page_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


def get_reminder_keyboard(booking_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"rem_conf_{booking_id}"))
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"rem_canc_{booking_id}"),
        InlineKeyboardButton(text="🔄 Перенести", callback_data=f"rem_resched_{booking_id}"),
    )
    return builder.as_markup()


def get_analytics_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Сегодня", callback_data="stats_today"))
    builder.row(InlineKeyboardButton(text="📆 За 7 дней", callback_data="stats_week"))
    builder.row(InlineKeyboardButton(text="🗓 За 30 дней", callback_data="stats_month"))
    return builder.as_markup()


def get_admin_booking_page_keyboard(bookings, context: str, page: int, total_pages: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for booking_id, *_rest in bookings:
        builder.row(InlineKeyboardButton(text=f"Действия по записи #{booking_id}", callback_data=f"booking_actions_{context}_{page}_{booking_id}"))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"bookings_page_{context}_{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"bookings_page_{context}_{page + 1}"))
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_admin_menu"))
    return builder.as_markup()


def get_admin_booking_actions_keyboard(booking_id: int, phone: str, context: str, page: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    digits = _normalize_phone(phone)
    if digits:
        builder.row(
            InlineKeyboardButton(text="💬 Написать", url=f"https://wa.me/{digits}"),
            InlineKeyboardButton(text="📞 Позвонить", url=f"tel:+{digits}"),
        )
    builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"admin_cancel_booking_{booking_id}_{context}_{page}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"bookings_page_{context}_{page}"))
    return builder.as_markup()
