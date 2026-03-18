import { tg } from '../telegram.js?v=5';
import { store } from '../store.js?v=5';
import { checkConfirmation } from './form.js?v=5';
import { generateDates, generateTimes, getSlotAvailability, hasAvailableSlots } from './datetime.js?v=5';
import { showToast } from './toast.js?v=5';

const selectTrigger = document.getElementById('select-trigger');
const selectLabel = document.getElementById('select-label');
const customOptionsContainer = document.getElementById('custom-options');

function formatServicePrice(priceValue) {
    const raw = String(priceValue ?? '').trim();
    if (!raw) {
        return '';
    }
    if (/[₸₽$€]/.test(raw)) {
        return raw;
    }
    return `${raw} ${store.currencySymbol}`;
}

function getUnavailableServiceMessage(reason) {
    if (reason === 'outside_working_hours') {
        return 'Эта услуга не помещается в выбранное время. Выберите более раннее время или другую дату.';
    }
    if (reason === 'busy_overlap') {
        return 'На выбранное время эта услуга недоступна. Выберите более раннее время или другую дату.';
    }
    if (reason === 'past') {
        return 'Выбранное время уже прошло. Выберите другой слот или другую дату.';
    }
    return 'Эта услуга сейчас недоступна для выбранных даты и времени. Выберите более раннее время или другую дату.';
}

function getServiceAvailability(serviceObj) {
    if (!store.selectedDate || !store.selectedTime) {
        return { selectable: true, reason: null };
    }

    const availability = getSlotAvailability(
        store.selectedDate,
        store.selectedTime,
        serviceObj.duration || 60,
    );

    return {
        selectable: availability.available,
        reason: availability.reason,
    };
}

function categoryHasSelectableContent(categoryId) {
    const subCats = store.dynamicCategories.filter(item => item.parent_id === categoryId);
    const dirServices = store.dynamicServices.filter(service => service.category_id === categoryId);

    if (dirServices.some(service => getServiceAvailability(service).selectable)) {
        return true;
    }

    return subCats.some(sub => categoryHasSelectableContent(sub.id));
}

function syncDateTimeSelectionAfterServiceChange() {
    generateDates();

    if (!store.selectedDate) {
        generateTimes();
        return;
    }

    if (!hasAvailableSlots(store.selectedDate)) {
        store.selectedDate = null;
        store.selectedTime = null;
        generateDates();
        generateTimes();
        showToast({
            title: 'Дата обновлена',
            message: 'Для этой услуги на выбранную дату больше нет подходящих окон. Выберите более раннее время или другую дату.',
            variant: 'neutral',
        });
        return;
    }

    if (store.selectedTime && !getSlotAvailability(store.selectedDate, store.selectedTime).available) {
        store.selectedTime = null;
        showToast({
            title: 'Время обновлено',
            message: 'Для этой услуги выбранное время не подходит. Выберите более раннее время или другую дату.',
            variant: 'neutral',
        });
    }

    generateDates();
    generateTimes(store.selectedDate);
}

