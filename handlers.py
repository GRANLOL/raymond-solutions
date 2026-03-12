import pandas as pd
import os
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from datetime import datetime, timedelta
import database
import keyboards
from os import getenv
from config import salon_config, update_config
import json

router = Router()

# Состояния для формы записи
class BookingForm(StatesGroup):
    entering_phone = State()

class ClearBookingsForm(StatesGroup):
    waiting_for_date = State()
    waiting_for_period_start = State()
    waiting_for_period_end = State()

class EditReminderSettingsForm(StatesGroup):
    text_1 = State()
    text_2 = State()
    time_2 = State()

@router.message(Command("start"))
async def start_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(message.from_user.id) == admin_id)
    
    use_masters = salon_config.get("use_masters", False)
    is_master = False
    
    if use_masters:
        master = await database.get_master_by_telegram_id(str(message.from_user.id))
        if master:
            is_master = True
            
    if is_master and not is_admin:
        await message.answer("Добро пожаловать в панель мастера!", reply_markup=keyboards.master_menu)
        return
    
    if is_admin:
        await message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)
    else:
        await message.answer(
            salon_config.get("welcome_text", "Привет! Выберите нужное действие:"),
            reply_markup=keyboards.get_main_menu(is_admin=is_admin, is_master=is_master)
        )

@router.message(F.text == "👤 Главное меню")
@router.message(F.text == "👤 Меню клиента")
async def client_menu_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(message.from_user.id) == admin_id)
    
    use_masters = salon_config.get("use_masters", False)
    is_master = False
    if use_masters:
        master = await database.get_master_by_telegram_id(str(message.from_user.id))
        is_master = bool(master)
        
    if not is_admin and not is_master:
        return
        
    await message.answer(
        "Вы переключились в главное меню клиента.",
        reply_markup=keyboards.get_main_menu(is_admin=is_admin, is_master=is_master)
    )

@router.message(Command("admin"))
@router.message(F.text == "⚙️ Панель управления")
async def admin_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return # Игнорим всех, кроме админа
        
    await message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)

@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await state.clear()
    
    # Safely delete if possible, otherwise answer
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)

@router.callback_query(F.data == "cancel_admin_action")
async def cancel_admin_action_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await state.clear()
    await callback.message.edit_text("Действие отменено.")

@router.message(Command("export_excel"))
@router.message(F.text == "📁 Excel")
async def export_excel_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
        
    bookings = await database.get_all_bookings()
    
    if not bookings:
        await message.answer("Пока нет ни одной записи для выгрузки. 🤷‍♀️")
        return
        
    # Преобразуем данные в DataFrame
    df = pd.DataFrame(bookings, columns=["Имя", "Телефон", "Дата", "Время", "Мастер"])
    file_path = "bookings_export.xlsx"
    
    # Сохраняем в Excel
    df.to_excel(file_path, index=False)
    
    # Отправляем файл
    excel_file = FSInputFile(file_path)
    await message.answer_document(excel_file, caption="📁 Ваши записи")
    
    # Удаляем временный файл
    os.remove(file_path)

@router.message(F.text == "🗓 Все записи")
async def view_all_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return # Игнорим всех, кроме админа
        
    bookings = await database.get_all_bookings()
    
    if not bookings:
        await message.answer("Пока нет ни одной записи. 🤷‍♀️")
        return
        
    use_masters = salon_config.get("use_masters", False)
    text = "🗓 <b>Все записи:</b>\n\n"
    for idx, (name, phone, date, time, master_name) in enumerate(bookings, 1):
        master_str = f" [Мастер: {master_name}]" if use_masters and master_name else ""
        text += f"<b>{idx}.</b> {date} в {time} — {name} ({phone}){master_str}\n"
        
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🗓 На сегодня")
async def todays_bookings_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    
    today_str = datetime.now().strftime("%d.%m.%Y")
    bookings = await database.get_bookings_by_date_full(today_str)
    
    if not bookings:
        await message.answer(f"На сегодня ({today_str}) записей нет. 🧘‍♀️")
        return
        
    use_masters = salon_config.get("use_masters", False)
    text = f"🗓 <b>Записи на сегодня ({today_str}):</b>\n\n"
    for idx, (name, phone, date, time, master_name) in enumerate(bookings, 1):
        master_str = f" [Мастер: {master_name}]" if use_masters and master_name else ""
        text += f"<b>{idx}.</b> {time} — {name} ({phone}){master_str}\n"
        
    await message.answer(text, parse_mode="HTML")

@router.message(Command("clear_bookings"))
@router.message(F.text == "🗑 Очистить")
async def clear_bookings_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return # Игнорим всех, кроме админа
        
    use_masters = salon_config.get("use_masters", False)
    await message.answer(
        "Выберите, какие записи вы хотите очистить:",
        reply_markup=keyboards.get_clear_options_keyboard(use_masters)
    )

# --- Обработчики меню очистки ---
@router.callback_query(F.data == "clear_today")
async def clear_today_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    await callback.message.edit_text(
        "Вы уверены, что хотите удалить ВСЕ записи на сегодня?", 
        reply_markup=keyboards.get_confirm_clear_keyboard("today")
    )

@router.callback_query(F.data == "clear_past")
async def clear_past_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    await callback.message.edit_text(
        "Вы уверены, что хотите удалить все прошедшие записи (до сегодняшнего дня)?", 
        reply_markup=keyboards.get_confirm_clear_keyboard("past")
    )

@router.callback_query(F.data == "clear_all")
async def clear_all_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    await callback.message.edit_text(
        "Вы уверены, что хотите удалить АБСОЛЮТНО ВСЕ записи из базы данных?", 
        reply_markup=keyboards.get_confirm_clear_keyboard("all")
    )

