from __future__ import annotations

import re

from .base import F, Router, FSMContext, datetime, getenv, json, keyboards, salon_config, update_config, types
from .states import AddBlacklistDateForm, AddBookingWindowForm, EditReminderSettingsForm, EditTimezoneForm, ScheduleIntervalForm, WorkingHoursForm

router = Router()


@router.message(F.text == "⚙️ Настройки")
async def system_settings_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    await message.answer("Настройки системы:", reply_markup=keyboards.get_system_settings_keyboard(False))


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    await callback.message.edit_text(
        "Настройки системы:",
        reply_markup=keyboards.get_system_settings_keyboard(False),
    )


@router.callback_query(F.data == "settings_reminders")
async def settings_reminders_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    text = "Настройки напоминаний:\n\n1. За 24 часа\n2. Второе уведомление (по умолчанию за 3 часа)"
    await callback.message.edit_text(text, reply_markup=keyboards.get_reminder_settings_keyboard())


@router.callback_query(F.data == "edit_rem_text_1")
async def edit_rem_text_1_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.text_1)
    msg = (
        "Введите новый текст для <b>первого напоминания (за 24 часа)</b>.\n\n"
        "Доступны переменные:\n"
        "• <code>{name}</code> — Имя клиента\n"
        "• <code>{master}</code> — Имя мастера\n"
        "• <code>{date}</code> — Дата\n"
        "• <code>{time}</code> — Время\n\n"
        "<i>Здравствуйте, {name}! Ждём вас завтра на запись {date} в {time}.</i>\n\n"
        "Введите ваш текст:"
    )
    await callback.message.answer(msg, parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.callback_query(F.data == "edit_rem_text_2")
async def edit_rem_text_2_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.text_2)
    msg = (
        "Введите новый текст для <b>второго напоминания</b>.\n\n"
        "Доступны переменные:\n"
        "<code>{name}</code>, <code>{master}</code>, <code>{date}</code>, <code>{time}</code>\n\n"
        "<b>Пример:</b>\n"
        "<i>{name}, напоминаем, что ваша запись уже сегодня ({date}) в {time}.</i>\n\n"
        "Введите ваш текст:"
    )
    await callback.message.answer(msg, parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.callback_query(F.data == "edit_rem_time_2")
async def edit_rem_time_2_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.time_2)
    await callback.message.answer(
        "За сколько <b>часов</b> до сеанса отправлять второе напоминание?\n"
        "Отправьте только число (например: <code>1</code>, <code>2</code> или <code>3</code>):",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard(),
    )
    await callback.answer()


@router.message(EditReminderSettingsForm.text_1)
async def process_rem_text_1(message: types.Message, state: FSMContext):
    update_config("reminder_1_text", message.text)
    await state.clear()
    await message.answer("✅ Текст первого напоминания успешно обновлен.")


@router.message(EditReminderSettingsForm.text_2)
async def process_rem_text_2(message: types.Message, state: FSMContext):
    update_config("reminder_2_text", message.text)
    await state.clear()
    await message.answer("✅ Текст второго напоминания успешно обновлен.")


@router.message(EditReminderSettingsForm.time_2)
async def process_rem_time_2(message: types.Message, state: FSMContext):
    try:
        hours = int(message.text.strip())
        if hours < 1 or hours > 23:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число часов от 1 до 23:", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return

    update_config("reminder_2_hours", hours)
    await state.clear()
    await message.answer(f"✅ Время второго напоминания успешно изменено на {hours} ч.")


@router.callback_query(F.data == "settings_timezone")
async def settings_timezone_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    current_tz = salon_config.get("timezone_offset", 3)
    text = (
        f"🌌 Настройка часового пояса\n\n"
        f"Текущее смещение: UTC{'+' if current_tz >= 0 else ''}{current_tz}\n\n"
        "Введите новое смещение в часах:"
    )
    await state.set_state(EditTimezoneForm.offset)
    await callback.message.edit_text(text, reply_markup=keyboards.get_cancel_admin_action_keyboard())


