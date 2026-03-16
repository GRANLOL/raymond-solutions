const privacyModal = document.getElementById('privacy-modal');
const privacyLink = document.getElementById('privacy-link');
const privacyClose = document.getElementById('privacy-close');

function openPrivacyModal() {
    if (!privacyModal) {
        return;
    }
    privacyModal.classList.add('active');
}

function closePrivacyModal() {
    if (!privacyModal) {
        return;
    }
    privacyModal.classList.remove('active');
}

export function initPrivacyModal() {
    if (!privacyModal || !privacyLink || !privacyClose) {
        return;
    }

    privacyLink.addEventListener('click', openPrivacyModal);
    privacyClose.addEventListener('click', closePrivacyModal);
    privacyModal.addEventListener('click', (event) => {
        if (event.target === privacyModal) {
            closePrivacyModal();
        }
    });
}
