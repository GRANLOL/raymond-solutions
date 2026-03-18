// Конфигурационный файл шаблона
// Вы можете изменить эти данные, чтобы быстро адаптировать WebApp под любой бизнес (Nogotki, Barbershop, СТО и т.д.)

const LOCAL_API_BASE_URL = "http://127.0.0.1:8001/api";
const REMOTE_API_BASE_URL = "https://api.tgbooking.online/api";
const API_OVERRIDE_KEY = "apiBaseUrlOverride";

function resolveApiBaseUrl() {
    const url = new URL(window.location.href);
    const apiOverride = url.searchParams.get("apiBaseUrl");
    const resetOverride = url.searchParams.get("resetApiBaseUrl");
    const isLocalHost = ["127.0.0.1", "localhost"].includes(window.location.hostname);
    const runtimeApiBaseUrl = window.__API_BASE_URL__;
    const isGitHubPages = window.location.hostname.endsWith("github.io");

    if (resetOverride === "1") {
        window.localStorage.removeItem(API_OVERRIDE_KEY);
    }

    if (apiOverride) {
        window.localStorage.setItem(API_OVERRIDE_KEY, apiOverride);
        return apiOverride;
    }

    const storedOverride = window.localStorage.getItem(API_OVERRIDE_KEY);
    if (storedOverride) {
        return storedOverride;
    }

    if (runtimeApiBaseUrl) {
        return runtimeApiBaseUrl;
    }

    if (isLocalHost) {
        return LOCAL_API_BASE_URL;
    }

    if (!isGitHubPages) {
        return `${window.location.origin}/api`;
    }

    return REMOTE_API_BASE_URL;
}

export const config = {
    // Название заведения, которое отображается в шапке
    salonName: "Nail Studio Deluxe",

    apiBaseUrl: resolveApiBaseUrl(),

    // Список услуг, доступных для выбора с ценами
    services: [
        { name: "Маникюр без покрытия", price: "900 ₸" },
        { name: "Маникюр + Гель-лак", price: "3 500 ₸" },
        { name: "Укрепление акрилом", price: "1 200 ₸" },
        { name: "Дизайн (Сложный)", price: "от 500 ₸" },
        { name: "Снятие чужой работы", price: "500 ₸" }
    ],

    // Доступные временные слоты для записи
    timeSlots: ["09:00", "12:00", "15:00", "18:00", "21:00"],

    // Настройки внешнего вида (передаются в Telegram)
    themeColors: {
        headerColor: '#FFFFFF', // Цвет шапки в клиенте Telegram
        backgroundColor: '#FAF6F5', // Основной цвет фона
        mainButtonColor: '#E2B6B3', // Цвет главной кнопки "Подтвердить"
        mainButtonTextColor: '#ffffff' // Цвет текста на главной кнопке
    }
};
