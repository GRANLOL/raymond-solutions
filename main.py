import asyncio
import hashlib
import hmac
import logging
import sys
import time
from urllib.parse import parse_qsl

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from config import BOT_TOKEN, salon_config
from database import init_db, get_all_busy_slots, get_all_services, get_all_categories, get_all_masters
from handlers import router
from reminders import start_scheduler

# Setup basic logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "https://granlol.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_telegram_init_data(init_data: str) -> bool:
    if not init_data:
        return False

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return False

    auth_date = data.get("auth_date")
    if not auth_date:
        return False

    try:
        if time.time() - int(auth_date) > 86400:
            return False
    except ValueError:
        return False

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated_hash, received_hash)


def require_webapp_auth(x_telegram_init_data: str | None) -> None:
    if not verify_telegram_init_data(x_telegram_init_data or ""):
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/busy-slots")
async def get_busy_slots(master_id: int = None, x_telegram_init_data: str | None = Header(default=None)) -> dict:
    require_webapp_auth(x_telegram_init_data)
    busy_slots = await get_all_busy_slots(master_id)
    return busy_slots if busy_slots else {}

@app.get("/api/get-content")
async def get_content(x_telegram_init_data: str | None = Header(default=None)) -> dict:
    require_webapp_auth(x_telegram_init_data)
    services = await get_all_services()
    categories = await get_all_categories()
    masters = await get_all_masters()
    use_masters = salon_config.get("use_masters", False)
    booking_window = salon_config.get("booking_window", 7)
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    working_hours = salon_config.get("working_hours", "10:00-20:00")
    schedule_interval = salon_config.get("schedule_interval", 30)
    timezone_offset = salon_config.get("timezone_offset", 3)
    
    return {
        "services": services,
        "categories": categories,
        "masters": masters,
        "use_masters": use_masters,
        "booking_window": booking_window,
        "working_days": working_days,
        "blacklisted_dates": blacklisted_dates,
        "working_hours": working_hours,
        "schedule_interval": schedule_interval,
        "timezone_offset": timezone_offset
    }

async def main():
    # Initialize the database
    await init_db()
    logging.info("Database initialized.")

    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Include the router from handlers.py
    dp.include_router(router)
    
    # Set bot commands in the menu
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню")
    ])

    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    
    logging.info("Starting bot polling and FastAPI server...")
    
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            server.serve(),
            start_scheduler(bot),
        )
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
