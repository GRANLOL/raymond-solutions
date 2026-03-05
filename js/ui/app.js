import { config } from './config.js';
import { tg, initTelegram } from './telegram.js';
import { fetchContent, fetchBusySlots } from './api.js';
import { populateServices, initServiceListeners } from './ui/services.js';
import { generateDates, generateTimes } from './ui/datetime.js';
import { initFormListeners } from './ui/form.js';
import { initModal } from './ui/modal.js';

// --- A. Configuration Injection ---
document.getElementById('salon-name-display').textContent = config.salonName;

// --- G. Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    // Implement Passive Event Listeners for touch events to prevent scroll-blocking
    document.addEventListener('touchstart', function () { }, { passive: true });
    document.addEventListener('touchmove', function () { }, { passive: true });

    initTelegram();

    const nameInput = document.getElementById('name-input');
    // Pre-fill user name from Telegram WebApp Context
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        nameInput.value = tg.initDataUnsafe.user.first_name || '';
    }

    // Wiring up listeners
    initServiceListeners();
    initFormListeners();
    initModal();

    // Fetching data
    await fetchContent();
    await fetchBusySlots();

    // Initial Render
    populateServices();
    generateDates();
    generateTimes();
});
