from __future__ import annotations

import json
import logging

from money import get_currency_symbol

from .base import (
    F,
    FSMContext,
    Router,
    cancel_booking_and_notify,
    database,
    finalize_web_booking,
    format_booking_history_text,
    format_user_booking_text,
    getenv,
    keyboards,
    salon_config,
    service_validate_web_booking,
    types,
)

router = Router()
logger = logging.getLogger(__name__)
USER_HISTORY_LIMIT = 5


def format_price_list_page(services, page: int, page_size: int = 20):
    from collections import defaultdict
    import math

    currency = get_currency_symbol()
    categories = defaultdict(list)
    for service in services:
        cat_name = service.get("category_name") or "Без категории"
        categories[cat_name].append(service)

    lines = [
        f"💸 <b>Прайс-лист</b>",
        f"<i>{salon_config.get('salon_name', 'Nail Studio')}</i>",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for category_name in sorted(categories.keys()):
        lines.append(f"✨ <b>{category_name}</b>")
        for service in categories[category_name]:
            lines.append(f"• {service['name']}")
            lines.append(f"  <b>{service['price']} {currency}</b>")
        lines.append("")

    total_lines = len(lines)
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
        await message.answer("💸 <b>Прайс-лист пока пуст</b>\n\nДобавьте услуги в админ-панели.", parse_mode="HTML")
        return

    text, total_pages = format_price_list_page(services, page=0, page_size=25)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboards.get_client_price_keyboard(0, total_pages))


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
        reply_markup=keyboards.get_client_price_keyboard(page, total_pages),
    )


@router.message(F.text == "📌 Адрес")
async def handle_address(message: types.Message):
    address = salon_config.get("address", "Адрес не указан.")
    hours = salon_config.get("working_hours", "")
    map_url = salon_config.get("map_url", "")

    text = f"📍 <b>Как нас найти</b>\n\n<b>Адрес:</b>\n{address}\n"
    if hours:
        text += f"\n<b>Часы работы:</b> <i>{hours}</i>\n"
    if map_url:
        text += f"\n<a href='{map_url}'>Открыть на карте</a>"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)


@router.message(F.text == "💅 Портфолио")
async def handle_portfolio(message: types.Message):
    portfolio_url = salon_config.get("portfolio_url", "")
    caption = "✨ <b>Наши работы</b>\n\n"
    if portfolio_url:
        caption += f"Посмотреть примеры можно здесь:\n<a href='{portfolio_url}'>Перейти в портфолио</a>"
    else:
        caption += "Ссылка на портфолио пока не добавлена."

    await message.answer(caption, parse_mode="HTML", disable_web_page_preview=False)


@router.message(F.text == "📲 Записаться")
async def launch_booking_webapp(message: types.Message):
    await message.answer(
        "📲 <b>Онлайн-запись</b>\n\nНажмите кнопку ниже, чтобы выбрать услугу, дату и время.",
        parse_mode="HTML",
        reply_markup=keyboards.get_booking_launch_keyboard(),
    )


@router.message(F.web_app_data)
async def process_web_app_data(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
        validated, error_text = await service_validate_web_booking(data)
        if error_text:
            await message.answer(error_text)
            return

        admin_id = getenv("ADMIN_ID")
        is_admin = bool(admin_id and str(message.from_user.id) == admin_id)

        await finalize_web_booking(
            message,
            service=validated["service"]["name"],
            date=validated["date"],
            time=validated["time"],
            duration=validated["duration"],
            phone=validated["phone"],
            name=validated["name"],
            price=validated["price"],
            is_admin=is_admin,
        )
        await state.clear()
    except Exception:
        logger.exception("Failed to process web_app_data")
        await message.answer("⚠️ Произошла ошибка при обработке данных. Попробуйте еще раз.")


@router.message(F.text == "📋 Мои записи")
async def my_bookings_handler(message: types.Message):
    await database.sync_completed_bookings()
    bookings = await database.get_user_bookings(message.from_user.id)
    active_bookings = [booking for booking in bookings if booking[5] == "scheduled"]
    history_count = len([booking for booking in bookings if booking[5] != "scheduled"])

    if not active_bookings:
        await message.answer(
            (
                "📋 <b>Активных записей сейчас нет</b>\n\n"
                f"🕘 Записей в истории: <b>{history_count}</b>\n"
                "Если захотите, откройте кнопку «История» или запишитесь на новый визит."
            ),
            parse_mode="HTML",
        )
        return

    summary_lines = ["📋 <b>Мои записи</b>", ""]
    summary_lines.append(f"📌 Активные: <b>{len(active_bookings)}</b>")
    summary_lines.append(f"🕘 В истории: <b>{history_count}</b>")
    summary_lines.extend(["", "Предстоящие визиты можно отменить прямо из кабинета."])
    await message.answer("\n".join(summary_lines), parse_mode="HTML")

    for booking_id, name, phone, date, time, status in active_bookings:
        await message.answer(
            format_user_booking_text(name, phone, date, time, status=status),
            reply_markup=keyboards.get_cancel_keyboard(message.from_user.id, booking_id),
            parse_mode="HTML",
        )

@router.message(F.text == "🕘 История")
async def booking_history_handler(message: types.Message):
    await database.sync_completed_bookings()
    bookings = await database.get_user_bookings(message.from_user.id)
    history_bookings = [booking for booking in bookings if booking[5] != "scheduled"][:USER_HISTORY_LIMIT]

    if not history_bookings:
        await message.answer(
            "🕘 <b>История пока пуста</b>\n\nЗавершённые и отменённые записи появятся здесь после первых визитов.",
            parse_mode="HTML",
        )
        return

    total_history = len([booking for booking in bookings if booking[5] != "scheduled"])
    await message.answer(
        format_booking_history_text(
            [(name, date, time, status, phone) for _booking_id, name, phone, date, time, status in history_bookings]
        ) + (
            f"\n\n<i>Показаны последние {USER_HISTORY_LIMIT} записей.</i>"
            if total_history > USER_HISTORY_LIMIT
            else ""
        ),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cancel_"))
async def cancel_booking_callback(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    user_id_str = parts[1]

    if str(callback.from_user.id) != user_id_str:
        await callback.answer("Это не ваша запись.", show_alert=True)
        return

    booking_id = None
    if len(parts) > 2:
        try:
            booking_id = int(parts[2])
        except ValueError:
            booking_id = None

    if booking_id is not None:
        booking = await database.get_booking_record_by_id(booking_id)
    else:
        booking = await database.get_user_booking(int(user_id_str))
        booking_id = booking[4] if booking else None

    if not booking:
        await callback.answer("Запись уже отменена или не найдена.", show_alert=True)
        return

    if len(parts) > 2 and booking_id is not None:
        _id, _user_id, name, phone, date, time, status, _duration = booking
        if status != "scheduled":
            await callback.answer("Эту запись уже нельзя отменить.", show_alert=True)
            return
    else:
        name, phone, date, time, booking_id = booking[:5]

    await cancel_booking_and_notify(
        callback,
        booking_id=booking_id,
        name=name,
        phone=phone,
        date=date,
        time=time,
    )
