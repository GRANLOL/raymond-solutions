import { config } from './config.js?v=5';

export const tg = window.Telegram.WebApp;

export function initTelegram() {
    console.info('Telegram WebApp init state:', {
        hasTelegramObject: Boolean(window.Telegram && window.Telegram.WebApp),
        initDataPresent: Boolean(tg.initData),
        initDataLength: tg.initData ? tg.initData.length : 0,
        hasUser: Boolean(tg.initDataUnsafe && tg.initDataUnsafe.user),
        platform: tg.platform || 'unknown'
    });

    tg.expand();
    if (typeof tg.disableVerticalSwipes === 'function') {
        tg.disableVerticalSwipes();
    }
    tg.ready();
    tg.setHeaderColor(config.themeColors.headerColor);
    tg.setBackgroundColor(config.themeColors.backgroundColor);
}
