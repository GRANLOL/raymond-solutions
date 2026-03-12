import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from config import BOT_TOKEN, salon_config
from database import init_db, get_all_busy_slots, get_all_services, get_all_time_slots, get_all_categories, get_all_masters
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

@app.get("/api/busy-slots")
async def get_busy_slots(master_id: int = None) -> dict:
    busy_slots = await get_all_busy_slots(master_id)
    return busy_slots if busy_slots else {}

@app.get("/api/get-content")
async def get_content() -> dict:
    services = await get_all_services()
    categories = await get_all_categories()
    time_slots = await get_all_time_slots()
    masters = await get_all_masters()
    use_masters = salon_config.get("use_masters", False)
    booking_window = salon_config.get("booking_window", 7)
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    return {
        "services": services,
        "categories": categories,
        "time_slots": time_slots,
        "masters": masters,
        "use_masters": use_masters,
        "booking_window": booking_window,
        "working_days": working_days,
        "blacklisted_dates": blacklisted_dates
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
