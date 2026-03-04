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
let dynamicServices = [];
let dynamicCategories = [];
let dynamicTimeSlots = [];
let dynamicMasters = [];
let useMasters = false;
let selectedMaster = null;

let dynamicBookingWindow = 7;
let workingDays = [1, 2, 3, 4, 5, 6, 0];
let blacklistedDates = [];

const months = ["Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря"];
const shortMonths = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"];
const days = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

// --- API ---
async function fetchBusySlots(masterId = null) {
    try {
        let url = 'https://miki-suffruticose-restrainedly.ngrok-free.dev/api/busy-slots';
        if (masterId !== null) {
            url += `?master_id=${masterId}`;
        }
        const response = await fetch(url, {
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

async function fetchContent() {
    try {
        const response = await fetch('https://miki-suffruticose-restrainedly.ngrok-free.dev/api/get-content', {
            headers: {
                'ngrok-skip-browser-warning': 'true',
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) throw new Error('Server returned ' + response.status);

        const data = await response.json();
        if (data.services && data.time_slots) {
            dynamicServices = data.services;
            if (data.categories) {
                dynamicCategories = data.categories;
            }
            if (data.masters) {
                dynamicMasters = data.masters;
            }
            if (data.use_masters !== undefined) {
                useMasters = data.use_masters;
            }
            dynamicTimeSlots = data.time_slots.map(ts => ts.time_value);
            if (data.booking_window) {
                dynamicBookingWindow = data.booking_window;
            }
            if (data.working_days) {
                workingDays = data.working_days;
            }
            if (data.blacklisted_dates) {
                blacklistedDates = data.blacklisted_dates;
            }
        }
    } catch (e) {
        console.error("Error fetching available content:", e);
        // Fallbacks back to config if API fails completely to ensure app still loads somewhat
        dynamicServices = config.services;
        dynamicTimeSlots = config.timeSlots;
        dynamicBookingWindow = 7;
        workingDays = [1, 2, 3, 4, 5, 6, 0];
        blacklistedDates = [];
        dynamicMasters = [];
        useMasters = false;
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

// Helper: create a clickable service row
function createServiceOption(serviceObj) {
    const optionDiv = document.createElement('div');
    optionDiv.className = 'custom-option';
    optionDiv.innerHTML = `
        <span class="service-name">${serviceObj.name}</span>
        <span class="service-price">${serviceObj.price}</span>
    `;
    optionDiv.addEventListener('click', () => {
        tg.HapticFeedback.impactOccurred('light');
        selectLabel.textContent = serviceObj.name;
        selectTrigger.classList.add('selected');

        document.querySelectorAll('.custom-option').forEach(opt => opt.classList.remove('selected'));
        optionDiv.classList.add('selected');

        closeDropdown();
        selectedService = serviceObj.name;
        selectedMaster = null;

        if (useMasters && dynamicMasters.length > 0) {
            document.getElementById('master-container').style.display = 'block';
            populateMasters();
            document.getElementById('date-container').style.display = 'none';
            document.getElementById('time-grid').style.display = 'none';
            document.querySelectorAll('.section-title')[2].style.display = 'none';
            document.querySelectorAll('.section-title')[3].style.display = 'none';
        } else {
            document.getElementById('master-container').style.display = 'none';
            document.getElementById('date-container').style.display = 'flex';
            document.getElementById('time-grid').style.display = 'grid';
            document.querySelectorAll('.section-title')[2].style.display = 'block';
            document.querySelectorAll('.section-title')[3].style.display = 'block';
        }
        checkConfirmation();
    }, { passive: true });
    return optionDiv;
}

// Custom Dropdown Logic
function populateServices(searchQuery = '') {
    const resultsContainer = document.getElementById('service-results');
    resultsContainer.innerHTML = '';

    // === SEARCH MODE: flat list ===
    if (searchQuery.trim().length > 0) {
        const query = searchQuery.toLowerCase();
        const filtered = dynamicServices.filter(s =>
            s.name.toLowerCase().includes(query) || s.price.toLowerCase().includes(query)
        );
        if (filtered.length === 0) {
            const notFoundDiv = document.createElement('div');
            notFoundDiv.className = 'custom-option';
            notFoundDiv.innerHTML = '<span class="service-name" style="color:#909090;">Нет услуг по вашему запросу</span>';
            resultsContainer.appendChild(notFoundDiv);
            return;
        }
        filtered.forEach(s => resultsContainer.appendChild(createServiceOption(s)));
        return;
    }

    // === ACCORDION MODE: category tree ===
    const topCategories = dynamicCategories.filter(c => c.parent_id === null || c.parent_id === undefined);
    const hasCategories = topCategories.length > 0;

    function renderCategoryNode(cat, isRoot) {
        const subCats = dynamicCategories.filter(c => c.parent_id === cat.id);
        const dirServices = dynamicServices.filter(s => s.category_id === cat.id);

        if (subCats.length === 0 && dirServices.length === 0) return null;

        const group = document.createElement('div');
        group.className = isRoot ? 'cat-group' : 'subcat-group';

        const header = document.createElement('div');
        header.className = isRoot ? 'cat-header' : 'subcat-header';

        const titleClass = isRoot ? 'cat-name' : 'subcat-name';
        const arrowClass = isRoot ? 'cat-arrow' : 'subcat-arrow';
        const hasChildren = subCats.length > 0 || dirServices.length > 0;

        header.innerHTML = `
            <span class="${titleClass}">${cat.name}</span>
            ${hasChildren ? `<span class="${arrowClass}">›</span>` : ''}
        `;

        const body = document.createElement('div');
        body.className = isRoot ? 'cat-body' : 'subcat-body';

        subCats.forEach(sub => {
            const subNode = renderCategoryNode(sub, false);
            if (subNode) body.appendChild(subNode);
        });

        dirServices.forEach(s => body.appendChild(createServiceOption(s)));

        header.addEventListener('click', (e) => {
            if (!isRoot) e.stopPropagation();
            if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            group.classList.toggle('open');
        });

        group.appendChild(header);
        group.appendChild(body);
        return group;
    }

    topCategories.forEach(topCat => {
        const node = renderCategoryNode(topCat, true);
        if (node) resultsContainer.appendChild(node);
    });

    // Uncategorized services at the bottom
    const uncategorized = dynamicServices.filter(s => s.category_id === null || s.category_id === undefined);
    if (uncategorized.length > 0) {
        if (hasCategories) {
            const divider = document.createElement('div');
            divider.className = 'cat-divider';
            divider.textContent = 'Другие услуги';
            resultsContainer.appendChild(divider);
        }
        uncategorized.forEach(s => resultsContainer.appendChild(createServiceOption(s)));
    }
}

// --- Search listener (bound ONCE, never destroyed) ---
(function initSearchListener() {
    const searchInput = document.getElementById('search-input');
    const searchContainer = document.getElementById('search-container');
    if (searchInput) {
        searchContainer.addEventListener('click', (e) => e.stopPropagation());
        searchInput.addEventListener('input', (e) => {
            populateServices(e.target.value);
        });
    }
})();

function toggleDropdown() {
    tg.HapticFeedback.impactOccurred('light');
    selectTrigger.classList.toggle('open');
    customOptionsContainer.classList.toggle('open');
    document.getElementById('service-wrapper').classList.toggle('open');
}

function closeDropdown() {
    selectTrigger.classList.remove('open');
    customOptionsContainer.classList.remove('open');
    document.getElementById('service-wrapper').classList.remove('open');
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.value = '';
        searchInput.blur();
    }
}

function populateMasters() {
    const masterGrid = document.getElementById('master-grid');
    masterGrid.innerHTML = '';

    dynamicMasters.forEach(masterObj => {
        const mDiv = document.createElement('div');
        mDiv.className = 'master-card';
        // We'd use a real avatar or fallback to a default icon
        mDiv.innerHTML = `
            <div class="master-avatar">👤</div>
            <div class="master-name">${masterObj.name}</div>
        `;

        mDiv.addEventListener('click', async () => {
            tg.HapticFeedback.impactOccurred('light');
            document.querySelectorAll('.master-card').forEach(el => el.classList.remove('selected'));
            mDiv.classList.add('selected');
            selectedMaster = masterObj;

            // Fetch busy slots for this specific master
            await fetchBusySlots(masterObj.id);

            // show date / time
            document.getElementById('date-container').style.display = 'flex';
            document.getElementById('time-grid').style.display = 'grid';
            document.querySelectorAll('.section-title')[2].style.display = 'block';
            document.querySelectorAll('.section-title')[3].style.display = 'block';

            // Re-render dates and times with per-master busy slots
            generateDates();
            selectedDate = null;
            selectedTime = null;
            timeGrid.innerHTML = '';
            checkConfirmation();
        });

        masterGrid.appendChild(mDiv);
    });
}

const closeDropdownListener = (e) => {
    if (!document.getElementById('service-wrapper').contains(e.target)) {
        closeDropdown();
    }
};

document.addEventListener('click', closeDropdownListener, { passive: true });
document.addEventListener('touchstart', closeDropdownListener, { passive: true });

selectTrigger.addEventListener('click', toggleDropdown);

// Generate Dates
function generateDates() {
    dateContainer.innerHTML = '';
    const today = new Date();

    let currentMonthHeader = -1;

    for (let i = 0; i < dynamicBookingWindow; i++) {
        const targetDate = new Date();
        targetDate.setDate(today.getDate() + i);

        // Check if we need a new month header (only if crossing over months in view)
        // Simplified approach: just rely on the card's month indicator if it's compact.
        // If user explicitly asked for a month header over the dates, we can add it, but it disrupts flex.
        // We will just make sure date cards show the month correctly.

        const dDay = days[targetDate.getDay()];
        const dMonth = shortMonths[targetDate.getMonth()];
        const dNum = targetDate.getDate();

        const m = (targetDate.getMonth() + 1).toString().padStart(2, '0');
        const d = dNum.toString().padStart(2, '0');
        const formattedDate = `${d}.${m}.${targetDate.getFullYear()}`;
        // Blacklisted dates are in DD.MM.YYYY format

        const dFull = `${dNum} ${months[targetDate.getMonth()]}`;

        const targetDay = targetDate.getDay();
        const isOffDay = !workingDays.includes(targetDay) || blacklistedDates.includes(formattedDate);

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

            if (busySlots[formattedDate] && busySlots[formattedDate].length >= dynamicTimeSlots.length) {
                card.classList.add('date-full');
            } else {
                card.onclick = () => selectDate(card, dFull, formattedDate);
            }
        }

        dateContainer.appendChild(card);
    }
}

// Generate Times
function generateTimes(formattedDate = null) {
    timeGrid.innerHTML = '';
    const busyTimes = formattedDate && busySlots[formattedDate] ? busySlots[formattedDate] : [];

    dynamicTimeSlots.forEach(time => {
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

    const isMasterValid = useMasters ? (selectedMaster !== null) : true;

    if (selectedService && isMasterValid && selectedDate && selectedTime && isPhoneValid && isNameValid) {
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

    // Async execution to let Telegram MainButton press animation finish before rendering
    setTimeout(() => {
        // Populate Modal Info
        modalService.textContent = selectedService;
        const mr = document.getElementById('modal-master-row');
        if (useMasters && selectedMaster) {
            document.getElementById('modal-master').textContent = selectedMaster.name;
            mr.style.display = 'block';
        } else {
            mr.style.display = 'none';
        }

        modalDate.textContent = selectedDate;
        modalTime.textContent = selectedTime;
        modalName.textContent = nameInput.value.trim();
        modalPhone.textContent = phoneInput.value;

        // Show Modal
        modal.classList.add('active');
        tg.MainButton.hide();
    }, 0);
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

    if (useMasters && selectedMaster) {
        data.master_id = selectedMaster.id;
    }

    setTimeout(() => {
        // Hide Confirmation Modal and Telegram Main Button
        modal.classList.remove('active');
        tg.MainButton.hide();

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
    }, 0);
}

// --- G. Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    // Implement Passive Event Listeners for touch events to prevent scroll-blocking
    document.addEventListener('touchstart', function () { }, { passive: true });
    document.addEventListener('touchmove', function () { }, { passive: true });

    // Pre-fill user name from Telegram WebApp Context
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        nameInput.value = tg.initDataUnsafe.user.first_name || '';
    }

    await fetchContent();
    await fetchBusySlots();
    populateServices();
    generateDates();
    generateTimes();
});
