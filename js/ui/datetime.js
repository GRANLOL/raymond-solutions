import { tg } from '../telegram.js';
import { store } from '../store.js';
import { checkConfirmation } from './form.js';

export function generateDates() {
    const dateContainer = document.getElementById('date-container');
    dateContainer.innerHTML = '';
    const today = new Date();

    for (let i = 0; i < store.dynamicBookingWindow; i++) {
        const targetDate = new Date();
        targetDate.setDate(today.getDate() + i);

        const dDay = store.days[targetDate.getDay()];
        const dMonth = store.shortMonths[targetDate.getMonth()];
        const dNum = targetDate.getDate();

        const m = (targetDate.getMonth() + 1).toString().padStart(2, '0');
        const d = dNum.toString().padStart(2, '0');
        const formattedDate = `${d}.${m}.${targetDate.getFullYear()}`;
        const dFull = `${dNum} ${store.months[targetDate.getMonth()]}`;

        const targetDay = targetDate.getDay();
        const isOffDay = !store.workingDays.includes(targetDay) || store.blacklistedDates.includes(formattedDate);

        const card = document.createElement('div');
        card.className = 'date-card fade-in';

        if (isOffDay) {
            card.classList.add('date-off');
            card.innerHTML = `
                <div class="date-day">${dDay}</div>
                <div class="date-month" style="font-size: 11px; font-weight: 500; margin-top: 6px;">Выходной</div>
            `;
        } else {
            card.innerHTML = `
                <div class="date-day">${dDay}</div>
                <div class="date-num">${dNum}</div>
                <div class="date-month">${dMonth}</div>
            `;

            if (store.busySlots[formattedDate] && store.busySlots[formattedDate].length >= store.dynamicTimeSlots.length) {
                card.classList.add('date-full');
            } else {
                card.onclick = () => selectDate(card, dFull, formattedDate);
            }
        }

        dateContainer.appendChild(card);
    }
}

export function generateTimes(formattedDate = null) {
    const timeGrid = document.getElementById('time-grid');
    timeGrid.innerHTML = '';
    const busyTimes = formattedDate && store.busySlots[formattedDate] ? store.busySlots[formattedDate] : [];

    store.dynamicTimeSlots.forEach(time => {
        const slot = document.createElement('div');
        slot.className = 'time-slot fade-in';
        slot.textContent = time;

        if (busyTimes.includes(time)) {
            slot.classList.add('slot-busy');
        } else {
            slot.onclick = () => selectTime(slot, time);
        }

        timeGrid.appendChild(slot);
    });
}

export function selectDate(element, dFull, formattedDate) {
    tg.HapticFeedback.impactOccurred('light');
    document.querySelectorAll('.date-card').forEach(el => el.classList.remove('active'));
    element.classList.add('active');
    store.selectedDate = formattedDate;
    store.selectedTime = null;
    generateTimes(formattedDate);
    checkConfirmation();
}

export function selectTime(element, timeStr) {
    tg.HapticFeedback.impactOccurred('light');
    document.querySelectorAll('.time-slot').forEach(el => el.classList.remove('active'));
    element.classList.add('active');
    store.selectedTime = timeStr;
    checkConfirmation();
}
