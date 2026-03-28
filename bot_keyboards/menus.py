from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu(is_admin: bool = False):
    from config import salon_config

    address_btn_text = salon_config.get("custom_btn_address_lbl", "📌 Адрес и контакты")
    portfolio_btn_text = salon_config.get("custom_btn_portfolio_lbl", "🖼 Примеры работ")
    portfolio_enabled = salon_config.get("custom_btn_portfolio_enabled", True)

    row2 = [KeyboardButton(text="💎 Услуги и цены")]
    if portfolio_enabled:
        row2.append(KeyboardButton(text=portfolio_btn_text))

    keyboard = [
        [KeyboardButton(text="🗓 Онлайн-запись")],
        row2,
        [KeyboardButton(text=address_btn_text), KeyboardButton(text="🗓 Актуальные записи")],
        [KeyboardButton(text="🕘 История")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Панель управления")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🗓 На сегодня"), KeyboardButton(text="🗓 Все записи"), KeyboardButton(text="📁 Категории")],
        [KeyboardButton(text="⚙️ Услуги")],
        [KeyboardButton(text="➕ Внести запись"), KeyboardButton(text="🕒 Свободные окна")],
        [KeyboardButton(text="📅 По дате")],
        [KeyboardButton(text="🗓 График"), KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="📃 Excel")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🗑 Очистить"), KeyboardButton(text="🔎 Поиск")],
        [KeyboardButton(text="👤 Меню клиента")],
    ],
    resize_keyboard=True,
)
