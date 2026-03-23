from __future__ import annotations

from bot_handlers.base import F, FSMContext, Router, keyboards, salon_config, update_config, types
from bot_handlers.settings import _is_admin
from bot_keyboards.settings import get_menu_buttons_keyboard, get_menu_button_edit_keyboard, get_portfolio_editor_keyboard
from bot_handlers.states import EditMenuButtonForm, EditPortfolioGalleryForm

router = Router()

@router.callback_query(F.data == "settings_menu_btns")
async def settings_menu_btns_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📱 <b>Кнопки меню клиента</b>\n\nЗдесь вы можете изменить названия кнопок и их содержимое.",
        parse_mode="HTML",
        reply_markup=get_menu_buttons_keyboard()
    )


@router.callback_query(F.data == "edit_menu_btn_address")
async def edit_menu_btn_address_cb(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    lbl = salon_config.get("custom_btn_address_lbl", "📍 Адрес и контакты")
    await callback.message.edit_text(
        f"Управление кнопкой: <b>{lbl}</b>",
        parse_mode="HTML",
        reply_markup=get_menu_button_edit_keyboard("address")
    )


@router.callback_query(F.data == "edit_menu_btn_portfolio")
async def edit_menu_btn_portfolio_cb(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    await callback.answer()
    lbl = salon_config.get("custom_btn_portfolio_lbl", "💅 Примеры работ")
    current_type = salon_config.get("custom_btn_portfolio_type", "portfolio")
    text = (
        f"Управление кнопкой: <b>{lbl}</b>\n\n"
        f"Текущий режим работы: <b>{'Галерея (фото)' if current_type == 'portfolio' else 'Текст (ссылки/контакты)'}</b>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_menu_button_edit_keyboard("portfolio", current_type)
    )


@router.callback_query(F.data.startswith("edit_btn_lbl_"))
async def edit_btn_lbl_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    btn_id = callback.data.replace("edit_btn_lbl_", "")
    await state.set_state(EditMenuButtonForm.label)
    await state.update_data(target_btn=btn_id)
    await callback.message.answer(
        "Введите новое название для кнопки (вместе с эмодзи).",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("settings_menu_btns", "← Назад")
    )
    await callback.answer()


@router.message(EditMenuButtonForm.label)
async def process_btn_lbl(message: types.Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data["target_btn"]
    text = message.text.strip()
    if len(text) > 30:
         await message.answer("Слишком длинное название. Попробуйте короче.", reply_markup=keyboards.get_cancel_admin_action_keyboard("settings_menu_btns", "← Назад"))
         return
    
    key = f"custom_btn_{btn_id}_lbl"
    update_config(key, text)
    await state.clear()
    await message.answer(
        "✅ Название кнопки успешно изменено! "
        "Чтобы кнопка обновилась у пользователей, им нужно будет просто отправить любое сообщение боту или нажать /start.",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("settings_menu_btns", "◀️ Обратно к меню")
    )


@router.callback_query(F.data.startswith("edit_btn_txt_"))
async def edit_btn_txt_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    btn_id = callback.data.replace("edit_btn_txt_", "")
    await state.set_state(EditMenuButtonForm.text)
    await state.update_data(target_btn=btn_id)
    
    current_txt = salon_config.get(f"custom_btn_{btn_id}_txt", "")
    
    text = "Введите текст, который будет отправлять бот при нажатии на эту кнопку.\n\nПоддерживается HTML разметка (теги &lt;b&gt;, &lt;i&gt;, &lt;a&gt;)."
    if btn_id == "address":
        text += "\n\n<i>Отправьте <code>-</code>, чтобы вернуть стандартный вывод адреса с картой.</i>"
        if not current_txt:
            address = salon_config.get("address", "Адрес не указан.")
            hours = salon_config.get("working_hours", "")
            map_url = salon_config.get("map_url", "")
            current_txt = f"📍 <b>Как нас найти</b>\n\n<b>Адрес:</b>\n{address}\n"
            if hours:
                current_txt += f"\n<b>Часы работы:</b> <i>{hours}</i>\n"
            if map_url:
                current_txt += f"\n<a href='{map_url}'>Открыть на карте</a>"
        
    if current_txt:
        # Escape HTML symbols so that it's displayed raw inside the <code> block for easy copy-pasting
        safe_txt = current_txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        text += f"\n\n<b>Текущий текст</b> (нажмите, чтобы скопировать):\n<code>{safe_txt}</code>"

    await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboards.get_cancel_admin_action_keyboard("settings_menu_btns", "← Назад"))
    await callback.answer()


@router.message(EditMenuButtonForm.text)
async def process_btn_txt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    btn_id = data["target_btn"]
    msg_text = message.text.strip()
    
    if btn_id == "address" and msg_text == "-":
         update_config("custom_btn_address_txt", "")
    else:
         try:
             # Validate HTML by sending a test message and immediately deleting it
             tmp = await message.answer(f"<i>Превью текста:</i>\n\n{msg_text}", parse_mode="HTML", disable_web_page_preview=True)
             try:
                 await tmp.delete()
             except Exception:
                 pass
         except Exception:
             await message.answer(
                 "⚠️ <b>Ошибка HTML-разметки!</b>\n\nУбедитесь, что вы закрыли все теги (например, <code>&lt;b&gt;текст&lt;/b&gt;</code>).\nПопробуйте написать текст еще раз.",
                 parse_mode="HTML",
                 reply_markup=keyboards.get_cancel_admin_action_keyboard("settings_menu_btns", "← Назад")
             )
             return
             
         update_config(f"custom_btn_{btn_id}_txt", msg_text)
         
    await state.clear()
    await message.answer("✅ Текст кнопки успешно сохранен!", reply_markup=keyboards.get_cancel_admin_action_keyboard("settings_menu_btns", "◀️ Обратно к меню"))


@router.callback_query(F.data.in_({"toggle_btn_type_text", "toggle_btn_type_portfolio"}))
async def toggle_btn_type_cb(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    new_type = callback.data.replace("toggle_btn_type_", "")
    update_config("custom_btn_portfolio_type", new_type)
    await callback.answer("Тип кнопки изменен")
    
    lbl = salon_config.get("custom_btn_portfolio_lbl", "💅 Примеры работ")
    text = (
        f"Управление кнопкой: <b>{lbl}</b>\n\n"
        f"Текущий режим работы: <b>{'Галерея (фото)' if new_type == 'portfolio' else 'Текст (ссылки/контакты)'}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_menu_button_edit_keyboard("portfolio", new_type))


@router.callback_query(F.data == "edit_portfolio_gallery")
async def edit_portfolio_gallery_cb(callback: types.CallbackQuery):
    if not _is_admin(callback.fromuser.id) if hasattr(callback, "fromuser") else not _is_admin(callback.from_user.id):
        return
    items = salon_config.get("portfolio_items", [])
    if not isinstance(items, list):
         items = []
    
    url = salon_config.get("portfolio_url", "")
    
    if hasattr(callback, "message"):
        text = (
            "🖼 <b>Управление галереей</b>\n\n"
            f"Фотографий загружено: <b>{len(items)}</b> из 10\n"
            f"Ссылка-кнопка внизу: " + (f"<b>{url}</b>" if url else "<i>не задана</i>")
        )
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_portfolio_editor_keyboard(len(items)), disable_web_page_preview=True)
        except Exception:
            pass
        try:
            await callback.answer()
        except Exception:
            pass


@router.callback_query(F.data == "portfolio_add_photo")
async def portfolio_add_photo_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(EditPortfolioGalleryForm.photo_upload)
    await callback.message.answer(
        "Отправьте сюда картинку (можно добавить к ней текст-описание в подпись).\n\n"
        "<i>Поддерживается 1 фото за раз.</i>",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("edit_menu_btn_portfolio", "← Назад")
    )
    await callback.answer()


@router.message(EditPortfolioGalleryForm.photo_upload, F.photo)
async def process_portfolio_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    caption = message.caption or ""
    
    items = salon_config.get("portfolio_items", [])
    if not isinstance(items, list):
        items = []
        
    if len(items) >= 10:
         await message.answer("Достигнут лимит (10 фото). Сначала очистите галерею.", reply_markup=keyboards.get_cancel_admin_action_keyboard("edit_menu_btn_portfolio", "← Назад"))
         return
         
    items.append({"media": file_id, "caption": caption})
    update_config("portfolio_items", items)
    await state.clear()
    await message.answer("✅ Фотография добавлена в галерею!", reply_markup=keyboards.get_cancel_admin_action_keyboard("edit_menu_btn_portfolio", "◀️ Управление галереей"))


@router.callback_query(F.data == "portfolio_edit_url")
async def portfolio_edit_url_cb(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(EditPortfolioGalleryForm.portfolio_url)
    await callback.message.answer(
        "Отправьте ссылку (или юзернейм `@username`) на ваш канал с работами, сайт или Instagram.\n\n"
        "Отправьте <code>-</code>, чтобы удалить кнопку.",
        parse_mode="HTML",
        reply_markup=keyboards.get_cancel_admin_action_keyboard("edit_menu_btn_portfolio", "← Назад")
    )
    await callback.answer()


@router.message(EditPortfolioGalleryForm.portfolio_url)
async def process_portfolio_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if url == "-":
        url = ""
    elif url.startswith("@"):
        url = f"https://t.me/{url[1:]}"
    elif not url.startswith("http"):
        url = f"https://{url}"
        
    update_config("portfolio_url", url)
    await state.clear()
    await message.answer("✅ Ссылка обновлена!", reply_markup=keyboards.get_cancel_admin_action_keyboard("edit_menu_btn_portfolio", "◀️ Управление галереей"))


@router.callback_query(F.data == "portfolio_clear")
async def portfolio_clear_cb(callback: types.CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return
    update_config("portfolio_items", [])
    try:
        await callback.answer("Галерея полностью очищена!", show_alert=True)
    except Exception:
        pass
    await edit_portfolio_gallery_cb(callback)
