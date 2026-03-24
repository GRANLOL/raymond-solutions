import { config } from './config.js?v=15';
import { store } from './store.js?v=15';
import { tg, initTelegram } from './telegram.js?v=15';
import { fetchContent, fetchBusySlots } from './api.js?v=15';
import { populateServices, initServiceListeners } from './ui/services.js?v=15';
import { generateDates, generateTimes } from './ui/datetime.js?v=15';
import { initFormListeners } from './ui/form.js?v=15';
import { initModal } from './ui/modal.js?v=15';
import { initPrivacyModal } from './ui/privacy.js?v=15';
import './ui/toast.js?v=15';

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
            const mainEl = document.getElementById('main-container') || document.querySelector('.container');
            const errEl = document.getElementById('error-container');
            if (mainEl) mainEl.style.display = 'none';
            if (errEl) {
                errEl.style.display = 'flex';
            } else {
                // Fallback: inject error message directly into page if old HTML is cached
                const wrapper = document.querySelector('.app-wrapper') || document.body;
                const div = document.createElement('div');
                div.className = 'error-container';
                div.style.cssText = 'display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;text-align:center;min-height:50vh;';
                div.innerHTML = '<div style="font-size:48px;margin-bottom:16px">⚠️</div><h2 style="font-size:22px;font-weight:700;margin-bottom:12px">Сервис временно недоступен</h2><p style="font-size:14px;opacity:0.7;margin-bottom:32px">Не удалось подключиться к серверу.<br>Попробуйте зайти немного позже.</p><button onclick="window.location.reload()" style="background:linear-gradient(135deg,#c9a227,#e8cd6a);color:#000;border:none;padding:14px 28px;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer">Обновить страницу</button>';
                wrapper.appendChild(div);
            }
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
