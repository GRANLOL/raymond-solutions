from __future__ import annotations

import os
from collections import Counter
from datetime import datetime

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
        ("Сумма по записям", f"{sum(int(price or 0) for _, _, _, _, price in bookings):,} ₸"),
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

    summary_ws["A9"] = "Что внутри"
    summary_ws["A9"].font = Font(bold=True, color="6B2B43")
    summary_ws["A10"] = "• Лист «Записи» — полный список клиентов"
    summary_ws["A11"] = "• Лист «По дням» — количество записей по датам"
    summary_ws.merge_cells("A9:B9")
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
        cell.number_format = '#,##0 "₸"'
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


async def send_client_home(
    message: types.Message,
    *,
    text: str,
    is_admin: bool,
) -> None:
    await message.answer(text, reply_markup=keyboards.get_booking_launch_keyboard())
    await message.answer(
        "Меню клиента обновлено.",
        reply_markup=keyboards.get_main_menu(is_admin=is_admin),
    )


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

    await send_client_home(
        message,
        text="Вы переключились в главное меню клиента.",
        is_admin=is_admin,
    )


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
    await callback.message.edit_text("Действие отменено.")


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
    caption = (
        f"📃 Экспорт записей\n"
        f"Салон: {salon_config.get('salon_name', 'Салон')}\n"
        f"Всего записей: {len(bookings)}"
    )
    await message.answer_document(excel_file, caption=caption)
    os.remove(file_path)


@router.message(F.text == "🗓 Все записи")
async def view_all_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    bookings = await database.get_all_bookings()
    if not bookings:
        await message.answer("Пока нет ни одной записи.")
        return

    text = "🗓 <b>Все записи:</b>\n\n"
    for idx, (name, phone, date, time, price) in enumerate(bookings, 1):
        safe_name = escape(name)
        safe_phone = escape(phone)
        safe_date = escape(date)
        safe_time = escape(time)
        text += f"<b>{idx}.</b> {safe_date} в {safe_time} — {safe_name} ({safe_phone}), {int(price or 0)} ₸\n"

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🗓 На сегодня")
async def todays_bookings_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    today_str = datetime.now().strftime("%d.%m.%Y")
    bookings = await database.get_bookings_by_date_full(today_str)
    if not bookings:
        await message.answer(f"На сегодня ({today_str}) записей нет.")
        return

    text = f"🗓 <b>Записи на сегодня ({today_str}):</b>\n\n"
    for idx, (name, phone, _date, time, price) in enumerate(bookings, 1):
        safe_name = escape(name)
        safe_phone = escape(phone)
        safe_time = escape(time)
        text += f"<b>{idx}.</b> {safe_time} — {safe_name} ({safe_phone}), {int(price or 0)} ₸\n"

    await message.answer(text, parse_mode="HTML")
