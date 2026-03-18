import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from booking_service import create_booking_and_notify
from booking_validation import validate_web_booking
from bot_handlers import router
from config import BOT_TOKEN, PORT, WEBAPP_AUTH_REQUIRED, WEBAPP_URL, salon_config
from database import get_all_busy_slots, get_all_categories, get_all_services, init_db
from logging_utils import configure_logging
from rate_limit import get_rate_limit_remaining
from reminders import start_scheduler
from webapp_security import allowed_origins, get_init_data_validation_error, get_user_from_init_data

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized.")
    yield


app = FastAPI(lifespan=lifespan)
app.state.bot = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(WEBAPP_URL),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "X-Telegram-Init-Data", "ngrok-skip-browser-warning"],
)


def require_webapp_auth(x_telegram_init_data: str | None) -> None:
    if not WEBAPP_AUTH_REQUIRED:
        return
    error = get_init_data_validation_error(x_telegram_init_data or "", BOT_TOKEN)
    if error is not None:
        logger.warning(
            "WebApp auth rejected: %s (header_present=%s, init_data_len=%s)",
            error,
            x_telegram_init_data is not None,
            len(x_telegram_init_data or ""),
        )
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/api/health")
async def healthcheck() -> dict:
    return {
        "ok": True,
        "webapp_auth_required": WEBAPP_AUTH_REQUIRED,
        "bot_ready": app.state.bot is not None,
    }


@app.get("/api/busy-slots")
async def get_busy_slots(x_telegram_init_data: str | None = Header(default=None)) -> dict:
    require_webapp_auth(x_telegram_init_data)
    busy_slots = await get_all_busy_slots()
    return busy_slots if busy_slots else {}


@app.get("/api/get-content")
async def get_content(x_telegram_init_data: str | None = Header(default=None)) -> dict:
    require_webapp_auth(x_telegram_init_data)
    services = await get_all_services()
    categories = await get_all_categories()
    booking_window = salon_config.get("booking_window", 7)
    working_days = salon_config.get("working_days", [1, 2, 3, 4, 5, 6, 0])
    blacklisted_dates = salon_config.get("blacklisted_dates", [])
    working_hours = salon_config.get("working_hours", "10:00-20:00")
    schedule_interval = salon_config.get("schedule_interval", 30)
    timezone_offset = salon_config.get("timezone_offset", 3)
    show_service_duration = bool(salon_config.get("show_service_duration", True))
    currency_symbol = salon_config.get("currency_symbol", "₸")

    return {
        "services": services,
        "categories": categories,
        "booking_window": booking_window,
        "working_days": working_days,
        "blacklisted_dates": blacklisted_dates,
        "working_hours": working_hours,
        "schedule_interval": schedule_interval,
        "timezone_offset": timezone_offset,
        "currency_symbol": currency_symbol,
        "show_service_duration": show_service_duration,
    }


@app.post("/api/bookings")
async def create_booking(payload: dict, x_telegram_init_data: str | None = Header(default=None)) -> dict:
    require_webapp_auth(x_telegram_init_data)
    user = get_user_from_init_data(x_telegram_init_data or "")
    if not user or "id" not in user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    remaining = get_rate_limit_remaining(f"api_booking:{user['id']}", cooldown_seconds=8)
    if remaining > 0:
        raise HTTPException(status_code=429, detail=f"Слишком много попыток. Повторите через {remaining} сек.")

    validated, error_text = await validate_web_booking(payload)
    if error_text:
        raise HTTPException(status_code=400, detail=error_text)

    success, message = await create_booking_and_notify(
        bot=app.state.bot,
        user_id=int(user["id"]),
        user_full_name=user.get("first_name") or user.get("username") or "Telegram user",
        service=validated["service"]["name"],
        date=validated["date"],
        time=validated["time"],
        duration=validated["duration"],
        phone=validated["phone"],
        name=validated["name"],
        price=validated["price"],
    )
    if not success:
        raise HTTPException(status_code=409, detail=message)
    return {"ok": True, "message": message}


async def main():
    bot = Bot(token=BOT_TOKEN)
    app.state.bot = bot
    dp = Dispatcher()
    dp.include_router(router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню")
    ])

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT)
    server = uvicorn.Server(config)
    scheduler_task = asyncio.create_task(start_scheduler(bot))

    logging.info("Starting bot polling and FastAPI server...")

    try:
        await asyncio.gather(
            dp.start_polling(bot),
            server.serve(),
        )
    finally:
        scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scheduler_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
