import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("CONFIG_PATH", PROJECT_ROOT / "config.json")).resolve()
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", PROJECT_ROOT / "bookings.db")).resolve()
PORT = int(os.getenv("PORT", "8000"))

with CONFIG_PATH.open(mode="r", encoding="utf-8") as f:
    salon_config = json.load(f)

def update_config(key: str, value):
    salon_config[key] = value
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open(mode="w", encoding="utf-8") as f:
        json.dump(salon_config, f, ensure_ascii=False, indent=2)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
WEBAPP_URL = os.getenv("WEBAPP_URL", salon_config.get("webapp_url", "https://granlol.github.io/manicure-webapp/"))


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


WEBAPP_AUTH_REQUIRED = _as_bool(
    os.getenv("WEBAPP_AUTH_REQUIRED"),
    salon_config.get("webapp_auth_required", True),
)

if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN provided in the .env file")

if not ADMIN_ID:
    raise ValueError("No ADMIN_ID provided in the .env file")
else:
    try:
        ADMIN_ID = int(ADMIN_ID)
    except ValueError:
        raise ValueError("ADMIN_ID must be an integer")
