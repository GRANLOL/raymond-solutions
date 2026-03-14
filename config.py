import os
import json
from dotenv import load_dotenv

load_dotenv()

with open("config.json", mode="r", encoding="utf-8") as f:
    salon_config = json.load(f)

def update_config(key: str, value):
    salon_config[key] = value
    with open("config.json", mode="w", encoding="utf-8") as f:
        json.dump(salon_config, f, ensure_ascii=False, indent=2)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
WEBAPP_URL = os.getenv("WEBAPP_URL", salon_config.get("webapp_url", "https://granlol.github.io/manicure-webapp/"))

if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN provided in the .env file")

if not ADMIN_ID:
    raise ValueError("No ADMIN_ID provided in the .env file")
else:
    try:
        ADMIN_ID = int(ADMIN_ID)
    except ValueError:
        raise ValueError("ADMIN_ID must be an integer")