export function createServiceOption(serviceObj) {
    const optionDiv = document.createElement('div');
    optionDiv.className = 'custom-option';

    const dot = document.createElement('span');
    dot.className = 'service-dot';
    dot.textContent = '●';

    const name = document.createElement('span');
    name.className = 'service-name';
    name.textContent = serviceObj.name;

    const price = document.createElement('span');
    price.className = 'service-price';
    price.textContent = formatServicePrice(serviceObj.price);

    const availability = getServiceAvailability(serviceObj);
    if (!availability.selectable) {
        optionDiv.classList.add('is-disabled');
        optionDiv.setAttribute('aria-disabled', 'true');
        optionDiv.title = getUnavailableServiceMessage(availability.reason);
    }
    if (store.selectedService === serviceObj.name) {
        optionDiv.classList.add('selected');
    }

    optionDiv.append(dot, name, price);
    optionDiv.addEventListener('click', () => {
        if (!availability.selectable) {
            if (tg.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred('warning');
            }
            showToast({
                title: 'Услуга недоступна',
                message: getUnavailableServiceMessage(availability.reason),
                variant: 'neutral',
            });
            return;
        }

        tg.HapticFeedback.impactOccurred('light');
        selectLabel.textContent = serviceObj.name;
        selectTrigger.classList.add('selected');

        document.querySelectorAll('.custom-option').forEach(opt => opt.classList.remove('selected'));
        optionDiv.classList.add('selected');

        closeDropdown();
        store.selectedService = serviceObj.name;
        store.selectedDuration = serviceObj.duration || 60;
        store.selectedPrice = parseInt((serviceObj.price || '0').replace(/\D/g, '')) || 0;
        syncDateTimeSelectionAfterServiceChange();
        populateServices();
        checkConfirmation();
    }, { passive: true });
    return optionDiv;
}

export function populateServices(searchQuery = '') {
    const resultsContainer = document.getElementById('service-results');
    resultsContainer.innerHTML = '';

    if (searchQuery.trim().length > 0) {
        const query = searchQuery.toLowerCase();
        const filtered = store.dynamicServices.filter(service =>
            service.name.toLowerCase().includes(query) || service.price.toLowerCase().includes(query),
        );
        if (filtered.length === 0) {
            const notFoundDiv = document.createElement('div');
            notFoundDiv.className = 'custom-option';
            notFoundDiv.innerHTML = '<span class="service-name" style="color:#909090;">Нет услуг по вашему запросу</span>';
            resultsContainer.appendChild(notFoundDiv);
            return;
        }
        filtered.forEach(service => resultsContainer.appendChild(createServiceOption(service)));
        return;
    }

    const topCategories = store.dynamicCategories.filter(category => category.parent_id === null || category.parent_id === undefined);
    const hasCategories = topCategories.length > 0;

    function renderCategoryNode(category, isRoot) {
        const subCats = store.dynamicCategories.filter(item => item.parent_id === category.id);
        const dirServices = store.dynamicServices.filter(service => service.category_id === category.id);

        if (subCats.length === 0 && dirServices.length === 0) {
            return null;
        }

        const group = document.createElement('div');
        group.className = isRoot ? 'cat-group' : 'subcat-group';

        const header = document.createElement('div');
        header.className = isRoot ? 'cat-header' : 'subcat-header';
        const hasSelectableContent = categoryHasSelectableContent(category.id);

        const title = document.createElement('span');
        title.className = isRoot ? 'cat-name' : 'subcat-name';
        title.textContent = category.name;
        header.appendChild(title);

        if (subCats.length > 0 || dirServices.length > 0) {
            const arrow = document.createElement('span');
            arrow.className = isRoot ? 'cat-arrow' : 'subcat-arrow';
            arrow.textContent = '›';
            header.appendChild(arrow);
        }

        const body = document.createElement('div');
        body.className = isRoot ? 'cat-body' : 'subcat-body';
        const inner = document.createElement('div');
        inner.className = 'body-inner';

        subCats.forEach(sub => {
            const subNode = renderCategoryNode(sub, false);
            if (subNode) {
                inner.appendChild(subNode);
            }
        });
        dirServices.forEach(service => inner.appendChild(createServiceOption(service)));
        body.appendChild(inner);

        header.addEventListener('click', (e) => {
            if (!isRoot) {
                e.stopPropagation();
            }
            if (!hasSelectableContent) {
                showToast({
                    title: 'Нет доступных услуг',
                    message: 'Для выбранных даты и времени услуги из этого раздела сейчас недоступны. Выберите более раннее время или другую дату.',
                    variant: 'neutral',
                });
                return;
            }
            if (window.tg && tg.HapticFeedback) {
                tg.HapticFeedback.impactOccurred('light');
            }

            const isOpen = group.classList.contains('open');
            if (isOpen) {
                body.style.height = body.scrollHeight + 'px';
                requestAnimationFrame(() => {
                    body.style.height = '0px';
                });
                group.classList.remove('open');
            } else {
                const prevHeight = body.style.height;
                body.style.height = 'auto';
                body.style.overflow = 'visible';
                const targetH = body.scrollHeight;
                body.style.overflow = '';
                body.style.height = prevHeight || '0px';
                body.offsetHeight;
                body.style.height = targetH + 'px';
                group.classList.add('open');
                body.addEventListener('transitionend', () => {
                    if (group.classList.contains('open')) {
                        body.style.height = 'auto';
                    }
                }, { once: true });
            }
        });

        if (!hasSelectableContent) {
            group.classList.add('is-disabled');
            header.classList.add('is-disabled');
        }

        group.appendChild(header);
        group.appendChild(body);
        return group;
    }

    topCategories.forEach(topCategory => {
        const node = renderCategoryNode(topCategory, true);
        if (node) {
            resultsContainer.appendChild(node);
        }
    });

    const uncategorized = store.dynamicServices.filter(service => service.category_id === null || service.category_id === undefined);
    if (uncategorized.length > 0) {
        if (hasCategories) {
            const divider = document.createElement('div');
            divider.className = 'cat-divider';
            divider.textContent = 'Другие услуги';
            resultsContainer.appendChild(divider);
        }
        uncategorized.forEach(service => resultsContainer.appendChild(createServiceOption(service)));
    }
}

