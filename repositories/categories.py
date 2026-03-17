from __future__ import annotations

from .base import aiosqlite, db_connect

async def add_category(name: str, parent_id: int | None = None):
    async with db_connect() as db:
        await db.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
        await db.commit()

async def get_all_categories():
    async with db_connect() as db:
        async with db.execute("SELECT id, name, parent_id FROM categories") as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "parent_id": r[2]} for r in rows]

async def get_category_by_id(category_id: int):
    async with db_connect() as db:
        async with db.execute("SELECT id, name, parent_id FROM categories WHERE id = ?", (category_id,)) as cursor:
            r = await cursor.fetchone()
            if r:
                return {"id": r[0], "name": r[1], "parent_id": r[2]}
            return None

async def get_category_descendant_ids(category_id: int) -> set[int]:
    categories = await get_all_categories()
    children_by_parent: dict[int | None, list[int]] = {}
    for category in categories:
        children_by_parent.setdefault(category["parent_id"], []).append(category["id"])

    descendants: set[int] = set()
    stack = list(children_by_parent.get(category_id, []))
    while stack:
        current_id = stack.pop()
        if current_id in descendants:
            continue
        descendants.add(current_id)
        stack.extend(children_by_parent.get(current_id, []))
    return descendants

async def update_category_name(category_id: int, name: str):
    async with db_connect() as db:
        await db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        await db.commit()

async def update_category_parent(category_id: int, parent_id: int | None):
    if parent_id == category_id:
        raise ValueError("Category cannot be its own parent")

    if parent_id is not None:
        parent = await get_category_by_id(parent_id)
        if not parent:
            raise ValueError("Parent category does not exist")

        descendants = await get_category_descendant_ids(category_id)
        if parent_id in descendants:
            raise ValueError("Category cannot be moved under its descendant")

    async with db_connect() as db:
        await db.execute("UPDATE categories SET parent_id = ? WHERE id = ?", (parent_id, category_id))
        await db.commit()

async def delete_category(category_id: int):
    async with db_connect() as db:
        async with db.execute("SELECT parent_id FROM categories WHERE id = ?", (category_id,)) as cursor:
            row = await cursor.fetchone()
        parent_id = row[0] if row else None

        await db.execute("UPDATE services SET category_id = NULL WHERE category_id = ?", (category_id,))
        await db.execute("UPDATE categories SET parent_id = ? WHERE parent_id = ?", (parent_id, category_id))
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()
