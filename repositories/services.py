from __future__ import annotations

import re

from .base import db_connect


def _parse_price_value(price) -> int:
    price_digits = re.sub(r"\D", "", str(price or ""))
    return int(price_digits) if price_digits else 0

async def add_service(name: str, price: str, duration: int = 60, description: str = "", category_id: int | None = None):
    async with db_connect() as db:
        await db.execute("INSERT INTO services (name, price, duration, description, category_id) VALUES (?, ?, ?, ?, ?)", (name, price, duration, description, category_id))
        await db.commit()

async def update_service_category(service_id: int, category_id: int | None):
    async with db_connect() as db:
        await db.execute("UPDATE services SET category_id = ? WHERE id = ?", (category_id, service_id))
        await db.commit()

async def update_service_name(service_id: int, name: str):
    async with db_connect() as db:
        await db.execute("UPDATE services SET name = ? WHERE id = ?", (name, service_id))
        await db.commit()

async def update_service_price(service_id: int, price: str):
    async with db_connect() as db:
        await db.execute("UPDATE services SET price = ? WHERE id = ?", (price, service_id))
        await db.commit()

async def get_service_by_id(service_id: int):
    async with db_connect() as db:
        async with db.execute("""
            SELECT s.id, s.name, s.price, s.duration, s.description, s.category_id, c.name
            FROM services s
            LEFT JOIN categories c ON s.category_id = c.id
            WHERE s.id = ?
        """, (service_id,)) as cursor:
            r = await cursor.fetchone()
            if r:
                return {
                    "id": r[0],
                    "name": r[1],
                    "price": r[2],
                    "price_value": _parse_price_value(r[2]),
                    "duration": r[3],
                    "description": r[4],
                    "category_id": r[5],
                    "category_name": r[6],
                }
            return None

async def get_service_by_name(service_name: str):
    async with db_connect() as db:
        async with db.execute("""
            SELECT s.id, s.name, s.price, s.duration, s.description, s.category_id, c.name
            FROM services s
            LEFT JOIN categories c ON s.category_id = c.id
            WHERE lower(trim(s.name)) = lower(trim(?))
            LIMIT 1
        """, (service_name,)) as cursor:
            row = await cursor.fetchone()

    if not row:
        return None

    price_text = row[2] or ""
    price_value = _parse_price_value(price_text)

    return {
        "id": row[0],
        "name": row[1],
        "price": row[2],
        "price_value": price_value,
        "duration": row[3],
        "description": row[4],
        "category_id": row[5],
        "category_name": row[6],
    }

async def get_all_services():
    async with db_connect() as db:
        async with db.execute("""
            SELECT s.id, s.name, s.price, s.duration, s.description, s.category_id, c.name
            FROM services s
            LEFT JOIN categories c ON s.category_id = c.id
        """) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "price": r[2],
                    "price_value": _parse_price_value(r[2]),
                    "duration": r[3],
                    "description": r[4],
                    "category_id": r[5],
                    "category_name": r[6],
                }
                for r in rows
            ]

async def delete_service(service_id: int):
    async with db_connect() as db:
        await db.execute("DELETE FROM services WHERE id = ?", (service_id,))
        await db.commit()

async def delete_all_services():
    async with db_connect() as db:
        await db.execute("DELETE FROM services")
        await db.commit()

async def update_service_duration(service_id: int, duration: int):
    async with db_connect() as db:
        await db.execute("UPDATE services SET duration=? WHERE id=?", (duration, service_id))
        await db.commit()
