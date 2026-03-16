from __future__ import annotations

from .base import InlineKeyboardButton, InlineKeyboardMarkup, datetime, timedelta


def get_services_keyboard(services, page: int = 0, page_size: int = 20):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    total = len(services)
    start = page * page_size
    end = min(start + page_size, total)
    page_services = services[start:end]

    for service in page_services:
        if isinstance(service, dict):
            name = service["name"]
            service_id = service["id"]
            cat_name = service.get("category_name")
        else:
            service_id = service[0]
            name = service[1]
            cat_name = service[5] if len(service) > 5 else None

        cat_info = f" [{cat_name}]" if cat_name else " [Своб.]"
        builder.row(InlineKeyboardButton(text=f"✏️ {name[:20]}{cat_info}", callback_data=f"edit_srv_{service_id}_{page}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"srv_page_{page - 1}"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"srv_page_{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data="add_service"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_service_edit_keyboard(service):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    service_id = service["id"]
    current_duration = service.get("duration", 60)
    builder.row(InlineKeyboardButton(text="📝 Изменить название", callback_data=f"eds_name_{service_id}"))
    builder.row(InlineKeyboardButton(text="💸 Изменить цену", callback_data=f"eds_price_{service_id}"))
    builder.row(InlineKeyboardButton(text=f"⏱ Изменить длительность ({current_duration} м)", callback_data=f"eds_dur_{service_id}"))
    builder.row(InlineKeyboardButton(text="📃 Изменить категорию", callback_data=f"eds_cat_{service_id}"))
    builder.row(InlineKeyboardButton(text="❌ Удалить услугу", callback_data=f"del_srv_{service_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_services"))
    return builder.as_markup()


def build_category_tree(categories, parent_id=None, depth=0, branch=None):
    if branch is None:
        branch = set()

    tree = []
    for category in categories:
        category_id = category["id"] if isinstance(category, dict) else category[0]
        category_parent_id = category.get("parent_id") if isinstance(category, dict) else (category[2] if len(category) > 2 else None)

        if category_parent_id == parent_id:
            if category_id in branch:
                continue
            tree.append((category, depth))
            tree.extend(build_category_tree(categories, category_id, depth + 1, branch | {category_id}))
    return tree


def get_categories_keyboard(categories):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    tree = build_category_tree(categories)
    for category, depth in tree:
        name = category["name"] if isinstance(category, dict) else category[1]
        category_id = category["id"] if isinstance(category, dict) else category[0]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        builder.row(InlineKeyboardButton(text=f"✏️ {prefix}{name[:20]}", callback_data=f"edit_cat_{category_id}"))
    builder.row(InlineKeyboardButton(text="➕ Создать категорию", callback_data="add_category"))
    builder.row(InlineKeyboardButton(text="➕ Создать подкатегорию", callback_data="add_subcategory_existing"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_action"))
    return builder.as_markup()


def get_category_edit_keyboard(category):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    category_id = category["id"]
    builder.row(InlineKeyboardButton(text="📝 Изменить название", callback_data=f"edc_name_{category_id}"))
    builder.row(InlineKeyboardButton(text="🔄 Переместить", callback_data=f"move_cat_{category_id}"))
    builder.row(InlineKeyboardButton(text="➕ Создать подкатегорию", callback_data=f"wiz_addsub_{category_id}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data=f"wiz_addsrv_{category_id}"))
    builder.row(InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_cat_{category_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_categories"))
    return builder.as_markup()


def get_select_category_keyboard(categories):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    tree = build_category_tree(categories)
    for category, depth in tree:
        name = category["name"] if isinstance(category, dict) else category[1]
        category_id = category["id"] if isinstance(category, dict) else category[0]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        builder.row(InlineKeyboardButton(text=f"{prefix}{name[:20]}", callback_data=f"sel_cat_{category_id}"))

    builder.row(InlineKeyboardButton(text="Без категории", callback_data="sel_cat_0"))
    return builder.as_markup()


def get_parent_category_keyboard(categories):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    tree = build_category_tree(categories)
    for category, depth in tree:
        name = category["name"] if isinstance(category, dict) else category[1]
        category_id = category["id"] if isinstance(category, dict) else category[0]
        prefix = "  " * depth + ("↳ " if depth > 0 else "📁 ")
        builder.row(InlineKeyboardButton(text=f"{prefix}{name[:20]}", callback_data=f"sel_parent_{category_id}"))

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

    for service in free_services:
        service_id = service["id"] if isinstance(service, dict) else service[0]
        service_name = service["name"] if isinstance(service, dict) else service[1]
        prefix = "✅ " if service_id in selected_ids else "⬜️ "
        builder.row(InlineKeyboardButton(text=f"{prefix}{service_name}", callback_data=f"toggle_srv_{service_id}"))

    builder.row(InlineKeyboardButton(text="Завершить выбор", callback_data="finish_service_selection"))
    return builder.as_markup()
