import { tg } from '../telegram.js';
import { store } from '../store.js';
import { config } from '../config.js';

async function postBooking(data) {
    const headers = {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
    };

    if (tg.initData) {
        headers['X-Telegram-Init-Data'] = tg.initData;
    }

    const response = await fetch(`${config.apiBaseUrl}/bookings`, {
        method: 'POST',
        headers,
        body: JSON.stringify(data),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || `Server returned ${response.status}`);
    }
    return payload;
}

export async function submitData() {
    tg.HapticFeedback.impactOccurred('medium');
    if (!store.selectedService || !store.selectedDate || !store.selectedTime) {
        return;
    }

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
    modalSubmit.textContent = 'Секунду...';

    const data = {
        service: store.selectedService,
        date: store.selectedDate,
        time: store.selectedTime,
        duration: store.selectedDuration || 60,
        price: store.selectedPrice || 0,
        phone: phoneInput.value,
        name: nameInput.value.trim(),
    };

    try {
        await postBooking(data);

        modal.classList.remove('active');
        tg.MainButton.hide();

        successService.textContent = store.selectedService;
        successDate.textContent =
            document.querySelector('.date-card.active .date-num').textContent +
            ' ' +
            document.querySelector('.date-card.active .date-month').textContent;
        successTime.textContent = store.selectedTime;

        successScreen.classList.add('active');
        tg.HapticFeedback.notificationOccurred('success');

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                successScreen.classList.add('animate');
            });
        });

        setTimeout(() => {
            if (tg.close) {
                tg.close();
            }
        }, 1800);
    } catch (error) {
        console.error('Booking submit failed:', error);
        tg.HapticFeedback.notificationOccurred('error');
        alert(error.message || 'Не удалось оформить запись.');
    } finally {
        modalSubmit.disabled = false;
        modalSubmit.textContent = 'Записаться';
        if (tg.MainButton.hideProgress) {
            tg.MainButton.hideProgress();
        }
    }
}
