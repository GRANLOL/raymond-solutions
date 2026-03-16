from __future__ import annotations

import os
from collections import Counter
from datetime import datetime

from money import format_money
from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .base import (
    Command,
    F,
    FSInputFile,
    Router,
    database,
    escape,
    getenv,
    keyboards,
    salon_config,
    types,
)

router = Router()

HEADER_FILL = PatternFill(fill_type="solid", fgColor="F4C7D9")
SUBHEADER_FILL = PatternFill(fill_type="solid", fgColor="FAE6EE")
THIN_BORDER = Border(
    left=Side(style="thin", color="E7BCCB"),
    right=Side(style="thin", color="E7BCCB"),
    top=Side(style="thin", color="E7BCCB"),
    bottom=Side(style="thin", color="E7BCCB"),
)
BOOKINGS_PAGE_SIZE = 10


def _safe_parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%d.%m.%Y")
    except ValueError:
        return None


def _fit_columns(ws) -> None:
    for column_cells in ws.columns:
        max_length = 0
        first_real_cell = next((cell for cell in column_cells if not isinstance(cell, MergedCell)), None)
        if first_real_cell is None:
            continue
        column_letter = get_column_letter(first_real_cell.column)
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            max_length = max(max_length, len(value))
            if not isinstance(cell, MergedCell):
                cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 36)


def _style_table_header(row) -> None:
    for cell in row:
        cell.font = Font(bold=True, color="6B2B43")
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _style_data_rows(ws, start_row: int, end_row: int, center_columns: set[int] | None = None) -> None:
    center_columns = center_columns or set()
    for row in ws.iter_rows(min_row=start_row, max_row=end_row):
        for cell in row:
            cell.border = THIN_BORDER
            if cell.column in center_columns:
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                cell.alignment = Alignment(vertical="center", wrap_text=True)


def _build_bookings_workbook(file_path: str, bookings: list[tuple[str, str, str, str, int | None]]) -> None:
    workbook = Workbook()
    summary_ws = workbook.active
    summary_ws.title = "Сводка"
    bookings_ws = workbook.create_sheet("Записи")
    daily_ws = workbook.create_sheet("По дням")

    salon_name = salon_config.get("salon_name", "Салон")
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    parsed_dates = [parsed for _, _, date, _, _ in bookings if (parsed := _safe_parse_date(date))]
    min_date = min(parsed_dates).strftime("%d.%m.%Y") if parsed_dates else "—"
    max_date = max(parsed_dates).strftime("%d.%m.%Y") if parsed_dates else "—"
    daily_counts = Counter(date for _, _, date, _, _ in bookings)

    summary_rows = [
        ("Отчет", f"Записи салона «{salon_name}»"),
        ("Сформирован", generated_at),
        ("Всего записей", len(bookings)),
        ("Период данных", f"{min_date} — {max_date}"),
        ("Уникальных телефонов", len({phone for _, phone, _, _, _ in bookings if phone})),
        ("Сумма по записям", format_money(sum(int(price or 0) for _, _, _, _, price in bookings))),
    ]

    summary_ws["A1"] = "Экспорт записей"
    summary_ws["A1"].font = Font(size=16, bold=True, color="6B2B43")
    summary_ws["A1"].alignment = Alignment(vertical="center")
    summary_ws.merge_cells("A1:B1")

    for idx, (label, value) in enumerate(summary_rows, start=3):
        label_cell = summary_ws[f"A{idx}"]
        value_cell = summary_ws[f"B{idx}"]
        label_cell.value = label
        value_cell.value = value
        label_cell.font = Font(bold=True, color="6B2B43")
        label_cell.fill = SUBHEADER_FILL
        label_cell.border = THIN_BORDER
        value_cell.border = THIN_BORDER

    summary_ws["A10"] = "Что внутри"
    summary_ws["A10"].font = Font(bold=True, color="6B2B43")
    summary_ws["A11"] = "• Лист «Записи» — полный список клиентов"
    summary_ws["A12"] = "• Лист «По дням» — количество записей по датам"
    summary_ws.merge_cells("A10:B10")
    _fit_columns(summary_ws)

    bookings_ws.append(["№", "Клиент / услуга", "Телефон", "Дата", "Время", "Цена"])
    for idx, (name, phone, date, time, price) in enumerate(bookings, start=1):
        bookings_ws.append([idx, name, phone, date, time, int(price or 0)])
    _style_table_header(bookings_ws[1])
    if bookings_ws.max_row > 1:
        _style_data_rows(bookings_ws, 2, bookings_ws.max_row, center_columns={1, 4, 5, 6})
    bookings_ws.freeze_panes = "A2"
    bookings_ws.auto_filter.ref = bookings_ws.dimensions
    for cell in bookings_ws["F"][1:]:
        cell.number_format = f'#,##0 "{salon_config.get("currency_symbol", "₸")}"'
    _fit_columns(bookings_ws)

    daily_ws.append(["Дата", "Количество записей"])
    for date, count in sorted(daily_counts.items(), key=lambda item: (_safe_parse_date(item[0]) or datetime.max)):
        daily_ws.append([date, count])
    _style_table_header(daily_ws[1])
    if daily_ws.max_row > 1:
        _style_data_rows(daily_ws, 2, daily_ws.max_row, center_columns={2})
    daily_ws.freeze_panes = "A2"
    daily_ws.auto_filter.ref = daily_ws.dimensions
    _fit_columns(daily_ws)

    workbook.save(file_path)


