import { config } from './config.js';

export const tg = window.Telegram.WebApp;

export function initTelegram() {
    tg.expand();
    tg.ready();
    tg.setHeaderColor(config.themeColors.headerColor);
    tg.setBackgroundColor(config.themeColors.backgroundColor);
}
