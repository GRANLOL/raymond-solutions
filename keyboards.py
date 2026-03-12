from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from datetime import datetime, timedelta
from config import salon_config

# Главное меню (обычные кнопки под строкой ввода)
def get_main_menu(is_admin: bool = False, is_master: bool = False):
    kb = [
        [KeyboardButton(text="🌸 Записаться", web_app=WebAppInfo(url="https://granlol.github.io/manicure-webapp/"))],
        [KeyboardButton(text="💸 Прайс-лист"), KeyboardButton(text="💅 Портфолио")],
        [KeyboardButton(text="📍 Адрес"), KeyboardButton(text="📋 Мои записи")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="⚙️ Панель управления")])
    if is_master:
        kb.append([KeyboardButton(text="💼 Панель мастера")])
        
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Меню администратора
admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🗓 На сегодня"), KeyboardButton(text="🗓 Все записи"), KeyboardButton(text="📁 Категории")],
        [KeyboardButton(text="⚙️ Услуги"), KeyboardButton(text="📅 Окно брони")],
        [KeyboardButton(text="📅 График"), KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="📁 Excel")],
        [KeyboardButton(text="🗑 Очистить"), KeyboardButton(text="👤 Меню клиента")]
    ],
    resize_keyboard=True
)

master_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Мои записи на сегодня"), KeyboardButton(text="🗓 Мои все записи")],
        [KeyboardButton(text="🔔 Настройка уведомлений")],
        [KeyboardButton(text="👤 Главное меню")]
    ],
    resize_keyboard=True
)

# Инлайн кнопка отмены
def get_cancel_keyboard(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"cancel_{user_id}")]
        ]
    )

def get_back_to_admin_menu_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_admin_menu"))
    return builder.as_markup()

def get_cancel_admin_action_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()

# Инлайн клавиатуры для управления услугами и временем
def get_services_keyboard(services, page: int = 0, page_size: int = 20):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    total = len(services)
    start = page * page_size
    end = min(start + page_size, total)
    page_services = services[start:end]
    
    for s in page_services:
        if isinstance(s, dict):
            name = s['name']
            s_id = s['id']
            cat_name = s.get('category_name')
        else:
            s_id = s[0]
            name = s[1]
            cat_name = s[5] if len(s) > 5 else None
            
        cat_info = f" [{cat_name}]" if cat_name else " [Своб.]"
        builder.row(InlineKeyboardButton(text=f"✏️ {name[:20]}{cat_info}", callback_data=f"edit_srv_{s_id}_{page}"))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"srv_page_{page - 1}"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"srv_page_{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data="add_service"))
    return builder.as_markup()

def get_service_edit_keyboard(service):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    s_id = service['id']
    cur_dur = service.get('duration', 60)
    builder.row(InlineKeyboardButton(text="📝 Изменить название", callback_data=f"eds_name_{s_id}"))
    builder.row(InlineKeyboardButton(text="💸 Изменить цену", callback_data=f"eds_price_{s_id}"))
    builder.row(InlineKeyboardButton(text=f"⏱ Изменить длительность ({cur_dur} м)", callback_data=f"eds_dur_{s_id}"))
    builder.row(InlineKeyboardButton(text="📁 Изменить категорию", callback_data=f"eds_cat_{s_id}"))
    builder.row(InlineKeyboardButton(text="❌ Удалить услугу", callback_data=f"del_srv_{s_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_services"))
    return builder.as_markup()

def get_time_slots_keyboard(time_slots):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for ts in time_slots:
        val = ts['time_value'] if isinstance(ts, dict) else ts[1]
        ts_id = ts['id'] if isinstance(ts, dict) else ts[0]
        builder.row(InlineKeyboardButton(text=f"❌ Удалить {val}", callback_data=f"del_ts_{ts_id}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить слоты", callback_data="add_time_slot"))
    return builder.as_markup()

