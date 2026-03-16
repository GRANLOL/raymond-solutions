import unittest

import bot_keyboards.common as common_keyboards
import bot_keyboards.catalog as catalog_keyboards
import bot_keyboards.menus as menu_keyboards


class KeyboardTests(unittest.TestCase):
    def test_get_main_menu_adds_admin_button(self):
        base_markup = menu_keyboards.get_main_menu(is_admin=False)
        extended_markup = menu_keyboards.get_main_menu(is_admin=True)

        base_count = sum(len(row) for row in base_markup.keyboard)
        extended_count = sum(len(row) for row in extended_markup.keyboard)

        self.assertGreater(extended_count, base_count)
        self.assertIsNone(base_markup.keyboard[0][0].web_app)
        labels = [button.text for row in base_markup.keyboard for button in row]
        self.assertIn("🕘 История", labels)
        self.assertNotIn("🔐 Конфиденциальность", labels)

    def test_build_category_tree_avoids_infinite_recursion_with_cycle(self):
        categories = [
            {"id": 1, "name": "Root", "parent_id": None},
            {"id": 2, "name": "Child", "parent_id": 1},
            {"id": 1, "name": "RootAgain", "parent_id": 2},
        ]

        tree = catalog_keyboards.build_category_tree(categories)

        self.assertTrue(len(tree) >= 2)

    def test_get_services_keyboard_adds_navigation_and_create_button(self):
        services = [{"id": index, "name": f"Service {index}", "price": str(index), "category_name": None} for index in range(25)]

        markup = catalog_keyboards.get_services_keyboard(services, page=0, page_size=20)
        callback_data = [button.callback_data for row in markup.inline_keyboard for button in row]

        self.assertIn("srv_page_1", callback_data)
        self.assertIn("add_service", callback_data)

    def test_get_booking_launch_keyboard_uses_inline_web_app_button(self):
        markup = common_keyboards.get_booking_launch_keyboard()
        button = markup.inline_keyboard[0][0]

        self.assertIsNotNone(button.web_app)

    def test_get_cancel_keyboard_adds_reschedule_button(self):
        markup = common_keyboards.get_cancel_keyboard(7, 15)
        first_row = markup.inline_keyboard[0]

        self.assertEqual(first_row[0].callback_data, "cancel_7_15")
        self.assertEqual(first_row[1].callback_data, "resched_7_15")

    def test_admin_booking_actions_prefers_telegram_link_when_user_id_exists(self):
        markup = common_keyboards.get_admin_booking_actions_keyboard(
            10,
            "+7 (777) 123-45-67",
            "today",
            0,
            telegram_user_id=123456789,
        )

        first_row = markup.inline_keyboard[0]
        self.assertEqual(first_row[0].url, "tg://user?id=123456789")
        self.assertEqual(first_row[1].callback_data, "show_phone_77771234567")

    def test_admin_booking_actions_include_no_show_for_scheduled(self):
        markup = common_keyboards.get_admin_booking_actions_keyboard(10, "+7 (777) 123-45-67", "today", 0)
        callback_data = [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]

        self.assertIn("admin_booking_status_10_no_show_today_0", callback_data)
