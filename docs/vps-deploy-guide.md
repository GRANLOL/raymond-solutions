# Подробная Инструкция По Переносу На VPS

## 1. Что Мы Хотим Получить В Итоге

После переноса у вас должно быть так:

- бот работает не на вашем компьютере, а на `VPS` (`удаленном сервере`)
- `FastAPI` (`API`, то есть серверная часть для WebApp) тоже работает на VPS
- `scheduler` (`планировщик`, то есть цикл напоминаний и фоновых задач) работает там же
- `ngrok` больше не нужен
- WebApp по-прежнему может жить на GitHub Pages
- WebApp обращается не к `ngrok`, а к вашему постоянному API-адресу
- бот сам запускается после перезагрузки сервера

## 2. Что Нужно Купить И Подготовить

### Что купить

Вам нужно:

1. `VPS`
2. `Домен`

### Что должно быть под рукой

Подготовьте заранее:

- токен Telegram-бота (`BOT_TOKEN`)
- ваш Telegram ID (`ADMIN_ID`)
- текущий проект у себя на компьютере
- файл [config.json](/c:/Users/User/Desktop/Main%20Project/config.json)
- файл `bookings.db`, если хотите перенести текущие записи

## 3. Какой VPS Брать

Для старта вам достаточно примерно такого тарифа:

- `1 vCPU`
- `1-2 GB RAM`
- `20 GB SSD`
- `Ubuntu 22.04` или `Ubuntu 24.04`

Операционная система `Ubuntu` это Linux-система, на которой очень удобно поднимать Python-проекты.

## 4. Какой Домен Брать

Домен можно взять любой нормальный, который вам подходит по цене и звучанию.

Примеры:

- `mybotservice.com`
- `mybeautybot.ru`
- `mysalonbot.kz`

Под ваш API удобно использовать `subdomain` (`субдомен` = адрес внутри домена):

- `api.mybotservice.com`

То есть:

- основной домен один
- API живет на `api.вашдомен`

## 5. Общая Схема Работы

Схема будет такой:

1. Вы покупаете VPS
2. Вы покупаете домен
3. Подключаетесь к VPS по `SSH` (`SSH` = способ удаленно войти в сервер через терминал)
4. Устанавливаете на сервер Python, `nginx`, `certbot`
5. Загружаете проект на сервер
6. Создаете `.env` на сервере
7. Запускаете проект
8. Настраиваете `systemd`, чтобы бот работал постоянно
9. Настраиваете `nginx`, чтобы API открывался по домену
10. Настраиваете `SSL` (`https`)
11. Меняете фронт с `ngrok` на постоянный API URL

## 6. Шаг 1. Купить VPS

Когда купите VPS, вам обычно дадут:

- `IP-адрес`
- логин `root`
- пароль или SSH-ключ

Пример:

- IP: `203.0.113.15`

Сохраните это, это понадобится для подключения.

## 7. Шаг 2. Купить Домен

После покупки домена вам нужно будет настроить `DNS` (`DNS` = система, которая говорит интернету, какой домен на какой IP ведет).

Для API вам нужна будет `A-запись` (`A record` = правило "этот домен указывает на этот IP").

Например:

- имя: `api`
- значение: `203.0.113.15`

Это означает:

- `api.mybotservice.com` ведет на ваш VPS

## 8. Шаг 3. Подключиться К Серверу

Если у вас Windows, можно подключаться через:

- Windows Terminal / PowerShell
- PuTTY

Обычно команда такая:

```powershell
ssh root@203.0.113.15
```

Если сервер просит подтвердить отпечаток ключа, соглашайтесь.

Если всё нормально, вы окажетесь внутри сервера.

## 9. Шаг 4. Обновить Сервер И Установить Нужные Пакеты

После входа выполните:

```bash
apt update
apt upgrade -y
apt install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx
```

Что это устанавливает:

- `python3` — Python
- `python3-venv` — виртуальное окружение (`venv` = изолированная папка с зависимостями проекта)
- `python3-pip` — установщик Python-библиотек
- `git` — чтобы скачать проект
- `nginx` — веб-сервер
- `certbot` — инструмент для выпуска SSL-сертификата

## 10. Шаг 5. Загрузить Проект На Сервер

Есть два нормальных варианта.

### Вариант А. Через Git

Если проект у вас уже в GitHub:

```bash
cd /opt
git clone https://github.com/ВАШ_РЕПО.git app
cd /opt/app
```

### Вариант Б. Через Архив / SCP

