from aiogram.fsm.state import State, StatesGroup


class BookingForm(StatesGroup):
    entering_phone = State()


class ClearBookingsForm(StatesGroup):
    waiting_for_date = State()
    waiting_for_period_start = State()
    waiting_for_period_end = State()


class EditReminderSettingsForm(StatesGroup):
    text_1 = State()
    text_2 = State()
    time_2 = State()


class EditBotProfileTextForm(StatesGroup):
    description = State()
    about = State()


class EditTimezoneForm(StatesGroup):
    offset = State()


class AddServiceForm(StatesGroup):
    category_id = State()
    name = State()
    price = State()
    duration = State()


class CategoryWizard(StatesGroup):
    main_name = State()
    sub_name = State()


class WizardAddServiceForm(StatesGroup):
    target_id = State()
    name = State()
    price = State()
    duration = State()


class EditServiceForm(StatesGroup):
    service_id = State()
    name = State()
    price = State()
    duration = State()
    category_id = State()


class EditCategoryForm(StatesGroup):
    category_id = State()
    name = State()
    new_parent = State()


class AddSubcategoryExistingForm(StatesGroup):
    parent_id = State()
    name = State()


class WorkingHoursForm(StatesGroup):
    hours = State()


class ScheduleIntervalForm(StatesGroup):
    interval = State()


class AddBookingWindowForm(StatesGroup):
    days = State()


class AddBlacklistDateForm(StatesGroup):
    date = State()


class AddBlockedSlotForm(StatesGroup):
    date = State()
    start_time = State()
    end_time = State()
    reason = State()


class ConfigureLunchBreakForm(StatesGroup):
    start_time = State()
    end_time = State()


class ConfigureSingleBreakForm(StatesGroup):
    date = State()
    start_time = State()
    end_time = State()


class EditCurrencyForm(StatesGroup):
    symbol = State()


class RescheduleBookingForm(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_confirmation = State()


class SearchBookingForm(StatesGroup):
    query = State()


class ManualBookingForm(StatesGroup):
    service_id = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    source = State()
    notes = State()
    confirm = State()


class AdminAvailabilityForm(StatesGroup):
    service_id = State()
    date = State()


class AdminBookingsByDateForm(StatesGroup):
    date = State()


class AdminEditBookingForm(StatesGroup):
    name = State()
    phone = State()
    notes = State()


class EditMenuButtonForm(StatesGroup):
    target_btn = State()
    label = State()
    text = State()


class EditPortfolioGalleryForm(StatesGroup):
    portfolio_url = State()
    photo_upload = State()


class EditWebAppHeaderForm(StatesGroup):
    name = State()
    tagline = State()
    logo_text = State()
    logo_url = State()