export function initServiceListeners() {
    const searchInput = document.getElementById('search-input');
    const searchContainer = document.getElementById('search-container');
    if (searchInput) {
        searchContainer.addEventListener('click', (e) => e.stopPropagation());
        searchInput.addEventListener('input', (e) => {
            populateServices(e.target.value);
        });
    }

    document.addEventListener('booking-selection-changed', () => {
        populateServices(searchInput ? searchInput.value : '');
    });

    selectTrigger.addEventListener('click', toggleDropdown);

    let touchStartY = 0;
    let touchStartX = 0;
    const scrollThreshold = 15;
    let lastDropdownScrollTime = 0;
    const scrollCooldown = 400;

    customOptionsContainer.addEventListener('scroll', () => {
        lastDropdownScrollTime = Date.now();
    }, { passive: true });

    customOptionsContainer.addEventListener('touchmove', () => {
        lastDropdownScrollTime = Date.now();
    }, { passive: true });

    document.addEventListener('touchstart', (e) => {
        touchStartY = e.touches[0].clientY;
        touchStartX = e.touches[0].clientX;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        const touch = e.changedTouches[0];
        const dy = Math.abs(touch.clientY - touchStartY);
        const dx = Math.abs(touch.clientX - touchStartX);
        if (dy > scrollThreshold || dx > scrollThreshold) {
            return;
        }
        if (Date.now() - lastDropdownScrollTime < scrollCooldown) {
            return;
        }
        if (!document.getElementById('service-wrapper').contains(e.target)) {
            closeDropdown();
        }
    }, { passive: true });

    document.addEventListener('click', (e) => {
        if (e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents) {
            return;
        }
        if (!document.getElementById('service-wrapper').contains(e.target)) {
            closeDropdown();
        }
    }, { passive: true });
}

export function toggleDropdown() {
    tg.HapticFeedback.impactOccurred('light');
    const isOpen = selectTrigger.classList.toggle('open');
    customOptionsContainer.classList.toggle('open', isOpen);
    document.getElementById('service-wrapper').classList.toggle('open', isOpen);
    document.body.classList.toggle('dropdown-open', isOpen);
}

export function closeDropdown() {
    selectTrigger.classList.remove('open');
    customOptionsContainer.classList.remove('open');
    document.getElementById('service-wrapper').classList.remove('open');
    document.body.classList.remove('dropdown-open');
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.value = '';
        searchInput.blur();
    }
}