Если не хотите через Git, можно загрузить проект архивом.

Но для будущих обновлений Git удобнее.

## 11. Шаг 6. Создать Виртуальное Окружение И Установить Зависимости

На сервере:

```bash
cd /opt/app
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

После этого все библиотеки проекта будут установлены в `.venv`.

## 12. Шаг 7. Создать `.env` На Сервере

В папке проекта создайте `.env`.

Пример:

```env
BOT_TOKEN=ВАШ_ТЕЛЕГРАМ_ТОКЕН
ADMIN_ID=ВАШ_TELEGRAM_ID
WEBAPP_URL=https://username.github.io/project/
WEBAPP_AUTH_REQUIRED=true
```

Важно:

- `WEBAPP_URL` должен указывать на реальный адрес вашей WebApp-страницы
- не на `ngrok`
- не на локальный адрес

## 13. Шаг 8. Перенести `config.json` И Базу

На сервер нужно перенести:

- [config.json](/c:/Users/User/Desktop/Main%20Project/config.json)
- `bookings.db` если вы хотите сохранить текущие данные

### Как перенести с Windows

Можно использовать `scp`.

Пример из PowerShell на вашем компьютере:

```powershell
scp config.json root@203.0.113.15:/opt/app/config.json
scp bookings.db root@203.0.113.15:/opt/app/bookings.db
```

Если базы у вас пока нет или она не нужна, можно не копировать. Тогда проект создаст новую.

## 14. Шаг 9. Проверить Ручной Запуск

Перед автоматизацией обязательно проверьте ручной запуск.

На сервере:

```bash
cd /opt/app
source .venv/bin/activate
python main.py
```

Что должно произойти:

- бот стартует
- API стартует
- scheduler стартует

Если всё хорошо, остановите процесс:

```bash
Ctrl + C
```

## 15. Шаг 10. Настроить `systemd`

`systemd` нужен, чтобы бот работал постоянно и сам перезапускался при сбое.

Создайте файл:

```bash
nano /etc/systemd/system/bookingbot.service
```

Вставьте:

```ini
[Unit]
Description=Telegram Booking Bot
After=network.target

