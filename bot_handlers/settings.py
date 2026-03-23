from __future__ import annotations

import re

from money import get_currency_symbol
from time_utils import get_salon_today

from .base import F, FSMContext, Router, database, datetime, getenv, keyboards, salon_config, timedelta, update_config, types
from .states import (
    AddBlacklistDateForm,
    AddBlockedSlotForm,
    AddBookingWindowForm,
    ConfigureLunchBreakForm,
    ConfigureSingleBreakForm,
    EditBotProfileTextForm,
    EditCurrencyForm,
    EditReminderSettingsForm,
    EditTimezoneForm,
    ScheduleIntervalForm,
    WorkingHoursForm,
)

router = Router()

DESCRIPTION_MAX_LENGTH = 512
ABOUT_TEXT_MAX_LENGTH = 120


def _is_admin(user_id: int) -> bool:
    admin_id = getenv("ADMIN_ID")
    return bool(admin_id and str(user_id) == admin_id)


def _schedule_markup():
    return keyboards.get_working_days_keyboard(
        salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0]),
        salon_config.get("blacklisted_dates", []),
    )


def _get_current_bot_text(key: str) -> str:
    value = str(salon_config.get(key, "") or "").strip()
    return value or "Не задано"


def _reminder_template_examples() -> str:
    return (
        "\n\nДоступные переменные:\n"
        "<code>{name}</code> - имя клиента\n"
        "<code>{date}</code> - дата записи\n"
        "<code>{time}</code> - время записи\n\n"
        "Пример:\n"
        "<code>Здравствуйте, {name}! Напоминаем о записи {date} в {time}.</code>"
    )


def _parse_working_hours_bounds() -> tuple[int, int]:
    match = re.search(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", salon_config.get("working_hours", "10:00-20:00") or "")
    start_str, end_str = ("10:00", "20:00")
    if match:
        start_str, end_str = match.group(1), match.group(2)
    elif "-" in str(salon_config.get("working_hours", "")):
        start_str, end_str = [part.strip() for part in salon_config.get("working_hours", "10:00-20:00").split("-", 1)]

    start_hours, start_minutes = map(int, start_str.split(":"))
    end_hours, end_minutes = map(int, end_str.split(":"))
    return start_hours * 60 + start_minutes, end_hours * 60 + end_minutes


def _build_break_boundaries() -> list[str]:
    start_mins, end_mins = _parse_working_hours_bounds()
    interval = int(salon_config.get("schedule_interval", 30) or 30)
    if interval <= 0:
        interval = 30

    values = []
    current = start_mins
    while current <= end_mins:
        values.append(f"{current // 60:02d}:{current % 60:02d}")
        current += interval
    return values


def _build_break_start_options(prefix: str) -> list[tuple[str, str]]:
    boundaries = _build_break_boundaries()
    return [(f"{prefix}_{value}", value) for value in boundaries[:-1]]


def _build_break_end_options(prefix: str, start_time: str) -> list[tuple[str, str]]:
    boundaries = _build_break_boundaries()
    return [(f"{prefix}_{value}", value) for value in boundaries if value > start_time]


def _breaks_menu_markup(blocked_slots):
    lunch_enabled = bool(salon_config.get("lunch_break_enabled", False))
    lunch_start = str(salon_config.get("lunch_break_start", "") or "").strip()
    lunch_end = str(salon_config.get("lunch_break_end", "") or "").strip()
    lunch_summary = f"{lunch_start}-{lunch_end}" if lunch_enabled and lunch_start and lunch_end else "не настроен"
    return keyboards.get_breaks_menu_keyboard(blocked_slots, lunch_summary, lunch_enabled)


def _build_single_break_date_options() -> list[tuple[str, str]]:
    booking_window = max(int(salon_config.get("booking_window", 7) or 7), 1)
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    blacklisted_dates = set(salon_config.get("blacklisted_dates", []))
    today = get_salon_today()
    options = []

    weekday_names = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 0: "Вс"}
    for offset in range(booking_window):
        current_date = today + timedelta(days=offset)
        js_weekday = (current_date.weekday() + 1) % 7
        date_str = current_date.strftime("%d.%m.%Y")
        if js_weekday not in working_days or date_str in blacklisted_dates:
            continue
        label = f"{current_date.strftime('%d.%m')} ({weekday_names[js_weekday]})"
        options.append((f"single_break_date_{date_str}", label))
    return options


