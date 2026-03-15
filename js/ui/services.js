import { tg } from '../telegram.js';
import { store } from '../store.js';
import { populateMasters } from './masters.js';
import { checkConfirmation } from './form.js';

const selectTrigger = document.getElementById('select-trigger');
const selectLabel = document.getElementById('select-label');
const customOptionsContainer = document.getElementById('custom-options');

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
    price.textContent = serviceObj.price;

    optionDiv.append(dot, name, price);
    optionDiv.addEventListener('click', () => {
        tg.HapticFeedback.impactOccurred('light');
        selectLabel.textContent = serviceObj.name;
        selectTrigger.classList.add('selected');

        document.querySelectorAll('.custom-option').forEach(opt => opt.classList.remove('selected'));
        optionDiv.classList.add('selected');

        closeDropdown();
        store.selectedService = serviceObj.name;
        store.selectedDuration = serviceObj.duration || 60;
        store.selectedPrice = parseInt((serviceObj.price || '0').replace(/\D/g, '')) || 0;
        store.selectedMaster = null;

        if (store.useMasters && store.dynamicMasters.length > 0) {
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

export function populateServices(searchQuery = '') {
    const resultsContainer = document.getElementById('service-results');
    resultsContainer.innerHTML = '';

    // === SEARCH MODE: flat list ===
    if (searchQuery.trim().length > 0) {
        const query = searchQuery.toLowerCase();
        const filtered = store.dynamicServices.filter(s =>
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
    const topCategories = store.dynamicCategories.filter(c => c.parent_id === null || c.parent_id === undefined);
    const hasCategories = topCategories.length > 0;

    function renderCategoryNode(cat, isRoot) {
        const subCats = store.dynamicCategories.filter(c => c.parent_id === cat.id);
        const dirServices = store.dynamicServices.filter(s => s.category_id === cat.id);

        if (subCats.length === 0 && dirServices.length === 0) return null;

        const group = document.createElement('div');
        group.className = isRoot ? 'cat-group' : 'subcat-group';

        const header = document.createElement('div');
        header.className = isRoot ? 'cat-header' : 'subcat-header';

        const titleClass = isRoot ? 'cat-name' : 'subcat-name';
        const arrowClass = isRoot ? 'cat-arrow' : 'subcat-arrow';
        const hasChildren = subCats.length > 0 || dirServices.length > 0;

        const title = document.createElement('span');
        title.className = titleClass;
        title.textContent = cat.name;
        header.appendChild(title);

        if (hasChildren) {
            const arrow = document.createElement('span');
            arrow.className = arrowClass;
            arrow.textContent = '›';
            header.appendChild(arrow);
        }

        const body = document.createElement('div');
        body.className = isRoot ? 'cat-body' : 'subcat-body';

        // Inner wrapper required for smooth grid-rows animation
        const inner = document.createElement('div');
        inner.className = 'body-inner';

        subCats.forEach(sub => {
            const subNode = renderCategoryNode(sub, false);
            if (subNode) inner.appendChild(subNode);
        });

        dirServices.forEach(s => inner.appendChild(createServiceOption(s)));

        body.appendChild(inner);

        header.addEventListener('click', (e) => {
            if (!isRoot) e.stopPropagation();
            if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');

            const isOpen = group.classList.contains('open');

            if (isOpen) {
                // Closing: pin current pixel height, then animate to 0
                body.style.height = body.scrollHeight + 'px';
                requestAnimationFrame(() => {
                    body.style.height = '0px';
                });
                group.classList.remove('open');
            } else {
                // Measure real content height cross-browser
                const prevHeight = body.style.height;
                body.style.height = 'auto';
                body.style.overflow = 'visible';
                const targetH = body.scrollHeight;
                body.style.overflow = '';
                body.style.height = prevHeight || '0px';

                // Force a reflow
                body.offsetHeight;

                // Animate to measured height
                body.style.height = targetH + 'px';
                group.classList.add('open');

                // After transition, set 'auto'
                body.addEventListener('transitionend', () => {
                    if (group.classList.contains('open')) body.style.height = 'auto';
                }, { once: true });
            }
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
    const uncategorized = store.dynamicServices.filter(s => s.category_id === null || s.category_id === undefined);
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

export function initServiceListeners() {
    const searchInput = document.getElementById('search-input');
    const searchContainer = document.getElementById('search-container');
    if (searchInput) {
        searchContainer.addEventListener('click', (e) => e.stopPropagation());
        searchInput.addEventListener('input', (e) => {
            populateServices(e.target.value);
        });
    }

    selectTrigger.addEventListener('click', toggleDropdown);

    // Scroll-aware close logic
    let _touchStartY = 0;
    let _touchStartX = 0;
    const _SCROLL_THRESHOLD = 15;
    let _lastDropdownScrollTime = 0;
    const _SCROLL_COOLDOWN = 400;

    customOptionsContainer.addEventListener('scroll', () => {
        _lastDropdownScrollTime = Date.now();
    }, { passive: true });

    customOptionsContainer.addEventListener('touchmove', () => {
        _lastDropdownScrollTime = Date.now();
    }, { passive: true });

    document.addEventListener('touchstart', (e) => {
        _touchStartY = e.touches[0].clientY;
        _touchStartX = e.touches[0].clientX;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        const touch = e.changedTouches[0];
        const dy = Math.abs(touch.clientY - _touchStartY);
        const dx = Math.abs(touch.clientX - _touchStartX);
        if (dy > _SCROLL_THRESHOLD || dx > _SCROLL_THRESHOLD) return;
        if (Date.now() - _lastDropdownScrollTime < _SCROLL_COOLDOWN) return;

        if (!document.getElementById('service-wrapper').contains(e.target)) {
            closeDropdown();
        }
    }, { passive: true });

    document.addEventListener('click', (e) => {
        if (e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents) return;
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
