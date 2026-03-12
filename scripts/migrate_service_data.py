"""
Migration script: backfill existing bookings with service_name and price
from the services table by matching the service name stored in the
`name` column of the bookings table (format: "Client Name (Service Name)").
"""

import asyncio
import aiosqlite
import re

async def migrate():
    async with aiosqlite.connect("bookings.db") as db:
        db.row_factory = aiosqlite.Row

        # Fetch all services into a lookup dict: name -> price
        async with db.execute("SELECT name, price FROM services") as cursor:
            services = await cursor.fetchall()

        service_prices = {}
        for s in services:
            name = s["name"]
            raw_price = s["price"] or "0"
            # Extract numeric part from price string like "1500 ₽" or "от 1200"
            numeric = re.sub(r"[^\d]", "", raw_price)
            price = int(numeric) if numeric else 0
            service_prices[name] = price

        print(f"Loaded {len(service_prices)} services from DB:")
        for n, p in service_prices.items():
            print(f"  {n!r} -> {p} ₽")

        # Fetch all bookings that are missing service_name
        async with db.execute("""
            SELECT id, name FROM bookings
            WHERE service_name IS NULL OR service_name = ''
        """) as cursor:
            bookings = await cursor.fetchall()

        print(f"\nFound {len(bookings)} bookings to update...")

        updated = 0
        for b in bookings:
            booking_id = b["id"]
            booking_name = b["name"] or ""

            # Format is "Client Name (Service Name)"
            match = re.search(r"\((.+)\)$", booking_name)
            if match:
                extracted_service = match.group(1).strip()
                price = service_prices.get(extracted_service, 0)
                await db.execute(
                    "UPDATE bookings SET service_name = ?, price = ? WHERE id = ?",
                    (extracted_service, price, booking_id)
                )
                print(f"  Booking #{booking_id}: service='{extracted_service}', price={price} ₽")
                updated += 1

        await db.commit()
        print(f"\n✅ Done! Updated {updated} / {len(bookings)} bookings.")

if __name__ == "__main__":
    asyncio.run(migrate())
