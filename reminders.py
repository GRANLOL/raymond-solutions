import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot

from database import get_bookings_for_reminders, update_reminder_level
from keyboards import get_reminder_keyboard

async def check_reminders(bot: Bot):
    try:
        now = datetime.now()
        # Fetch bookings that haven't received the final reminder yet (level < 2)
        bookings = await get_bookings_for_reminders(2)

        for b in bookings:
            b_id, user_id, name, date_str, time_str, master_name, reminder_level = b
            try:
                booking_dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
            except ValueError:
                continue
                
            time_diff = booking_dt - now
            hours_until = time_diff.total_seconds() / 3600.0

            if hours_until < 0:
                continue

            master_display = master_name if master_name else "Мастер салона"

            # 24-hour reminder
            if reminder_level == 0 and hours_until <= 24:
                msg = (f"Здравствуйте, {name}! 📬\n\n"
                       f"Напоминаем о вашей записи на маникюр к мастеру *{master_display}*\n"
                       f"Завтра ({date_str}) в {time_str}.\n\n"
                       f"Будем вас ждать!")
                try:
                    await bot.send_message(user_id, text=msg, reply_markup=get_reminder_keyboard(b_id), parse_mode="Markdown")
                    await update_reminder_level(b_id, 1)
                except Exception as e:
                    logging.error(f"Failed to send 24h reminder to {user_id}: {e}")

            # 3-hour reminder
            elif reminder_level == 1 and hours_until <= 3:
                msg = (f"Здравствуйте, {name}! ⏳\n\n"
                       f"Напоминаем, что ваша запись к мастеру *{master_display}* состоится уже скоро!\n"
                       f"Сегодня ({date_str}) в {time_str}.\n\n"
                       f"До встречи!")
                try:
                    await bot.send_message(user_id, text=msg, reply_markup=get_reminder_keyboard(b_id), parse_mode="Markdown")
                    await update_reminder_level(b_id, 2)
                except Exception as e:
                    logging.error(f"Failed to send 3h reminder to {user_id}: {e}")
                    
    except Exception as e:
        logging.error(f"Error in check_reminders: {e}")

async def start_scheduler(bot: Bot):
    """Background task to check for upcoming bookings periodically."""
    logging.info("Reminder scheduler started.")
    while True:
        try:
            await check_reminders(bot)
        except Exception as e:
            logging.error(f"Scheduler loop error: {e}")
        
        # Checking every 15 minutes
        await asyncio.sleep(15 * 60)
