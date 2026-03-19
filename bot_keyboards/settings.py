from __future__ import annotations

from .base import InlineKeyboardButton, salon_config


def get_working_days_keyboard(working_days, blacklisted_dates=None):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    blacklisted_dates = blacklisted_dates or []
    builder = InlineKeyboardBuilder()
    days_map = {
        1: "Пн",
        2: "Вт",
        3: "Ср",
        4: "Чт",
        5: "Пт",
        6: "Сб",
        0: "Вс",
    }

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
    builder.row(InlineKeyboardButton(text="🍽 Перерыв", callback_data="manage_breaks"))
    for date_str in blacklisted_dates:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ Удалить выходной {date_str}",
                callback_data=f"del_bl_{date_str}",
            )
        )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_system_settings_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    duration_enabled = bool(salon_config.get("show_service_duration", True))
    builder.row(InlineKeyboardButton(text="🔔 Настройки напоминаний", callback_data="settings_reminders"))
    builder.row(InlineKeyboardButton(text="🤖 Тексты бота", callback_data="settings_bot_texts"))
    builder.row(InlineKeyboardButton(text="🕒 Часовой пояс (UTC)", callback_data="settings_timezone"))
    builder.row(InlineKeyboardButton(text="🗓 Окно брони", callback_data="settings_booking_window"))
    builder.row(InlineKeyboardButton(text="🕔 Часы работы", callback_data="settings_working_hours"))
    builder.row(InlineKeyboardButton(text="🧭 Шаг записи", callback_data="settings_interval"))
    builder.row(
        InlineKeyboardButton(
            text=f"💱 Валюта: {salon_config.get('currency_symbol', '₸')}",
            callback_data="settings_currency",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"⏱ Длительность услуг: {'вкл' if duration_enabled else 'выкл'}",
            callback_data="toggle_service_duration_visibility",
        )
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_admin_menu"))
    return builder.as_markup()


def get_reminder_settings_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Текст за 24 часа", callback_data="edit_rem_text_1"))
    builder.row(InlineKeyboardButton(text="✏️ Текст второго уведомления", callback_data="edit_rem_text_2"))
    builder.row(InlineKeyboardButton(text="🕒 Время второго уведомления", callback_data="edit_rem_time_2"))
    builder.row(InlineKeyboardButton(text="← Назад в настройки", callback_data="back_to_settings"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_bot_texts_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Описание профиля", callback_data="edit_bot_description"))
    builder.row(InlineKeyboardButton(text="💬 Текст пустого чата", callback_data="edit_bot_about"))
    builder.row(InlineKeyboardButton(text="← Назад в настройки", callback_data="back_to_settings"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_clear_options_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Очистить за сегодня", callback_data="clear_today"))
    builder.row(InlineKeyboardButton(text="📆 Очистить за дату", callback_data="clear_date"))
    builder.row(InlineKeyboardButton(text="🗓 Очистить за период", callback_data="clear_period"))
    builder.row(InlineKeyboardButton(text="🧹 Очистить прошлое", callback_data="clear_past"))
    builder.row(InlineKeyboardButton(text="📛 Очистить все записи", callback_data="clear_all"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_confirm_clear_keyboard(action: str, payload: str = ""):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    cb_data = f"confirm_clear_{action}"
    if payload:
        cb_data = f"confirm_clear_{action}_{payload}"
    builder.row(InlineKeyboardButton(text="🗑 Да, очистить", callback_data=cb_data))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_currency_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for symbol in ("₸", "₽", "$", "€"):
        builder.row(InlineKeyboardButton(text=f"Выбрать {symbol}", callback_data=f"set_currency_{symbol}"))
    builder.row(InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="set_currency_custom"))
    builder.row(InlineKeyboardButton(text="← Назад в настройки", callback_data="back_to_settings"))
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
    builder.row(InlineKeyboardButton(text="← Назад к графику", callback_data="back_to_schedule"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_breaks_menu_keyboard(blocked_slots, lunch_summary: str, lunch_enabled: bool):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    lunch_text = f"🍽 Обед: {lunch_summary}" if lunch_enabled else "🍽 Обед: не настроен"
    builder.row(InlineKeyboardButton(text=lunch_text, callback_data="configure_lunch_break"))
    builder.row(InlineKeyboardButton(text="🗓 Настроить отдельный перерыв", callback_data="start_single_break"))
    for blocked_slot_id, date, start_time, end_time, _reason in blocked_slots[:12]:
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 {date} {start_time}-{end_time}",
                callback_data=f"del_block_{blocked_slot_id}",
            )
        )
    builder.row(InlineKeyboardButton(text="← Назад к графику", callback_data="back_to_schedule"))
    builder.row(InlineKeyboardButton(text="✖ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_break_dates_keyboard(date_options, back_callback: str = "manage_blocked_slots"):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    row = []
    for callback_data, label in date_options:
        row.append(InlineKeyboardButton(text=label, callback_data=callback_data))
        if len(row) == 2:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="← Назад", callback_data=back_callback))
    builder.row(InlineKeyboardButton(text="✖ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_break_time_keyboard(time_options, back_callback: str, disable_callback: str | None = None):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    row = []
    for callback_data, label in time_options:
        row.append(InlineKeyboardButton(text=label, callback_data=callback_data))
        if len(row) == 3:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    if disable_callback:
        builder.row(InlineKeyboardButton(text="🚫 Выключить обед", callback_data=disable_callback))
    builder.row(InlineKeyboardButton(text="← Назад", callback_data=back_callback))
    builder.row(InlineKeyboardButton(text="✖ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()
