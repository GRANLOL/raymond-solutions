from __future__ import annotations

from .base import InlineKeyboardButton, salon_config


def get_working_days_keyboard(working_days, blacklisted_dates=None):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    blacklisted_dates = blacklisted_dates or []
    builder = InlineKeyboardBuilder()
    days_map = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 0: "Вс"}

    row = []
    for day_idx in [1, 2, 3, 4, 5, 6, 0]:
        is_active = day_idx in working_days
        row.append(
            InlineKeyboardButton(
                text=f"{days_map[day_idx]} {'✅' if is_active else '❌'}",
                callback_data=f"toggle_day_{day_idx}",
            )
        )
        if len(row) == 3:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)

    builder.row(InlineKeyboardButton(text="➕ Добавить выходную дату", callback_data="add_blacklist_date"))
    builder.row(InlineKeyboardButton(text="🚫 Блокировки времени", callback_data="manage_blocked_slots"))
    for date_str in blacklisted_dates:
        builder.row(InlineKeyboardButton(text=f"❌ Удалить выходной {date_str}", callback_data=f"del_bl_{date_str}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_system_settings_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    duration_enabled = bool(salon_config.get("show_service_duration", True))
    builder.row(InlineKeyboardButton(text="📬 Настройки напоминаний", callback_data="settings_reminders"))
    builder.row(InlineKeyboardButton(text="🌌 Часовой пояс (UTC)", callback_data="settings_timezone"))
    builder.row(InlineKeyboardButton(text="🕒 Часы работы", callback_data="settings_working_hours"))
    builder.row(InlineKeyboardButton(text="⏳ Шаг записи", callback_data="settings_interval"))
    builder.row(InlineKeyboardButton(text=f"💱 Валюта: {salon_config.get('currency_symbol', '₸')}", callback_data="settings_currency"))
    builder.row(InlineKeyboardButton(text=f"⏱ Длительность услуг: {'вкл' if duration_enabled else 'выкл'}", callback_data="toggle_service_duration_visibility"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_reminder_settings_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Текст за 24 часа", callback_data="edit_rem_text_1"))
    builder.row(InlineKeyboardButton(text="✏️ Текст второго уведомления", callback_data="edit_rem_text_2"))
    builder.row(InlineKeyboardButton(text="🕒 Время второго уведомления", callback_data="edit_rem_time_2"))
    builder.row(InlineKeyboardButton(text="◀️ Назад в настройки", callback_data="back_to_settings"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_clear_options_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗓 Очистить за сегодня", callback_data="clear_today"))
    builder.row(InlineKeyboardButton(text="📆 Очистить за дату", callback_data="clear_date"))
    builder.row(InlineKeyboardButton(text="🗓️ Очистить за период", callback_data="clear_period"))
    builder.row(InlineKeyboardButton(text="🧹 Очистить прошедшие", callback_data="clear_past"))
    builder.row(InlineKeyboardButton(text="🗑 Очистить все записи", callback_data="clear_all"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_confirm_clear_keyboard(action: str, payload: str = ""):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    cb_data = f"confirm_clear_{action}"
    if payload:
        cb_data = f"confirm_clear_{action}_{payload}"
    builder.row(InlineKeyboardButton(text="⚠️ Да, очистить", callback_data=cb_data))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_currency_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for symbol in ("₸", "₽", "$", "€"):
        builder.row(InlineKeyboardButton(text=f"Выбрать {symbol}", callback_data=f"set_currency_{symbol}"))
    builder.row(InlineKeyboardButton(text="⌨️ Ввести вручную", callback_data="set_currency_custom"))
    builder.row(InlineKeyboardButton(text="◀️ Назад в настройки", callback_data="back_to_settings"))
    return builder.as_markup()


def get_blocked_slots_keyboard(blocked_slots):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить блокировку", callback_data="add_blocked_slot"))
    for blocked_slot_id, date, start_time, end_time, _reason in blocked_slots[:20]:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ {date} {start_time}-{end_time}",
                callback_data=f"del_block_{blocked_slot_id}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад к графику", callback_data="back_to_schedule"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()
