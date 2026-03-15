from __future__ import annotations

import os
from datetime import datetime

from .base import (
    Command,
    F,
    FSInputFile,
    Router,
    database,
    escape,
    getenv,
    keyboards,
    pd,
    salon_config,
    types,
)

router = Router()


async def send_client_home(
    message: types.Message,
    *,
    text: str,
    is_admin: bool,
    is_master: bool,
) -> None:
    await message.answer(text, reply_markup=keyboards.get_booking_launch_keyboard())
    await message.answer(
        "Меню клиента обновлено.",
        reply_markup=keyboards.get_main_menu(is_admin=is_admin, is_master=is_master),
    )


@router.message(Command("start"))
async def start_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(message.from_user.id) == admin_id)

    if is_admin:
        await message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)
        return

    await send_client_home(
        message,
        text=salon_config.get("welcome_text", "Привет! Выберите нужное действие:"),
        is_admin=is_admin,
        is_master=False,
    )


@router.message(F.text == "👤 Главное меню")
@router.message(F.text == "👤 Меню клиента")
async def client_menu_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(message.from_user.id) == admin_id)

    if not is_admin:
        return

    await send_client_home(
        message,
        text="Вы переключились в главное меню клиента.",
        is_admin=is_admin,
        is_master=False,
    )


@router.message(Command("admin"))
@router.message(F.text == "⚙️ Панель управления")
async def admin_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    await message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)


@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu_callback(callback: types.CallbackQuery, state):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)


@router.callback_query(F.data == "cancel_admin_action")
async def cancel_admin_action_callback(callback: types.CallbackQuery, state):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    await state.clear()
    await callback.message.edit_text("Действие отменено.")


@router.message(Command("export_excel"))
@router.message(F.text == "📃 Excel")
async def export_excel_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    bookings = await database.get_all_bookings()
    if not bookings:
        await message.answer("Пока нет ни одной записи для выгрузки.")
        return

    df = pd.DataFrame(bookings, columns=["Имя", "Телефон", "Дата", "Время", "Мастер"])
    file_path = "bookings_export.xlsx"
    df.to_excel(file_path, index=False)

    excel_file = FSInputFile(file_path)
    await message.answer_document(excel_file, caption="📃 Ваши записи")
    os.remove(file_path)


@router.message(F.text == "🗓 Все записи")
async def view_all_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    bookings = await database.get_all_bookings()
    if not bookings:
        await message.answer("Пока нет ни одной записи.")
        return

    text = "🗓 <b>Все записи:</b>\n\n"
    for idx, (name, phone, date, time, _master_name) in enumerate(bookings, 1):
        safe_name = escape(name)
        safe_phone = escape(phone)
        safe_date = escape(date)
        safe_time = escape(time)
        text += f"<b>{idx}.</b> {safe_date} в {safe_time} — {safe_name} ({safe_phone})\n"

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🗓 На сегодня")
async def todays_bookings_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    today_str = datetime.now().strftime("%d.%m.%Y")
    bookings = await database.get_bookings_by_date_full(today_str)
    if not bookings:
        await message.answer(f"На сегодня ({today_str}) записей нет.")
        return

    text = f"🗓 <b>Записи на сегодня ({today_str}):</b>\n\n"
    for idx, (name, phone, _date, time, _master_name) in enumerate(bookings, 1):
        safe_name = escape(name)
        safe_phone = escape(phone)
        safe_time = escape(time)
        text += f"<b>{idx}.</b> {safe_time} — {safe_name} ({safe_phone})\n"

    await message.answer(text, parse_mode="HTML")
