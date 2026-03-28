from __future__ import annotations

from money import get_currency_symbol

from .base import F, Router, FSMContext, build_category_list_text, filter_valid_parent_categories, keyboards, database, escape, getenv, types
from .states import AddServiceForm, AddSubcategoryExistingForm, CategoryWizard, EditCategoryForm, EditServiceForm, WizardAddServiceForm
from repositories.services import delete_all_services
from repositories.categories import delete_all_categories

router = Router()


def _currency() -> str:
    return get_currency_symbol()


def _format_services_page(services, page: int) -> str:
    total = len(services)
    page_size = 20
    start = page * page_size
    end = min(start + page_size, total)
    lines = [f"⚙️ <b>Услуги</b>", f"<i>Всего: {total} • Страница {page + 1}</i>", ""]
    for service in services[start:end]:
        cat_info = f" • {service.get('category_name')}" if service.get("category_name") else ""
        lines.append(f"• <b>{escape(service['name'])}</b>")
        lines.append(f"  {escape(str(service['price']))}{escape(_currency())}{escape(cat_info)}")
    if end < total:
        lines.append("")
        lines.append("…")
    return "\n".join(lines)


def _format_service_card(service: dict, title: str = "Редактирование услуги") -> str:
    cat_name = service.get("category_name") or "Без категории"
    duration = service.get("duration")
    lines = [
        f"⚙️ <b>{title}</b>",
        "",
        f"📝 <b>Название:</b> {escape(service['name'])}",
        f"💸 <b>Цена:</b> {escape(str(service['price']))}{escape(_currency())}",
        f"📁 <b>Категория:</b> {escape(cat_name)}",
    ]
    if duration:
        lines.append(f"⏱ <b>Длительность:</b> {escape(str(duration))} мин")
    return "\n".join(lines)


@router.message(F.text == "⚙️ Услуги")
async def manage_services_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    services = await database.get_all_services()
    if not services:
        await message.answer("⚙️ <b>Список услуг пуст</b>", parse_mode="HTML", reply_markup=keyboards.get_services_keyboard(services))
        return
    await message.answer(_format_services_page(services, page=0), parse_mode="HTML", reply_markup=keyboards.get_services_keyboard(services, page=0))


@router.callback_query(F.data.startswith("del_srv_"))
async def del_service_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
    srv_id = int(callback.data.split("_")[2])
    await database.delete_service(srv_id)
    services = await database.get_all_services()
    text = "✅ <b>Услуга удалена</b>\n\n" + (_format_services_page(services, 0) if services else "Список услуг пуст.")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.get_services_keyboard(services))


@router.callback_query(F.data.startswith("edit_srv_"))
async def edit_service_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    parts = callback.data.split("_")
    srv_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    await state.update_data(services_page=page)

    service = await database.get_service_by_id(srv_id)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await callback.message.edit_text(_format_service_card(service), parse_mode="HTML", reply_markup=keyboards.get_service_edit_keyboard(service))


@router.callback_query(F.data == "back_to_services")
async def back_to_services_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    page = data.get("services_page", 0)
    await state.clear()
    services = await database.get_all_services()
    if not services:
        await callback.message.edit_text("⚙️ <b>Список услуг пуст</b>", parse_mode="HTML", reply_markup=keyboards.get_services_keyboard(services))
        return
    await callback.message.edit_text(_format_services_page(services, page), parse_mode="HTML", reply_markup=keyboards.get_services_keyboard(services, page=page))


@router.callback_query(F.data.startswith("srv_page_"))
async def services_page_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    page = int(callback.data.split("_")[2])
    services = await database.get_all_services()
    await callback.message.edit_text(_format_services_page(services, page), parse_mode="HTML", reply_markup=keyboards.get_services_keyboard(services, page=page))
    await callback.answer()


