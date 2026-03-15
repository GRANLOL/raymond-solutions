import { tg } from '../telegram.js';
import { store } from '../store.js';
import { submitData } from './submit.js';

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
    tg.HapticFeedback.impactOccurred('medium');

    const nameInput = document.getElementById('name-input');
    const phoneInput = document.getElementById('phone-input');

    setTimeout(() => {
        modalService.textContent = store.selectedService;
        modalDate.textContent = store.selectedDate;
        modalTime.textContent = store.selectedTime;
        modalName.textContent = nameInput.value.trim();
        modalPhone.textContent = phoneInput.value;

        modal.classList.add('active');
        tg.MainButton.hide();
    }, 0);
}

export function hideModal() {
    tg.HapticFeedback.impactOccurred('light');
    modal.classList.remove('active');
    tg.MainButton.show();
}
