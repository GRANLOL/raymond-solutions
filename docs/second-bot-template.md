# Second Bot Template

Короткий шаблон для поднятия второго бота на том же VPS.

## Идея

Первый бот уже работает:

- папка: `/opt/app`
- порт: `8000`
- сервис: `bookingbot`

Второй бот будет отдельным экземпляром:

- папка: `/opt/client2`
- порт: `8010`
- сервис: `bookingbot-client2`

## 1. Папка проекта

```bash
cd /opt
git clone https://github.com/GRANLOL/manicure-webapp.git client2
cd /opt/client2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. `.env` второго бота

Пример:

```env
BOT_TOKEN=SECOND_BOT_TOKEN
ADMIN_ID=SECOND_ADMIN_ID
WEBAPP_URL=https://SECOND_GITHUB_PAGES_URL
WEBAPP_AUTH_REQUIRED=true
PORT=8010
DATABASE_PATH=/opt/client2/bookings.db
CONFIG_PATH=/opt/client2/config.json
```

## 3. Данные второго бота

Нужно положить:

- `/opt/client2/config.json`
- `/opt/client2/bookings.db` при необходимости

Если база не нужна, создастся новая.

## 4. Сервис `systemd`

Файл:

```bash
nano /etc/systemd/system/bookingbot-client2.service
```

Содержимое:

```ini
[Unit]
Description=Telegram Booking Bot Client 2
After=network.target

[Service]
WorkingDirectory=/opt/client2
ExecStart=/opt/client2/.venv/bin/python main.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```

Применить:

```bash
systemctl daemon-reload
systemctl enable bookingbot-client2
systemctl start bookingbot-client2
systemctl status bookingbot-client2
```

## 5. Nginx для второго бота

Пример для субдомена `api2.tgbooking.online`:

```bash
nano /etc/nginx/sites-available/bookingbot-client2
```

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name api2.tgbooking.online;

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включить:

```bash
ln -s /etc/nginx/sites-available/bookingbot-client2 /etc/nginx/sites-enabled/bookingbot-client2
nginx -t
systemctl reload nginx
```

## 6. SSL для второго бота

```bash
certbot --nginx -d api2.tgbooking.online
```

## 7. Обновить фронт второго бота

Во фронте второго бота должен быть свой API:

```js
const REMOTE_API_BASE_URL = "https://api2.tgbooking.online/api";
```

## 8. Полезные команды

Статус:

```bash
systemctl status bookingbot-client2
```

Логи:

```bash
journalctl -u bookingbot-client2 -n 50 --no-pager
```

Рестарт:

```bash
systemctl restart bookingbot-client2
```

## 9. Что отличает второго бота от первого

Должны отличаться:

- `BOT_TOKEN`
- `ADMIN_ID`
- `WEBAPP_URL`
- `PORT`
- `DATABASE_PATH`
- `CONFIG_PATH`
- `systemd service`
- `nginx config`
- домен или субдомен API

Не нужно отдельно:

- второй VPS
- второй IP

## 10. Оценка по времени

Если без сюрпризов:

- `20-40 минут` быстро
- `40-60 минут` спокойно и с проверками
