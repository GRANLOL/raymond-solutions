import { config } from './config.js?v=5';
import { tg, initTelegram } from './telegram.js?v=5';
import { fetchContent, fetchBusySlots } from './api.js?v=5';
import { populateServices, initServiceListeners } from './ui/services.js?v=5';
import { generateDates, generateTimes } from './ui/datetime.js?v=5';
import { initFormListeners } from './ui/form.js?v=5';
import { initModal } from './ui/modal.js?v=5';
import { initPrivacyModal } from './ui/privacy.js?v=5';
import './ui/toast.js?v=5';

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

// --- A. Configuration Injection ---
applyHeaderBranding();

// --- G. Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    // Implement Passive Event Listeners for touch events to prevent scroll-blocking
    document.addEventListener('touchstart', function () { }, { passive: true });
    document.addEventListener('touchmove', function () { }, { passive: true });

    applyHeaderBranding();
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
    initPrivacyModal();

    // Fetching data
    await fetchContent();
    await fetchBusySlots();

    // Initial Render
    populateServices();
    generateDates();
    generateTimes();
});
