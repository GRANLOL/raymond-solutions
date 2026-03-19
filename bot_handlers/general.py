from __future__ import annotations

import os
from collections import Counter
from datetime import datetime

from money import format_money
from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from .states import SearchBookingForm

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


def _status_label(status: str) -> str:
    return {
        "scheduled": "Активна",
        "completed": "Выполнена",
        "no_show": "Не пришел",
        "cancelled": "Отменена",
    }.get(status, status)


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


def _build_bookings_workbook(file_path: str, bookings: list[tuple[str, str, str, str, int | None, str]]) -> None:
    workbook = Workbook()
    summary_ws = workbook.active
    summary_ws.title = "Сводка"
    bookings_ws = workbook.create_sheet("Записи")
    daily_ws = workbook.create_sheet("По дням")

    salon_name = salon_config.get("salon_name", "Салон")
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    parsed_dates = [parsed for _, _, date, _, _, _ in bookings if (parsed := _safe_parse_date(date))]
    min_date = min(parsed_dates).strftime("%d.%m.%Y") if parsed_dates else "-"
    max_date = max(parsed_dates).strftime("%d.%m.%Y") if parsed_dates else "-"
    daily_counts = Counter(date for _, _, date, _, _, _ in bookings)

    summary_rows = [
        ("Отчет", f"Записи салона «{salon_name}»"),
        ("Сформирован", generated_at),
        ("Всего записей", len(bookings)),
        ("Период данных", f"{min_date} - {max_date}"),
        ("Уникальных телефонов", len({phone for _, phone, _, _, _, _ in bookings if phone})),
        ("Сумма по записям", format_money(sum(int(price or 0) for _, _, _, _, price, _ in bookings))),
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

    _fit_columns(summary_ws)

    bookings_ws.append(["№", "Клиент / услуга", "Телефон", "Дата", "Время", "Цена", "Статус"])
    for idx, (name, phone, date, time, price, status) in enumerate(bookings, start=1):
        bookings_ws.append([idx, name, phone, date, time, int(price or 0), _status_label(status)])
    _style_table_header(bookings_ws[1])
    if bookings_ws.max_row > 1:
        _style_data_rows(bookings_ws, 2, bookings_ws.max_row, center_columns={1, 4, 5, 6, 7})
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


def _get_last_page(items, page_size: int = BOOKINGS_PAGE_SIZE) -> int:
    total = len(items)
    total_pages = max((total - 1) // page_size + 1, 1)
    return total_pages - 1


def _render_booking_page(bookings, title: str, page: int):
    page_items, page, total_pages = _paginate(bookings, page)
    lines = [f"🗓 <b>{title}</b>", f"<i>Страница {page + 1} из {total_pages}</i>", ""]
    for idx, (_booking_id, name, phone, date, time, price, status) in enumerate(page_items, start=1 + page * BOOKINGS_PAGE_SIZE):
        safe_name = escape(name)
        safe_phone = escape(phone)
        safe_date = escape(date)
        safe_time = escape(time)
        status_badge = {
            "scheduled": "🟢 Активна",
            "completed": "✅ Выполнена",
            "no_show": "🟠 Не пришел",
            "cancelled": "❌ Отменена",
        }.get(status, escape(_status_label(status)))
        lines.append(
            f"┌ <b>Запись #{idx}</b>\n"
            f"├ <b>Когда:</b> {safe_date} в {safe_time}\n"
            f"├ <b>Клиент:</b> {safe_name}\n"
            f"├ <b>Телефон:</b> {safe_phone}\n"
            f"├ <b>Статус:</b> {status_badge}\n"
            f"└ <b>Сумма:</b> {escape(format_money(price))}\n"
        )
    if not page_items:
        lines.append("Записей пока нет.")
    return "\n".join(lines), page_items, page, total_pages


async def _show_booking_list(message_or_callback, *, context: str, page: int = 0):
    await database.sync_completed_bookings()
    if context == "today":
        today_str = datetime.now().strftime("%d.%m.%Y")
        bookings = await database.get_bookings_by_date_detailed(today_str)
        title = f"Записи на сегодня ({today_str})"
    else:
        bookings = await database.get_all_bookings_detailed()
        title = "Все записи"

    text, page_items, page, total_pages = _render_booking_page(bookings, title, page)
    markup = keyboards.get_admin_booking_page_keyboard(page_items, context, page, total_pages)

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=markup)


async def send_client_home(message: types.Message, *, text: str, is_admin: bool) -> None:
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboards.get_booking_launch_keyboard(),
    )
    await message.answer(
        "👤 <b>Личный кабинет</b>\n\n"
        "Здесь можно посмотреть свои записи, историю и быстро вернуться к оформлению новой записи.",
        parse_mode="HTML",
        reply_markup=keyboards.get_main_menu(is_admin=is_admin),
    )