def get_working_days_keyboard(working_days, blacklisted_dates=[]):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    # Map for JS day index -> Russian Name
    days_map = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 0: "Вс"}
    
    # We will build rows of 3 buttons for days
    row = []
    for day_idx in [1, 2, 3, 4, 5, 6, 0]:
        name = days_map[day_idx]
        is_active = day_idx in working_days
        text = f"{name} {'✅' if is_active else '❌'}"
        row.append(InlineKeyboardButton(text=text, callback_data=f"toggle_day_{day_idx}"))
        if len(row) == 3:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
        
    builder.row(InlineKeyboardButton(text="➕ Добавить выходную дату", callback_data="add_blacklist_date"))
    
    for date_str in blacklisted_dates:
        builder.row(InlineKeyboardButton(text=f"❌ Удалить выходной {date_str}", callback_data=f"del_bl_{date_str}"))
        
    return builder.as_markup()

def build_category_tree(categories, parent_id=None, depth=0):
    tree = []
    for c in categories:
        c_id = c['id'] if isinstance(c, dict) else c[0]
        p_id = c.get('parent_id') if isinstance(c, dict) else (c[2] if len(c) > 2 else None)
        
        if p_id == parent_id:
            tree.append((c, depth))
            tree.extend(build_category_tree(categories, c_id, depth + 1))
    return tree

def get_categories_keyboard(categories):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    tree = build_category_tree(categories)
    for c, depth in tree:
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        builder.row(InlineKeyboardButton(text=f"✏️ {prefix}{name[:20]}", callback_data=f"edit_cat_{c_id}"))
    builder.row(InlineKeyboardButton(text="➕ Создать категорию", callback_data="add_category"))
    builder.row(InlineKeyboardButton(text="➕ Создать подкатегорию", callback_data="add_subcategory_existing"))
    return builder.as_markup()

