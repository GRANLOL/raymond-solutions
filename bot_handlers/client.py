from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from html import escape

from money import get_currency_symbol

from booking_validation import parse_working_hours, slot_overlaps
from rate_limit import get_rate_limit_remaining
from time_utils import get_salon_now
from .states import RescheduleBookingForm
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
PORTFOLIO_PREVIEW_LIMIT = 5


def _format_reschedule_date_label(target_date: datetime.date) -> str:
    weekdays = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    return f"{target_date.strftime('%d.%m')} · {weekdays[target_date.weekday()]}"


async def _build_reschedule_date_options(duration: int) -> list[tuple[str, str]]:
    salon_now = get_salon_now()
    booking_window = max(int(salon_config.get("booking_window", 7) or 7), 1)
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    blacklisted_dates = set(salon_config.get("blacklisted_dates", []))
    options: list[tuple[str, str]] = []

    for offset in range(booking_window):
        target_date = salon_now.date() + timedelta(days=offset)
        date_value = target_date.strftime("%d.%m.%Y")
        js_weekday = (target_date.weekday() + 1) % 7
        if js_weekday not in working_days or date_value in blacklisted_dates:
            continue

        times = await _build_reschedule_time_options(date_value, duration)
        if times:
            options.append((_format_reschedule_date_label(target_date), date_value))

    return options


async def _build_reschedule_time_options(
    date_value: str,
    duration: int,
    *,
    current_date: str | None = None,
    current_time: str | None = None,
) -> list[str]:
    start_mins, end_mins = parse_working_hours(salon_config.get("working_hours", "10:00-20:00"))
    interval = int(salon_config.get("schedule_interval", 30) or 30)
    if interval <= 0:
        interval = 30

    busy_slots = await database.get_busy_slots_by_date(date_value)
    if current_date == date_value and current_time:
        busy_slots = [
            busy for busy in busy_slots
            if not (busy.get("time") == current_time and int(busy.get("duration") or 60) == int(duration or 60))
        ]

    salon_now = get_salon_now()
    salon_today = salon_now.strftime("%d.%m.%Y")
    current_salon_mins = salon_now.hour * 60 + salon_now.minute if date_value == salon_today else -1

    available_times: list[str] = []
    for slot_start in range(start_mins, end_mins - int(duration or 60) + 1, interval):
        if slot_start <= current_salon_mins:
            continue

        is_busy = False
        for busy in busy_slots:
            try:
                busy_h, busy_m = map(int, busy["time"].split(":"))
            except (KeyError, ValueError, AttributeError):
                continue
            busy_start = busy_h * 60 + busy_m
            busy_duration = int(busy.get("duration") or 60)
            if slot_overlaps(slot_start, int(duration or 60), busy_start, busy_duration):
                is_busy = True
                break

        if not is_busy:
            available_times.append(f"{slot_start // 60:02d}:{slot_start % 60:02d}")

    return available_times


def format_price_list_page(services, page: int, page_size: int = 20):
    from collections import defaultdict
    import math

    currency = get_currency_symbol()
    categories = defaultdict(list)
    for service in services:
        cat_name = service.get("category_name") or "Без категории"
        categories[cat_name].append(service)

    lines = [
        f"💎 <b>Услуги и цены</b>",
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


def _get_portfolio_items(limit: int = PORTFOLIO_PREVIEW_LIMIT) -> list[dict[str, str]]:
    raw_items = salon_config.get("portfolio_items", [])
    if not isinstance(raw_items, list):
        return []

    items: list[dict[str, str]] = []
    for raw_item in raw_items:
        media = ""
        caption = ""

        if isinstance(raw_item, str):
            media = raw_item.strip()
        elif isinstance(raw_item, dict):
            media = str(
                raw_item.get("media")
                or raw_item.get("url")
                or raw_item.get("file_id")
                or ""
            ).strip()
            caption = str(raw_item.get("caption") or "").strip()
        else:
            continue

        if media:
            items.append({"media": media, "caption": caption})

        if len(items) >= limit:
            break

    return items


@router.message(F.text.in_({"💸 Прайс-лист", "💎 Услуги и цены"}))
async def handle_price(message: types.Message):
    services = await database.get_all_services()
    if not services:
        await message.answer("💎 <b>Услуги и цены пока не добавлены</b>\n\nСначала добавьте их в админ-панели.", parse_mode="HTML")
        return

    text, total_pages = format_price_list_page(services, page=0, page_size=25)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboards.get_client_price_keyboard(0, total_pages))


