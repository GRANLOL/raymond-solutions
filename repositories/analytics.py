from __future__ import annotations

from .base import _parse_booking_date, _period_start_date, aiosqlite, db_connect

async def _get_bookings_in_period(period_days: int):
    start_date = _period_start_date(period_days)
    end_date = _period_start_date(0)
    async with db_connect() as db:
        async with db.execute("""
            SELECT date, time, price, service_name, phone
            FROM bookings
        """) as cursor:
            rows = await cursor.fetchall()

    bookings = []
    for row in rows:
        booking_date = _parse_booking_date(row[0])
        if booking_date and start_date <= booking_date <= end_date:
            bookings.append({
                "date": booking_date,
                "time": row[1],
                "price": row[2],
                "service_name": row[3],
                "phone": row[4],
            })
    return bookings

async def get_revenue_stats(period_days: int) -> dict:
    bookings = await _get_bookings_in_period(period_days)
    prices = []
    for item in bookings:
        try:
            prices.append(int(float(item["price"] or 0)))
        except (TypeError, ValueError):
            prices.append(0)
    total_bookings = len(bookings)
    total_revenue = sum(prices)
    avg_price = int(total_revenue / total_bookings) if total_bookings else 0
    return {
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "avg_price": avg_price,
    }

async def get_top_services(period_days: int, limit: int = 5) -> list:
    from collections import Counter

    bookings = await _get_bookings_in_period(period_days)
    counter = Counter(
        item["service_name"]
        for item in bookings
        if item["service_name"]
    )
    return counter.most_common(limit)

async def get_bookings_by_weekday(period_days: int) -> dict:
    weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    result = {name: 0 for name in weekday_names}
    bookings = await _get_bookings_in_period(period_days)
    for item in bookings:
        result[weekday_names[item["date"].weekday()]] += 1
    return result

async def get_peak_hours(period_days: int, top_n: int = 3) -> list:
    from collections import Counter

    bookings = await _get_bookings_in_period(period_days)
    counter = Counter(item["time"] for item in bookings if item["time"])
    return counter.most_common(top_n)

async def get_client_stats(period_days: int) -> dict:
    period_bookings = await _get_bookings_in_period(period_days)
    period_phones = {item["phone"] for item in period_bookings if item["phone"]}
    period_start = _period_start_date(period_days)

    async with db_connect() as db:
        async with db.execute("SELECT phone, date FROM bookings") as cursor:
            rows = await cursor.fetchall()

    returning = set()
    for phone, date_str in rows:
        if phone not in period_phones:
            continue
        booking_date = _parse_booking_date(date_str)
        if booking_date and booking_date < period_start:
            returning.add(phone)

    new_clients = len(period_phones - returning)
    returning_clients = len(returning)
    return {"new": new_clients, "returning": returning_clients}