@router.callback_query(F.data == "clear_date")
async def clear_date_cb(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    await state.set_state(ClearBookingsForm.waiting_for_date)
    await callback.message.edit_text(
        "Введите дату для очистки в формате ДД.ММ.ГГГГ (например, 25.12.2023):",
        reply_markup=keyboards.get_cancel_admin_action_keyboard()
    )

@router.message(ClearBookingsForm.waiting_for_date)
async def process_clear_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    import re
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
        await message.answer("Неверный формат. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
        return
    await state.clear()
    await message.answer(
        f"Вы уверены, что хотите удалить все записи за {date_str}?",
        reply_markup=keyboards.get_confirm_clear_keyboard("date", date_str)
    )

@router.callback_query(F.data == "clear_period")
async def clear_period_cb(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    await state.set_state(ClearBookingsForm.waiting_for_period_start)
    await callback.message.edit_text(
        "Введите НАЧАЛЬНУЮ дату периода в формате ДД.ММ.ГГГГ:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard()
    )

@router.message(ClearBookingsForm.waiting_for_period_start)
async def process_clear_period_start(message: types.Message, state: FSMContext):
    start_str = message.text.strip()
    import re
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", start_str):
        await message.answer("Неверный формат. Пожалуйста, введите начальную дату в формате ДД.ММ.ГГГГ:")
        return
    await state.update_data(clear_start=start_str)
    await state.set_state(ClearBookingsForm.waiting_for_period_end)
    await message.answer(
        f"Начальная дата: {start_str}\nТеперь введите КОНЕЧНУЮ дату в формате ДД.ММ.ГГГГ:",
        reply_markup=keyboards.get_cancel_admin_action_keyboard()
    )

@router.message(ClearBookingsForm.waiting_for_period_end)
async def process_clear_period_end(message: types.Message, state: FSMContext):
    end_str = message.text.strip()
    import re
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", end_str):
        await message.answer("Неверный формат. Пожалуйста, введите конечную дату в формате ДД.ММ.ГГГГ:")
        return
    data = await state.get_data()
    start_str = data.get("clear_start")
    await state.clear()
    
    payload = f"{start_str}-{end_str}"
    await message.answer(
        f"Вы уверены, что хотите удалить все записи с {start_str} по {end_str}?",
        reply_markup=keyboards.get_confirm_clear_keyboard("period", payload)
    )

@router.callback_query(F.data == "clear_master")
async def clear_master_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    masters = await database.get_all_masters()
    if not masters:
        await callback.message.edit_text("Список мастеров пуст.", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return
    await callback.message.edit_text(
        "Выберите мастера, чьи записи вы хотите удалить:",
        reply_markup=keyboards.get_clear_master_selection_keyboard(masters)
    )

@router.callback_query(F.data.startswith("clear_master_id_"))
async def clear_master_id_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    m_id = callback.data.split("_")[3]
    await callback.message.edit_text(
        f"Вы уверены, что хотите удалить все записи выбранного мастера?",
        reply_markup=keyboards.get_confirm_clear_keyboard("master", m_id)
    )

# --- Обработчики подтверждений удаления ---
@router.callback_query(F.data.startswith("confirm_clear_"))
async def confirm_clear_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    
    parts = callback.data.split("_", 3)
    action = parts[2]
    payload = parts[3] if len(parts) > 3 else ""
    
    deleted = 0
    if action == "today":
        today_str = datetime.now().strftime("%d.%m.%Y")
        deleted = await database.delete_bookings_by_date(today_str)
        text = f"✅ Успешно удалено {deleted} записей за сегодня ({today_str})."
    elif action == "past":
        deleted = await database.delete_past_bookings()
        text = f"✅ Успешно удалено {deleted} старых записей."
    elif action == "all":
        await database.clear_bookings()
        text = "✅ База данных полностью очищена от записей."
    elif action == "date":
        deleted = await database.delete_bookings_by_date(payload)
        text = f"✅ Успешно удалено {deleted} записей за {payload}."
    elif action == "period":
        start_str, end_str = payload.split("-")
        deleted = await database.delete_bookings_by_period(start_str, end_str)
        text = f"✅ Успешно удалено {deleted} записей в периоде с {start_str} по {end_str}."
    elif action == "master":
        m_id = int(payload)
        deleted = await database.delete_bookings_by_master(m_id)
        text = f"✅ Успешно удалено {deleted} записей выбранного мастера."
    else:
        text = "Произошла ошибка, неизвестное действие."
        
    await callback.message.edit_text(text)


def format_price_list_page(services, page: int, page_size: int = 20):
    from collections import defaultdict
    categories = defaultdict(list)
    for s in services:
        cat_name = s.get('category_name') or "Без категории"
        categories[cat_name].append(s)
        
    sorted_cats = sorted(categories.keys())
    
    # Flatten into a list of lines so we can paginate them
    lines = []
    lines.append(f"<b>💰 ПРАЙС-ЛИСТ | {salon_config.get('salon_name', 'Ноготочки')}</b>")
    lines.append("______________________________\n")
    
    for cat in sorted_cats:
        lines.append(f"<b>📁 {cat}</b>")
        for s in categories[cat]:
            lines.append(f"▪️ {s['name']} — {s['price']}₽")
        lines.append("") # Empty line between categories
        
    total_lines = len(lines)
    
    import math
    total_pages = math.ceil(total_lines / page_size) if total_lines else 1
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total_lines)
    
    page_text = "\n".join(lines[start_idx:end_idx])
    if total_pages > 1:
        page_text += f"\n<i>Страница {page + 1} из {total_pages}</i>"
        
    return page_text, total_pages

@router.message(F.text == "💸 Прайс-лист")
async def handle_price(message: types.Message):
    services = await database.get_all_services()
    if not services:
        await message.answer("Прайс-лист пока не заполнен.")
        return
        
    # We will paginate by 25 lines of text
    text, total_pages = format_price_list_page(services, page=0, page_size=25)
    
    await message.answer(
        text, 
        parse_mode="HTML",
        reply_markup=keyboards.get_client_price_keyboard(0, total_pages)
    )

@router.callback_query(F.data.startswith("client_price_page_"))
async def price_page_cb(callback: types.CallbackQuery):
    page_str = callback.data.split("_")[3]
    try:
        page = int(page_str)
    except ValueError:
        return
        
    services = await database.get_all_services()
    if not services:
        await callback.answer("Прайс-лист пуст", show_alert=True)
        return
        
    text, total_pages = format_price_list_page(services, page=page, page_size=25)
    
    await callback.message.edit_text(
        text, 
        parse_mode="HTML",
        reply_markup=keyboards.get_client_price_keyboard(page, total_pages)
    )


@router.message(F.text == "📍 Адрес")
async def handle_address(message: types.Message):
    address = salon_config.get('address', 'Адрес не указан.')
    hours = salon_config.get('working_hours', '')
    map_url = salon_config.get('map_url', '')
    
    text = f"<b>📍 Наш адрес</b>\n\n🏠 {address}\n"
    if hours:
        text += f"⏱ <i>{hours}</i>\n"
    if map_url:
        text += f"\n👉 <a href='{map_url}'>Открыть в картах</a>"
        
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)
@router.message(F.text == "💅 Портфолио")
async def handle_portfolio(message: types.Message):
    caption = "<b>📸 Наши работы</b>\n\n"
    portfolio_url = salon_config.get('portfolio_url', '')
    if portfolio_url:
        caption += f"🔗 <a href='{portfolio_url}'>Перейти в наше портфолио</a>"
    else:
        caption += "Портфолио не указано."
        
    await message.answer(caption, parse_mode="HTML")

@router.message(F.web_app_data)
async def process_web_app_data(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
        service = data.get('service')
        date = data.get('date')
        time = data.get('time')
        duration = data.get('duration', 60)
        phone = data.get('phone')
        name = data.get('name')
        price = int(data.get('price', 0) or 0)
        
        # Extract master_id from web app data
        admin_id = getenv("ADMIN_ID")
        is_admin = bool(admin_id and str(message.from_user.id) == admin_id)
        
        use_masters = salon_config.get("use_masters", False)
        is_master = False
        master_id = None
        
        if use_masters:
            master = await database.get_master_by_telegram_id(str(message.from_user.id))
            is_master = bool(master)
            master_id_raw = data.get("master_id")
            if master_id_raw:
                master_id = int(master_id_raw)
                
        booked_slots = await database.get_booked_slots(date, master_id=master_id)
        if time in booked_slots:
            await message.answer("К сожалению, это время уже занято. Пожалуйста, выберите другое в приложении.")
            return

        if name:
            full_name_service = f"{name} ({service})"
        else:
            full_name_service = f"{message.from_user.full_name} ({service})"
        
        # SAVE BOOKING ONCE
        await database.add_booking(
            user_id=message.from_user.id,
            name=full_name_service,
            phone=phone,
            date=date,
            time=time,
            master_id=master_id,
            duration=duration,
            service_name=service,
            price=price
        )
        
        # ОЧИЩАЕ МЕНЮ ОТ GHOST KEYBOARD И ПОДТВЕРЖДЕНИЕ ПОЛЬЗОВАТЕЛЮ
        # Отправляем сообщение удаляющее пустую клавиатуру WebApp
        remove_msg = await message.answer(
            "⏳ Загрузка...",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # Удаляем его и отправляем финальное с новой клавиатурой
        await remove_msg.delete()

        await message.answer(
            f"✅ Запись подтверждена!\n\nУслуга: {service}\n📅 Дата: {date}\n⏰ Время: {time}\n📞 Телефон: {phone}\n\nЖдем вас!",
            reply_markup=keyboards.get_main_menu(is_admin=is_admin, is_master=is_master)
        )
        
        # NOTIFY ADMIN AND MASTER
        msg_text = f"🔔 НОВАЯ ЗАПИСЬ!\n\n👤 Клиент: {full_name_service}\n📞 Тел: {phone}\n📅 Дата: {date}\n⏰ Время: {time}"
        
        if admin_id:
            try:
                await message.bot.send_message(admin_id, msg_text)
            except Exception:
                pass 
                
        # Notify the selected master (not the current user)
        if master_id:
            try:
                import aiosqlite
                async with aiosqlite.connect("bookings.db") as db:
                    async with db.execute("SELECT telegram_id FROM masters WHERE id = ?", (master_id,)) as cursor:
                        row = await cursor.fetchone()
                        if row and row[0]:
                            await message.bot.send_message(row[0], msg_text)
            except Exception as e:
                print(f"Failed sending to master: {e}")
                
        await state.clear()

    except Exception as e:
        print(f"Error parsing web_app_data: {e}")
        await message.answer("⚠️ Произошла ошибка при обработке данных. Попробуйте еще раз.")

@router.message(F.text == "📋 Мои записи")
async def my_bookings_handler(message: types.Message):
    booking = await database.get_user_booking(message.from_user.id)
    
    if not booking:
        await message.answer("У вас нет активных записей. 🤷‍♀️")
        return
        
    name, phone, date, time, booking_id = booking
    
    text = "🗓 <b>Ваша активная запись:</b>\n\n"
    text += f"👤 <b>Имя/Услуга:</b> {name}\n"
    text += f"📅 <b>Дата:</b> {date}\n"
    text += f"⏰ <b>Время:</b> {time}\n"
    text += f"📞 <b>Телефон:</b> {phone}\n"
    
    await message.answer(text, reply_markup=keyboards.get_cancel_keyboard(message.from_user.id), parse_mode="HTML")

@router.callback_query(F.data.startswith("cancel_"))
async def cancel_booking_callback(callback: types.CallbackQuery):
    user_id_str = callback.data.split("_")[1]
    
    if str(callback.from_user.id) != user_id_str:
        await callback.answer("Это не ваша запись!", show_alert=True)
        return
        
    user_id = int(user_id_str)
    
    # Get booking details before deleting to notify admin and master
    booking = await database.get_user_booking(user_id)
    if not booking:
        await callback.answer("Запись уже отменена или не найдена.", show_alert=True)
        return
        
    # updated get_user_booking must return master_id. We need to go adjust database.py if not.
    # We will assume get_user_booking returns a length of 5.
    name, phone, date, time, booking_id = booking[:5]
    
    # We'll fetch the true active booking from DB directly to get master_id safely without breaking existing structures
    import aiosqlite
    master_id = None
    async with aiosqlite.connect("bookings.db") as db:
        async with db.execute("SELECT master_id FROM bookings WHERE id = ?", (booking_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                master_id = row[0]
                
    await database.cancel_booking(user_id)
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
            # We need to fetch the master telegram ID
            async with aiosqlite.connect("bookings.db") as db:
                async with db.execute("SELECT telegram_id FROM masters WHERE id = ?", (master_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        await callback.bot.send_message(row[0], msg_text)
        except Exception as e:
            print(f"Failed sending cancel to master: {e}")

# --- MASTER PANEL ---
@router.message(F.text == "💼 Панель мастера")
async def master_panel_handler(message: types.Message):
    master = await database.get_master_by_telegram_id(str(message.from_user.id))
    if not master:
        return
    await message.answer("Вы перешли в панель мастера.", reply_markup=keyboards.master_menu)

@router.message(F.text == "📅 Мои записи на сегодня")
async def master_today_bookings_handler(message: types.Message):
    master = await database.get_master_by_telegram_id(str(message.from_user.id))
    if not master:
        return
        
    today = datetime.now().strftime("%d.%m.%Y")
    bookings = await database.get_bookings_by_master_and_date(master['id'], today)
    
    if not bookings:
        await message.answer("🏖 На сегодня у вас нет записей.")
        return
    
    text = "🗓 <b>Ваши записи на сегодня:</b>\n\n"
    for idx, (name, phone, date, time) in enumerate(bookings, 1):
        text += f"<b>{idx}.</b> {time} — {name} ({phone})\n"
        
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🗓 Мои все записи")
async def master_all_bookings_handler(message: types.Message):
    master = await database.get_master_by_telegram_id(str(message.from_user.id))
    if not master:
        return
        
    bookings = await database.get_bookings_by_master(master['id'])
    
    if not bookings:
        await message.answer("У вас пока нет записей. 🤷‍♀️")
        return
    
    text = "🗓 <b>Все ваши записи:</b>\n\n"
    for idx, (name, phone, date, time) in enumerate(bookings, 1):
        text += f"<b>{idx}.</b> {date} в {time} — {name} ({phone})\n"
        
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🔔 Настройка уведомлений")
async def master_notifications_handler(message: types.Message):
    master = await database.get_master_by_telegram_id(str(message.from_user.id))
    if not master:
        return
    await message.answer(
        "🔔 Уведомления о записях активны.\n\nВы будете получать сообщение каждый раз, когда клиент записывается к вам или отменяет запись."
    )


# --- ADMIN PANEL DATABASES Management ---

class EditServiceNameForm(StatesGroup):
    value = State()

class EditServicePriceForm(StatesGroup):
    value = State()

class EditReminderSettingsForm(StatesGroup):
    text_1 = State()
    text_2 = State()
    time_2 = State()

class EditTimezoneForm(StatesGroup):
    offset = State()

class EditServiceDurationForm(StatesGroup):
    value = State()

class AddServiceForm(StatesGroup):
    category_id = State()
    name = State()
    price = State()
    duration = State()

class CategoryWizard(StatesGroup):
    main_name = State()
    sub_name = State()

class WizardAddServiceForm(StatesGroup):
    target_id = State()
    name = State()
    price = State()
    duration = State()

class EditServiceForm(StatesGroup):
    service_id = State()
    name = State()
    price = State()
    category_id = State()

class EditCategoryForm(StatesGroup):
    category_id = State()
    name = State()
    new_parent = State()

class AddSubcategoryExistingForm(StatesGroup):
    parent_id = State()
    name = State()

class AddMasterForm(StatesGroup):
    name = State()
    telegram_id = State()
    category_id = State()

class WorkingHoursForm(StatesGroup):
    hours = State()

class ScheduleIntervalForm(StatesGroup):
    interval = State()

class AddBookingWindowForm(StatesGroup):
    days = State()

class AddBlacklistDateForm(StatesGroup):
    date = State()

@router.message(F.text == "⚙️ Настройки")
async def system_settings_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
        
    use_masters = salon_config.get("use_masters", False)
    await message.answer(
        "Настройки системы:",
        reply_markup=keyboards.get_system_settings_keyboard(use_masters)
    )

@router.callback_query(F.data == "toggle_use_masters")
async def toggle_use_masters_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
        
    use_masters = not salon_config.get("use_masters", False)
    update_config("use_masters", use_masters)
    
    await callback.message.edit_reply_markup(
        reply_markup=keyboards.get_system_settings_keyboard(use_masters)
    )

@router.callback_query(F.data == "back_to_settings")
async def back_to_settings_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    use_masters = salon_config.get("use_masters", False)
    await callback.message.edit_text(
        "Настройки системы:",
        reply_markup=keyboards.get_system_settings_keyboard(use_masters)
    )

# --- Настройки напоминаний ---
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
        "Вы можете использовать следующие <code>переменные</code> (просто вставьте их в текст, и бот заменит их автоматически):\n"
        "• <code>{name}</code> — Имя клиента\n"
        "• <code>{master}</code> — Имя мастера\n"
        "• <code>{date}</code> — Дата (например 15.03.2026)\n"
        "• <code>{time}</code> — Время (например 14:00)\n\n"
        "<b>Пример идеального запроса для копирования:</b>\n"
        "<i>Здравствуйте, {name}! Ждём вас завтра на классный маникюр к мастеру {master}. Ваше время: {date} в {time}!</i>\n\n"
        "Введите ваш текст:"
    )
    await callback.message.answer(msg, parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()
    
@router.callback_query(F.data == "edit_rem_text_2")
async def edit_rem_text_2_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.text_2)
    msg = (
        "Введите новый текст для <b>второго напоминания</b>.\n\n"
        "Все те же переменные доступны:\n"
        "<code>{name}</code>, <code>{master}</code>, <code>{date}</code>, <code>{time}</code>\n\n"
        "<b>Пример:</b>\n"
        "<i>{name}, напоминаем, что ваша запись к {master} уже сегодня ({date}) в {time}! До встречи!</i>\n\n"
        "Введите ваш текст:"
    )
    await callback.message.answer(msg, parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.callback_query(F.data == "edit_rem_time_2")
async def edit_rem_time_2_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditReminderSettingsForm.time_2)
    await callback.message.answer("За сколько <b>часов</b> до сеанса отправлять второе напоминание?\nОтправьте только число (например: <code>1</code>, <code>2</code> или <code>3</code>):", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(EditReminderSettingsForm.text_1)
async def process_rem_text_1(message: types.Message, state: FSMContext):
    update_config("reminder_1_text", message.text)
    await state.clear()
    await message.answer("✅ Текст первого напоминания успешно обновлен! Откройте 'Панель управления' -> 'Настройки'.")

@router.message(EditReminderSettingsForm.text_2)
async def process_rem_text_2(message: types.Message, state: FSMContext):
    update_config("reminder_2_text", message.text)
    await state.clear()
    await message.answer("✅ Текст второго напоминания успешно обновлен!")

@router.message(EditReminderSettingsForm.time_2)
async def process_rem_time_2(message: types.Message, state: FSMContext):
    try:
        hours = int(message.text.strip())
        if hours < 1 or hours > 23:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число часов (от 1 до 23):", reply_markup=keyboards.get_cancel_admin_action_keyboard())
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
    text = f"🌍 Настройка часового пояса\n\nТекущее смещение: UTC{'+' if current_tz >= 0 else ''}{current_tz}\n\nВведите новое смещение в часах (например: 3 для Москвы, 5 для Екатеринбурга, -4 для Нью-Йорка):"
    
    await state.set_state(EditTimezoneForm.offset)
    await callback.message.edit_text(text, reply_markup=keyboards.get_cancel_admin_action_keyboard())

@router.message(EditTimezoneForm.offset)
async def process_timezone_offset(message: types.Message, state: FSMContext):
    try:
        offset = int(message.text.replace('+', '').strip())
        if not (-12 <= offset <= 14):
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число от -12 до 14 (например, 3 или -5).")
        return
        
    update_config("timezone_offset", offset)
    await state.clear()
    
    use_masters = salon_config.get("use_masters", False)
    await message.answer(f"✅ Часовой пояс успешно сохранен: UTC{'+' if offset >= 0 else ''}{offset}", reply_markup=keyboards.get_system_settings_keyboard(use_masters))

@router.callback_query(F.data.startswith("del_master_"))
async def del_master_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    m_id = int(callback.data.split("_")[2])
    await database.delete_master(m_id)
    masters = await database.get_all_masters()
    await callback.message.edit_text("Мастер удален. Список:", reply_markup=keyboards.get_masters_keyboard(masters))

@router.callback_query(F.data == "add_master")
async def add_master_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await state.set_state(AddMasterForm.name)
    await callback.message.answer("Введите имя мастера:")
    await callback.answer()

@router.message(AddMasterForm.name)
async def process_master_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddMasterForm.telegram_id)
    await message.answer("Введите Telegram ID мастера (число):")

@router.message(AddMasterForm.telegram_id)
async def process_master_tg_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data['name']
    tg_id = message.text
    
    # We will just save with None category for simplicity for now
    await database.add_master(name=name, telegram_id=tg_id, category_id=None)
    await state.clear()
    
    masters = await database.get_all_masters()
    await message.answer(f"✅ Мастер '{name}' успешно добавлен!", reply_markup=keyboards.get_masters_keyboard(masters))

@router.message(F.text == "📅 График")
async def manage_schedule_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
        
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    
    await message.answer(
        "Настройка графика работы:\nВыберите рабочие дни недели и управляйте выходными (черным списком дат).", 
        reply_markup=keyboards.get_working_days_keyboard(working_days, blacklisted_dates)
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
    await callback.message.answer("Введите дату выходного в формате ДД.ММ.ГГГГ (например, 31.12.2023):", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(AddBlacklistDateForm.date)
async def process_blacklist_date(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    import re
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
        reply_markup=keyboards.get_working_days_keyboard(working_days, blacklisted_dates)
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
    
@router.message(F.text == "📅 Окно брони")
async def edit_booking_window_handler(message: types.Message, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    current_window = salon_config.get("booking_window", 7)
    await state.set_state(AddBookingWindowForm.days)
    await message.answer(f"Текущее окно бронирования: {current_window} дн.\nВведите новое количество дней (например, 14):", reply_markup=keyboards.get_cancel_admin_action_keyboard())

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
    if not admin_id or str(callback.from_user.id) != admin_id: return
    current_wh = salon_config.get("working_hours", "10:00-20:00")
    await state.set_state(WorkingHoursForm.hours)
    await callback.message.edit_text(f"Текущие рабочие часы: {current_wh}\nВведите новые рабочие часы в формате ЧЧ:ММ-ЧЧ:ММ (например, 10:00-20:00):", reply_markup=keyboards.get_cancel_admin_action_keyboard())

@router.message(WorkingHoursForm.hours)
async def process_working_hours(message: types.Message, state: FSMContext):
    import re
    wh = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}-\d{2}:\d{2}$", wh):
        await message.answer("Неверный формат. Пожалуйста, введите в формате ЧЧ:ММ-ЧЧ:ММ (например, 10:00-20:00):", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return
    update_config("working_hours", wh)
    await state.clear()
    await message.answer(f"✅ Рабочие часы успешно изменены на {wh}.")

@router.callback_query(F.data == "settings_interval")
async def settings_interval_cb(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    current_interval = salon_config.get("schedule_interval", 30)
    await state.set_state(ScheduleIntervalForm.interval)
    await callback.message.edit_text(f"Текущий шаг записи: {current_interval} мин.\nВведите новый интервал в минутах (например, 15, 30, 60):", reply_markup=keyboards.get_cancel_admin_action_keyboard())

@router.message(ScheduleIntervalForm.interval)
async def process_schedule_interval(message: types.Message, state: FSMContext):
    try:
        val = int(message.text.strip())
        if val <= 0: raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число в минутах (например, 30):", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return
    update_config("schedule_interval", val)
    await state.clear()
    await message.answer(f"✅ Шаг записи изменен на {val} мин.")

@router.message(F.text == "⚙️ Услуги")
async def manage_services_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
        
    services = await database.get_all_services()
    if not services:
        await message.answer("Список услуг пуст.", reply_markup=keyboards.get_services_keyboard(services))
    else:
        total = len(services)
        text = f"📋 Услуги ({total} шт.) — страница 1:\n"
        for s in services[:20]:
            cat_info = f" ({s.get('category_name')})" if s.get('category_name') else ""
            line = f"• {s['name']}{cat_info} — {s['price']}₽\n"
            if len(text) + len(line) > 3800:
                text += "…\n"
                break
            text += line
        await message.answer(text, reply_markup=keyboards.get_services_keyboard(services, page=0))

@router.callback_query(F.data.startswith("del_srv_"))
async def del_service_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    srv_id = int(callback.data.split("_")[2])
    await database.delete_service(srv_id)
    services = await database.get_all_services()
    await callback.message.edit_text("Услуга удалена. Список текущих услуг:", reply_markup=keyboards.get_services_keyboard(services))

@router.callback_query(F.data.startswith("edit_srv_"))
async def edit_service_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    parts = callback.data.split("_")
    srv_id = int(parts[2])
    # Page number is encoded as last part (default 0 for compatibility)
    page = int(parts[3]) if len(parts) > 3 else 0
    await state.update_data(services_page=page)
    
    service = await database.get_service_by_id(srv_id)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    
    cat_name = service.get('category_name')
    cat_info = f"\n📁 Категория: {cat_name}" if cat_name else "\n📁 Категория: Без категории"
    text = f"⚙️ Редактирование услуги:\n\n📝 Название: {service['name']}\n💸 Цена: {service['price']}₽{cat_info}"
    await callback.message.edit_text(text, reply_markup=keyboards.get_service_edit_keyboard(service))

@router.callback_query(F.data == "back_to_services")
async def back_to_services_callback(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('services_page', 0)
    await state.clear()
    services = await database.get_all_services()
    if not services:
        await callback.message.edit_text("Список услуг пуст.", reply_markup=keyboards.get_services_keyboard(services))
    else:
        total = len(services)
        page_size = 20
        start = page * page_size
        end = min(start + page_size, total)
        text = f"📋 Услуги ({total} шт.) — страница {page + 1}:\n"
        for s in services[start:end]:
            cat_info = f" ({s.get('category_name')})" if s.get('category_name') else ""
            line = f"• {s['name']}{cat_info} — {s['price']}₽\n"
            if len(text) + len(line) > 3800:
                text += "…\n"
                break
            text += line
        await callback.message.edit_text(text, reply_markup=keyboards.get_services_keyboard(services, page=page))

@router.callback_query(F.data.startswith("srv_page_"))
async def services_page_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    page = int(callback.data.split("_")[2])
    services = await database.get_all_services()
    total = len(services)
    page_size = 20
    start = page * page_size
    end = min(start + page_size, total)
    text = f"📋 Услуги ({total} шт.) — страница {page + 1}:\n"
    for s in services[start:end]:
        cat_info = f" ({s.get('category_name')})" if s.get('category_name') else ""
        line = f"• {s['name']}{cat_info} — {s['price']}₽\n"
        if len(text) + len(line) > 3800:
            text += "…\n"
            break
        text += line
    await callback.message.edit_text(text, reply_markup=keyboards.get_services_keyboard(services, page=page))
    await callback.answer()

@router.callback_query(F.data.startswith("eds_name_"))
async def eds_name_callback(callback: types.CallbackQuery, state: FSMContext):
    srv_id = int(callback.data.split("_")[2])
    await state.update_data(service_id=srv_id)
    await state.set_state(EditServiceForm.name)
    await callback.message.answer("Введите новое название для услуги:", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(EditServiceForm.name)
async def process_edit_service_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    srv_id = data['service_id']
    await database.update_service_name(srv_id, message.text)
    await state.clear()
    
    service = await database.get_service_by_id(srv_id)
    cat_name = service.get('category_name')
    cat_info = f"\n📁 Категория: {cat_name}" if cat_name else "\n📁 Категория: Без категории"
    text = f"✅ Название изменено!\n\n⚙️ Редактирование услуги:\n\n📝 Название: {service['name']}\n💸 Цена: {service['price']}₽{cat_info}"
    await message.answer(text, reply_markup=keyboards.get_service_edit_keyboard(service))

@router.callback_query(F.data.startswith("eds_price_"))
async def eds_price_callback(callback: types.CallbackQuery, state: FSMContext):
    srv_id = int(callback.data.split("_")[2])
    await state.update_data(service_id=srv_id)
    await state.set_state(EditServiceForm.price)
    await callback.message.answer("Введите новую цену для услуги:", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(EditServiceForm.price)
async def process_edit_service_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    srv_id = data['service_id']
    await database.update_service_price(srv_id, message.text)
    await state.clear()
    
    service = await database.get_service_by_id(srv_id)
    cat_name = service.get('category_name')
    cat_info = f"\n📁 Категория: {cat_name}" if cat_name else "\n📁 Категория: Без категории"
    text = f"✅ Цена изменена!\n\n⚙️ Редактирование услуги:\n\n📝 Название: {service['name']}\n💸 Цена: {service['price']}₽{cat_info}"
    await message.answer(text, reply_markup=keyboards.get_service_edit_keyboard(service))

@router.callback_query(F.data.startswith("eds_cat_"))
async def eds_cat_callback(callback: types.CallbackQuery, state: FSMContext):
    srv_id = int(callback.data.split("_")[2])
    categories = await database.get_all_categories()
    if not categories:
        await callback.answer("Нет доступных категорий!", show_alert=True)
        return
        
    await state.update_data(service_id=srv_id)
    await state.set_state(EditServiceForm.category_id)
    await callback.message.edit_text("Выберите новую категорию:", reply_markup=keyboards.get_select_category_keyboard(categories))

@router.callback_query(EditServiceForm.category_id, F.data.startswith("sel_cat_"))
async def process_edit_service_cat(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    if cat_id == 0:
        cat_id = None
        
    data = await state.get_data()
    srv_id = data['service_id']
    await database.update_service_category(srv_id, cat_id)
    await state.clear()
    
    service = await database.get_service_by_id(srv_id)
    cat_name = service.get('category_name')
    cat_info = f"\n📁 Категория: {cat_name}" if cat_name else "\n📁 Категория: Без категории"
    text = f"✅ Категория изменена!\n\n⚙️ Редактирование услуги:\n\n📝 Название: {service['name']}\n💸 Цена: {service['price']}₽{cat_info}"
    await callback.message.edit_text(text, reply_markup=keyboards.get_service_edit_keyboard(service))

@router.message(F.text == "📁 Категории")
async def manage_categories_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
        
    categories = await database.get_all_categories()
    if not categories:
        await message.answer("Список категорий пуст.", reply_markup=keyboards.get_categories_keyboard(categories))
    else:
        text = "Список категорий:\n"
        tree = keyboards.build_category_tree(categories)
        for c, depth in tree:
            name = c['name'] if isinstance(c, dict) else c[1]
            prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
            text += f"{prefix}{name}\n"
        await message.answer(text, reply_markup=keyboards.get_categories_keyboard(categories))

@router.callback_query(F.data.startswith("del_cat_"))
async def del_category_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    cat_id = int(callback.data.split("_")[2])
    await database.delete_category(cat_id)
    categories = await database.get_all_categories()
    
    text = "Категория удалена. Список:\n"
    tree = keyboards.build_category_tree(categories)
    for c, depth in tree:
        name = c['name'] if isinstance(c, dict) else c[1]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        text += f"{prefix}{name}\n"
        
    await callback.message.edit_text(text, reply_markup=keyboards.get_categories_keyboard(categories))

@router.callback_query(F.data.startswith("edit_cat_"))
async def edit_category_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    cat_id = int(callback.data.split("_")[2])
    category = await database.get_category_by_id(cat_id)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    
    text = f"📁 Редактирование категории:\n\n📝 Название: {category['name']}"
    await callback.message.edit_text(text, reply_markup=keyboards.get_category_edit_keyboard(category))

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    categories = await database.get_all_categories()
    if not categories:
        await callback.message.edit_text("Список категорий пуст.", reply_markup=keyboards.get_categories_keyboard(categories))
    else:
        text = "Список категорий:\n"
        tree = keyboards.build_category_tree(categories)
        for c, depth in tree:
            name = c['name'] if isinstance(c, dict) else c[1]
            prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
            text += f"{prefix}{name}\n"
        await callback.message.edit_text(text, reply_markup=keyboards.get_categories_keyboard(categories))

@router.callback_query(F.data.startswith("edc_name_"))
async def edc_name_callback(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=cat_id)
    await state.set_state(EditCategoryForm.name)
    await callback.message.answer("Введите новое название для категории:", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(EditCategoryForm.name)
async def process_edit_category_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cat_id = data['category_id']
    await database.update_category_name(cat_id, message.text)
    await state.clear()
    
    category = await database.get_category_by_id(cat_id)
    text = f"✅ Название изменено!\n\n📁 Редактирование категории:\n\n📝 Название: {category['name']}"
    await message.answer(text, reply_markup=keyboards.get_category_edit_keyboard(category))

@router.callback_query(F.data.startswith("move_cat_"))
async def move_category_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
        
    cat_id = int(callback.data.split("_")[2])
    categories = await database.get_all_categories()
    
    # Filter out the category itself to prevent infinite cyclic graphs
    valid_categories = [c for c in categories if c['id'] != cat_id]
    
    await state.update_data(category_id=cat_id)
    await state.set_state(EditCategoryForm.new_parent)
    await callback.message.edit_text(
        "Выберите новую родительскую категорию для перемещения:", 
        reply_markup=keyboards.get_parent_category_keyboard(valid_categories)
    )

@router.callback_query(EditCategoryForm.new_parent, F.data.startswith("sel_parent_"))
async def process_move_category_parent(callback: types.CallbackQuery, state: FSMContext):
    parent_id = int(callback.data.split("_")[2])
    if parent_id == 0:
        parent_id = None
        
    data = await state.get_data()
    cat_id = data['category_id']
    
    await database.update_category_parent(cat_id, parent_id)
    await state.clear()
    
    category = await database.get_category_by_id(cat_id)
    text = f"✅ Категория успешно перемещена!\n\n📁 Редактирование категории:\n\n📝 Название: {category['name']}"
    await callback.message.edit_text(text, reply_markup=keyboards.get_category_edit_keyboard(category))

@router.callback_query(F.data == "add_category")
async def add_category_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
        
    await state.set_state(CategoryWizard.main_name)
    await callback.message.answer("Введите название новой категории:", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(CategoryWizard.main_name)
async def process_wizard_main_name(message: types.Message, state: FSMContext):
    cat_name = message.text
    await database.add_category(name=cat_name, parent_id=None)
    categories = await database.get_all_categories()
    
    # Find the newly created category ID
    new_main_id = None
    for c in reversed(categories):
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        if name == cat_name:
            new_main_id = c_id
            break
            
    # Check for free services
    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)
            
    has_free = len(free_services) > 0
    
    await state.update_data(main_id=new_main_id, main_name=cat_name)
    await message.answer(
        f"✅ Основная категория '{cat_name}' добавлена!\nЧто делаем дальше?",
        reply_markup=keyboards.get_wizard_keyboard(main_id=new_main_id, main_name=cat_name, has_free_services=has_free)
    )

@router.callback_query(F.data.startswith("wiz_addsub_"))
async def wizard_add_sub(callback: types.CallbackQuery, state: FSMContext):
    main_id = int(callback.data.split("_")[2])
    cat = await database.get_category_by_id(main_id)
    main_name = cat['name'] if cat else 'Основная категория'
    
    # Strictly reset sub_id so it doesn't leak from older flows
    await state.update_data(main_id=main_id, main_name=main_name, sub_id=None, sub_name=None)
    await state.set_state(CategoryWizard.sub_name)
    await callback.message.edit_text(f"Введите название подкатегории для '{main_name}':", reply_markup=keyboards.get_cancel_admin_action_keyboard())

@router.message(CategoryWizard.sub_name)
async def process_wizard_sub_name(message: types.Message, state: FSMContext):
    sub_name = message.text
    data = await state.get_data()
    main_id = data.get('main_id')
    main_name = data.get('main_name')
    
    await database.add_category(name=sub_name, parent_id=main_id)
    categories = await database.get_all_categories()
    
    new_sub_id = None
    for c in reversed(categories):
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        if name == sub_name:
            new_sub_id = c_id
            break
            
    # Check for free services
    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)
            
    has_free = len(free_services) > 0
    
    await message.answer(
        f"✅ Подкатегория '{sub_name}' (внутри '{main_name}') добавлена!\nЧто делаем дальше?",
        reply_markup=keyboards.get_wizard_keyboard(main_id=main_id, main_name=main_name, sub_id=new_sub_id, sub_name=sub_name, has_free_services=has_free)
    )

@router.callback_query(F.data.startswith("wiz_attach_"))
async def wizard_attach_services(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    
    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)
            
    await state.update_data(new_category_id=target_id, selected_services=[], free_services=free_services)
    await state.set_state("AttachServicesForm:selecting")
    
    await callback.message.edit_text(
        "Выберите свободные услуги для прикрепления:",
        reply_markup=keyboards.get_free_services_keyboard(free_services, [])
    )

@router.callback_query(F.data.startswith("wiz_addsrv_"))
async def wizard_add_service(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    cat = await database.get_category_by_id(target_id)
    if not cat:
        return
        
    # Strictly derive hierarchy from DB to prevent dirty FSM leakage
    if cat['parent_id']:
        parent_cat = await database.get_category_by_id(cat['parent_id'])
        main_id = cat['parent_id']
        main_name = parent_cat['name'] if parent_cat else "Категория"
        sub_id = target_id
        sub_name = cat['name']
    else:
        main_id = target_id
        main_name = cat['name']
        sub_id = None
        sub_name = None
        
    await state.update_data(target_id=target_id, 
                            main_id=main_id, 
                            main_name=main_name, 
                            sub_id=sub_id, 
                            sub_name=sub_name)
    display_name = sub_name if sub_name else main_name
    await state.set_state(WizardAddServiceForm.name)
    await callback.message.edit_text(f"Введите название новой услуги для '{display_name}':", reply_markup=keyboards.get_cancel_admin_action_keyboard())

@router.message(WizardAddServiceForm.name)
async def process_wizard_service_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(WizardAddServiceForm.price)
    await message.answer("Введите цену услуги (например, 2000):", reply_markup=keyboards.get_cancel_admin_action_keyboard())

@router.message(WizardAddServiceForm.price)
async def process_wizard_service_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(WizardAddServiceForm.duration)
    await message.answer("Введите длительность услуги в минутах (например: 30, 60, 90, 120):", reply_markup=keyboards.get_cancel_admin_action_keyboard())

@router.message(WizardAddServiceForm.duration)
async def process_wizard_service_duration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data['name']
    target_id = data['target_id']
    price = data['price']
    
    try:
        duration = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите число в минутах (например, 60):", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return

    await database.add_service(name=name, price=price, duration=duration, description="", category_id=target_id)
    
    # Retrieve wizard context to redraw keyboard
    main_id = data.get('main_id')
    main_name = data.get('main_name')
    sub_id = data.get('sub_id')
    sub_name = data.get('sub_name')
    
    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)
            
    has_free = len(free_services) > 0
    
    await message.answer(
        f"✅ Услуга '{name}' добавлена!\nЧто делаем дальше?",
        reply_markup=keyboards.get_wizard_keyboard(main_id=main_id, main_name=main_name, sub_id=sub_id, sub_name=sub_name, has_free_services=has_free)
    )

@router.callback_query(F.data == "wiz_finish")
async def wizard_finish(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    categories = await database.get_all_categories()
    
    text = "✅ Работа с категориями завершена. Список:\n"
    tree = keyboards.build_category_tree(categories)
    for c, depth in tree:
        name = c['name'] if isinstance(c, dict) else c[1]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        text += f"{prefix}{name}\n"
        
    await callback.message.edit_text(text, reply_markup=keyboards.get_categories_keyboard(categories))

# === ADD SUBCATEGORY EXISTING ===
@router.callback_query(F.data == "add_subcategory_existing")
async def add_subcategory_existing(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
        
    categories = await database.get_all_categories()
    if not categories:
        await callback.message.answer("Сначала создайте хотя бы одну основную категорию!")
        return
        
    await state.set_state(AddSubcategoryExistingForm.parent_id)
    await callback.message.answer("К какой категории добавить подкатегорию?", reply_markup=keyboards.get_parent_category_keyboard(categories))
    await callback.answer()

@router.callback_query(AddSubcategoryExistingForm.parent_id, F.data.startswith("sel_parent_"))
async def process_subcat_parent(callback: types.CallbackQuery, state: FSMContext):
    parent_id = int(callback.data.split("_")[2])
    if parent_id == 0:
        parent_id = None
    await state.update_data(parent_id=parent_id)
    await state.set_state(AddSubcategoryExistingForm.name)
    await callback.message.edit_text("Родительская категория выбрана. Введите название подкатегории:", reply_markup=keyboards.get_cancel_admin_action_keyboard())

@router.message(AddSubcategoryExistingForm.name)
async def process_subcat_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    parent_id = data.get('parent_id')
    cat_name = message.text
    
    await database.add_category(name=cat_name, parent_id=parent_id)
    categories = await database.get_all_categories()
    
    new_sub_id = None
    for c in reversed(categories):
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        if name == cat_name:
            new_sub_id = c_id
            break
            
    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)
            
    has_free = len(free_services) > 0
    
    if has_free and new_sub_id:
        await state.update_data(new_category_id=new_sub_id, selected_services=[], free_services=free_services)
        await state.set_state("AttachServicesForm:selecting")
        await message.answer(
            f"✅ Подкатегория '{cat_name}' добавлена!\nЕсть свободные услуги, прикрепить их?",
            reply_markup=keyboards.get_free_services_keyboard(free_services, [])
        )
    else:
        await state.clear()
        text = f"✅ Подкатегория '{cat_name}' добавлена! Список:\n"
        tree = keyboards.build_category_tree(categories)
        for c, depth in tree:
            name = c['name'] if isinstance(c, dict) else c[1]
            prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
            text += f"{prefix}{name}\n"
        await message.answer(text, reply_markup=keyboards.get_categories_keyboard(categories))

# === TOGGLE SERVICE SELECTION FOR BOTH FLOWS ===
@router.callback_query(F.data.startswith("toggle_srv_"))
async def toggle_service_selection(callback: types.CallbackQuery, state: FSMContext):
    srv_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected = data.get('selected_services', [])
    free_services = data.get('free_services', [])
    
    if srv_id in selected:
        selected.remove(srv_id)
    else:
        selected.append(srv_id)
        
    await state.update_data(selected_services=selected)
    await callback.message.edit_reply_markup(reply_markup=keyboards.get_free_services_keyboard(free_services, selected))

@router.callback_query(F.data == "finish_service_selection")
async def finish_service_selection(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_cat_id = data.get('new_category_id')
    selected = data.get('selected_services', [])
    
    if new_cat_id and selected:
        for srv_id in selected:
            await database.update_service_category(srv_id, new_cat_id)
            
    await state.clear()
    categories = await database.get_all_categories()
    
    msg = "✅ Категория и услуги успешно сохранены!" if selected else "✅ Категория сохранена без добавления услуг."
    text = f"{msg} Список:\n"
    tree = keyboards.build_category_tree(categories)
    for c, depth in tree:
        name = c['name'] if isinstance(c, dict) else c[1]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        text += f"{prefix}{name}\n"
        
    await callback.message.edit_text(text, reply_markup=keyboards.get_categories_keyboard(categories))


@router.callback_query(F.data == "add_service")
async def add_service_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
        
    categories = await database.get_all_categories()
    if not categories:
        await state.update_data(category_id=None)
        await state.set_state(AddServiceForm.name)
        await callback.message.answer("Введите название новой услуги:")
    else:
        await state.set_state(AddServiceForm.category_id)
        await callback.message.answer("Выберите категорию для новой услуги:", reply_markup=keyboards.get_select_category_keyboard(categories))
    await callback.answer()

@router.callback_query(AddServiceForm.category_id, F.data.startswith("sel_cat_"))
async def process_service_category(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    cat_val = cat_id if cat_id > 0 else None
    await state.update_data(category_id=cat_val)
    await state.set_state(AddServiceForm.name)
    await callback.message.edit_text("Категория выбрана. Теперь введите название новой услуги:")

@router.message(AddServiceForm.name)
async def process_service_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddServiceForm.price)
    await message.answer("Введите цену услуги (например, 2000):")

@router.message(AddServiceForm.price)
async def process_service_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(AddServiceForm.duration)
    await message.answer("Введите длительность услуги в минутах (например, 30, 60, 90):")

@router.message(AddServiceForm.duration)
async def process_service_duration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data['name']
    category_id = data.get('category_id')
    price = data['price']
    
    try:
        duration = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите число в минутах (например, 60):")
        return
        
    await database.add_service(name=name, price=price, duration=duration, description="", category_id=category_id)
    await state.clear()
    
    services = await database.get_all_services()
    await message.answer(f"✅ Услуга '{name}' добавлена!", reply_markup=keyboards.get_services_keyboard(services))


@router.callback_query(F.data.startswith("edit_srv_"))
async def edit_service_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    
    parts = callback.data.split("_")
    s_id = int(parts[2])
    
    # Needs a database helper to get single service
    service = await database.get_service_by_id(s_id)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
        
    await callback.message.edit_text(
        f"Управление услугой: <b>{service['name']}</b>\n"
        f"Цена: {service['price']}\n"
        f"Длительность: {service.get('duration', 60)} мин.",
        reply_markup=keyboards.get_service_edit_keyboard(service),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("del_srv_"))
async def del_service_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id: return
    s_id = int(callback.data.split("_")[2])
    await database.delete_service(s_id)
    services = await database.get_all_services()
    await callback.message.edit_text("✅ Услуга удалена.", reply_markup=keyboards.get_services_keyboard(services))

@router.callback_query(F.data.startswith("eds_name_"))
async def eds_name_cb(callback: types.CallbackQuery, state: FSMContext):
    s_id = int(callback.data.split("_")[2])
    await state.update_data(edit_service_id=s_id)
    await state.set_state(EditServiceNameForm.value)
    await callback.message.answer("Введите новое название для услуги:", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(EditServiceNameForm.value)
async def process_eds_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    s_id = data['edit_service_id']
    await database.update_service_name(s_id, message.text)
    await state.clear()
    
    service = await database.get_service_by_id(s_id)
    await message.answer("✅ Название изменено!", reply_markup=keyboards.get_service_edit_keyboard(service))

@router.callback_query(F.data.startswith("eds_price_"))
async def eds_price_cb(callback: types.CallbackQuery, state: FSMContext):
    s_id = int(callback.data.split("_")[2])
    await state.update_data(edit_service_id=s_id)
    await state.set_state(EditServicePriceForm.value)
    await callback.message.answer("Введите новую цену (текстом/числом):", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(EditServicePriceForm.value)
async def process_eds_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    s_id = data['edit_service_id']
    await database.update_service_price(s_id, message.text)
    await state.clear()
    
    service = await database.get_service_by_id(s_id)
    await message.answer("✅ Цена изменена!", reply_markup=keyboards.get_service_edit_keyboard(service))

@router.callback_query(F.data.startswith("eds_dur_"))
async def eds_dur_cb(callback: types.CallbackQuery, state: FSMContext):
    s_id = int(callback.data.split("_")[2])
    await state.update_data(edit_service_id=s_id)
    await state.set_state(EditServiceDurationForm.value)
    await callback.message.answer("Введите новую длительность услуги в минутах (например, 30, 60, 90):", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()

@router.message(EditServiceDurationForm.value)
async def process_eds_dur(message: types.Message, state: FSMContext):
    data = await state.get_data()
    s_id = data['edit_service_id']
    
    try:
        dur = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите число в минутах (например, 60):", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return
        
    await database.update_service_duration(s_id, dur)
    await state.clear()
    
    service = await database.get_service_by_id(s_id)
    await message.answer("✅ Длительность изменена!", reply_markup=keyboards.get_service_edit_keyboard(service))

@router.callback_query(F.data.startswith("eds_cat_"))
async def eds_cat_cb(callback: types.CallbackQuery, state: FSMContext):
    s_id = int(callback.data.split("_")[2])
    categories = await database.get_all_categories()
    if not categories:
        await callback.answer("Категорий пока нет.", show_alert=True)
        return
    await state.update_data(edit_service_id=s_id)
    # We reuse the sel_cat_ callback which was mapped to AddServiceForm.category_id, but here 
    # we'll map it differently or just use the inline keyboard and catch it. We'll add a state.
    # Let's add an explicit EditServiceCategoryForm if needed, or simply intercept "eds_sel_cat_"
    await callback.message.answer("Эта функция редактирования категории в разработке.")
    await callback.answer()


# ========================================
# Напоминания: Обработка кнопок
# ========================================

@router.callback_query(F.data.startswith("rem_conf_"))
async def reminder_confirm_cb(callback: types.CallbackQuery):
    booking_id = int(callback.data.split("_")[2])
    booking = await database.get_booking_by_id(booking_id)
    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return
        
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🎉 Спасибо за подтверждение! Ждём вас в назначенное время.")
    
    admin_id = getenv("ADMIN_ID")
    if admin_id:
        msg = f"✅ Клиент {booking[0]} подтвердил запись на {booking[2]} в {booking[3]}."
        if booking[4]:
            msg += f" Мастер: {booking[4]}"
        try:
            await callback.bot.send_message(admin_id, msg)
        except:
            pass

@router.callback_query(F.data.startswith("rem_canc_"))
async def reminder_cancel_cb(callback: types.CallbackQuery):
    booking_id = int(callback.data.split("_")[2])
    booking = await database.get_booking_by_id(booking_id)
    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return
        
    await database.delete_booking_by_id(booking_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("😔 Ваша запись отменена. Будем рады видеть вас снова!")
    
    admin_id = getenv("ADMIN_ID")
    if admin_id:
        msg = f"❌ Клиент {booking[0]} отменил запись на {booking[2]} в {booking[3]} через напоминание."
        if booking[4]:
            msg += f" Мастер: {booking[4]}"
        try:
            await callback.bot.send_message(admin_id, msg)
        except:
            pass

@router.callback_query(F.data.startswith("rem_resched_"))
async def reminder_resched_cb(callback: types.CallbackQuery):
    booking_id = int(callback.data.split("_")[2])
    booking = await database.get_booking_by_id(booking_id)
    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return
        
    await database.delete_booking_by_id(booking_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🔄 Ваша предыдущая запись отменена. Пожалуйста, зайдите в 'Записаться' и выберите новое время.")
    
    admin_id = getenv("ADMIN_ID")
    if admin_id:
        msg = f"🔄 Клиент {booking[0]} отменил запись на {booking[2]} в {booking[3]} (Перенос) и сейчас выберет новое время."
        if booking[4]:
            msg += f" (Мастер: {booking[4]})"
        try:
            await callback.bot.send_message(admin_id, msg)
        except:
            pass

# ==================== ANALYTICS ====================

@router.message(F.text == "📊 Статистика")
async def analytics_menu_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    await message.answer(
        "📊 <b>Выберите период для статистики:</b>",
        reply_markup=keyboards.get_analytics_keyboard(),
        parse_mode="HTML"
    )

async def build_stats_report(period_days: int, period_label: str) -> str:
    revenue = await database.get_revenue_stats(period_days)
    top_services = await database.get_top_services(period_days, limit=5)
    weekday_stats = await database.get_bookings_by_weekday(period_days)
    peak_hours = await database.get_peak_hours(period_days, top_n=3)
    clients = await database.get_client_stats(period_days)

    lines = [f"📊 <b>Статистика: {period_label}</b>\n"]

    # Revenue block
    lines.append("💰 <b>Выручка:</b>")
    total = revenue['total_revenue']
    count = revenue['total_bookings']
    avg = revenue['avg_price']
    lines.append(f"  Записей: {count} | Сумма: {total:,} ₽ | Средний чек: {avg:,} ₽\n")

    # Top services block
    if top_services:
        lines.append("🏆 <b>Топ услуг:</b>")
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (name, cnt) in enumerate(top_services):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            lines.append(f"  {medal} {name} — {cnt} записей")
        lines.append("")
    else:
        lines.append("🏆 <b>Топ услуг:</b> нет данных\n")

    # Weekday load
    busy_days = {k: v for k, v in weekday_stats.items() if v > 0}
    if busy_days:
        lines.append("📅 <b>Загруженность по дням:</b>")
        day_parts = " | ".join(f"{day}: {cnt}" for day, cnt in busy_days.items())
        lines.append(f"  {day_parts}\n")

    # Peak hours
    if peak_hours:
        lines.append("⏰ <b>Пиковые часы:</b>")
        hour_parts = ", ".join(f"{h} ({c} зап.)" for h, c in peak_hours)
        lines.append(f"  {hour_parts}\n")

    # Client stats
    lines.append("👥 <b>Клиенты:</b>")
    lines.append(f"  Новых: {clients['new']} | Повторных: {clients['returning']}")

    return "\n".join(lines)

@router.callback_query(F.data == "stats_today")
async def stats_today_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
    await callback.message.edit_text("⏳ Считаю...", parse_mode="HTML")
    report = await build_stats_report(0, "Сегодня")
    await callback.message.edit_text(report, parse_mode="HTML")

@router.callback_query(F.data == "stats_week")
async def stats_week_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
    await callback.message.edit_text("⏳ Считаю...", parse_mode="HTML")
    report = await build_stats_report(7, "За 7 дней")
    await callback.message.edit_text(report, parse_mode="HTML")

@router.callback_query(F.data == "stats_month")
async def stats_month_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
    await callback.message.edit_text("⏳ Считаю...", parse_mode="HTML")
    report = await build_stats_report(30, "За 30 дней")
    await callback.message.edit_text(report, parse_mode="HTML")
