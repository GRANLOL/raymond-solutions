from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu(is_admin: bool = False):
    from config import salon_config
    address_btn_text = salon_config.get("custom_btn_address_lbl", "📍 Адрес и контакты")
    portfolio_btn_text = salon_config.get("custom_btn_portfolio_lbl", "💅 Примеры работ")
    
    keyboard = [
        [KeyboardButton(text="📅 Онлайн-запись")],
        [KeyboardButton(text="💎 Услуги и цены"), KeyboardButton(text=portfolio_btn_text)],
        [KeyboardButton(text=address_btn_text), KeyboardButton(text="🗓 Мои визиты")],
        [KeyboardButton(text="🕰 История записей")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Панель управления")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🗓 На сегодня"), KeyboardButton(text="🗓 Все записи"), KeyboardButton(text="📁 Категории")],
        [KeyboardButton(text="⚙️ Услуги")],
        [KeyboardButton(text="🗓 График"), KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="📃 Excel")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🗑 Очистить"), KeyboardButton(text="🔎 Поиск")],
        [KeyboardButton(text="👤 Меню клиента")],
    ],
    resize_keyboard=True,
)
