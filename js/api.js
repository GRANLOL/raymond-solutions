import { config } from './config.js?v=5';
import { store } from './store.js?v=5';
import { tg } from './telegram.js?v=5';

const API_BASE_URL = config.apiBaseUrl;

function getApiHeaders() {
    const headers = {
        'ngrok-skip-browser-warning': 'true',
        'Content-Type': 'application/json',
    };

    if (tg.initData) {
        headers['X-Telegram-Init-Data'] = tg.initData;
    }

    return headers;
}

export async function fetchBusySlots() {
    try {
        const response = await fetch(`${API_BASE_URL}/busy-slots`, {
            headers: getApiHeaders(),
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();
        if (typeof data === 'object' && data !== null) {
            store.busySlots = data;
        }
    } catch (e) {
        console.error("Error fetching busy slots:", e);
    }
}

export async function fetchContent() {
    try {
        const response = await fetch(`${API_BASE_URL}/get-content`, {
            headers: getApiHeaders(),
        });
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();
        if (data.services) {
            store.dynamicServices = data.services;
            if (data.categories) {
                store.dynamicCategories = data.categories;
            }
            if (data.working_hours) {
                store.workingHours = data.working_hours;
            }
            if (data.schedule_interval) {
                store.scheduleInterval = data.schedule_interval;
            }
            if (data.booking_window) {
                store.dynamicBookingWindow = data.booking_window;
            }
            if (data.working_days) {
                store.workingDays = data.working_days;
            }
            if (data.blacklisted_dates) {
                store.blacklistedDates = data.blacklisted_dates;
            }
            if (data.timezone_offset !== undefined) {
                store.timezoneOffset = data.timezone_offset;
            }
            if (data.currency_symbol) {
                store.currencySymbol = data.currency_symbol;
            }
        }
    } catch (e) {
        console.error("Error fetching available content:", e);
        store.dynamicServices = config.services;
        store.workingHours = "10:00-20:00";
        store.scheduleInterval = 30;
        store.dynamicBookingWindow = 7;
        store.workingDays = [1, 2, 3, 4, 5, 6, 0];
        store.blacklistedDates = [];
        store.currencySymbol = '₸';
    }
}