@router.message(Command("start"))
async def start_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(message.from_user.id) == admin_id)

    if is_admin:
        await message.answer(
            "⚙️ <b>Панель администратора</b>\n\nВыберите нужный раздел ниже.",
            parse_mode="HTML",
            reply_markup=keyboards.admin_menu,
        )
        return

    welcome_text = salon_config.get(
        "welcome_text",
        "📅 <b>Онлайн-запись</b>\n\nВыберите удобное время и оформите запись онлайн.",
    )
    await send_client_home(message, text=welcome_text, is_admin=is_admin)


@router.message(F.text == "👤 Главное меню")
@router.message(F.text == "👤 Меню клиента")
async def client_menu_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    is_admin = bool(admin_id and str(message.from_user.id) == admin_id)
    if not is_admin:
        return
    await send_client_home(
        message,
        text="📅 <b>Онлайн-запись</b>\n\nВыберите удобное время и оформите запись онлайн.",
        is_admin=is_admin,
    )


@router.message(Command("admin"))
@router.message(F.text == "⚙️ Панель управления")
async def admin_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    await message.answer(
        "⚙️ <b>Панель администратора</b>\n\nВыберите нужный раздел ниже.",
        parse_mode="HTML",
        reply_markup=keyboards.admin_menu,
    )


@router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu_callback(callback: types.CallbackQuery, state):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "⚙️ <b>Панель администратора</b>\n\nВыберите нужный раздел ниже.",
        parse_mode="HTML",
        reply_markup=keyboards.admin_menu,
    )


@router.callback_query(F.data == "cancel_admin_action")
async def cancel_admin_action_callback(callback: types.CallbackQuery, state):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return
    await callback.answer()
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
        await message.answer("📃 <b>Нет записей для выгрузки</b>", parse_mode="HTML")
        return

    file_path = "bookings_export.xlsx"
    _build_bookings_workbook(file_path, bookings)

    excel_file = FSInputFile(file_path)
    caption = (
        f"📃 <b>Экспорт записей</b>\n"
        f"<b>Салон:</b> {escape(salon_config.get('salon_name', 'Салон'))}\n"
        f"<b>Всего записей:</b> {len(bookings)}"
    )
    await message.answer_document(excel_file, caption=caption, parse_mode="HTML")
    os.remove(file_path)


@router.message(F.text == "🗓 Все записи")
async def view_all_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    bookings = await database.get_all_bookings_detailed()
    await _show_booking_list(message, context="all", page=_get_last_page(bookings))


@router.message(F.text == "🗓 На сегодня")
async def todays_bookings_handler(message: types.Message):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    await _show_booking_list(message, context="today", page=0)


@router.message(F.text == "🔎 Поиск")
async def search_bookings_handler(message: types.Message, state):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return
    await state.set_state(SearchBookingForm.query)
    await message.answer(
        "🔎 <b>Поиск записи</b>\n\nВведите имя, телефон, дату или время. Например: <code>777</code> или <code>21.03.2026</code>.",
        parse_mode="HTML",
    )


@router.message(SearchBookingForm.query)
async def process_booking_search(message: types.Message, state):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(message.from_user.id) != admin_id:
        return

    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Введите хотя бы 2 символа для поиска.")
        return

    results = await database.search_bookings(query, limit=10)
    await state.clear()
    if not results:
        await message.answer("🔎 <b>Ничего не найдено</b>\n\nПопробуйте другой запрос.", parse_mode="HTML")
        return

    lines = [f"🔎 <b>Результаты поиска</b>", f"<i>Запрос: {escape(query)}</i>", ""]
    for booking_id, name, phone, date, time, status in results:
        lines.append(
            f"<b>#{booking_id}</b> {escape(name)}\n"
            f"Статус: {escape(_status_label(status))}\n"
            f"Когда: {escape(date)} в {escape(time)}\n"
            f"Телефон: {escape(phone)}\n"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


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
    booking_id, user_id, name, phone, date, time, status, _duration = booking
    text = (
        "📝 <b>Карточка записи</b>\n\n"
        f"<b>Клиент:</b> {escape(name)}\n"
        f"<b>Телефон:</b> {escape(phone)}\n"
        f"<b>Дата:</b> {escape(date)}\n"
        f"<b>Время:</b> {escape(time)}\n"
        f"<b>Статус:</b> {escape(_status_label(status))}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboards.get_admin_booking_actions_keyboard(
            booking_id,
            phone,
            context,
            int(page_str),
            status=status,
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


@router.callback_query(F.data.startswith("admin_booking_status_"))
async def admin_booking_status_callback(callback: types.CallbackQuery):
    admin_id = getenv("ADMIN_ID")
    if not admin_id or str(callback.from_user.id) != admin_id:
        return

    prefix = "admin_booking_status_"
    payload = callback.data[len(prefix):]
    first_separator = payload.find("_")
    booking_id_str = payload[:first_separator]
    status, context, page_str = payload[first_separator + 1 :].rsplit("_", 2)

    await database.update_booking_status(int(booking_id_str), status)
    await callback.answer("Статус обновлен")
    await _show_booking_list(callback, context=context, page=int(page_str))
