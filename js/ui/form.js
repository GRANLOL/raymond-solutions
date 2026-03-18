import { tg } from '../telegram.js?v=5';
import { store } from '../store.js?v=5';
import { showModal } from './modal.js?v=5';
import { showToast } from './toast.js?v=5';

const bookingButton = document.getElementById('booking-submit-btn');

function notifyHaptic(type, level) {
    if (!tg.HapticFeedback) {
        return;
    }

    if (type === 'notification') {
        tg.HapticFeedback.notificationOccurred(level);
        return;
    }

    tg.HapticFeedback.impactOccurred(level);
}

export function getFormIssues() {
    const nameInput = document.getElementById('name-input');
    const phoneInput = document.getElementById('phone-input');
    const digitsOnly = phoneInput.value.replace(/\D/g, '');
    const issues = [];

    if (!store.selectedService) {
        issues.push({ field: 'service', message: 'Выберите услугу.' });
    }
    if (!store.selectedDate) {
        issues.push({ field: 'date', message: 'Выберите дату.' });
    }
    if (!store.selectedTime) {
        issues.push({ field: 'time', message: 'Выберите время.' });
    }
    if (nameInput.value.trim().length === 0) {
        issues.push({ field: 'name', message: 'Укажите имя.' });
    }
    if (digitsOnly.length < 11) {
        issues.push({ field: 'phone', message: 'Введите корректный номер телефона.' });
    }

    return issues;
}

export function checkConfirmation() {
    const issues = getFormIssues();

    if (!bookingButton) {
        return;
    }

    const isValid = issues.length === 0;
    bookingButton.classList.toggle('is-disabled', !isValid);
    bookingButton.classList.toggle('is-ready', isValid);
    bookingButton.setAttribute('aria-disabled', String(!isValid));
}

function focusField(field) {
    const map = {
        service: document.getElementById('select-trigger'),
        date: document.getElementById('date-container'),
        time: document.getElementById('time-grid'),
        name: document.getElementById('name-input'),
        phone: document.getElementById('phone-input'),
    };

    const target = map[field];
    if (!target) {
        return;
    }

    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (typeof target.focus === 'function') {
        target.focus({ preventScroll: true });
    }
}

export function initFormListeners() {
    const nameInput = document.getElementById('name-input');
    const phoneInput = document.getElementById('phone-input');

    if (bookingButton) {
        bookingButton.addEventListener('click', () => {
            const issues = getFormIssues();
            if (issues.length > 0) {
                notifyHaptic('notification', 'warning');
                showToast({
                    title: 'Не хватает данных',
                    message: issues[0].message,
                    variant: 'neutral',
                });
                focusField(issues[0].field);
                return;
            }

            notifyHaptic('impact', 'medium');
            showModal();
        });
    }

    nameInput.addEventListener('input', () => {
        checkConfirmation();
    });

    phoneInput.addEventListener('input', (e) => {
        notifyHaptic('impact', 'light');

        let input = e.target.value.replace(/\D/g, '');
        if (input.length > 0 && input[0] === '8') {
            input = '7' + input.substring(1);
        } else if (input.length > 0 && input[0] !== '7') {
            input = '7' + input;
        }

        if (input.length === 0) {
            e.target.value = '';
            checkConfirmation();
            return;
        }

        let formatted = '+7';
        if (input.length > 1) {
            formatted += ' (' + input.substring(1, 4);
        }
        if (input.length >= 5) {
            formatted += ') ' + input.substring(4, 7);
        }
        if (input.length >= 8) {
            formatted += '-' + input.substring(7, 9);
        }
        if (input.length >= 10) {
            formatted += '-' + input.substring(9, 11);
        }

        e.target.value = formatted;
        checkConfirmation();
    });

    checkConfirmation();
}
