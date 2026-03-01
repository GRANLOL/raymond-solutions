import { config } from './config.js';

// --- A. Configuration Injection ---
document.getElementById('salon-name-display').textContent = config.salonName;

// --- B. Telegram API Initialization ---
const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

tg.setHeaderColor(config.themeColors.headerColor);
tg.setBackgroundColor(config.themeColors.backgroundColor);

// --- C. Application State ---
let selectedService = null;
let selectedDate = null;
let selectedTime = null;

const months = ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря"];
const shortMonths = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"];
const days = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

// --- D. DOM Elements ---
const selectTrigger = document.getElementById('select-trigger');
const selectLabel = document.getElementById('select-label');
const customOptionsContainer = document.getElementById('custom-options');
const dateContainer = document.getElementById('date-container');
const timeGrid = document.getElementById('time-grid');
const phoneInput = document.getElementById('phone-input');

// --- E. Generation Functions ---

// Custom Dropdown Logic
function populateServices() {
    config.services.forEach(service => {
        const optionDiv = document.createElement('div');
        optionDiv.className = 'custom-option';
        optionDiv.textContent = service;

        optionDiv.addEventListener('click', () => {
            tg.HapticFeedback.impactOccurred('light');
            selectLabel.textContent = service;
            selectTrigger.classList.add('selected');

            document.querySelectorAll('.custom-option').forEach(opt => opt.classList.remove('selected'));
            optionDiv.classList.add('selected');

            closeDropdown();
            selectedService = service;
            checkConfirmation();
        });

        customOptionsContainer.appendChild(optionDiv);
    });
}

function toggleDropdown() {
    tg.HapticFeedback.impactOccurred('light');
    selectTrigger.classList.toggle('open');
    customOptionsContainer.classList.toggle('open');
}

function closeDropdown() {
    selectTrigger.classList.remove('open');
    customOptionsContainer.classList.remove('open');
}

document.addEventListener('click', (e) => {
    if (!document.getElementById('service-wrapper').contains(e.target)) {
        closeDropdown();
    }
});

selectTrigger.addEventListener('click', toggleDropdown);

// Generate Dates
function generateDates() {
    const today = new Date();
    for (let i = 0; i < 7; i++) {
        const targetDate = new Date();
        targetDate.setDate(today.getDate() + i);

        const dDay = days[targetDate.getDay()];
        const dMonth = shortMonths[targetDate.getMonth()];
        const dNum = targetDate.getDate();
        const dFull = `${dNum} ${months[targetDate.getMonth()]}`;

        const card = document.createElement('div');
        card.className = 'date-card';
        card.innerHTML = `
            <div class="date-day">${dDay}</div>
            <div class="date-num">${dNum}</div>
            <div class="date-month">${dMonth}</div>
        `;

        card.onclick = () => selectDate(card, dFull);
        dateContainer.appendChild(card);
    }
}

// Generate Times
function generateTimes() {
    config.timeSlots.forEach(time => {
        const slot = document.createElement('div');
        slot.className = 'time-slot';
        slot.textContent = time;

        slot.onclick = () => selectTime(slot, time);
        timeGrid.appendChild(slot);
    });
}

// --- F. Event Handlers ---
function selectDate(element, dateStr) {
    tg.HapticFeedback.impactOccurred('light');
    document.querySelectorAll('.date-card').forEach(el => el.classList.remove('active'));
    element.classList.add('active');
    selectedDate = dateStr;
    checkConfirmation();
}

function selectTime(element, timeStr) {
    tg.HapticFeedback.impactOccurred('light');
    document.querySelectorAll('.time-slot').forEach(el => el.classList.remove('active'));
    element.classList.add('active');
    selectedTime = timeStr;
    checkConfirmation();
}

function checkConfirmation() {
    // Basic phone validation: count digits
    const digitsOnly = phoneInput.value.replace(/\D/g, '');
    const isPhoneValid = digitsOnly.length >= 10;

    if (selectedService && selectedDate && selectedTime && isPhoneValid) {
        if (tg.MainButton) {
            tg.MainButton.text = "ПОДТВЕРДИТЬ ЗАПИСЬ";
            tg.MainButton.color = config.themeColors.mainButtonColor;
            tg.MainButton.textColor = config.themeColors.mainButtonTextColor;
            tg.MainButton.show();

            tg.MainButton.offClick(submitData);
            tg.MainButton.onClick(submitData);
        }
    } else {
        if (tg.MainButton) tg.MainButton.hide();
    }
}

// Phone input validation listener
phoneInput.addEventListener('input', () => {
    checkConfirmation();
});

function submitData() {
    tg.HapticFeedback.impactOccurred('medium');
    if (!selectedService || !selectedDate || !selectedTime) return;

    tg.MainButton.showProgress();

    const data = {
        service: selectedService,
        date: selectedDate,
        time: selectedTime,
        phone: phoneInput.value
    };

    tg.sendData(JSON.stringify(data));
}

// --- G. Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    populateServices();
    generateDates();
    generateTimes();
});
