from __future__ import annotations

import re

from money import get_currency_symbol

from .base import F, FSMContext, Router, database, datetime, getenv, keyboards, salon_config, update_config, types
from .states import (
    AddBlacklistDateForm,
    AddBlockedSlotForm,
    AddBookingWindowForm,
    EditCurrencyForm,
    EditReminderSettingsForm,
    EditTimezoneForm,
    ScheduleIntervalForm,
    WorkingHoursForm,
)

router = Router()


def _is_admin(user_id: int) -> bool:
    admin_id = getenv("ADMIN_ID")
    return bool(admin_id and str(user_id) == admin_id)


def _schedule_markup():
    return keyboards.get_working_days_keyboard(
        salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0]),
        salon_config.get("blacklisted_dates", []),
    )


@router.message(F.text == "⚙️ Настройки")
async def system_settings_handler(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    await message.answer("Настройки системы:", reply_markup=keyboards.get_system_settings_keyboard(False))


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("Настройки системы:", reply_markup=keyboards.get_system_settings_keyboard(False))


@router.callback_query(F.data == "settings_reminders")
async def settings_reminders_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    text = (
        "Настройки напоминаний:\n\n"
        "1. Первое уведомление за 24 часа\n"
        "2. Второе уведомление за несколько часов до записи"
    )
    await callback.message.edit_text(text, reply_markup=keyboards.get_reminder_settings_keyboard())


@router.callback_query(F.data == "edit_rem_text_1")
async def edit_rem_text_1_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.text_1)
    await callback.message.answer(
        "Введите новый текст для первого напоминания.",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_rem_text_2")
async def edit_rem_text_2_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.text_2)
    await callback.message.answer(
        "Введите новый текст для второго напоминания.",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )
    await callback.answer()


@router.callback_query(F.data == "edit_rem_time_2")
async def edit_rem_time_2_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.time_2)
    await callback.message.answer(
        "За сколько часов до записи отправлять второе напоминание?",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )
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

    current_tz = salon_config.get("timezone_offset", 3)
    await state.set_state(EditTimezoneForm.offset)
    await callback.message.edit_text(
        f"Текущее смещение: UTC{'+' if current_tz >= 0 else ''}{current_tz}\nВведите новое смещение в часах:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.message(EditTimezoneForm.offset)
async def process_timezone_offset(message: types.Message, state: FSMContext):
    try:
        offset = int(message.text.replace("+", "").strip())
        if not (-12 <= offset <= 14):
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите число от -12 до 14.")
        return

    update_config("timezone_offset", offset)
    await state.clear()
    await message.answer(
        f"✅ Часовой пояс сохранен: UTC{'+' if offset >= 0 else ''}{offset}",
        reply_markup=keyboards.get_system_settings_keyboard(False),
    )


@router.callback_query(F.data == "settings_currency")
async def settings_currency_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    current_symbol = get_currency_symbol()
    await callback.message.edit_text(
        f"Текущая валюта: {current_symbol}\nВыберите символ или введите свой.",
        reply_markup=keyboards.get_currency_keyboard(),
    )


@router.callback_query(F.data.startswith("set_currency_"))
async def set_currency_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    payload = callback.data.replace("set_currency_", "", 1)
    if payload == "custom":
        await state.set_state(EditCurrencyForm.symbol)
        await callback.message.edit_text(
            "Введите символ или короткое обозначение валюты.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return

    update_config("currency_symbol", payload)
    await callback.message.edit_text(
        f"✅ Валюта обновлена: {payload}",
        reply_markup=keyboards.get_system_settings_keyboard(False),
    )


@router.message(EditCurrencyForm.symbol)
async def process_currency_symbol(message: types.Message, state: FSMContext):
    symbol = (message.text or "").strip()
    if not symbol or len(symbol) > 8:
        await message.answer("Введите короткий символ валюты до 8 символов.")
        return
    update_config("currency_symbol", symbol)
    await state.clear()
    await message.answer(f"✅ Валюта обновлена: {symbol}", reply_markup=keyboards.get_system_settings_keyboard(False))


@router.message(F.text == "🗓 График")
async def manage_schedule_handler(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    await message.answer(
        "Настройка графика работы:\nВыберите рабочие дни и управляйте блокировками.",
        reply_markup=_schedule_markup(),
    )


@router.callback_query(F.data == "back_to_schedule")
async def back_to_schedule_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        "Настройка графика работы:\nВыберите рабочие дни и управляйте блокировками.",
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


@router.callback_query(F.data == "add_blacklist_date")
async def add_blacklist_date_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AddBlacklistDateForm.date)
    await callback.message.answer(
        "Введите дату выходного в формате ДД.ММ.ГГГГ:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_schedule", "◀️ К графику"),
    )
    await callback.answer()


@router.message(AddBlacklistDateForm.date)
async def process_blacklist_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
        await message.answer("Неверный формат. Используйте ДД.ММ.ГГГГ.")
        return

    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    if date_str not in blacklisted_dates:
        blacklisted_dates.append(date_str)
        update_config("blacklisted_dates", blacklisted_dates)

    await state.clear()
    await message.answer(f"✅ Дата {date_str} добавлена в выходные.", reply_markup=_schedule_markup())


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


@router.callback_query(F.data == "manage_blocked_slots")
async def manage_blocked_slots_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    blocked_slots = await database.get_blocked_slots()
    text = "Блокировки времени:\n\nДобавляйте обед, технические окна и срочные ограничения."
    await callback.message.edit_text(text, reply_markup=keyboards.get_blocked_slots_keyboard(blocked_slots))


@router.callback_query(F.data == "add_blocked_slot")
async def add_blocked_slot_callback(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AddBlockedSlotForm.date)
    await callback.message.answer(
        "Введите дату блокировки в формате ДД.ММ.ГГГГ:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("manage_blocked_slots", "◀️ К блокировкам"),
    )
    await callback.answer()


@router.message(AddBlockedSlotForm.date)
async def process_blocked_slot_date(message: types.Message, state: FSMContext):
    value = message.text.strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", value):
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ.")
        return
    await state.update_data(date=value)
    await state.set_state(AddBlockedSlotForm.start_time)
    await message.answer("Введите время начала в формате ЧЧ:ММ:")


@router.message(AddBlockedSlotForm.start_time)
async def process_blocked_slot_start(message: types.Message, state: FSMContext):
    value = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", value):
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ.")
        return
    await state.update_data(start_time=value)
    await state.set_state(AddBlockedSlotForm.end_time)
    await message.answer("Введите время окончания в формате ЧЧ:ММ:")


@router.message(AddBlockedSlotForm.end_time)
async def process_blocked_slot_end(message: types.Message, state: FSMContext):
    value = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", value):
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ.")
        return
    data = await state.get_data()
    start_time = data["start_time"]
    try:
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(value, "%H:%M")
        if end_dt <= start_dt:
            raise ValueError
    except ValueError:
        await message.answer("Время окончания должно быть позже времени начала.")
        return
    await state.update_data(end_time=value)
    await state.set_state(AddBlockedSlotForm.reason)
    await message.answer("Введите причину блокировки или отправьте '-' если без причины:")


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
        f"✅ Блокировка добавлена: {data['date']} {data['start_time']}-{data['end_time']}",
        reply_markup=keyboards.get_blocked_slots_keyboard(blocked_slots),
    )


