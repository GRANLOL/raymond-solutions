import { config } from './config.js';
import { tg, initTelegram } from './telegram.js';
import { fetchContent, fetchBusySlots } from './api.js';
import { populateServices, initServiceListeners } from './ui/services.js';
import { generateDates, generateTimes } from './ui/datetime.js';
import { initFormListeners } from './ui/form.js';
import { initModal } from './ui/modal.js';
import { initPrivacyModal } from './ui/privacy.js';
import './ui/toast.js';

const SAVED_PHONE_KEY = 'savedBookingPhone';

function loadSavedPhone() {
    try {
        return window.localStorage.getItem(SAVED_PHONE_KEY) || '';
    } catch (error) {
        console.warn('Unable to read saved phone from localStorage:', error);
        return '';
    }
}

function ensureTaglineElement(header) {
    let taglineEl = header.querySelector('.salon-tagline');
    if (!taglineEl) {
        taglineEl = document.createElement('div');
        taglineEl.className = 'salon-tagline';
        taglineEl.hidden = true;
        header.appendChild(taglineEl);
    }
    return taglineEl;
}

function applyHeaderBranding() {
    const header = document.querySelector('.salon-header');
    const nameEl = document.getElementById('salon-name-display');
    const brandMark = header.querySelector('.salon-logo-placeholder');
    const taglineEl = ensureTaglineElement(header);

    nameEl.textContent = config.salonName;

    const logoUrl = String(config.salonLogoUrl || '').trim();
    const logoText = String(config.salonLogoText || '').trim();
    const tagline = String(config.salonTagline || '').trim();

    header.classList.remove('salon-header--text-only', 'salon-header--with-image');
    brandMark.classList.remove('salon-logo-placeholder--image');
    brandMark.removeAttribute('style');
    brandMark.hidden = false;
    brandMark.textContent = '';

    if (logoUrl) {
        header.classList.add('salon-header--with-image');
        brandMark.classList.add('salon-logo-placeholder--image');
        brandMark.style.backgroundImage = `url("${logoUrl}")`;
        brandMark.style.backgroundSize = 'cover';
        brandMark.style.backgroundPosition = 'center';
        brandMark.style.backgroundRepeat = 'no-repeat';
    } else {
        if (logoText) {
            brandMark.textContent = logoText;
        } else {
            header.classList.add('salon-header--text-only');
            brandMark.hidden = true;
        }
    }

    if (tagline) {
        taglineEl.textContent = tagline;
        taglineEl.hidden = false;
    } else {
        taglineEl.hidden = true;
        taglineEl.textContent = '';
    }
}

function revealInitialView() {
    const bootStartedAt = Number(document.body.dataset.bootStartedAt || Date.now());
    const elapsed = Date.now() - bootStartedAt;
    const minVisibleBootMs = 150;
    const reveal = () => {
        window.requestAnimationFrame(() => {
            document.body.classList.remove('app-booting');
            document.body.classList.add('app-ready');
        });
    };

    if (elapsed >= minVisibleBootMs) {
        reveal();
        return;
    }

    window.setTimeout(reveal, minVisibleBootMs - elapsed);
}

// --- A. Configuration Injection ---
applyHeaderBranding();

// --- G. Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    document.body.dataset.bootStartedAt = String(Date.now());
    // Implement Passive Event Listeners for touch events to prevent scroll-blocking
    document.addEventListener('touchstart', function () { }, { passive: true });
    document.addEventListener('touchmove', function () { }, { passive: true });

    applyHeaderBranding();
    initTelegram();

    const nameInput = document.getElementById('name-input');
    const phoneInput = document.getElementById('phone-input');
    // Pre-fill user name from Telegram WebApp Context
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        nameInput.value = tg.initDataUnsafe.user.first_name || '';
    }
    phoneInput.value = loadSavedPhone();

    // Wiring up listeners
    initServiceListeners();
    initFormListeners();
    initModal();
    initPrivacyModal();

    try {
        // Fetching data
        await fetchContent();
        
        if (store.hasConnectionError) {
            document.getElementById('main-container').style.display = 'none';
            document.getElementById('error-container').style.display = 'flex';
            applyHeaderBranding();
            return;
        }

        await fetchBusySlots();

        applyHeaderBranding();

        // Initial Render
        populateServices();
        generateDates();
        generateTimes();
    } finally {
        revealInitialView();
    }
});
