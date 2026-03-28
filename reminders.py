import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from html import escape

from aiogram import Bot

from backup_service import run_scheduled_backup_if_due
from config import salon_config
from database import (
    get_bookings_by_date_full,
    get_due_first_reminders,
    get_due_second_reminders,
    mark_first_reminder_sent,
    mark_second_reminder_sent,
    sync_completed_bookings,
)
from runtime_state import get_runtime_value, set_runtime_value
from time_utils import get_salon_now

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "instagram": "Instagram",
    "phone": "Звонок",
    "offline": "Офлайн",
    "manual": "Вручную",
}


def format_reminder(template: str, name: str, date: str, time: str) -> str:
    return template.replace("{name}", escape(name)).replace("{date}", escape(date)).replace("{time}", escape(time))


def _get_reminder_grace_delta() -> timedelta:
    minutes = int(salon_config.get("reminder_grace_minutes", 30) or 30)
    return timedelta(minutes=max(minutes, 0))


def _is_stale_reminder(now: datetime, due_at_iso: str | None) -> bool:
    if not due_at_iso:
        return False
    try:
        due_at = datetime.fromisoformat(due_at_iso)
    except ValueError:
        return False
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=now.tzinfo)
    return now - due_at > _get_reminder_grace_delta()


def _get_default_digest_hour() -> int:
    working_hours = str(salon_config.get("working_hours", "10:00-20:00") or "")
    match = re.search(r"(\d{1,2}):\d{2}", working_hours)
    return int(match.group(1)) if match else 9


def _get_digest_hour(config_key: str, default: int) -> int:
    raw = salon_config.get(config_key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _source_label(value: str | None) -> str:
    return SOURCE_LABELS.get((value or "").strip(), value or "—")


def _format_digest_message(
    *,
    title: str,
    target_date: str,
    bookings: list[tuple],
) -> str:
    lines = [
        f"📋 <b>{title}</b>",
        f"<b>Дата:</b> {target_date}",
        f"<b>Записей:</b> {len(bookings)}",
        "",
    ]

    for index, (name, phone, _date, time, price, service_name, source, notes, created_by_admin) in enumerate(bookings[:7], start=1):
        source_text = _source_label(source)
        origin_text = " · внесена вручную" if int(created_by_admin or 0) else ""
        service_text = service_name or "Без услуги"
        line = (
            f"{index}. {escape(name)} ({escape(service_text)}) — {escape(time)} — "
            f"{escape(phone)} — {escape(str(price or 0))} — {escape(source_text)}{origin_text}"
        )
        lines.append(line)
        if notes:
            lines.append(f"   <i>Комментарий: {escape(notes)}</i>")

    if len(bookings) > 7:
        lines.extend(["", f"<i>И ещё {len(bookings) - 7} записей.</i>"])

    return "\n".join(lines)


async def check_reminders(bot: Bot):
    try:
        await sync_completed_bookings()
        now = get_salon_now()
        now_iso = now.isoformat()

        first_due = await get_due_first_reminders(now_iso)
        for booking_id, user_id, name, date_str, time_str, due_at_iso in first_due:
            if _is_stale_reminder(now, due_at_iso):
                await mark_first_reminder_sent(booking_id, now_iso)
                logger.info("Skipped stale 24h reminder for booking %s", booking_id)
                continue
            template_1 = salon_config.get(
                "reminder_1_text",
                "🔔 <b>Здравствуйте, {name}!</b>\n\nНапоминаем, что вы записаны к нам на завтра <b>({date})</b> в <b>{time}</b>.\nЖдём вас! ✨",
            )
            msg = format_reminder(template_1, name, date_str, time_str)
            try:
                await bot.send_message(user_id, text=msg, parse_mode="HTML")
                await mark_first_reminder_sent(booking_id, now_iso)
            except Exception as exc:
                logger.error("Failed to send 24h reminder to %s: %s", user_id, exc)

        second_due = await get_due_second_reminders(now_iso)
        for booking_id, user_id, name, date_str, time_str, due_at_iso in second_due:
            if _is_stale_reminder(now, due_at_iso):
                await mark_second_reminder_sent(booking_id, now_iso)
                logger.info("Skipped stale configurable reminder for booking %s", booking_id)
                continue
            template_2 = salon_config.get(
                "reminder_2_text",
                "⏰ <b>Здравствуйте, {name}!</b>\n\nНапоминаем, что ваша запись состоится уже сегодня <b>({date})</b> в <b>{time}</b>.\nДо скорой встречи! 👋",
            )
            msg = format_reminder(template_2, name, date_str, time_str)
            try:
                await bot.send_message(user_id, text=msg, parse_mode="HTML")
                await mark_second_reminder_sent(booking_id, now_iso)
            except Exception as exc:
                logger.error("Failed to send configurable reminder to %s: %s", user_id, exc)
    except Exception as exc:
        logger.error("Error in check_reminders: %s", exc)


async def send_admin_daily_digest(bot: Bot) -> None:
    admin_target = os.getenv("ADMIN_ID") or salon_config.get("admin_id") or None
    if not admin_target:
        return

    salon_now = get_salon_now()
    digest_hour = _get_digest_hour("admin_digest_hour", _get_default_digest_hour())
    today_key = salon_now.date().isoformat()
    if salon_now.hour < digest_hour or get_runtime_value("last_admin_digest_date") == today_key:
        return

    today_str = salon_now.strftime("%d.%m.%Y")
    bookings = await get_bookings_by_date_full(today_str)
    set_runtime_value("last_admin_digest_date", today_key)
    if not bookings:
        return

    message = _format_digest_message(
        title="Сводка на сегодня",
        target_date=today_str,
        bookings=bookings,
    )
    await bot.send_message(admin_target, message, parse_mode="HTML")


async def send_admin_tomorrow_digest(bot: Bot) -> None:
    admin_target = os.getenv("ADMIN_ID") or salon_config.get("admin_id") or None
    if not admin_target:
        return

    salon_now = get_salon_now()
    digest_hour = _get_digest_hour("admin_tomorrow_digest_hour", 20)
    tomorrow = salon_now.date() + timedelta(days=1)
    tomorrow_key = tomorrow.isoformat()
    if salon_now.hour < digest_hour or get_runtime_value("last_admin_tomorrow_digest_date") == tomorrow_key:
        return

    tomorrow_str = tomorrow.strftime("%d.%m.%Y")
    bookings = await get_bookings_by_date_full(tomorrow_str)
    set_runtime_value("last_admin_tomorrow_digest_date", tomorrow_key)
    if not bookings:
        return

    message = _format_digest_message(
        title="Сводка на завтра",
        target_date=tomorrow_str,
        bookings=bookings,
    )
    await bot.send_message(admin_target, message, parse_mode="HTML")


async def run_maintenance(bot: Bot) -> None:
    backup_path = run_scheduled_backup_if_due()
    if backup_path is not None:
        logger.info("Scheduled backup created: %s", backup_path)

    try:
        await send_admin_daily_digest(bot)
    except Exception as exc:
        logger.error("Failed to send admin daily digest: %s", exc)

    try:
        await send_admin_tomorrow_digest(bot)
    except Exception as exc:
        logger.error("Failed to send admin tomorrow digest: %s", exc)


async def start_scheduler(bot: Bot):
    logger.info("Reminder scheduler started.")
    try:
        while True:
            try:
                await check_reminders(bot)
                await run_maintenance(bot)
            except Exception as exc:
                logger.error("Scheduler loop error: %s", exc)

            await asyncio.sleep(15 * 60)
    except asyncio.CancelledError:
        logger.info("Reminder scheduler stopped.")
        raise
