import { tg } from '../telegram.js?v=15';
import { store } from '../store.js?v=15';
import { submitData } from './submit.js?v=15';
import { checkConfirmation } from './form.js?v=15';

const modal = document.getElementById('confirm-modal');
const modalService = document.getElementById('modal-service');
const modalDate = document.getElementById('modal-date');
const modalTime = document.getElementById('modal-time');
const modalName = document.getElementById('modal-name');
const modalPhone = document.getElementById('modal-phone');
const modalCancel = document.getElementById('modal-cancel');
const modalSubmit = document.getElementById('modal-submit');

export function initModal() {
    modalCancel.addEventListener('click', hideModal);
    modalSubmit.addEventListener('click', submitData);
}

export function showModal() {
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('medium');
    }

    const nameInput = document.getElementById('name-input');
    const phoneInput = document.getElementById('phone-input');

    setTimeout(() => {
        modalService.textContent = store.selectedService;
        modalDate.textContent = store.selectedDate;
        modalTime.textContent = store.selectedTime;
        modalName.textContent = nameInput.value.trim();
        modalPhone.textContent = phoneInput.value;

        document.body.classList.add('modal-open');
        modal.classList.add('active');
    }, 0);
}

export function hideModal() {
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
    }
    document.body.classList.remove('modal-open');
    modal.classList.remove('active');
    checkConfirmation();
}
