import { tg } from '../telegram.js?v=15';
import { store } from '../store.js?v=15';
import { checkConfirmation } from './form.js?v=15';

function getWorkingDayBounds() {
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

    return {
        startMins: startH * 60 + startM,
        endMins: endH * 60 + endM,
    };
}

function getSalonNow() {
    const nowLocal = new Date();
    const utcMs = nowLocal.getTime() + (nowLocal.getTimezoneOffset() * 60000);
    const salonNowMs = utcMs + (store.timezoneOffset * 3600000);
    return new Date(salonNowMs);
}

function getSalonTodayString(salonNow) {
    const sM = (salonNow.getMonth() + 1).toString().padStart(2, '0');
    const sD = salonNow.getDate().toString().padStart(2, '0');
    return `${sD}.${sM}.${salonNow.getFullYear()}`;
}

function getBusyInterval(busy) {
    const [bH, bM] = busy.time.split(':').map(Number);
    const start = bH * 60 + bM;
    const end = start + (busy.duration || 60);
    return { start, end };
}

function resolveBusyAvailabilityReason(busy, slotStart, slotEnd) {
    const { start: busyStart, end: busyEnd } = getBusyInterval(busy);
    if (!(slotStart < busyEnd && slotEnd > busyStart)) {
        return null;
    }

    const kind = busy.kind || 'booking';
    if (kind === 'booking') {
        return { available: false, reason: 'busy_overlap', label: 'Занято' };
    }

    const startsInsideBreak = slotStart >= busyStart && slotStart < busyEnd;
    if (kind === 'lunch') {
        return {
            available: false,
            reason: startsInsideBreak ? 'lunch_break' : 'crosses_break',
            label: startsInsideBreak ? (busy.label || 'Обед') : 'Не помещается',
        };
    }

    return {
        available: false,
        reason: startsInsideBreak ? 'custom_break' : 'crosses_break',
        label: startsInsideBreak ? (busy.label || 'Перерыв') : 'Не помещается',
    };
}

export function getSlotAvailability(formattedDate, timeStr, durationOverride = null) {
    if (!formattedDate || !timeStr) {
        return { available: true, reason: null };
    }

    const busyArr = store.busySlots[formattedDate] || [];
    const { startMins, endMins } = getWorkingDayBounds();
    const serviceDur = Number(durationOverride ?? store.selectedDuration) || 60;

    const [h, min] = timeStr.split(':').map(Number);
    const slotStart = h * 60 + min;
    const slotEnd = slotStart + serviceDur;

    const salonNow = getSalonNow();
    const salonTodayStr = getSalonTodayString(salonNow);

    if (formattedDate === salonTodayStr) {
        const currentSalonMins = salonNow.getHours() * 60 + salonNow.getMinutes();
        if (slotStart <= currentSalonMins) {
            return { available: false, reason: 'past' };
        }
    }

    if (slotStart < startMins || slotEnd > endMins) {
        return { available: false, reason: 'outside_working_hours' };
    }

    for (const busy of busyArr) {
        const busyAvailability = resolveBusyAvailabilityReason(busy, slotStart, slotEnd);
        if (busyAvailability) {
            return busyAvailability;
        }
    }

    return { available: true, reason: null };
}

// Helper function to check if a given date has any available (non-past, non-busy) slots
export function hasAvailableSlots(formattedDate, durationOverride = null) {
    const { startMins, endMins } = getWorkingDayBounds();
    const interval = Number(store.scheduleInterval) || 30;
    const serviceDur = Number(durationOverride ?? store.selectedDuration) || 60;

    const salonNow = getSalonNow();
    const salonTodayStr = getSalonTodayString(salonNow);

    let currentSalonMins = -1;

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
        const timeStr = `${Math.floor(m / 60).toString().padStart(2, '0')}:${(m % 60).toString().padStart(2, '0')}`;
        const availability = getSlotAvailability(formattedDate, timeStr, durationOverride);
        isBusy = !availability.available;

        if (!isBusy) {
            return true; // Found at least one available slot
        }
    }
    return false; // No available slots found for this date
}

function renderDateEmptyState(dateContainer) {
    dateContainer.classList.add('date-container--empty');

    const emptyState = document.createElement('div');
    emptyState.className = 'date-container-empty';
    emptyState.innerHTML = '<span style="font-size: 18px; margin-right: 8px;">✨</span>Выберите услугу, чтобы увидеть расписание';
    dateContainer.appendChild(emptyState);
}

function renderDateSkeletons(container, count = 7) {
    container.innerHTML = '';
    container.classList.remove('date-container--empty');
    for (let i = 0; i < count; i++) {
        const skeleton = document.createElement('div');
        skeleton.className = 'skeleton skeleton-date';
        skeleton.style.animationDelay = `${i * 30}ms`;
        container.appendChild(skeleton);
    }
}

