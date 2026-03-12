import { tg } from '../telegram.js';
import { store } from '../store.js';
import { checkConfirmation } from './form.js';

// Helper function to check if a given date has any available (non-past, non-busy) slots
function hasAvailableSlots(formattedDate) {
    const busyArr = formattedDate && store.busySlots[formattedDate] ? store.busySlots[formattedDate] : [];

    const timeMatch = store.workingHours.match(/(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/);
    let startStr = '10:00', endStr = '20:00';
    if (timeMatch) {
        startStr = timeMatch[1];
        endStr = timeMatch[2];
    } else if (store.workingHours.includes('-')) {
        [startStr, endStr] = store.workingHours.split('-');
    }

    const [startH, startM] = startStr.split(':').map(Number);
    const [endH, endM] = endStr.split(':').map(Number);

    const startMins = startH * 60 + startM;
    const endMins = endH * 60 + endM;
    const interval = Number(store.scheduleInterval) || 30;
    const serviceDur = Number(store.selectedDuration) || 60;

    let currentSalonMins = -1;
    const nowLocal = new Date();
    const utcMs = nowLocal.getTime() + (nowLocal.getTimezoneOffset() * 60000);
    const salonNowMs = utcMs + (store.timezoneOffset * 3600000);
    const salonNow = new Date(salonNowMs);

    const sM = (salonNow.getMonth() + 1).toString().padStart(2, '0');
    const sD = salonNow.getDate().toString().padStart(2, '0');
    const salonTodayStr = `${sD}.${sM}.${salonNow.getFullYear()}`;

    if (formattedDate === salonTodayStr) {
        currentSalonMins = salonNow.getHours() * 60 + salonNow.getMinutes();
    }

    for (let m = startMins; m + serviceDur <= endMins; m += interval) {
        // Skip past slots entirely
        if (m <= currentSalonMins) {
            continue;
        }

        const slotStart = m;
        const slotEnd = m + serviceDur;

        let isBusy = false;
        for (const busy of busyArr) {
            const [bH, bM] = busy.time.split(':').map(Number);
            const bStart = bH * 60 + bM;
            const bEnd = bStart + (busy.duration || 60);

            if (slotStart < bEnd && slotEnd > bStart) {
                isBusy = true;
                break;
            }
        }

        if (!isBusy) {
            return true; // Found at least one available slot
        }
    }
    return false; // No available slots found for this date
}

export function generateDates() {
    const dateContainer = document.getElementById('date-container');
    dateContainer.innerHTML = '';

    // Calculate current time in salon's timezone
    const nowLocal = new Date();
    const utcMs = nowLocal.getTime() + (nowLocal.getTimezoneOffset() * 60000);
    const salonNowMs = utcMs + (store.timezoneOffset * 3600000);
    const todayTarget = new Date(salonNowMs);

    for (let i = 0; i < store.dynamicBookingWindow; i++) {
        const targetDate = new Date(salonNowMs);
        targetDate.setDate(todayTarget.getDate() + i);

        const dDay = store.days[targetDate.getDay()];
        const dMonth = store.shortMonths[targetDate.getMonth()];
        const dNum = targetDate.getDate();

        const m = (targetDate.getMonth() + 1).toString().padStart(2, '0');
        const d = dNum.toString().padStart(2, '0');
        const formattedDate = `${d}.${m}.${targetDate.getFullYear()}`;
        const dFull = `${dNum} ${store.months[targetDate.getMonth()]}`;

        const targetDay = targetDate.getDay();
        const isOffDay = !store.workingDays.includes(targetDay) || store.blacklistedDates.includes(formattedDate);
        const hasSlots = hasAvailableSlots(formattedDate); // Check for available slots

        const card = document.createElement('div');
        card.className = 'date-card fade-in';

        if (isOffDay || !hasSlots) { // Disable if it's an off day or has no available slots
            card.classList.add('date-off');
            card.innerHTML = `
                <div class="date-day">${dDay}</div>
                <div class="date-month" style="font-size: 9px; font-weight: 500; margin-top: 4px;">${isOffDay ? 'Выходной' : 'Нет мест'}</div>
            `;
        } else {
            card.innerHTML = `
                <div class="date-day">${dDay}</div>
                <div class="date-num">${dNum}</div>
                <div class="date-month">${dMonth}</div>
            `;
            card.onclick = () => selectDate(card, dFull, formattedDate);
        }

        dateContainer.appendChild(card);
    }
}

export function generateTimes(formattedDate = null) {
    const timeGrid = document.getElementById('time-grid');
    timeGrid.innerHTML = '';
    const busyArr = formattedDate && store.busySlots[formattedDate] ? store.busySlots[formattedDate] : [];

    // Use regex to strictly extract HH:MM pairs, ignoring other text like "ПН-ВС"
    const timeMatch = store.workingHours.match(/(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})/);
    let startStr = '10:00', endStr = '20:00';
    if (timeMatch) {
        startStr = timeMatch[1];
        endStr = timeMatch[2];
    } else if (store.workingHours.includes('-')) {
        [startStr, endStr] = store.workingHours.split('-');
    }

    const [startH, startM] = startStr.split(':').map(Number);
    const [endH, endM] = endStr.split(':').map(Number);

    const startMins = startH * 60 + startM;
    const endMins = endH * 60 + endM;
    const interval = Number(store.scheduleInterval) || 30;
    const serviceDur = Number(store.selectedDuration) || 60;

    // Timezone check to prevent booking in the past
    let currentSalonMins = -1;
    const nowLocal = new Date();
    const utcMs = nowLocal.getTime() + (nowLocal.getTimezoneOffset() * 60000);
    const salonNowMs = utcMs + (store.timezoneOffset * 3600000);
    const salonNow = new Date(salonNowMs);

    const sM = (salonNow.getMonth() + 1).toString().padStart(2, '0');
    const sD = salonNow.getDate().toString().padStart(2, '0');
    const salonTodayStr = `${sD}.${sM}.${salonNow.getFullYear()}`;

    if (formattedDate === salonTodayStr) {
        currentSalonMins = salonNow.getHours() * 60 + salonNow.getMinutes();
    }

    for (let m = startMins; m + serviceDur <= endMins; m += interval) {
        // Skip past slots entirely
        if (m <= currentSalonMins) {
            continue;
        }

        const h = Math.floor(m / 60).toString().padStart(2, '0');
        const min = (m % 60).toString().padStart(2, '0');
        const timeStr = `${h}:${min}`;

        const slotStart = m;
        const slotEnd = m + serviceDur;

        let isBusy = false;
        for (const busy of busyArr) {
            const [bH, bM] = busy.time.split(':').map(Number);
            const bStart = bH * 60 + bM;
            const bEnd = bStart + (busy.duration || 60);

            if (slotStart < bEnd && slotEnd > bStart) {
                isBusy = true;
                break;
            }
        }

        const slot = document.createElement('div');
        slot.className = 'time-slot fade-in';
        slot.textContent = timeStr;

        if (isBusy) {
            slot.classList.add('slot-busy');
        } else {
            slot.onclick = () => selectTime(slot, timeStr);
        }

        timeGrid.appendChild(slot);
    }
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
