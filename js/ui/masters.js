import { tg } from '../telegram.js';
import { store } from '../store.js';
import { fetchBusySlots } from '../api.js';
import { generateDates } from './datetime.js';
import { checkConfirmation } from './form.js';

export function populateMasters() {
    const masterGrid = document.getElementById('master-grid');
    masterGrid.innerHTML = '';

    store.dynamicMasters.forEach(masterObj => {
        const mDiv = document.createElement('div');
        mDiv.className = 'master-card';
        // HTML structure for a master item
        mDiv.innerHTML = `
            <div class="master-avatar">👤</div>
            <div class="master-name">${masterObj.name}</div>
        `;

        mDiv.addEventListener('click', async () => {
            tg.HapticFeedback.impactOccurred('light');
            document.querySelectorAll('.master-card').forEach(el => el.classList.remove('selected'));
            mDiv.classList.add('selected');
            store.selectedMaster = masterObj;

            // Fetch busy slots for this specific master
            await fetchBusySlots(masterObj.id);

            // show date / time sections
            document.getElementById('date-container').style.display = 'flex';
            document.getElementById('time-grid').style.display = 'grid';
            document.querySelectorAll('.section-title')[2].style.display = 'block';
            document.querySelectorAll('.section-title')[3].style.display = 'block';

            // Re-render dates and times with per-master busy slots
            generateDates();
            store.selectedDate = null;
            store.selectedTime = null;
            document.getElementById('time-grid').innerHTML = '';
            checkConfirmation();
        });

        masterGrid.appendChild(mDiv);
    });
}
