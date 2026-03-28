import database
from money import format_money


async def build_stats_report(period_days: int, period_label: str) -> str:
    revenue = await database.get_revenue_stats(period_days)
    status_stats = await database.get_booking_status_stats(period_days)
    source_stats = await database.get_source_stats(period_days)
    top_services = await database.get_top_services(period_days, limit=5)
    weekday_stats = await database.get_bookings_by_weekday(period_days)
    peak_hours = await database.get_peak_hours(period_days, top_n=3)
    clients = await database.get_client_stats(period_days)

    lines = [f"📊 <b>Статистика: {period_label}</b>\n"]

    lines.append("💰 <b>Выручка:</b>")
    total = revenue["total_revenue"]
    count = revenue["total_bookings"]
    avg = revenue["avg_price"]
    lines.append(f"  Выполнено: {count} | Сумма: {format_money(total)} | Средний чек: {format_money(avg)}\n")

    lines.append("🧾 <b>Статусы записей:</b>")
    lines.append(
        "  "
        f"Выполнено: {status_stats['completed']} | "
        f"Отменено: {status_stats['cancelled']} | "
        f"Не пришли: {status_stats['no_show']}\n"
    )

    if top_services:
        lines.append("🏆 <b>Топ услуг:</b>")
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (name, cnt) in enumerate(top_services):
            medal = medals[i] if i < len(medals) else f"{i + 1}."
            lines.append(f"  {medal} {name} - {cnt} записей")
        lines.append("")
    else:
        lines.append("🏆 <b>Топ услуг:</b> нет данных\n")

    busy_days = {k: v for k, v in weekday_stats.items() if v > 0}
    if busy_days:
        lines.append("🗓 <b>Загруженность по дням:</b>")
        day_parts = " | ".join(f"{day}: {cnt}" for day, cnt in busy_days.items())
        lines.append(f"  {day_parts}\n")

    if peak_hours:
        lines.append("⏰ <b>Пиковые часы:</b>")
        hour_parts = ", ".join(f"{h} ({c} зап.)" for h, c in peak_hours)
        lines.append(f"  {hour_parts}\n")

    if source_stats:
        lines.append("📍 <b>Источники записей:</b>")
        source_parts = " | ".join(f"{source}: {count}" for source, count in sorted(source_stats.items()))
        lines.append(f"  {source_parts}\n")

    lines.append("👥 <b>Клиенты:</b>")
    lines.append(f"  Новых: {clients['new']} | Повторных: {clients['returning']}")

    return "\n".join(lines)
