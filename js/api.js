import { config } from './config.js';
import { store } from './store.js';
import { tg } from './telegram.js';

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
            if (data.show_service_duration !== undefined) {
                store.showServiceDuration = Boolean(data.show_service_duration);
            }
            if (data.webapp_salon_name !== undefined) {
                config.salonName = data.webapp_salon_name;
            }
            if (data.webapp_salon_tagline !== undefined) {
                config.salonTagline = data.webapp_salon_tagline;
            }
            if (data.webapp_logo_type !== undefined) {
                if (data.webapp_logo_type === "none") {
                    config.salonLogoUrl = "";
                    config.salonLogoText = "";
                } else if (data.webapp_logo_type === "text") {
                    config.salonLogoUrl = "";
                    config.salonLogoText = data.webapp_logo_text || "";
                } else if (data.webapp_logo_type === "url") {
                    config.salonLogoUrl = data.webapp_logo_url || "";
                    config.salonLogoText = "";
                }
            }
        }
    } catch (e) {
        console.error("Error fetching available content:", e);
        store.hasConnectionError = true;
    }
}
