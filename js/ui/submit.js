import { tg } from '../telegram.js?v=5';
import { store } from '../store.js?v=5';
import { config } from '../config.js?v=5';
import { getFormIssues } from './form.js?v=5';
import { showToast } from './toast.js?v=5';

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
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('medium');
    }

    const issues = getFormIssues();
    if (issues.length > 0) {
        showToast({
            title: 'Проверьте форму',
            message: issues[0].message,
            variant: 'neutral',
        });
        return;
    }

    const modalSubmit = document.getElementById('modal-submit');
    const modal = document.getElementById('confirm-modal');
    const successScreen = document.getElementById('success-screen');
    const successService = document.getElementById('success-service');
    const successDate = document.getElementById('success-date');
    const successTime = document.getElementById('success-time');
    const phoneInput = document.getElementById('phone-input');
    const nameInput = document.getElementById('name-input');

    modalSubmit.disabled = true;
    modalSubmit.textContent = 'Подтверждаем...';

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

        successService.textContent = store.selectedService;
        successDate.textContent =
            document.querySelector('.date-card.active .date-num').textContent +
            ' ' +
            document.querySelector('.date-card.active .date-month').textContent;
        successTime.textContent = store.selectedTime;

        successScreen.classList.add('active');
        if (tg.HapticFeedback) {
            tg.HapticFeedback.notificationOccurred('success');
        }

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
        if (tg.HapticFeedback) {
            tg.HapticFeedback.notificationOccurred('error');
        }
        showToast({
            title: 'Не удалось оформить запись',
            message: error.message || 'Попробуйте еще раз.',
            variant: 'neutral',
            duration: 2800,
        });
    } finally {
        modalSubmit.disabled = false;
        modalSubmit.textContent = 'Подтвердить запись';
    }
}