[Service]
WorkingDirectory=/opt/app
ExecStart=/opt/app/.venv/bin/python main.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```

Сохраните файл.

Затем выполните:

```bash
systemctl daemon-reload
systemctl enable bookingbot
systemctl start bookingbot
systemctl status bookingbot
```

Если статус показывает, что сервис жив, значит всё хорошо.

## 16. Шаг 11. Проверить Логи Сервиса

Чтобы посмотреть логи:

```bash
journalctl -u bookingbot -f
```

Это покажет живой лог процесса.

Очень полезно на этапе первого запуска.

## 17. Шаг 12. Настроить `nginx`

Сейчас ваш FastAPI работает внутри сервера.

Например:

- `127.0.0.1:8000`

Но снаружи нужно открыть API по нормальному домену:

- `api.mybotservice.com`

Создайте конфиг:

```bash
nano /etc/nginx/sites-available/bookingbot
```

Вставьте:

```nginx
server {
    server_name api.mybotservice.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включите сайт:

```bash
ln -s /etc/nginx/sites-available/bookingbot /etc/nginx/sites-enabled/bookingbot
nginx -t
systemctl reload nginx
```

Если `nginx -t` пишет `syntax is ok`, значит конфиг корректный.

## 18. Шаг 13. Получить SSL

Теперь нужно включить `https`.

Выполните:

```bash
certbot --nginx -d api.mybotservice.com
```

Что сделает `certbot`:

- выпустит бесплатный SSL-сертификат
- подставит его в `nginx`
- включит `https`

После этого ваш API должен открываться по:

```text
https://api.mybotservice.com
```

## 19. Шаг 14. Проверить API

Откройте в браузере:

```text
https://api.mybotservice.com/api/health
```

Вы должны увидеть что-то вроде:

```json
{
  "ok": true,
  "webapp_auth_required": true,
  "bot_ready": true
}
```

Если так, значит серверная часть уже почти готова.

## 20. Шаг 15. Обновить WebApp

Это очень важный шаг.

Сейчас у вас фронт ещё знает про `ngrok`.

В файле [js/config.js](/c:/Users/User/Desktop/Main%20Project/js/config.js) нужно заменить боевой API-адрес.

Смысл такой:

было:

```js
const REMOTE_API_BASE_URL = "https://...ngrok.../api";
```

должно стать:

```js
const REMOTE_API_BASE_URL = "https://api.mybotservice.com/api";
```

После этого надо задеплоить фронт заново на GitHub Pages.

## 21. Шаг 16. Проверить CORS И WebApp Auth

У вас это уже есть в проекте:

- CORS строится от `WEBAPP_URL`
- WebApp auth проверяется через `X-Telegram-Init-Data`

Что важно:

- в `.env` на сервере `WEBAPP_URL` должен совпадать с реальным адресом WebApp
- фронт должен ходить в новый API-домен

Если тут всё совпадает, WebApp будет работать нормально.

## 22. Шаг 17. Финальная Проверка

Прогоните руками:

1. Открыть бота
2. Нажать `Записаться`
3. Открыть WebApp
4. Загрузить услуги и слоты
5. Создать запись
6. Проверить, что запись пришла в бота
7. Проверить `Мои записи`
8. Проверить отмену
9. Проверить перенос
10. Проверить `/api/health`

Если всё работает, значит перенос успешен.

## 23. Что Делать При Обновлениях В Будущем

Когда захотите обновить проект:

```bash
cd /opt/app
git pull
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart bookingbot
```

Потом проверить:

```bash
systemctl status bookingbot
journalctl -u bookingbot -n 100
```

## 24. Что Не Забыть

- не пушить `.env` в GitHub
- держать копию `bookings.db`
- делать backup
- проверять логи после запуска
- проверить, что домен действительно указывает на VPS
- проверить, что `WEBAPP_URL` совпадает с GitHub Pages адресом

## 25. Самый Короткий Чек-Лист

Если совсем коротко, порядок такой:

1. Купить VPS
2. Купить домен
3. Прописать DNS на `api.вашдомен`
4. Подключиться по SSH
5. Установить Python, nginx, certbot
6. Залить проект
7. Создать `.env`
8. Перенести `config.json` и `bookings.db`
9. Проверить `python main.py`
10. Настроить `systemd`
11. Настроить `nginx`
12. Выпустить SSL
13. Поменять `ngrok` URL на боевой API URL
14. Задеплоить фронт
15. Протестировать всё заново

## 26. Что Я Рекомендую Лично Вам

Не пытайтесь сразу сделать идеально.

Ваш правильный порядок сейчас:

1. Поднять один сервер
2. Убрать `ngrok`
3. Довести до стабильного состояния
4. Прогнать все сценарии
5. Дать первым людям
6. Только потом думать о мультиклиентской архитектуре

Это самый здравый путь.

## 27. Подготовка Под Несколько Клиентов На Одном VPS

Если вы хотите временно держать несколько отдельных клиентов на одном VPS, проект теперь это позволяет без большой переделки архитектуры.

Для каждого экземпляра можно задать свои параметры через `.env`:

```env
PORT=8010
DATABASE_PATH=/opt/booking-clients/client-a/bookings.db
CONFIG_PATH=/opt/booking-clients/client-a/config.json
```

Что это значит:

- `PORT` — внутренний порт FastAPI для конкретного экземпляра
- `DATABASE_PATH` — путь к отдельной SQLite-базе этого клиента
- `CONFIG_PATH` — путь к отдельному конфигу этого клиента

Пример для второго клиента:

```env
PORT=8011
DATABASE_PATH=/opt/booking-clients/client-b/bookings.db
CONFIG_PATH=/opt/booking-clients/client-b/config.json
```

То есть логика такая:

- один и тот же код проекта
- несколько разных `.env`
- несколько разных `config.json`
- несколько разных `bookings.db`
- несколько `systemd`-сервисов

Пример структуры:

```text
/opt/booking-clients/client-a
/opt/booking-clients/client-b
/opt/booking-clients/client-c
```

## 28. Как Временно Жить Без Домена

Если вы пока не хотите покупать домен, для тестового периода можно сделать упрощённую схему:

- WebApp остаётся на GitHub Pages
- VPS поднимается без домена
- API открывается временно по IP VPS и порту через `nginx` или напрямую

Важно понимать:

- это временный тестовый вариант
- он хуже, чем нормальный домен + `https`
- но для 1-2 первых клиентов и проверки спроса может быть приемлем

Если идёте этим путём, используйте порядок:

1. поднять один экземпляр на VPS
2. проверить `python main.py`
3. проверить `/api/health`
4. заменить `ngrok` URL во фронте на временный адрес VPS
5. протестировать всё руками

Когда увидите, что идея реально нужна людям, тогда уже переносить всё на домен и полноценный `SSL`.
