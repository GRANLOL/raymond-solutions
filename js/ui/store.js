import { config } from './config.js';

// Central State Management
export const store = {
    selectedService: null,
    selectedDate: null,
    selectedTime: null,
    busySlots: {},
    dynamicServices: [],
    dynamicCategories: [],
    dynamicTimeSlots: [],
    dynamicMasters: [],
    useMasters: false,
    selectedMaster: null,
    dynamicBookingWindow: 7,
    workingDays: [1, 2, 3, 4, 5, 6, 0],
    blacklistedDates: [],
    months: ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря"],
    shortMonths: ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"],
    days: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
};
