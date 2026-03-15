import { config } from './config.js';

// Central State Management
export const store = {
    selectedService: null,
    selectedDate: null,
    selectedTime: null,
    selectedPrice: 0,
    busySlots: {},
    dynamicServices: [],
    dynamicCategories: [],
    dynamicBookingWindow: 7,
    workingDays: [1, 2, 3, 4, 5, 6, 0],
    blacklistedDates: [],
    workingHours: "10:00-20:00",
    scheduleInterval: 30,
    selectedDuration: 60,
    timezoneOffset: 3,
    months: ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря"],
    shortMonths: ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"],
    days: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
};
