import { tg } from '../telegram.js';
import { store } from '../store.js';
import { config } from '../config.js';
import { showModal } from './modal.js';

export function checkConfirmation() {
    const phoneInput = document.getElementById('phone-input');
    const nameInput = document.getElementById('name-input');

    const digitsOnly = phoneInput.value.replace(/\D/g, '');
    const isPhoneValid = digitsOnly.length >= 11;
    const isNameValid = nameInput.value.trim().length > 0;

    if (store.selectedService && store.selectedDate && store.selectedTime && isPhoneValid && isNameValid) {
        if (tg.MainButton) {
            tg.MainButton.text = "ПОДТВЕРДИТЬ ЗАПИСЬ";
            tg.MainButton.color = config.themeColors.mainButtonColor;
            tg.MainButton.textColor = config.themeColors.mainButtonTextColor;
            tg.MainButton.show();
            tg.MainButton.offClick(showModal);
            tg.MainButton.onClick(showModal);
        }
    } else if (tg.MainButton) {
        tg.MainButton.hide();
    }
}

export function initFormListeners() {
    const nameInput = document.getElementById('name-input');
    const phoneInput = document.getElementById('phone-input');

    nameInput.addEventListener('input', () => {
        checkConfirmation();
    });

    phoneInput.addEventListener('input', (e) => {
        tg.HapticFeedback.impactOccurred('light');

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
}