@router.callback_query(F.data.startswith("eds_name_"))
async def eds_name_callback(callback: types.CallbackQuery, state: FSMContext):
    srv_id = int(callback.data.split("_")[2])
    await state.update_data(service_id=srv_id)
    await state.set_state(EditServiceForm.name)
    await callback.message.answer("Введите <b>новое название</b> услуги:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.message(EditServiceForm.name)
async def process_edit_service_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    srv_id = data["service_id"]
    service = await database.get_service_by_id(srv_id)
    if not service:
        await state.clear()
        await message.answer("Услуга не найдена.")
        return

    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название услуги не должно быть пустым.", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return

    if await database.service_name_exists(new_name, service.get("category_id"), exclude_service_id=srv_id):
        await message.answer(
            "В этой категории уже есть услуга с таким названием. Используйте другое название.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard(),
        )
        return

    await database.update_service_name(srv_id, new_name)
    await state.clear()

    service = await database.get_service_by_id(srv_id)
    await message.answer(_format_service_card(service, "Название изменено"), parse_mode="HTML", reply_markup=keyboards.get_service_edit_keyboard(service))


@router.callback_query(F.data.startswith("eds_price_"))
async def eds_price_callback(callback: types.CallbackQuery, state: FSMContext):
    srv_id = int(callback.data.split("_")[2])
    await state.update_data(service_id=srv_id)
    await state.set_state(EditServiceForm.price)
    await callback.message.answer("Введите <b>новую цену</b> услуги:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.message(EditServiceForm.price)
async def process_edit_service_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    srv_id = data["service_id"]
    await database.update_service_price(srv_id, message.text)
    await state.clear()

    service = await database.get_service_by_id(srv_id)
    await message.answer(_format_service_card(service, "Цена изменена"), parse_mode="HTML", reply_markup=keyboards.get_service_edit_keyboard(service))


@router.callback_query(F.data.startswith("eds_dur_"))
async def eds_duration_callback(callback: types.CallbackQuery, state: FSMContext):
    srv_id = int(callback.data.split("_")[2])
    await state.update_data(service_id=srv_id)
    await state.set_state(EditServiceForm.duration)
    await callback.message.answer("Введите <b>новую длительность</b> услуги в минутах:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.message(EditServiceForm.duration)
async def process_edit_service_duration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    srv_id = data["service_id"]
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число минут.", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return

    await database.update_service_duration(srv_id, duration)
    await state.clear()

    service = await database.get_service_by_id(srv_id)
    await message.answer(_format_service_card(service, "Длительность изменена"), parse_mode="HTML", reply_markup=keyboards.get_service_edit_keyboard(service))


@router.callback_query(F.data.startswith("eds_cat_"))
async def eds_cat_callback(callback: types.CallbackQuery, state: FSMContext):
    srv_id = int(callback.data.split("_")[2])
    categories = await database.get_all_categories()
    if not categories:
        await callback.answer("Нет доступных категорий", show_alert=True)
        return

    await state.update_data(service_id=srv_id)
    await state.set_state(EditServiceForm.category_id)
    await callback.message.edit_text("Выберите <b>новую категорию</b>:", parse_mode="HTML", reply_markup=keyboards.get_select_category_keyboard(categories))


@router.callback_query(EditServiceForm.category_id, F.data.startswith("sel_cat_"))
async def process_edit_service_cat(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cat_id = int(callback.data.split("_")[2])
    if cat_id == 0:
        cat_id = None

    data = await state.get_data()
    srv_id = data["service_id"]
    await database.update_service_category(srv_id, cat_id)
    await state.clear()

    service = await database.get_service_by_id(srv_id)
    await callback.message.edit_text(_format_service_card(service, "Категория изменена"), parse_mode="HTML", reply_markup=keyboards.get_service_edit_keyboard(service))


@router.message(F.text == "📁 Категории")
async def manage_categories_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    categories = await database.get_all_categories()
    if not categories:
        await message.answer("📁 <b>Список категорий пуст</b>", parse_mode="HTML", reply_markup=keyboards.get_categories_keyboard(categories))
    else:
        await message.answer(build_category_list_text(categories), parse_mode="HTML", reply_markup=keyboards.get_categories_keyboard(categories))


@router.callback_query(F.data.startswith("del_cat_"))
async def del_category_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
    cat_id = int(callback.data.split("_")[2])
    await database.delete_category(cat_id)
    categories = await database.get_all_categories()

    text = "✅ Категория удалена.\n" + build_category_list_text(categories)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.get_categories_keyboard(categories))


@router.callback_query(F.data.startswith("edit_cat_"))
async def edit_category_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    cat_id = int(callback.data.split("_")[2])
    category = await database.get_category_by_id(cat_id)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    text = f"📁 <b>Редактирование категории</b>\n\n📝 <b>Название:</b> {escape(category['name'])}"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.get_category_edit_keyboard(category))


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    categories = await database.get_all_categories()
    if not categories:
        await callback.message.edit_text("📁 <b>Список категорий пуст</b>", parse_mode="HTML", reply_markup=keyboards.get_categories_keyboard(categories))
    else:
        await callback.message.edit_text(build_category_list_text(categories), parse_mode="HTML", reply_markup=keyboards.get_categories_keyboard(categories))


@router.callback_query(F.data.startswith("edc_name_"))
async def edc_name_callback(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=cat_id)
    await state.set_state(EditCategoryForm.name)
    await callback.message.answer("Введите <b>новое название</b> категории:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.message(EditCategoryForm.name)
async def process_edit_category_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cat_id = data["category_id"]
    await database.update_category_name(cat_id, message.text)
    await state.clear()

    category = await database.get_category_by_id(cat_id)
    text = f"✅ <b>Название изменено</b>\n\n📁 <b>Категория</b>\n\n📝 <b>Название:</b> {escape(category['name'])}"
    await message.answer(text, parse_mode="HTML", reply_markup=keyboards.get_category_edit_keyboard(category))


@router.callback_query(F.data.startswith("move_cat_"))
async def move_category_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    await callback.answer()
    cat_id = int(callback.data.split("_")[2])
    categories = await database.get_all_categories()

    descendant_ids = await database.get_category_descendant_ids(cat_id)
    invalid_ids = descendant_ids | {cat_id}
    valid_categories = filter_valid_parent_categories(categories, invalid_ids)

    await state.update_data(category_id=cat_id)
    await state.set_state(EditCategoryForm.new_parent)
    await callback.message.edit_text(
        "Выберите <b>новую родительскую категорию</b>:",
        parse_mode="HTML",
        reply_markup=keyboards.get_parent_category_keyboard(valid_categories)
    )


@router.callback_query(EditCategoryForm.new_parent, F.data.startswith("sel_parent_"))
async def process_move_category_parent(callback: types.CallbackQuery, state: FSMContext):
    parent_id = int(callback.data.split("_")[2])
    if parent_id == 0:
        parent_id = None

    data = await state.get_data()
    cat_id = data["category_id"]

    try:
        await database.update_category_parent(cat_id, parent_id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await state.clear()

    category = await database.get_category_by_id(cat_id)
    text = f"✅ <b>Категория перемещена</b>\n\n📁 <b>Категория</b>\n\n📝 <b>Название:</b> {escape(category['name'])}"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.get_category_edit_keyboard(category))


@router.callback_query(F.data == "add_category")
async def add_category_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    await state.set_state(CategoryWizard.main_name)
    await callback.message.answer("Введите <b>название новой категории</b>:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())
    await callback.answer()


@router.message(CategoryWizard.main_name)
async def process_wizard_main_name(message: types.Message, state: FSMContext):
    cat_name = message.text
    await database.add_category(name=cat_name, parent_id=None)
    categories = await database.get_all_categories()

    new_main_id = None
    for c in reversed(categories):
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        if name == cat_name:
            new_main_id = c_id
            break

    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)

    has_free = len(free_services) > 0

    await state.update_data(main_id=new_main_id, main_name=cat_name)
    await message.answer(
        f"✅ Категория <b>{escape(cat_name)}</b> добавлена.\n\nЧто делаем дальше?",
        parse_mode="HTML",
        reply_markup=keyboards.get_wizard_keyboard(main_id=new_main_id, main_name=cat_name, has_free_services=has_free)
    )


@router.callback_query(F.data.startswith("wiz_addsub_"))
async def wizard_add_sub(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    main_id = int(callback.data.split("_")[2])
    cat = await database.get_category_by_id(main_id)
    main_name = cat['name'] if cat else 'Основная категория'

    await state.update_data(main_id=main_id, main_name=main_name, sub_id=None, sub_name=None)
    await state.set_state(CategoryWizard.sub_name)
    await callback.message.edit_text(f"Введите <b>название подкатегории</b> для «{escape(main_name)}»:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())


@router.message(CategoryWizard.sub_name)
async def process_wizard_sub_name(message: types.Message, state: FSMContext):
    sub_name = message.text
    data = await state.get_data()
    main_id = data.get('main_id')
    main_name = data.get('main_name')

    await database.add_category(name=sub_name, parent_id=main_id)
    categories = await database.get_all_categories()

    new_sub_id = None
    for c in reversed(categories):
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        if name == sub_name:
            new_sub_id = c_id
            break

    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)

    has_free = len(free_services) > 0

    await message.answer(
        f"✅ Подкатегория <b>{escape(sub_name)}</b> добавлена в «{escape(main_name)}».\n\nЧто делаем дальше?",
        parse_mode="HTML",
        reply_markup=keyboards.get_wizard_keyboard(main_id=main_id, main_name=main_name, sub_id=new_sub_id, sub_name=sub_name, has_free_services=has_free)
    )


@router.callback_query(F.data.startswith("wiz_attach_"))
async def wizard_attach_services(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    target_id = int(callback.data.split("_")[2])

    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)

    await state.update_data(new_category_id=target_id, selected_services=[], free_services=free_services)
    await state.set_state("AttachServicesForm:selecting")

    await callback.message.edit_text(
        "Выберите <b>свободные услуги</b> для прикрепления:",
        parse_mode="HTML",
        reply_markup=keyboards.get_free_services_keyboard(free_services, [])
    )


@router.callback_query(F.data.startswith("wiz_addsrv_"))
async def wizard_add_service(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    target_id = int(callback.data.split("_")[2])
    cat = await database.get_category_by_id(target_id)
    if not cat:
        return

    if cat['parent_id']:
        parent_cat = await database.get_category_by_id(cat['parent_id'])
        main_id = cat['parent_id']
        main_name = parent_cat['name'] if parent_cat else "Категория"
        sub_id = target_id
        sub_name = cat['name']
    else:
        main_id = target_id
        main_name = cat['name']
        sub_id = None
        sub_name = None

    await state.update_data(target_id=target_id, main_id=main_id, main_name=main_name, sub_id=sub_id, sub_name=sub_name)
    display_name = sub_name if sub_name else main_name
    await state.set_state(WizardAddServiceForm.name)
    await callback.message.edit_text(f"Введите <b>название новой услуги</b> для «{escape(display_name)}»:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())


@router.message(WizardAddServiceForm.name)
async def process_wizard_service_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(WizardAddServiceForm.price)
    await message.answer("Введите <b>цену услуги</b>:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())


@router.message(WizardAddServiceForm.price)
async def process_wizard_service_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(WizardAddServiceForm.duration)
    await message.answer("Введите <b>длительность услуги</b> в минутах:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())


@router.message(WizardAddServiceForm.duration)
async def process_wizard_service_duration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = (data['name'] or '').strip()
    target_id = data['target_id']
    price = data['price']

    try:
        duration = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите число минут, например: 60.", reply_markup=keyboards.get_cancel_admin_action_keyboard())
        return

    if await database.service_name_exists(name, target_id):
        await message.answer(
            "В этой категории уже есть услуга с таким названием. Используйте другое название.",
            reply_markup=keyboards.get_cancel_admin_action_keyboard(),
        )
        return

    await database.add_service(name=name, price=price, duration=duration, description="", category_id=target_id)

    main_id = data.get('main_id')
    main_name = data.get('main_name')
    sub_id = data.get('sub_id')
    sub_name = data.get('sub_name')

    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)

    has_free = len(free_services) > 0

    await message.answer(
        f"✅ Услуга <b>{escape(name)}</b> добавлена.\n\nЧто делаем дальше?",
        parse_mode="HTML",
        reply_markup=keyboards.get_wizard_keyboard(main_id=main_id, main_name=main_name, sub_id=sub_id, sub_name=sub_name, has_free_services=has_free)
    )


@router.callback_query(F.data == "wiz_finish")
async def wizard_finish(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    categories = await database.get_all_categories()

    text = "✅ <b>Работа с категориями завершена</b>\n\n" + build_category_list_text(categories)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.get_categories_keyboard(categories))


@router.callback_query(F.data == "add_subcategory_existing")
async def add_subcategory_existing(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    categories = await database.get_all_categories()
    if not categories:
        await callback.message.answer("Сначала создайте хотя бы одну основную категорию.")
        return

    await state.set_state(AddSubcategoryExistingForm.parent_id)
    await callback.message.answer("К какой <b>категории</b> добавить подкатегорию?", parse_mode="HTML", reply_markup=keyboards.get_parent_category_keyboard(categories))
    await callback.answer()


@router.callback_query(AddSubcategoryExistingForm.parent_id, F.data.startswith("sel_parent_"))
async def process_subcat_parent(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    parent_id = int(callback.data.split("_")[2])
    if parent_id == 0:
        parent_id = None
    await state.update_data(parent_id=parent_id)
    await state.set_state(AddSubcategoryExistingForm.name)
    await callback.message.edit_text("Родительская категория выбрана. Введите <b>название подкатегории</b>:", parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard())


@router.message(AddSubcategoryExistingForm.name)
async def process_subcat_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    parent_id = data.get('parent_id')
    cat_name = message.text

    await database.add_category(name=cat_name, parent_id=parent_id)
    categories = await database.get_all_categories()

    new_sub_id = None
    for c in reversed(categories):
        name = c['name'] if isinstance(c, dict) else c[1]
        c_id = c['id'] if isinstance(c, dict) else c[0]
        if name == cat_name:
            new_sub_id = c_id
            break

    all_services = await database.get_all_services()
    free_services = []
    for s in all_services:
        s_cat_id = s.get('category_id') if isinstance(s, dict) else (s[4] if isinstance(s, tuple) and len(s) > 4 else None)
        if s_cat_id is None:
            free_services.append(s)

    has_free = len(free_services) > 0

    if has_free and new_sub_id:
        await state.update_data(new_category_id=new_sub_id, selected_services=[], free_services=free_services)
        await state.set_state("AttachServicesForm:selecting")
        await message.answer(
            f"✅ Подкатегория <b>{escape(cat_name)}</b> добавлена.\n\nЕсть свободные услуги. Прикрепить их?",
            parse_mode="HTML",
            reply_markup=keyboards.get_free_services_keyboard(free_services, [])
        )
    else:
        await state.clear()
        text = f"✅ Подкатегория <b>{escape(cat_name)}</b> добавлена.\n\n" + build_category_list_text(categories)
        await message.answer(text, parse_mode="HTML", reply_markup=keyboards.get_categories_keyboard(categories))


@router.callback_query(F.data.startswith("toggle_srv_"))
async def toggle_service_selection(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    srv_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected = data.get('selected_services', [])
    free_services = data.get('free_services', [])

    if srv_id in selected:
        selected.remove(srv_id)
    else:
        selected.append(srv_id)

    await state.update_data(selected_services=selected)
    await callback.message.edit_reply_markup(reply_markup=keyboards.get_free_services_keyboard(free_services, selected))


@router.callback_query(F.data == "finish_service_selection")
async def finish_service_selection(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    new_cat_id = data.get('new_category_id')
    selected = data.get('selected_services', [])

    if new_cat_id and selected:
        for srv_id in selected:
            await database.update_service_category(srv_id, new_cat_id)

    await state.clear()
    categories = await database.get_all_categories()

    msg = "✅ Категория и услуги успешно сохранены." if selected else "✅ Категория сохранена без добавления услуг."
    text = f"{msg}\n\n" + build_category_list_text(categories)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboards.get_categories_keyboard(categories))


@router.callback_query(F.data == "add_service")
async def add_service_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    categories = await database.get_all_categories()
    if not categories:
        await state.update_data(category_id=None)
        await state.set_state(AddServiceForm.name)
        await callback.message.answer("Введите <b>название новой услуги</b>:", parse_mode="HTML")
    else:
        await state.set_state(AddServiceForm.category_id)
        await callback.message.answer("Выберите <b>категорию</b> для новой услуги:", parse_mode="HTML", reply_markup=keyboards.get_select_category_keyboard(categories))
    await callback.answer()


@router.callback_query(AddServiceForm.category_id, F.data.startswith("sel_cat_"))
async def process_service_category(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cat_id = int(callback.data.split("_")[2])
    cat_val = cat_id if cat_id > 0 else None
    await state.update_data(category_id=cat_val)
    await state.set_state(AddServiceForm.name)
    await callback.message.edit_text("Категория выбрана. Теперь введите <b>название новой услуги</b>:", parse_mode="HTML")


@router.message(AddServiceForm.name)
async def process_service_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddServiceForm.price)
    await message.answer("Введите <b>цену услуги</b>:", parse_mode="HTML")


@router.message(AddServiceForm.price)
async def process_service_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(AddServiceForm.duration)
    await message.answer("Введите <b>длительность услуги</b> в минутах:", parse_mode="HTML")


@router.message(AddServiceForm.duration)
async def process_service_duration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = (data['name'] or '').strip()
    category_id = data.get('category_id')
    price = data['price']

    try:
        duration = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите число минут, например: 60.")
        return

    if await database.service_name_exists(name, category_id):
        await message.answer("В этой категории уже есть услуга с таким названием. Используйте другое название.")
        return

    await database.add_service(name=name, price=price, duration=duration, description="", category_id=category_id)
    await state.clear()

    services = await database.get_all_services()
    await message.answer(f"✅ Услуга <b>{escape(name)}</b> добавлена.", parse_mode="HTML", reply_markup=keyboards.get_services_keyboard(services))


@router.callback_query(F.data == "confirm_delete_all_services")
async def confirm_delete_all_services_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите безвозвратно удалить <b>ВСЕ</b> услуги?\n\n<i>Категории останутся, но станут абсолютно пустыми.</i>",
        parse_mode="HTML",
        reply_markup=keyboards.get_confirm_delete_all_services_keyboard()
    )


@router.callback_query(F.data == "action_delete_all_services")
async def action_delete_all_services_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await delete_all_services()
    await callback.answer("✅ Все услуги были успешно удалены", show_alert=True)
    services = await database.get_all_services()
    await callback.message.edit_text(
        _format_services_page(services, 0),
        parse_mode="HTML",
        reply_markup=keyboards.get_services_keyboard(services, 0)
    )


@router.callback_query(F.data == "confirm_delete_all_categories")
async def confirm_delete_all_categories_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите безвозвратно удалить <b>ВСЕ</b> категории?\n\n<i>Все привязанные к ним услуги останутся в базе, но перейдут в общий список \"Свободных услуг\" (Без категории).</i>",
        parse_mode="HTML",
        reply_markup=keyboards.get_confirm_delete_all_categories_keyboard()
    )


@router.callback_query(F.data == "action_delete_all_categories")
async def action_delete_all_categories_cb(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await delete_all_categories()
    await callback.answer("✅ Все категории были успешно удалены", show_alert=True)
    categories = await database.get_all_categories()
    text = build_category_list_text(categories)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboards.get_categories_keyboard(categories)
    )