@router.callback_query(F.data.startswith("client_price_page_"))
async def price_page_cb(callback: types.CallbackQuery):
    page_str = callback.data.split("_")[3]
    try:
        page = int(page_str)
    except ValueError:
        await callback.answer()
        return

    services = await database.get_all_services()
    if not services:
        await callback.answer("Услуги не найдены", show_alert=True)
        return

    await callback.answer()
    text, total_pages = format_price_list_page(services, page=page, page_size=25)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboards.get_client_price_keyboard(page, total_pages),
    )


def is_address_btn(message: types.Message) -> bool:
    return message.text in (salon_config.get("custom_btn_address_lbl", "📍 Адрес и контакты"), "📌 Адрес")

@router.message(is_address_btn)
async def handle_address(message: types.Message):
    custom_txt = salon_config.get("custom_btn_address_txt")
    if custom_txt:
        await message.answer(custom_txt, parse_mode="HTML", disable_web_page_preview=False)
        return

    address = salon_config.get("address", "Адрес не указан.")
    hours = salon_config.get("working_hours", "")
    map_url = salon_config.get("map_url", "")

    text = f"📍 <b>Как нас найти</b>\n\n<b>Адрес:</b>\n{address}\n"
    if hours:
        text += f"\n<b>Часы работы:</b> <i>{hours}</i>\n"
    if map_url:
        text += f"\n<a href='{map_url}'>Открыть на карте</a>"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=False)


def is_portfolio_btn(message: types.Message) -> bool:
    return message.text in (salon_config.get("custom_btn_portfolio_lbl", "💅 Примеры работ"), "🖼 Примеры работ")

@router.message(is_portfolio_btn)
async def handle_portfolio(message: types.Message):
    btn_type = salon_config.get("custom_btn_portfolio_type", "portfolio")
    lbl = salon_config.get("custom_btn_portfolio_lbl", "💅 Примеры работ")
    
    if btn_type == "text":
        custom_txt = salon_config.get("custom_btn_portfolio_txt") or "Текст не настроен."
        await message.answer(custom_txt, parse_mode="HTML", disable_web_page_preview=False)
        return

    portfolio_url = salon_config.get("portfolio_url", "")
    portfolio_items = _get_portfolio_items()

    if portfolio_items:
        media_group = []
        for index, item in enumerate(portfolio_items):
            item_caption = escape(item["caption"])
            if index == 0:
                lines = [
                    f"<b>{escape(lbl)}</b>",
                    "",
                ]
                if item_caption:
                    lines.extend([item_caption])
                if portfolio_url:
                    lines.extend(["", "Полную галерею можно открыть по кнопке ниже."])
                caption = "\n".join(lines)
            else:
                caption = item_caption

            media_group.append(
                types.InputMediaPhoto(
                    media=item["media"],
                    caption=caption or None,
                    parse_mode="HTML" if caption else None,
                )
            )

        await message.bot.send_media_group(chat_id=message.from_user.id, media=media_group)

        if portfolio_url:
            await message.answer(
                "✨ Больше примеров доступно в полной галерее.",
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=keyboards.get_portfolio_keyboard(portfolio_url),
            )
        return

    if portfolio_url:
        await message.answer(
            (
                f"<b>{escape(lbl)}</b>\n\n"
                "Сейчас полная подборка открывается отдельной ссылкой.\n"
                "Нажмите кнопку ниже, чтобы посмотреть."
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboards.get_portfolio_keyboard(portfolio_url),
        )
        return

    await message.answer(
        (
            f"<b>{escape(lbl)}</b>\n\n"
            "Галерея пока не добавлена.\n"
            "Чуть позже здесь появятся фотографии с подписями."
        ),
        parse_mode="HTML",
    )


@router.message(F.text.in_({"📅 Записаться", "📲 Записаться", "📅 Онлайн-запись"}))
async def launch_booking_webapp(message: types.Message):
    await message.answer(
        "📅 <b>Онлайн-запись</b>\n\nВыберите удобное время и оформите запись онлайн.",
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


@router.message(F.text.in_({"📋 Мои записи", "🗓 Мои визиты"}))
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
                "Если захотите, откройте вкладку «История записей» или оформите новый визит."
            ),
            parse_mode="HTML",
        )
        return

    for booking_id, name, phone, date, time, status in active_bookings:
        await message.answer(
            format_user_booking_text(name, phone, date, time, status=status),
            reply_markup=keyboards.get_cancel_keyboard(message.from_user.id, booking_id),
            parse_mode="HTML",
        )

