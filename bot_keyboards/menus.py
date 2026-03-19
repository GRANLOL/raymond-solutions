from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu(is_admin: bool = False):
    keyboard = [
        [KeyboardButton(text="📅 Записаться")],
        [KeyboardButton(text="💸 Прайс-лист"), KeyboardButton(text="🖼 Примеры работ")],
        [KeyboardButton(text="📌 Адрес"), KeyboardButton(text="📋 Мои записи")],
        [KeyboardButton(text="🕘 История")],
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
