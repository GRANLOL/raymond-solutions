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
let busySlots = {};

const months = ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря"];
const shortMonths = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"];
const days = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

// --- API ---
async function fetchBusySlots() {
    try {
        const response = await fetch('https://miki-suffruticose-restrainedly.ngrok-free.dev/api/busy-slots', {
            headers: {
                'ngrok-skip-browser-warning': 'true',
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            console.error("Server API Error. Status:", response.status);
            console.log("Raw Response Text:", await response.text());
            throw new Error('Server returned ' + response.status);
        }

        const data = await response.json();

        // Validate it's a dictionary
        if (typeof data === 'object' && data !== null) {
            busySlots = data;
        } else {
            console.warn("Expected dictionary, got:", data);
        }
    } catch (e) {
        console.error("Error fetching busy slots:", e);
    }
}

// --- D. DOM Elements ---
const selectTrigger = document.getElementById('select-trigger');
const selectLabel = document.getElementById('select-label');
const customOptionsContainer = document.getElementById('custom-options');
const dateContainer = document.getElementById('date-container');
const timeGrid = document.getElementById('time-grid');
const nameInput = document.getElementById('name-input');
const phoneInput = document.getElementById('phone-input');

// Modal Elements
const modal = document.getElementById('confirm-modal');
const modalService = document.getElementById('modal-service');
const modalDate = document.getElementById('modal-date');
const modalTime = document.getElementById('modal-time');
const modalName = document.getElementById('modal-name');
const modalPhone = document.getElementById('modal-phone');
const modalCancel = document.getElementById('modal-cancel');
const modalSubmit = document.getElementById('modal-submit');

// Success Screen Elements
const successScreen = document.getElementById('success-screen');
const successService = document.getElementById('success-service');
const successDate = document.getElementById('success-date');
const successTime = document.getElementById('success-time');

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
    dateContainer.innerHTML = '';
    const today = new Date();
    for (let i = 0; i < 7; i++) {
        const targetDate = new Date();
        targetDate.setDate(today.getDate() + i);

        const dDay = days[targetDate.getDay()];
        const dMonth = shortMonths[targetDate.getMonth()];
        const dNum = targetDate.getDate();

        const m = (targetDate.getMonth() + 1).toString().padStart(2, '0');
        const d = dNum.toString().padStart(2, '0');
        const formattedDate = `${d}.${m}`;

        const dFull = `${dNum} ${months[targetDate.getMonth()]}`;

        const card = document.createElement('div');
        card.className = 'date-card fade-in';
        card.innerHTML = `
            <div class="date-day">${dDay}</div>
            <div class="date-num">${dNum}</div>
            <div class="date-month">${dMonth}</div>
        `;

        if (busySlots[formattedDate] && busySlots[formattedDate].length >= config.timeSlots.length) {
            card.classList.add('date-full');
        } else {
            card.onclick = () => selectDate(card, dFull, formattedDate);
        }

        dateContainer.appendChild(card);
    }
}

// Generate Times
function generateTimes(formattedDate = null) {
    timeGrid.innerHTML = '';
    const busyTimes = formattedDate && busySlots[formattedDate] ? busySlots[formattedDate] : [];

    config.timeSlots.forEach(time => {
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

// --- F. Event Handlers ---
function selectDate(element, dFull, formattedDate) {
    tg.HapticFeedback.impactOccurred('light');
    document.querySelectorAll('.date-card').forEach(el => el.classList.remove('active'));
    element.classList.add('active');
    selectedDate = formattedDate; // use the DB format to submit
    selectedTime = null; // reset time selection
    generateTimes(formattedDate);
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
    const digitsOnly = phoneInput.value.replace(/\D/g, '');
    const isPhoneValid = digitsOnly.length >= 11; // 7 + 10 digits
    const isNameValid = nameInput.value.trim().length > 0;

    if (selectedService && selectedDate && selectedTime && isPhoneValid && isNameValid) {
        if (tg.MainButton) {
            tg.MainButton.text = "ПОДТВЕРДИТЬ ЗАПИСЬ";
            tg.MainButton.color = config.themeColors.mainButtonColor;
            tg.MainButton.textColor = config.themeColors.mainButtonTextColor;
            tg.MainButton.show();

            tg.MainButton.offClick(submitData); // Remove previous if any
            tg.MainButton.offClick(showModal);
            tg.MainButton.onClick(showModal);
        }
    } else {
        if (tg.MainButton) tg.MainButton.hide();
    }
}

// Name input validation listener
nameInput.addEventListener('input', () => {
    checkConfirmation();
});

// Phone input validation with Mask
phoneInput.addEventListener('input', (e) => {
    // Fire haptic on every digit except backspace if we want, but letting it fire on input is fine
    tg.HapticFeedback.impactOccurred('light');

    let input = e.target.value.replace(/\D/g, ''); // Keep only digits

    // Force start with 7
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

function showModal() {
    tg.HapticFeedback.impactOccurred('medium');

    // Populate Modal Info
    modalService.textContent = selectedService;
    modalDate.textContent = selectedDate;
    modalTime.textContent = selectedTime;
    modalName.textContent = nameInput.value.trim();
    modalPhone.textContent = phoneInput.value;

    // Show Modal
    modal.classList.add('active');
    tg.MainButton.hide();
}

function hideModal() {
    tg.HapticFeedback.impactOccurred('light');
    modal.classList.remove('active');
    tg.MainButton.show();
}

modalCancel.addEventListener('click', hideModal);
modalSubmit.addEventListener('click', submitData);

function submitData() {
    tg.HapticFeedback.impactOccurred('medium');
    if (!selectedService || !selectedDate || !selectedTime) return;

    tg.MainButton.showProgress();
    modalSubmit.disabled = true;
    modalSubmit.textContent = "Секунду...";

    const data = {
        service: selectedService,
        date: selectedDate,
        time: selectedTime,
        phone: phoneInput.value,
        name: nameInput.value.trim()
    };

    // Hide Confirmation Modal
    modal.classList.remove('active');

    // Populate and Show Success Screen
    successService.textContent = selectedService;
    successDate.textContent = document.querySelector('.date-card.active .date-num').textContent + ' ' + document.querySelector('.date-card.active .date-month').textContent;
    successTime.textContent = selectedTime;

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
}

// --- G. Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    // Pre-fill user name from Telegram WebApp Context
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        nameInput.value = tg.initDataUnsafe.user.first_name || '';
    }

    await fetchBusySlots();
    populateServices();
    generateDates();
    generateTimes();
});