def _paginate(items, page: int, page_size: int = BOOKINGS_PAGE_SIZE):
    total = len(items)
    total_pages = max((total - 1) // page_size + 1, 1)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    return items[start:end], page, total_pages


def _render_booking_page(bookings, title: str, page: int):
    page_items, page, total_pages = _paginate(bookings, page)
    lines = [f"{title}\n", f"Страница {page + 1} из {total_pages}\n"]
    for idx, (_booking_id, name, phone, date, time, price) in enumerate(page_items, start=1 + page * BOOKINGS_PAGE_SIZE):
        safe_name = escape(name)
        safe_phone = escape(phone)
        safe_date = escape(date)
        safe_time = escape(time)
        lines.append(f"<b>{idx}.</b> {safe_date} {safe_time} — {safe_name} ({safe_phone}), {escape(format_money(price))}")
    if not page_items:
        lines.append("Записей нет.")
    return "\n".join(lines), page_items, page, total_pages


async def _show_booking_list(message_or_callback, *, context: str, page: int = 0):
    if context == "today":
        today_str = datetime.now().strftime("%d.%m.%Y")
        bookings = await database.get_bookings_by_date_detailed(today_str)
        title = f"🗓 <b>Записи на сегодня ({today_str})</b>"
    else:
        bookings = await database.get_all_bookings_detailed()
        title = "🗓 <b>Все записи</b>"

    text, page_items, page, total_pages = _render_booking_page(bookings, title, page)
    markup = keyboards.get_admin_booking_page_keyboard(page_items, context, page, total_pages)

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=markup)


async def send_client_home(message: types.Message, *, text: str, is_admin: bool) -> None:
    await message.answer(text, reply_markup=keyboards.get_booking_launch_keyboard())
    await message.answer("Меню клиента обновлено.", reply_markup=keyboards.get_main_menu(is_admin=is_admin))


@router.message(Command("start"))
async def start_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(message.from_user.id) == admin_id)

    if is_admin:
        await message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)
        return

    await send_client_home(
        message,
        text=salon_config.get("welcome_text", "Привет! Выберите нужное действие:"),
        is_admin=is_admin,
    )


@router.message(F.text == "👤 Главное меню")
@router.message(F.text == "👤 Меню клиента")
async def client_menu_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(message.from_user.id) == admin_id)
    if not is_admin:
        return
    await send_client_home(message, text="Вы переключились в главное меню клиента.", is_admin=is_admin)


@router.message(Command("admin"))
@router.message(F.text == "⚙️ Панель управления")
async def admin_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    await message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)


@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu_callback(callback: types.CallbackQuery, state):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Добро пожаловать в панель администратора!", reply_markup=keyboards.admin_menu)


@router.callback_query(F.data == "cancel_admin_action")
async def cancel_admin_action_callback(callback: types.CallbackQuery, state):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await state.clear()
    await callback.message.delete()


@router.message(Command("export_excel"))
@router.message(F.text == "📃 Excel")
async def export_excel_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    bookings = await database.get_all_bookings()
    if not bookings:
        await message.answer("Пока нет ни одной записи для выгрузки.")
        return

    file_path = "bookings_export.xlsx"
    _build_bookings_workbook(file_path, bookings)

    excel_file = FSInputFile(file_path)
    caption = f"📃 Экспорт записей\nСалон: {salon_config.get('salon_name', 'Салон')}\nВсего записей: {len(bookings)}"
    await message.answer_document(excel_file, caption=caption)
    os.remove(file_path)


@router.message(F.text == "🗓 Все записи")
async def view_all_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    await _show_booking_list(message, context="all", page=0)


@router.message(F.text == "🗓 На сегодня")
async def todays_bookings_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    await _show_booking_list(message, context="today", page=0)


@router.callback_query(F.data.startswith("bookings_page_"))
async def bookings_page_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
    _, _, context, page_str = callback.data.split("_", 3)
    await _show_booking_list(callback, context=context, page=int(page_str))


@router.callback_query(F.data.startswith("booking_actions_"))
async def booking_actions_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
    _, _, context, page_str, booking_id_str = callback.data.split("_", 4)
    booking = await database.get_booking_record_by_id(int(booking_id_str))
    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    booking_id, user_id, name, phone, date, time, _master_id = booking
    text = (
        "Действия по записи:\n\n"
        f"Клиент: {escape(name)}\n"
        f"Телефон: {escape(phone)}\n"
        f"Дата: {escape(date)}\n"
        f"Время: {escape(time)}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboards.get_admin_booking_actions_keyboard(
            booking_id,
            phone,
            context,
            int(page_str),
            telegram_user_id=user_id,
        ),
    )


@router.callback_query(F.data.startswith("show_phone_"))
async def show_phone_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    phone = callback.data.replace("show_phone_", "", 1)
    await callback.answer(f"Номер: +{phone}", show_alert=True)


@router.callback_query(F.data.startswith("admin_cancel_booking_"))
async def admin_cancel_booking_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    _, _, _, booking_id_str, context, page_str = callback.data.split("_", 5)
    await database.delete_booking_by_id(int(booking_id_str))
    await callback.answer("Запись отменена")
    await _show_booking_list(callback, context=context, page=int(page_str))
