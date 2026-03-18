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
    salonLogoUrl: "https://sdmntprnznorth.oaiusercontent.com/files/00000000-3674-720b-8852-19b9fb516598/raw?se=2026-03-18T18:17:26Z&sp=r&sv=2026-02-06&sr=b&scid=c1d03747-68c3-4f11-9c99-f3366d7c0011&skoid=d5627e4c-566b-4761-a954-54993b0ed17b&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-03-17T22:17:37Z&ske=2026-03-18T22:17:37Z&sks=b&skv=2026-02-06&sig=bM/W5Imo56Ds9G0wSNBZQK%2BhCCGzq4Wa9NfLpUvkAGQ%3D",
    salonLogoText: "",
    salonTagline: "online booking",

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