@router.callback_query(F.data.startswith("del_block_"))
async def delete_blocked_slot_callback(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    blocked_slot_id = int(callback.data.split("_")[2])
    await database.delete_blocked_slot(blocked_slot_id)
    blocked_slots = await database.get_blocked_slots()
    await callback.message.edit_reply_markup(reply_markup=keyboards.get_blocked_slots_keyboard(blocked_slots))


@router.message(F.text == "🗓 Окно брони")
async def edit_booking_window_handler(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    current_window = salon_config.get("booking_window", 7)
    await state.set_state(AddBookingWindowForm.days)
    await message.answer(
        f"Текущее окно бронирования: {current_window} дней.\nВведите новое значение:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.message(AddBookingWindowForm.days)
async def process_booking_window(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
        if days < 1 or days > 365:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число от 1 до 365.")
        return
    update_config("booking_window", days)
    await state.clear()
    await message.answer(f"✅ Окно бронирования изменено на {days} дней.", reply_markup=keyboards.get_system_settings_keyboard(False))


@router.callback_query(F.data == "settings_working_hours")
async def settings_working_hours_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    current_wh = salon_config.get("working_hours", "10:00-20:00")
    await state.set_state(WorkingHoursForm.hours)
    await callback.message.edit_text(
        f"Текущие часы работы: {current_wh}\nВведите новые часы в формате ЧЧ:ММ-ЧЧ:ММ:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.message(WorkingHoursForm.hours)
async def process_working_hours(message: types.Message, state: FSMContext):
    wh = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", wh):
        await message.answer(
            "Неверный формат. Используйте ЧЧ:ММ-ЧЧ:ММ.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
        )
        return
    update_config("working_hours", wh)
    await state.clear()
    await message.answer(f"✅ Часы работы изменены на {wh}.", reply_markup=keyboards.get_system_settings_keyboard(False))


@router.callback_query(F.data == "settings_interval")
async def settings_interval_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    current_interval = salon_config.get("schedule_interval", 30)
    await state.set_state(ScheduleIntervalForm.interval)
    await callback.message.edit_text(
        f"Текущий шаг записи: {current_interval} мин.\nВведите новый интервал в минутах:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("back_to_settings", "◀️ В настройки"),
    )


@router.message(ScheduleIntervalForm.interval)
async def process_schedule_interval(message: types.Message, state: FSMContext):
    try:
        val = int(message.text.strip())
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число минут.")
        return

    update_config("schedule_interval", val)
    await state.clear()
    await message.answer(f"✅ Шаг записи изменен на {val} мин.", reply_markup=keyboards.get_system_settings_keyboard(False))