def _breaks_menu_text(blocked_slots) -> str:
    lunch_enabled = bool(salon_config.get("lunch_break_enabled", False))
    lunch_start = str(salon_config.get("lunch_break_start", "") or "").strip()
    lunch_end = str(salon_config.get("lunch_break_end", "") or "").strip()
    lunch_line = f"{lunch_start}-{lunch_end}" if lunch_enabled and lunch_start and lunch_end else "не настроен"

    lines = [
        "🍽 <b>Перерыв</b>",
        "",
        f"Постоянный обед: <b>{lunch_line}</b>",
        "Обед действует на все рабочие даты, включая будущие даты после текущего окна записи.",
        "",
    ]

    if blocked_slots:
        lines.append("Разовые перерывы:")
        for _slot_id, date_str, start_time, end_time, _reason in blocked_slots[:12]:
            lines.append(f"• {date_str} {start_time}-{end_time}")
    else:
        lines.append("Разовые перерывы пока не настроены.")

    return "\n".join(lines)


@router.message(F.text == "⚙️ Настройки")
async def system_settings_handler(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    await message.answer("⚙️ <b>Настройки системы</b>\n\nВыберите раздел для изменения.", parse_mode="HTML", reply_markup=keyboards.get_system_settings_keyboard())


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    await callback.message.edit_text("⚙️ <b>Настройки системы</b>\n\nВыберите раздел для изменения.", parse_mode="HTML", reply_markup=keyboards.get_system_settings_keyboard())


@router.callback_query(F.data == "settings_reminders")
async def settings_reminders_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    default_rem1 = "Здравствуйте, {name}! Напоминаем о вашей записи завтра ({date}) в {time}."
    default_rem2 = "Здравствуйте, {name}! Напоминаем, ваша запись состоится сегодня ({date}) в {time}."
    
    rem1 = salon_config.get("reminder_1_text", "")
    rem2 = salon_config.get("reminder_2_text", "")
    rem1_display = f"<blockquote>{rem1}</blockquote>" if rem1 else f"<blockquote>{default_rem1}</blockquote> (по умолчанию)"
    rem2_display = f"<blockquote>{rem2}</blockquote>" if rem2 else f"<blockquote>{default_rem2}</blockquote> (по умолчанию)"
    hours = salon_config.get("reminder_2_hours", 2)
    
    text = (
        "🔔 <b>Настройки напоминаний</b>\n\n"
        "1. Первое уведомление отправляется за <b>24 часа</b>.\n"
        f"Установленный текст:\n{rem1_display}\n\n"
        f"2. Второе уведомление отправляется за <b>{hours} ч.</b> до записи.\n"
        f"Установленный текст:\n{rem2_display}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.get_reminder_settings_keyboard())


@router.callback_query(F.data == "settings_bot_texts")
async def settings_bot_texts_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()

    short_desc = "Не задано"
    try:
        short_desc_obj = await callback.bot.get_my_short_description()
        if short_desc_obj and short_desc_obj.short_description:
            short_desc = short_desc_obj.short_description
    except Exception:
        short_desc = _get_current_bot_text("bot_description")

    desc = "Не задано"
    try:
        desc_obj = await callback.bot.get_my_description()
        if desc_obj and desc_obj.description:
            desc = desc_obj.description
    except Exception:
        desc = _get_current_bot_text("bot_about_text")

    await callback.message.edit_text(
        "🤖 <b>Тексты бота</b>\n\n"
        f"Описание профиля: <b>{short_desc}</b>\n\n"
        f"Текст пустого чата: <b>{desc}</b>\n\n"
        "Здесь можно настроить текст профиля бота и краткий текст для пустого чата.",
        parse_mode="HTML",
        reply_markup=keyboards.get_bot_texts_keyboard(),
    )


@router.callback_query(F.data == "edit_bot_description")
async def edit_bot_description_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(EditBotProfileTextForm.description)
    await callback.message.answer(
        "Введите новое <b>описание профиля</b> бота.\n\n"
        "Этот краткий текст показывается в профиле бота и в шапке.\n"
        "Чтобы очистить описание, отправьте <code>-</code>.",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "← Назад в настройки"),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_bot_about")
async def edit_bot_about_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(EditBotProfileTextForm.about)
    await callback.message.answer(
        "Введите новый <b>текст пустого чата</b>.\n\n"
        "Этот текст показывается в пустом чате с ботом.\n"
        "Чтобы очистить текст, отправьте <code>-</code>.",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "← Назад в настройки"),
    )
    await callback.answer()


@router.message(EditBotProfileTextForm.description)
async def process_bot_description_text(message: types.Message, state: FSMContext):
    value = (message.text or "").strip()
    if value == "-":
        value = ""
    if len(value) > DESCRIPTION_MAX_LENGTH:
        await message.answer(
            f"Описание должно быть не длиннее {DESCRIPTION_MAX_LENGTH} символов.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "← Назад в настройки"),
        )
        return

    try:
        await message.bot.set_my_short_description(short_description=value or None)
    except Exception:
        await message.answer(
            "Не удалось обновить описание профиля через Telegram API. Попробуйте позже.",
            reply_markup=keyboards.get_bot_texts_keyboard(),
        )
        return

    update_config("bot_description", value)
    await state.clear()
    await message.answer("✅ Описание профиля обновлено.", reply_markup=keyboards.get_bot_texts_keyboard())


@router.message(EditBotProfileTextForm.about)
async def process_bot_about_text(message: types.Message, state: FSMContext):
    value = (message.text or "").strip()
    if value == "-":
        value = ""
    if len(value) > ABOUT_TEXT_MAX_LENGTH:
        await message.answer(
            f"Текст пустого чата должен быть не длиннее {ABOUT_TEXT_MAX_LENGTH} символов.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "← Назад в настройки"),
        )
        return

    try:
        await message.bot.set_my_description(description=value or None)
    except Exception:
        await message.answer(
            "Не удалось обновить текст пустого чата через Telegram API. Попробуйте позже.",
            reply_markup=keyboards.get_bot_texts_keyboard(),
        )
        return

    update_config("bot_about_text", value)
    await state.clear()
    await message.answer("✅ Текст пустого чата обновлен.", reply_markup=keyboards.get_bot_texts_keyboard())


@router.callback_query(F.data == "edit_rem_text_1")
async def edit_rem_text_1_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.text_1)
    current = salon_config.get("reminder_1_text", "")
    default_text = "Здравствуйте, {name}! Напоминаем о вашей записи завтра ({date}) в {time}."
    current_display = f"\n\nТекущий текст:\n<blockquote>{current}</blockquote>" if current else f"\n\nТекст по умолчанию:\n<blockquote>{default_text}</blockquote>"
    await callback.message.answer(
        "Введите новый текст для <b>первого напоминания</b>."
        + current_display
        + _reminder_template_examples(),
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_rem_text_2")
async def edit_rem_text_2_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.text_2)
    current = salon_config.get("reminder_2_text", "")
    default_text = "Здравствуйте, {name}! Напоминаем, ваша запись состоится сегодня ({date}) в {time}."
    current_display = f"\n\nТекущий текст:\n<blockquote>{current}</blockquote>" if current else f"\n\nТекст по умолчанию:\n<blockquote>{default_text}</blockquote>"
    await callback.message.answer(
        "Введите новый текст для <b>второго напоминания</b>."
        + current_display
        + _reminder_template_examples(),
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_rem_time_2")
async def edit_rem_time_2_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.time_2)
    await callback.message.answer("За сколько часов до записи отправлять <b>второе напоминание</b>?", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.message(EditReminderSettingsForm.text_1)
async def process_rem_text_1(message: types.Message, state: FSMContext):
    update_config("reminder_1_text", message.text)
    await state.clear()
    await message.answer("✅ Текст первого напоминания обновлен.", reply_markup=keyboards.get_reminder_settings_keyboard())


@router.message(EditReminderSettingsForm.text_2)
async def process_rem_text_2(message: types.Message, state: FSMContext):
    update_config("reminder_2_text", message.text)
    await state.clear()
    await message.answer("✅ Текст второго напоминания обновлен.", reply_markup=keyboards.get_reminder_settings_keyboard())


@router.message(EditReminderSettingsForm.time_2)
async def process_rem_time_2(message: types.Message, state: FSMContext):
    try:
        hours = int(message.text.strip())
        if hours < 1 or hours > 23:
            raise ValueError
    except ValueError:
        await message.answer(
            "Пожалуйста, введите число от 1 до 23.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return

    update_config("reminder_2_hours", hours)
    await state.clear()
    await message.answer(f"✅ Второе напоминание будет отправляться за {hours} ч.", reply_markup=keyboards.get_reminder_settings_keyboard())


@router.callback_query(F.data == "settings_timezone")
async def settings_timezone_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    await callback.answer()
    current_tz = salon_config.get("timezone_offset", 3)
    await state.set_state(EditTimezoneForm.offset)
    await callback.message.edit_text(
        f"🕒 <b>Часовой пояс</b>\n\nТекущее смещение: <b>UTC{'+' if current_tz >= 0 else ''}{current_tz}</b>\nВведите новое смещение в часах:",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.callback_query(F.data == "settings_booking_window")
async def settings_booking_window_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    current_window = salon_config.get("booking_window", 7)
    await state.set_state(AddBookingWindowForm.days)
    await callback.message.edit_text(
        f"🗓 <b>Окно брони</b>\n\nТекущее значение: <b>{current_window}</b> дней.\nВведите новое значение:",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.message(EditTimezoneForm.offset)
async def process_timezone_offset(message: types.Message, state: FSMContext):
    try:
        offset = int(message.text.replace("+", "").strip())
        if not (-12 <= offset <= 14):
            raise ValueError
    except ValueError:
        await message.answer(
            "Пожалуйста, введите число от -12 до 14.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return

    update_config("timezone_offset", offset)
    await state.clear()
    await message.answer(
        f"✅ Часовой пояс сохранен: UTC{'+' if offset >= 0 else ''}{offset}",
        reply_markup=keyboards.get_system_settings_keyboard(),
    )


@router.callback_query(F.data == "settings_currency")
async def settings_currency_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    current_symbol = get_currency_symbol()
    await callback.message.edit_text(
        f"💱 <b>Валюта</b>\n\nТекущий символ: <b>{current_symbol}</b>\nВыберите вариант ниже или введите свой.",
        parse_mode="HTML",
        reply_markup=keyboards.get_currency_keyboard(),
    )


@router.callback_query(F.data == "toggle_service_duration_visibility")
async def toggle_service_duration_visibility_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()

    new_value = not bool(salon_config.get("show_service_duration", True))
    update_config("show_service_duration", new_value)
    status_text = "включено" if new_value else "выключено"
    await callback.message.edit_text(
        f"⚙️ <b>Настройки системы</b>\n\nОтображение длительности услуг {status_text}.",
        parse_mode="HTML",
        reply_markup=keyboards.get_system_settings_keyboard(),
    )


@router.callback_query(F.data.startswith("set_currency_"))
async def set_currency_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    payload = callback.data.replace("set_currency_", "", 1)
    if payload == "custom":
        await state.set_state(EditCurrencyForm.symbol)
        await callback.message.edit_text(
            "Введите символ или короткое обозначение валюты.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return

    update_config("currency_symbol", payload)
    await callback.message.edit_text(f"✅ Валюта обновлена: <b>{payload}</b>", parse_mode="HTML", reply_markup=keyboards.get_system_settings_keyboard())


@router.message(EditCurrencyForm.symbol)
async def process_currency_symbol(message: types.Message, state: FSMContext):
    symbol = (message.text or "").strip()
    if not symbol or len(symbol) > 8:
        await message.answer(
            "Введите короткий символ валюты до 8 символов.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return
    update_config("currency_symbol", symbol)
    await state.clear()
    await message.answer(f"✅ Валюта обновлена: <b>{symbol}</b>", parse_mode="HTML", reply_markup=keyboards.get_system_settings_keyboard())


@router.message(F.text == "🗓 График")
async def manage_schedule_handler(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    await message.answer(
        "🗓 <b>График работы</b>\n\nВыберите рабочие дни и управляйте блокировками.",
        parse_mode="HTML",
        reply_markup=_schedule_markup(),
    )


@router.callback_query(F.data == "back_to_schedule")
async def back_to_schedule_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🗓 <b>График работы</b>\n\nВыберите рабочие дни и управляйте блокировками.",
        parse_mode="HTML",
        reply_markup=_schedule_markup(),
    )


@router.callback_query(F.data.startswith("toggle_day_"))
async def toggle_day_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    day_idx = int(callback.data.split("_")[2])
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    if day_idx in working_days:
        working_days.remove(day_idx)
    else:
        working_days.append(day_idx)
        working_days.sort()

    update_config("working_days", working_days)
    await callback.message.edit_reply_markup(reply_markup=_schedule_markup())
    await callback.answer()


@router.callback_query(F.data == "add_blacklist_date")
async def add_blacklist_date_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AddBlacklistDateForm.date)
    await callback.message.answer("Введите выходной день в формате <code>ДД.ММ.ГГГГ</code>.", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.message(AddBlacklistDateForm.date)
async def process_blacklist_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
        await message.answer("Неверный формат. Используйте <code>ДД.ММ.ГГГГ</code>.", parse_mode="HTML")
        return

    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    if date_str not in blacklisted_dates:
        blacklisted_dates.append(date_str)
        update_config("blacklisted_dates", blacklisted_dates)

    await state.clear()
    await message.answer(f"✅ Дата <b>{date_str}</b> добавлена в выходные.", parse_mode="HTML", reply_markup=_schedule_markup())


@router.callback_query(F.data.startswith("del_bl_"))
async def del_blacklist_date_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return

    date_str = callback.data.split("del_bl_")[1]
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    if date_str in blacklisted_dates:
        blacklisted_dates.remove(date_str)
        update_config("blacklisted_dates", blacklisted_dates)

    await callback.message.edit_reply_markup(reply_markup=_schedule_markup())
    await callback.answer()


@router.callback_query(F.data == "manage_breaks")
async def manage_breaks_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.clear()
    blocked_slots = await database.get_blocked_slots()
    await callback.message.edit_text(
        _breaks_menu_text(blocked_slots),
        parse_mode="HTML",
        reply_markup=_breaks_menu_markup(blocked_slots),
    )


@router.callback_query(F.data == "configure_lunch_break")
async def configure_lunch_break_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.clear()
    await state.set_state(ConfigureLunchBreakForm.start_time)
    lunch_enabled = bool(salon_config.get("lunch_break_enabled", False))
    lunch_start = str(salon_config.get("lunch_break_start", "") or "").strip()
    lunch_end = str(salon_config.get("lunch_break_end", "") or "").strip()
    current_lunch = f"{lunch_start}-{lunch_end}" if lunch_enabled and lunch_start and lunch_end else "не настроен"
    await callback.message.edit_text(
        "🍽 <b>Обед</b>\n\n"
        "Обед действует на все рабочие даты, включая будущие даты после текущего окна бронирования.\n"
        f"Сейчас: <b>{current_lunch}</b>\n\n"
        "Сначала выберите время начала.",
        parse_mode="HTML",
        reply_markup=keyboards.get_break_time_keyboard(
            _build_break_start_options("lunch_start"),
            back_callback="manage_breaks",
            disable_callback="disable_lunch_break" if lunch_enabled else None,
        ),
    )


@router.callback_query(F.data == "disable_lunch_break")
async def disable_lunch_break_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer("Обед выключен")
    await state.clear()
    update_config("lunch_break_enabled", False)
    blocked_slots = await database.get_blocked_slots()
    await callback.message.edit_text(
        _breaks_menu_text(blocked_slots),
        parse_mode="HTML",
        reply_markup=_breaks_menu_markup(blocked_slots),
    )


@router.callback_query(F.data.startswith("lunch_start_"))
async def lunch_break_start_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    start_time = callback.data.removeprefix("lunch_start_")
    await callback.answer()
    await state.update_data(start_time=start_time)
    await state.set_state(ConfigureLunchBreakForm.end_time)
    await callback.message.edit_text(
        "🍽 <b>Обед</b>\n\nВыберите время окончания. Перерыв будет применяться на все рабочие даты.",
        parse_mode="HTML",
        reply_markup=keyboards.get_break_time_keyboard(
            _build_break_end_options("lunch_end", start_time),
            back_callback="configure_lunch_break",
            disable_callback="disable_lunch_break" if bool(salon_config.get("lunch_break_enabled", False)) else None,
        ),
    )


@router.callback_query(F.data.startswith("lunch_end_"))
async def lunch_break_end_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    end_time = callback.data.removeprefix("lunch_end_")
    data = await state.get_data()
    start_time = data.get("start_time")
    if not start_time or end_time <= start_time:
        await callback.answer("Неверный интервал", show_alert=True)
        return

    update_config("lunch_break_start", start_time)
    update_config("lunch_break_end", end_time)
    update_config("lunch_break_enabled", True)
    await state.clear()
    await callback.answer("Обед сохранен")
    blocked_slots = await database.get_blocked_slots()
    await callback.message.edit_text(
        _breaks_menu_text(blocked_slots),
        parse_mode="HTML",
        reply_markup=_breaks_menu_markup(blocked_slots),
    )


@router.callback_query(F.data == "start_single_break")
async def start_single_break_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.clear()
    date_options = _build_single_break_date_options()
    if not date_options:
        await callback.message.edit_text(
            "🗓 <b>Отдельный перерыв</b>\n\nВ текущем окне записи нет рабочих дат для настройки разового перерыва.",
            parse_mode="HTML",
            reply_markup=keyboards.get_break_dates_keyboard([], back_callback="manage_breaks"),
        )
        return
    await state.set_state(ConfigureSingleBreakForm.date)
    await callback.message.edit_text(
        "🗓 <b>Отдельный перерыв</b>\n\nЭтот перерыв действует только на одну дату. Выберите дату.",
        parse_mode="HTML",
        reply_markup=keyboards.get_break_dates_keyboard(date_options, back_callback="manage_breaks"),
    )


@router.callback_query(F.data.startswith("single_break_date_"))
async def single_break_date_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    date_str = callback.data.removeprefix("single_break_date_")
    await callback.answer()
    await state.update_data(date=date_str)
    await state.set_state(ConfigureSingleBreakForm.start_time)
    await callback.message.edit_text(
        f"🗓 <b>Отдельный перерыв</b>\n\nДата: <b>{date_str}</b>\nВыберите время начала.",
        parse_mode="HTML",
        reply_markup=keyboards.get_break_time_keyboard(
            _build_break_start_options("single_break_start"),
            back_callback="start_single_break",
        ),
    )


@router.callback_query(F.data.startswith("single_break_start_"))
async def single_break_start_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    start_time = callback.data.removeprefix("single_break_start_")
    await callback.answer()
    await state.update_data(start_time=start_time)
    await state.set_state(ConfigureSingleBreakForm.end_time)
    data = await state.get_data()
    await callback.message.edit_text(
        f"🗓 <b>Отдельный перерыв</b>\n\nДата: <b>{data.get('date')}</b>\nНачало: <b>{start_time}</b>\nВыберите время окончания.",
        parse_mode="HTML",
        reply_markup=keyboards.get_break_time_keyboard(
            _build_break_end_options("single_break_end", start_time),
            back_callback="start_single_break",
        ),
    )


@router.callback_query(F.data.startswith("single_break_end_"))
async def single_break_end_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    end_time = callback.data.removeprefix("single_break_end_")
    data = await state.get_data()
    start_time = data.get("start_time")
    date_str = data.get("date")
    if not start_time or not date_str or end_time <= start_time:
        await callback.answer("Неверный интервал", show_alert=True)
        return

    await database.add_blocked_slot(
        date=date_str,
        start_time=start_time,
        end_time=end_time,
        reason="Перерыв",
    )
    await state.clear()
    await callback.answer("Перерыв сохранен")
    blocked_slots = await database.get_blocked_slots()
    await callback.message.edit_text(
        _breaks_menu_text(blocked_slots),
        parse_mode="HTML",
        reply_markup=_breaks_menu_markup(blocked_slots),
    )


@router.callback_query(F.data == "manage_blocked_slots")
async def manage_blocked_slots_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    blocked_slots = await database.get_blocked_slots()
    text = "⛔ <b>Блокировки времени</b>\n\nЗдесь можно добавить обед, техническое окно или другое ограничение."
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.get_blocked_slots_keyboard(blocked_slots))


@router.callback_query(F.data == "add_blocked_slot")
async def add_blocked_slot_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AddBlockedSlotForm.date)
    await callback.message.answer("Введите дату блокировки в формате <code>ДД.ММ.ГГГГ</code>.", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.message(AddBlockedSlotForm.date)
async def process_blocked_slot_date(message: types.Message, state: FSMContext):
    value = message.text.strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", value):
        await message.answer(
            "Неверный формат даты. Используйте <code>ДД.ММ.ГГГГ</code>.",
            parse_mode="HTML",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_schedule", "◀️ К графику"),
        )
        return
    await state.update_data(date=value)
    await state.set_state(AddBlockedSlotForm.start_time)
    await message.answer("Введите время <b>начала</b> в формате <code>ЧЧ:ММ</code>.", parse_mode="HTML")


@router.message(AddBlockedSlotForm.start_time)
async def process_blocked_slot_start(message: types.Message, state: FSMContext):
    value = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", value):
        await message.answer(
            "Неверный формат времени. Используйте <code>ЧЧ:ММ</code>.",
            parse_mode="HTML",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_schedule", "◀️ К графику"),
        )
        return
    await state.update_data(start_time=value)
    await state.set_state(AddBlockedSlotForm.end_time)
    await message.answer("Введите время <b>окончания</b> в формате <code>ЧЧ:ММ</code>.", parse_mode="HTML")


@router.message(AddBlockedSlotForm.end_time)
async def process_blocked_slot_end(message: types.Message, state: FSMContext):
    value = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", value):
        await message.answer(
            "Неверный формат времени. Используйте <code>ЧЧ:ММ</code>.",
            parse_mode="HTML",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_schedule", "◀️ К графику"),
        )
        return
    data = await state.get_data()
    start_time = data["start_time"]
    try:
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(value, "%H:%M")
        if end_dt <= start_dt:
            raise ValueError
    except ValueError:
        await message.answer(
            "Время окончания должно быть позже времени начала.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_schedule", "◀️ К графику"),
        )
        return
    await state.update_data(end_time=value)
    await state.set_state(AddBlockedSlotForm.reason)
    await message.answer("Введите причину блокировки или отправьте <code>-</code>, если без причины.", parse_mode="HTML")


@router.message(AddBlockedSlotForm.reason)
async def process_blocked_slot_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reason = None if message.text.strip() == "-" else message.text.strip()
    await database.add_blocked_slot(
        date=data["date"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        reason=reason,
    )
    await state.clear()
    blocked_slots = await database.get_blocked_slots()
    await message.answer(
        f"✅ Блокировка добавлена: <b>{data['date']}</b> {data['start_time']}-{data['end_time']}",
        parse_mode="HTML",
        reply_markup=keyboards.get_blocked_slots_keyboard(blocked_slots),
    )


@router.callback_query(F.data.startswith("del_block_"))
async def delete_blocked_slot_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    blocked_slot_id = int(callback.data.split("_")[2])
    await database.delete_blocked_slot(blocked_slot_id)
    blocked_slots = await database.get_blocked_slots()
    await callback.message.edit_text(
        _breaks_menu_text(blocked_slots),
        parse_mode="HTML",
        reply_markup=_breaks_menu_markup(blocked_slots),
    )
    await callback.answer()
    return
    await callback.message.edit_reply_markup(reply_markup=keyboards.get_blocked_slots_keyboard(blocked_slots))
    await callback.answer()


@router.message(F.text == "🗓 Окно брони")
async def edit_booking_window_handler(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    current_window = salon_config.get("booking_window", 7)
    await state.set_state(AddBookingWindowForm.days)
    await message.answer(
        f"🗓 <b>Окно брони</b>\n\nТекущее значение: <b>{current_window}</b> дней.\nВведите новое значение:",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.message(AddBookingWindowForm.days)
async def process_booking_window(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
        if days < 1 or days > 365:
            raise ValueError
    except ValueError:
        await message.answer(
            "Пожалуйста, введите число от 1 до 365.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return
    update_config("booking_window", days)
    await state.clear()
    await message.answer(f"✅ Окно бронирования изменено на {days} дней.", reply_markup=keyboards.get_system_settings_keyboard())


@router.callback_query(F.data == "settings_working_hours")
async def settings_working_hours_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    current_wh = salon_config.get("working_hours", "10:00-20:00")
    await state.set_state(WorkingHoursForm.hours)
    await callback.message.edit_text(
        f"🕘 <b>Часы работы</b>\n\nТекущее значение: <b>{current_wh}</b>\nВведите новое в формате <code>ЧЧ:ММ-ЧЧ:ММ</code>.",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.message(WorkingHoursForm.hours)
async def process_working_hours(message: types.Message, state: FSMContext):
    wh = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", wh):
        await message.answer(
            "Неверный формат. Используйте <code>ЧЧ:ММ-ЧЧ:ММ</code>.",
            parse_mode="HTML",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return

    conflicting_bookings = await database.get_future_bookings_outside_working_hours(wh)
    if conflicting_bookings:
        preview_lines = [
            f"• {item['date']} {item['time']} — {item['name']}"
            for item in conflicting_bookings[:5]
        ]
        suffix = "\n• ..." if len(conflicting_bookings) > 5 else ""
        await message.answer(
            "Нельзя сохранить новый график: есть активные записи вне этих часов.\n\n"
            "Попросите клиента перенести запись самостоятельно или отмените её вручную, а затем попробуйте снова:\n"
            f"{chr(10).join(preview_lines)}{suffix}",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return

    update_config("working_hours", wh)
    await state.clear()
    await message.answer(f"✅ Часы работы изменены на {wh}.", reply_markup=keyboards.get_system_settings_keyboard())


@router.callback_query(F.data == "settings_interval")
async def settings_interval_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    current_interval = salon_config.get("schedule_interval", 30)
    await state.set_state(ScheduleIntervalForm.interval)
    await callback.message.edit_text(
        f"⏱ <b>Шаг записи</b>\n\nТекущий интервал: <b>{current_interval}</b> мин.\nВведите новое значение в минутах:",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.message(ScheduleIntervalForm.interval)
async def process_schedule_interval(message: types.Message, state: FSMContext):
    try:
        val = int(message.text.strip())
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "Пожалуйста, введите положительное число минут.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return

    update_config("schedule_interval", val)
    await state.clear()
    await message.answer(f"✅ Шаг записи изменен на {val} мин.", reply_markup=keyboards.get_system_settings_keyboard())