function renderTimeSkeletons(container, count = 6) {
    container.innerHTML = '';
    for (let i = 0; i < count; i++) {
        const skeleton = document.createElement('div');
        skeleton.className = 'skeleton skeleton-time';
        // Diagonal grid stagger
        skeleton.style.animationDelay = `${(Math.floor(i / 3) + (i % 3)) * 30}ms`;
        container.appendChild(skeleton);
    }
}

// Use a counter to prevent overlapping asynchronous renders
let dateGenerationToken = 0;

export async function generateDates() {
    const currentToken = ++dateGenerationToken;
    const dateContainer = document.getElementById('date-container');
    
    if (!store.selectedService) {
        dateContainer.innerHTML = '';
        renderDateEmptyState(dateContainer);
        return;
    }

    renderDateSkeletons(dateContainer, 7);
    
    // Artificial premium delay for glassmorphism skeletons
    await new Promise(r => setTimeout(r, 400));
    
    if (currentToken !== dateGenerationToken) return; // Abort if selection changed

    dateContainer.innerHTML = '';
    dateContainer.classList.remove('date-container--empty');
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
        const hasSlots = hasAvailableSlots(formattedDate);

        const card = document.createElement('div');
        card.className = 'date-card fade-in';
        card.style.animationDelay = `${i * 35}ms`;

        if (isOffDay || !hasSlots) {
            card.classList.add(isOffDay ? 'date-off' : 'date-full');
            card.innerHTML = `
                <div class="date-day">${dDay}</div>
                <div class="date-num">${dNum}</div>
                <div class="date-month">${dMonth}</div>
            `;
        } else {
            card.innerHTML = `
                <div class="date-day">${dDay}</div>
                <div class="date-num">${dNum}</div>
                <div class="date-month">${dMonth}</div>
            `;
            card.onclick = () => selectDate(card, dFull, formattedDate);
            if (store.selectedDate === formattedDate) {
                card.classList.add('active');
            }
        }

        dateContainer.appendChild(card);
    }
}

let timeGenerationToken = 0;

export async function generateTimes(formattedDate = null) {
    const currentToken = ++timeGenerationToken;
    const timeGrid = document.getElementById('time-grid');
    
    if (!formattedDate) {
        timeGrid.innerHTML = '';
        const emptyState = document.createElement('div');
        emptyState.className = 'time-grid-empty';
        emptyState.innerHTML = '<span style="font-size: 16px; margin-right: 8px;">🕒</span>Сначала выберите дату, чтобы увидеть время';
        timeGrid.appendChild(emptyState);
        return;
    }

    renderTimeSkeletons(timeGrid, 9);

    await new Promise(r => setTimeout(r, 350));
    
    if (currentToken !== timeGenerationToken) return;

    timeGrid.innerHTML = '';

    // Use regex to strictly extract HH:MM pairs, ignoring other text like day labels
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

    let renderedSlots = 0;

    for (let m = startMins; m + serviceDur <= endMins; m += interval) {
        // Skip past slots entirely
        if (m <= currentSalonMins) {
            continue;
        }

        const h = Math.floor(m / 60).toString().padStart(2, '0');
        const min = (m % 60).toString().padStart(2, '0');
        const timeStr = `${h}:${min}`;

        const slot = document.createElement('div');
        slot.className = 'time-slot fade-in';
        // Elegant staggered delay (diagonal flow)
        slot.style.animationDelay = `${(renderedSlots % 3 + Math.floor(renderedSlots / 3)) * 35}ms`;
        
        const availability = getSlotAvailability(formattedDate, timeStr);
        const content = document.createElement('div');
        content.className = 'time-slot-content';

        const timeLabel = document.createElement('span');
        timeLabel.className = 'time-slot-time';
        timeLabel.textContent = timeStr;
        content.appendChild(timeLabel);

        if (!availability.available) {
            slot.classList.add('slot-busy');
            slot.classList.add(`slot-${availability.reason.replace(/_/g, '-')}`);
            const note = document.createElement('span');
            note.className = 'time-slot-note';
            note.textContent = availability.label || 'Недоступно';
            content.appendChild(note);
        } else {
            slot.onclick = () => selectTime(slot, timeStr);
            if (store.selectedTime === timeStr) {
                slot.classList.add('active');
            }
        }

        slot.appendChild(content);
        timeGrid.appendChild(slot);
        renderedSlots += 1;
    }

    if (renderedSlots === 0) {
        const emptyState = document.createElement('div');
        emptyState.className = 'time-grid-empty';
        emptyState.innerHTML = '<span style="font-size: 16px; margin-right: 8px;">😔</span>На эту дату сейчас нет слотов';
        timeGrid.appendChild(emptyState);
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
    document.dispatchEvent(new CustomEvent('booking-selection-changed'));
}

export function selectTime(element, timeStr) {
    tg.HapticFeedback.impactOccurred('light');
    document.querySelectorAll('.time-slot').forEach(el => el.classList.remove('active'));
    element.classList.add('active');
    store.selectedTime = timeStr;
    checkConfirmation();
    document.dispatchEvent(new CustomEvent('booking-selection-changed'));
}
