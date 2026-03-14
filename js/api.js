import { config } from './config.js';
import { store } from './store.js';
import { tg } from './telegram.js';

const API_BASE_URL = config.apiBaseUrl;

function getApiHeaders() {
    const headers = {
        'ngrok-skip-browser-warning': 'true',
        'Content-Type': 'application/json'
    };

    if (tg.initData) {
        headers['X-Telegram-Init-Data'] = tg.initData;
    }

    return headers;
}

export async function fetchBusySlots(masterId = null) {
    try {
        let url = `${API_BASE_URL}/busy-slots`;
        if (masterId !== null) {
            url += `?master_id=${masterId}`;
        }
        const response = await fetch(url, {
            headers: getApiHeaders()
        });

        if (!response.ok) {
            console.error("Server API Error. Status:", response.status);
            throw new Error('Server returned ' + response.status);
        }

        const data = await response.json();

        if (typeof data === 'object' && data !== null) {
            store.busySlots = data;
        } else {
            console.warn("Expected dictionary, got:", data);
        }
    } catch (e) {
        console.error("Error fetching busy slots:", e);
    }
}

export async function fetchContent() {
    try {
        const response = await fetch(`${API_BASE_URL}/get-content`, {
            headers: getApiHeaders()
        });
        if (!response.ok) throw new Error('Server returned ' + response.status);

        const data = await response.json();
        if (data.services) {
            store.dynamicServices = data.services;
            if (data.categories) store.dynamicCategories = data.categories;
            if (data.masters) store.dynamicMasters = data.masters;
            if (data.use_masters !== undefined) store.useMasters = data.use_masters;
            if (data.working_hours) store.workingHours = data.working_hours;
            if (data.schedule_interval) store.scheduleInterval = data.schedule_interval;
            if (data.booking_window) store.dynamicBookingWindow = data.booking_window;
            if (data.working_days) store.workingDays = data.working_days;
            if (data.blacklisted_dates) store.blacklistedDates = data.blacklisted_dates;
            if (data.timezone_offset !== undefined) store.timezoneOffset = data.timezone_offset;
        }
    } catch (e) {
        console.error("Error fetching available content:", e);
        // Fallbacks back to config if API fails completely to ensure app still loads somewhat
        store.dynamicServices = config.services;
        store.workingHours = "10:00-20:00";
        store.scheduleInterval = 30;
        store.dynamicBookingWindow = 7;
        store.workingDays = [1, 2, 3, 4, 5, 6, 0];
        store.blacklistedDates = [];
        store.dynamicMasters = [];
        store.useMasters = false;
    }
}