@router.message(EditTimezoneForm.offset)
async def process_timezone_offset(message: types.Message, state: FSMContext):
    try:
        offset = int(message.text.replace("+", "").strip())
        if not (-12 <= offset <= 14):
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число от -12 до 14.")
        return

    update_config("timezone_offset", offset)
    await state.clear()
    await message.answer(
        f"✅ Часовой пояс успешно сохранен: UTC{'+' if offset >= 0 else ''}{offset}",
        reply_markup=keyboards.get_system_settings_keyboard(False),
    )


@router.message(F.text == "🗓 График")
async def manage_schedule_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    await message.answer(
        "Настройка графика работы:\nВыберите рабочие дни недели и управляйте выходными датами.",
        reply_markup=keyboards.get_working_days_keyboard(working_days, blacklisted_dates),
    )


@router.callback_query(F.data.startswith("toggle_day_"))
async def toggle_day_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    day_idx = int(callback.data.split("_")[2])
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    if day_idx in working_days:
        working_days.remove(day_idx)
    else:
        working_days.append(day_idx)
        working_days.sort()

    update_config("working_days", working_days)
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    await callback.message.edit_reply_markup(reply_markup=keyboards.get_working_days_keyboard(working_days, blacklisted_dates))


@router.callback_query(F.data == "add_blacklist_date")
async def add_blacklist_date_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    await state.set_state(AddBlacklistDateForm.date)
    await callback.message.answer(
        "Введите дату выходного в формате ДД.ММ.ГГГГ:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard(),
    )
    await callback.answer()


@router.message(AddBlacklistDateForm.date)
async def process_blacklist_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
        await message.answer("Неверный формат. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
        return

    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    if date_str not in blacklisted_dates:
        blacklisted_dates.append(date_str)
        update_config("blacklisted_dates", blacklisted_dates)

    await state.clear()
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    await message.answer(
        f"✅ Дата {date_str} добавлена в список выходных.",
        reply_markup=keyboards.get_working_days_keyboard(working_days, blacklisted_dates),
    )


@router.callback_query(F.data.startswith("del_bl_"))
async def del_blacklist_date_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    date_str = callback.data.split("del_bl_")[1]
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    if date_str in blacklisted_dates:
        blacklisted_dates.remove(date_str)
        update_config("blacklisted_dates", blacklisted_dates)

    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    await callback.message.edit_reply_markup(reply_markup=keyboards.get_working_days_keyboard(working_days, blacklisted_dates))


@router.message(F.text == "🗓 Окно брони")
async def edit_booking_window_handler(message: types.Message, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    current_window = salon_config.get("booking_window", 7)
    await state.set_state(AddBookingWindowForm.days)
    await message.answer(
        f"Текущее окно бронирования: {current_window} дн.\nВведите новое количество дней:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard(),
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
    await message.answer(f"✅ Окно бронирования успешно изменено на {days} дн.")


@router.callback_query(F.data == "settings_working_hours")
async def settings_working_hours_cb(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    current_wh = salon_config.get("working_hours", "10:00-20:00")
    await state.set_state(WorkingHoursForm.hours)
    await callback.message.edit_text(
        f"Текущие рабочие часы: {current_wh}\nВведите новые рабочие часы в формате ЧЧ:ММ-ЧЧ:ММ:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard(),
    )


@router.message(WorkingHoursForm.hours)
async def process_working_hours(message: types.Message, state: FSMContext):
    wh = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", wh):
        await message.answer("Неверный формат. Пожалуйста, введите в формате ЧЧ:ММ-ЧЧ:ММ.", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return

    update_config("working_hours", wh)
    await state.clear()
    await message.answer(f"✅ Рабочие часы успешно изменены на {wh}.")


@router.callback_query(F.data == "settings_interval")
async def settings_interval_cb(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    current_interval = salon_config.get("schedule_interval", 30)
    await state.set_state(ScheduleIntervalForm.interval)
    await callback.message.edit_text(
        f"Текущий шаг записи: {current_interval} мин.\nВведите новый интервал в минутах:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard(),
    )


@router.message(ScheduleIntervalForm.interval)
async def process_schedule_interval(message: types.Message, state: FSMContext):
    try:
        val = int(message.text.strip())
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число в минутах.", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return

    update_config("schedule_interval", val)
    await state.clear()
    await message.answer(f"✅ Шаг записи изменен на {val} мин.")
