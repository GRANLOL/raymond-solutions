import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

import bot_handlers
import main


class AppSmokeTests(unittest.IsolatedAsyncioTestCase):
    def test_router_is_aggregated(self):
        self.assertGreater(len(bot_handlers.router.sub_routers), 0)

    def test_require_webapp_auth_rejects_invalid_data(self):
        with patch.object(main, "WEBAPP_AUTH_REQUIRED", True), \
             patch.object(main, "get_init_data_validation_error", return_value="hash mismatch"):
            with self.assertRaises(HTTPException) as ctx:
                main.require_webapp_auth("bad")

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_get_content_returns_expected_shape(self):
        with patch.object(main, "require_webapp_auth"), \
             patch.object(main, "get_all_services", AsyncMock(return_value=[{"id": 1}])), \
             patch.object(main, "get_all_categories", AsyncMock(return_value=[{"id": 2}])):
            content = await main.get_content("init-data")

        self.assertIn("services", content)
        self.assertIn("categories", content)
        self.assertIn("booking_window", content)

    async def test_create_booking_returns_success_payload(self):
        with patch.object(main, "require_webapp_auth"), \
             patch.object(main, "get_user_from_init_data", return_value={"id": 5, "first_name": "Alice"}), \
             patch.object(main, "validate_web_booking", AsyncMock(return_value=({
                 "service": {"name": "Маникюр"},
                 "date": "15.03.2026",
                 "time": "10:00",
                 "duration": 60,
                 "phone": "+7 (777) 777-77-77",
                 "name": "Alice",
                 "price": 2500,
             }, None))), \
             patch.object(main, "create_booking_and_notify", AsyncMock(return_value=(True, "ok"))):
            payload = await main.create_booking({"service": "Маникюр"}, "init-data")

        self.assertEqual(payload, {"ok": True, "message": "ok"})
