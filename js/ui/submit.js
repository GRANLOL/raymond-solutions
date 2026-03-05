import { tg } from '../telegram.js';
import { store } from '../store.js';
import { config } from '../config.js';

export function submitData() {
    tg.HapticFeedback.impactOccurred('medium');
    if (!store.selectedService || !store.selectedDate || !store.selectedTime) return;

    tg.MainButton.showProgress();
    const modalSubmit = document.getElementById('modal-submit');
    const modal = document.getElementById('confirm-modal');
    const successScreen = document.getElementById('success-screen');
    const successService = document.getElementById('success-service');
    const successDate = document.getElementById('success-date');
    const successTime = document.getElementById('success-time');
    const phoneInput = document.getElementById('phone-input');
    const nameInput = document.getElementById('name-input');

    modalSubmit.disabled = true;
    modalSubmit.textContent = "Секунду...";

    const data = {
        service: store.selectedService,
        date: store.selectedDate,
        time: store.selectedTime,
        phone: phoneInput.value,
        name: nameInput.value.trim()
    };

    if (store.useMasters && store.selectedMaster) {
        data.master_id = store.selectedMaster.id;
    }

    setTimeout(() => {
        // Hide Confirmation Modal and Telegram Main Button
        modal.classList.remove('active');
        tg.MainButton.hide();

        // Populate and Show Success Screen
        successService.textContent = store.selectedService;
        successDate.textContent = document.querySelector('.date-card.active .date-num').textContent + ' ' + document.querySelector('.date-card.active .date-month').textContent;
        successTime.textContent = store.selectedTime;

        // Step 1: Immediately trigger fade-in
        successScreen.classList.add('active');
        tg.HapticFeedback.notificationOccurred('success');

        // Step 2: requestAnimationFrame to smoothly draw checkmark animation
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                successScreen.classList.add('animate');
            });
        });

        // Step 3: Call tg.sendData after 2.5 seconds
        setTimeout(() => {
            tg.sendData(JSON.stringify(data));
        }, 2500);
    }, 0);
}
