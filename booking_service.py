from os import getenv

from aiogram import types

import database
import keyboards


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
    master_id: int | None,
    is_admin: bool,
    is_master: bool,
) -> None:
    full_name_service = f"{name} ({service})" if name else f"{message.from_user.full_name} ({service})"

    await database.add_booking(
        user_id=message.from_user.id,
        name=full_name_service,
        phone=phone,
        date=date,
        time=time,
        master_id=master_id,
        duration=duration,
        service_name=service,
        price=price,
    )

    remove_msg = await message.answer("⏳ Загрузка...", reply_markup=types.ReplyKeyboardRemove())
    await remove_msg.delete()

    await message.answer(
        f"✅ Запись подтверждена!\n\nУслуга: {service}\n📅 Дата: {date}\n⏰ Время: {time}\n📞 Телефон: {phone}\n\nЖдем вас!",
        reply_markup=keyboards.get_main_menu(is_admin=is_admin, is_master=is_master),
    )

    msg_text = f"🔔 НОВАЯ ЗАПИСЬ!\n\n👤 Клиент: {full_name_service}\n📞 Тел: {phone}\n📅 Дата: {date}\n⏰ Время: {time}"
    admin_id = getenv("ADMIN_ID")
    if admin_id:
        try:
            await message.bot.send_message(admin_id, msg_text)
        except Exception:
            pass

    if master_id:
        try:
            master = await database.get_master_by_id(master_id)
            if master and master.get("telegram_id"):
                await message.bot.send_message(master["telegram_id"], msg_text)
        except Exception:
            pass


def format_user_booking_text(name: str, phone: str, date: str, time: str) -> str:
    text = "🗓 <b>Ваша запись:</b>\n\n"
    text += f"👤 <b>Имя/Услуга:</b> {name}\n"
    text += f"📅 <b>Дата:</b> {date}\n"
    text += f"⏰ <b>Время:</b> {time}\n"
    text += f"📞 <b>Телефон:</b> {phone}\n"
    return text


async def cancel_booking_and_notify(callback: types.CallbackQuery, *, booking_id: int, name: str, phone: str, date: str, time: str, master_id: int | None) -> None:
    await database.delete_booking_by_id(booking_id)
    await callback.message.edit_text("✅ Ваша запись успешно отменена.")

    msg_text = f"⚠️ ОТМЕНА ЗАПИСИ\n\nКлиент: {name}\nДата: {date}\nВремя: {time}\nТелефон: {phone}"
    admin_id = getenv("ADMIN_ID")
    if admin_id:
        try:
            await callback.bot.send_message(admin_id, msg_text)
        except Exception:
            pass

    if master_id:
        try:
            master = await database.get_master_by_id(master_id)
            if master and master.get("telegram_id"):
                await callback.bot.send_message(master["telegram_id"], msg_text)
        except Exception:
            pass