def get_category_edit_keyboard(category):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    c_id = category['id']
    builder.row(InlineKeyboardButton(text="📝 Изменить название", callback_data=f"edc_name_{c_id}"))
    builder.row(InlineKeyboardButton(text="🔄 Переместить", callback_data=f"move_cat_{c_id}"))
    builder.row(InlineKeyboardButton(text="➕ Создать подкатегорию", callback_data=f"wiz_addsub_{c_id}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data=f"wiz_addsrv_{c_id}"))
    builder.row(InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_cat_{c_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_categories"))
    return builder.as_markup()

def get_select_category_keyboard(categories):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    tree = build_category_tree(categories)
    for c, depth in tree:
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        builder.row(InlineKeyboardButton(text=f"{prefix}{name[:20]}", callback_data=f"sel_cat_{c_id}"))
        
    builder.row(InlineKeyboardButton(text="Без категории", callback_data="sel_cat_0"))
    return builder.as_markup()

def get_parent_category_keyboard(categories):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    tree = build_category_tree(categories)
    for c, depth in tree:
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        builder.row(InlineKeyboardButton(text=f"{prefix}{name[:20]}", callback_data=f"sel_parent_{c_id}"))
        
    builder.row(InlineKeyboardButton(text="Сделать основной (без родителя)", callback_data="sel_parent_0"))
    return builder.as_markup()

def get_wizard_keyboard(main_id, main_name, sub_id=None, sub_name=None, has_free_services=False):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    if sub_id:
        if has_free_services:
            builder.row(InlineKeyboardButton(text=f"📎 Добавить свободные услуги в '{sub_name[:15]}'", callback_data=f"wiz_attach_{sub_id}"))
        builder.row(InlineKeyboardButton(text=f"➕ Добавить новую услугу в '{sub_name[:15]}'", callback_data=f"wiz_addsrv_{sub_id}"))
        builder.row(InlineKeyboardButton(text=f"➕ Добавить еще подкатегорию в '{main_name[:15]}'", callback_data=f"wiz_addsub_{main_id}"))
    else:
        builder.row(InlineKeyboardButton(text=f"➕ Создать подкатегорию (внутри '{main_name[:15]}')", callback_data=f"wiz_addsub_{main_id}"))
        if has_free_services:
            builder.row(InlineKeyboardButton(text=f"📎 Добавить свободные услуги в '{main_name[:15]}'", callback_data=f"wiz_attach_{main_id}"))
        builder.row(InlineKeyboardButton(text=f"➕ Добавить новую услугу в '{main_name[:15]}'", callback_data=f"wiz_addsrv_{main_id}"))
            
    builder.row(InlineKeyboardButton(text="✅ Завершить", callback_data="wiz_finish"))
    return builder.as_markup()

def get_free_services_keyboard(free_services, selected_ids):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    for s in free_services:
        s_id = s['id'] if isinstance(s, dict) else s[0]
        s_name = s['name'] if isinstance(s, dict) else s[1]
        
        # Check if selected
        is_selected = s_id in selected_ids
        prefix = "✅ " if is_selected else "⬜️ "
        
        builder.row(InlineKeyboardButton(text=f"{prefix}{s_name}", callback_data=f"toggle_srv_{s_id}"))
        
    builder.row(InlineKeyboardButton(text="Завершить выбор", callback_data="finish_service_selection"))
    return builder.as_markup()

def get_system_settings_keyboard(use_masters: bool):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    status_text = "ВКЛ" if use_masters else "ВЫКЛ"
    builder.row(InlineKeyboardButton(text=f"Режим мастеров: {status_text}", callback_data="toggle_use_masters"))
    if use_masters:
        builder.row(InlineKeyboardButton(text="👥 Управление мастерами", callback_data="manage_masters"))
    builder.row(InlineKeyboardButton(text="📬 Настройки напоминаний", callback_data="settings_reminders"))
    builder.row(InlineKeyboardButton(text="🕒 Часы работы", callback_data="settings_working_hours"))
    builder.row(InlineKeyboardButton(text="⏳ Шаг/Интервал записи", callback_data="settings_interval"))
    return builder.as_markup()

def get_reminder_settings_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Текст за 24 часа", callback_data="edit_rem_text_1"))
    builder.row(InlineKeyboardButton(text="✏️ Текст второго увед.", callback_data="edit_rem_text_2"))
    builder.row(InlineKeyboardButton(text="🕒 Время второго увед.", callback_data="edit_rem_time_2"))
    builder.row(InlineKeyboardButton(text="◀️ Назад в настройки", callback_data="back_to_settings"))
    return builder.as_markup()

def get_masters_keyboard(masters):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for m in masters:
        m_id = m['id']
        name = m['name']
        builder.row(InlineKeyboardButton(text=f"❌ Удалить {name}", callback_data=f"del_master_{m_id}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить мастера", callback_data="add_master"))
    builder.row(InlineKeyboardButton(text="◀️ Назад в настройки", callback_data="back_to_settings"))
    return builder.as_markup()

# --- Clear Bookings Keyboards ---
def get_clear_options_keyboard(use_masters: bool):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Очистить за сегодня", callback_data="clear_today"))
    builder.row(InlineKeyboardButton(text="📆 Очистить за дату", callback_data="clear_date"))
    builder.row(InlineKeyboardButton(text="🗓️ Очистить за период", callback_data="clear_period"))
    if use_masters:
        builder.row(InlineKeyboardButton(text="👤 Очистить по мастеру", callback_data="clear_master"))
    builder.row(InlineKeyboardButton(text="🧹 Очистить прошедшие (до сегодня)", callback_data="clear_past"))
    builder.row(InlineKeyboardButton(text="🗑 Очистить ВСЕ записи", callback_data="clear_all"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()

def get_confirm_clear_keyboard(action: str, payload: str = ""):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    cb_data = f"confirm_clear_{action}"
    if payload:
        # Append payload to callback. E.g. confirm_clear_date_12.12.2023
        cb_data = f"confirm_clear_{action}_{payload}"
    builder.row(InlineKeyboardButton(text="⚠️ ДА, ОЧИСТИТЬ", callback_data=cb_data))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()

def get_clear_master_selection_keyboard(masters):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for m in masters:
        builder.row(InlineKeyboardButton(text=f"👤 {m['name']}", callback_data=f"clear_master_id_{m['id']}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()

def get_client_price_keyboard(page: int, total_pages: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    if total_pages <= 1:
        return None
        
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"client_price_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"client_price_page_{page + 1}"))
        
    if nav_buttons:
        builder.row(*nav_buttons)
        
    return builder.as_markup()

def get_reminder_keyboard(booking_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"rem_conf_{booking_id}"))
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"rem_canc_{booking_id}"),
        InlineKeyboardButton(text="🔄 Перенести", callback_data=f"rem_resched_{booking_id}")
    )
    return builder.as_markup()
