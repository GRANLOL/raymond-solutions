from __future__ import annotations

from config import salon_config


def get_currency_symbol() -> str:
    return str(salon_config.get("currency_symbol", "₸")).strip() or "₸"


def format_money(value) -> str:
    try:
        amount = int(float(value or 0))
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:,} {get_currency_symbol()}".replace(",", " ")