@router.message(F.text.in_({"🕘 История", "🕰 История записей"}))
async def booking_history_handler(message: types.Message):
    await database.sync_completed_bookings()
    bookings = await database.get_user_bookings(message.from_user.id)
    history_bookings = [booking for booking in bookings if booking[5] != "scheduled"][:USER_HISTORY_LIMIT]

    if not history_bookings:
        await message.answer(
            "🕰 <b>История пока пуста</b>\n\nЗдесь будут храниться все ваши завершённые и отменённые визиты.",
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


@router.callback_query(F.data.regexp(r"^resched_\d+_\d+$"))
async def start_reschedule_callback(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Не удалось определить запись.", show_alert=True)
        return

    user_id_str = parts[1]
    if str(callback.from_user.id) != user_id_str:
        await callback.answer("Это не ваша запись.", show_alert=True)
        return

    try:
        booking_id = int(parts[2])
    except ValueError:
        await callback.answer("Не удалось определить запись.", show_alert=True)
        return

    booking = await database.get_booking_record_by_id(booking_id)
    if not booking:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    _id, _user_id, name, phone, current_date, current_time, status, duration = booking
    if status != "scheduled":
        await callback.answer("Эту запись уже нельзя перенести.", show_alert=True)
        return

    date_options = await _build_reschedule_date_options(int(duration or 60))
    if not date_options:
        await callback.answer("Свободных дат для переноса сейчас нет.", show_alert=True)
        return

    await state.set_state(RescheduleBookingForm.waiting_for_date)
    await state.update_data(
        booking_id=booking_id,
        booking_name=name,
        booking_phone=phone,
        current_date=current_date,
        current_time=current_time,
        duration=int(duration or 60),
    )
    await callback.answer()
    await callback.message.answer(
        (
            "🔁 <b>Перенос записи</b>\n\n"
            f"<b>Сейчас:</b> {current_date} в {current_time}\n"
            "Выберите новую дату:"
        ),
        parse_mode="HTML",
        reply_markup=keyboards.get_reschedule_dates_keyboard(booking_id, date_options),
    )


@router.callback_query(F.data.startswith("resched_date_"))
async def reschedule_date_callback(callback: types.CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    parts = callback.data.split("_", 3)
    if len(parts) != 4:
        await callback.answer("Не удалось определить дату.", show_alert=True)
        return

    booking_id = int(parts[2])
    date_value = parts[3]
    if state_data.get("booking_id") != booking_id:
        await callback.answer("Сессия переноса устарела. Начните заново.", show_alert=True)
        return

    time_options = await _build_reschedule_time_options(
        date_value,
        int(state_data["duration"]),
        current_date=state_data.get("current_date"),
        current_time=state_data.get("current_time"),
    )
    if not time_options:
        await callback.answer("На эту дату нет свободного времени.", show_alert=True)
        return

    await state.set_state(RescheduleBookingForm.waiting_for_time)
    await state.update_data(new_date=date_value)
    await callback.answer()
    await callback.message.edit_text(
        (
            "🔁 <b>Перенос записи</b>\n\n"
            f"<b>Новая дата:</b> {date_value}\n"
            "Выберите новое время:"
        ),
        parse_mode="HTML",
        reply_markup=keyboards.get_reschedule_times_keyboard(booking_id, date_value, time_options),
    )


@router.callback_query(F.data.startswith("resched_time_"))
async def reschedule_time_callback(callback: types.CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    parts = callback.data.split("_", 4)
    if len(parts) != 5:
        await callback.answer("Не удалось определить время.", show_alert=True)
        return

    booking_id = int(parts[2])
    date_value = parts[3]
    time_value = parts[4]
    if state_data.get("booking_id") != booking_id:
        await callback.answer("Сессия переноса устарела. Начните заново.", show_alert=True)
        return

    await state.set_state(RescheduleBookingForm.waiting_for_confirmation)
    await state.update_data(new_date=date_value, new_time=time_value)
    await callback.answer()
    await callback.message.edit_text(
        (
            "🔁 <b>Подтвердите перенос</b>\n\n"
            f"<b>Было:</b> {state_data['current_date']} в {state_data['current_time']}\n"
            f"<b>Станет:</b> {date_value} в {time_value}"
        ),
        parse_mode="HTML",
        reply_markup=keyboards.get_reschedule_confirm_keyboard(booking_id, date_value, time_value),
    )


@router.callback_query(F.data.startswith("resched_confirm_"))
async def reschedule_confirm_callback(callback: types.CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    parts = callback.data.split("_", 4)
    if len(parts) != 5:
        await callback.answer("Не удалось подтвердить перенос.", show_alert=True)
        return

    booking_id = int(parts[2])
    date_value = parts[3]
    time_value = parts[4]
    if state_data.get("booking_id") != booking_id:
        await callback.answer("Сессия переноса устарела. Начните заново.", show_alert=True)
        return

    remaining = get_rate_limit_remaining(f"reschedule_confirm:{callback.from_user.id}", cooldown_seconds=4)
    if remaining > 0:
        await callback.answer(f"Слишком быстро. Повторите через {remaining} сек.", show_alert=True)
        return

    booking = await database.get_booking_record_by_id(booking_id)
    if not booking:
        await callback.answer("Запись не найдена.", show_alert=True)
        await state.clear()
        return

    _id, _user_id, name, phone, _current_date, _current_time, status, _duration = booking
    if status != "scheduled":
        await callback.answer("Эту запись уже нельзя перенести.", show_alert=True)
        await state.clear()
        return

    moved = await database.reschedule_booking_if_available(booking_id, date_value, time_value)
    if not moved:
        await callback.answer("Этот слот уже занят. Выберите другое время.", show_alert=True)
        return

    admin_id = getenv("ADMIN_ID")
    if admin_id:
        await callback.bot.send_message(
            admin_id,
            (
                "🔁 <b>Запись перенесена</b>\n\n"
                f"<b>Клиент:</b> {name}\n"
                f"<b>Телефон:</b> {phone}\n"
                f"<b>Было:</b> {state_data['current_date']} в {state_data['current_time']}\n"
                f"<b>Стало:</b> {date_value} в {time_value}"
            ),
            parse_mode="HTML",
        )

    await callback.answer("Запись перенесена")
    await callback.message.edit_text(
        (
            "✅ <b>Запись перенесена</b>\n\n"
            f"<b>Новая дата:</b> {date_value}\n"
            f"<b>Новое время:</b> {time_value}"
        ),
        parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(F.data.startswith("resched_cancel_"))
async def reschedule_cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Перенос отменён")
    await callback.message.edit_text(
        "❌ <b>Перенос отменён</b>\n\nЕсли нужно, вы можете открыть перенос заново из карточки записи.",
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
