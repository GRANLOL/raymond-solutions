import re
from datetime import datetime, timedelta, timezone

import database
from config import salon_config


def parse_working_hours(working_hours: str) -> tuple[int, int]:
    match = re.search(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", working_hours or "")
    start_str, end_str = ("10:00", "20:00")
    if match:
        start_str, end_str = match.group(1), match.group(2)
    elif working_hours and "-" in working_hours:
        start_str, end_str = [part.strip() for part in working_hours.split("-", 1)]

    start_h, start_m = map(int, start_str.split(":"))
    end_h, end_m = map(int, end_str.split(":"))
    return start_h * 60 + start_m, end_h * 60 + end_m


def normalize_phone(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return None
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    elif not digits.startswith("7"):
        digits = "7" + digits
    if len(digits) != 11:
        return None
    return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"


def slot_overlaps(slot_start: int, slot_duration: int, busy_start: int, busy_duration: int) -> bool:
    slot_end = slot_start + slot_duration
    busy_end = busy_start + busy_duration
    return slot_start < busy_end and slot_end > busy_start


async def validate_web_booking(data: dict) -> tuple[dict | None, str | None]:
    service_name = (data.get("service") or "").strip()
    date_str = (data.get("date") or "").strip()
    time_str = (data.get("time") or "").strip()
    client_name = (data.get("name") or "").strip()
    phone = normalize_phone(data.get("phone"))

    if not service_name:
        return None, "Не удалось определить услугу. Выберите услугу заново."
    if not date_str or not time_str:
        return None, "Дата или время записи не указаны. Откройте форму и выберите слот заново."
    if not client_name:
        return None, "Укажите имя перед подтверждением записи."
    if not phone:
        return None, "Телефон указан в неверном формате. Используйте номер в формате +7."

    service = await database.get_service_by_name(service_name)
    if not service:
        return None, "Выбранная услуга больше недоступна. Обновите форму и попробуйте снова."

    duration = int(service.get("duration") or 60)
    price = int(service.get("price_value") or 0)

    use_masters = salon_config.get("use_masters", False)
    master_id = None
    if use_masters:
        master_id_raw = data.get("master_id")
        if master_id_raw in (None, ""):
            return None, "Сначала выберите мастера."
        try:
            master_id = int(master_id_raw)
        except (TypeError, ValueError):
            return None, "Передан некорректный мастер. Выберите мастера заново."

        master = await database.get_master_by_id(master_id)
        if not master:
            return None, "Выбранный мастер больше недоступен. Обновите форму и попробуйте снова."

    try:
        booking_date = datetime.strptime(date_str, "%d.%m.%Y").date()
        booking_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return None, "Дата или время переданы в неверном формате."

    tz_offset = salon_config.get("timezone_offset", 3)
    salon_tz = timezone(timedelta(hours=tz_offset))
    salon_now = datetime.now(timezone.utc).astimezone(salon_tz)
    booking_dt = datetime.combine(booking_date, booking_time, tzinfo=salon_tz)
    if booking_dt <= salon_now:
        return None, "Нельзя записаться на прошедшее время. Выберите другой слот."

    booking_window = max(int(salon_config.get("booking_window", 7) or 7), 1)
    last_allowed_date = salon_now.date() + timedelta(days=booking_window - 1)
    if booking_date > last_allowed_date:
        return None, "Эта дата находится вне доступного окна записи."

    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    js_weekday = (booking_date.weekday() + 1) % 7
    if js_weekday not in working_days:
        return None, "На выбранную дату запись недоступна. Выберите рабочий день."

    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    if date_str in blacklisted_dates:
        return None, "На выбранную дату запись отключена. Выберите другую дату."

    start_mins, end_mins = parse_working_hours(salon_config.get("working_hours", "10:00-20:00"))
    slot_mins = booking_time.hour * 60 + booking_time.minute
    if slot_mins < start_mins or slot_mins + duration > end_mins:
        return None, "Выбранное время вне рабочих часов. Обновите форму и выберите другой слот."

    interval = int(salon_config.get("schedule_interval", 30) or 30)
    if interval <= 0:
        interval = 30
    if (slot_mins - start_mins) % interval != 0:
        return None, "Выбранное время не соответствует шагу расписания. Обновите форму и выберите слот заново."

    busy_slots = await database.get_busy_slots_by_date(date_str, master_id=master_id)
    for busy in busy_slots:
        try:
            busy_h, busy_m = map(int, busy["time"].split(":"))
        except (KeyError, ValueError, AttributeError):
            continue

        busy_start = busy_h * 60 + busy_m
        busy_duration = int(busy.get("duration") or 60)
        if slot_overlaps(slot_mins, duration, busy_start, busy_duration):
            return None, "К сожалению, это время уже занято. Обновите форму и выберите другой слот."

    return {
        "service": service,
        "date": date_str,
        "time": time_str,
        "duration": duration,
        "price": price,
        "phone": phone,
        "name": client_name,
        "master_id": master_id,
    }, None
