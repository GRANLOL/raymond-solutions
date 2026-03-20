# Server Cheatsheet

Короткая шпаргалка для сервера `bookingbot`.

## Подключение

```powershell
ssh root@84.247.171.240
```

## Сервис бота

Проверить статус:

```bash
systemctl status bookingbot
```

Перезапустить:

```bash
systemctl restart bookingbot
```

Остановить:

```bash
systemctl stop bookingbot
```

Запустить:

```bash
systemctl start bookingbot
```

## Логи

Последние 50 строк:

```bash
journalctl -u bookingbot -n 50 --no-pager
```

Смотреть вживую:

```bash
journalctl -u bookingbot -f
```

## Nginx

Проверить конфиг:

```bash
nginx -t
```

Перечитать конфиг:

```bash
systemctl reload nginx
```

Проверить статус:

```bash
systemctl status nginx
```

## Проект

Перейти в папку проекта:

```bash
cd /opt/app
```

Посмотреть файлы:

```bash
ls -la /opt/app
```

Открыть `.env`:

```bash
nano /opt/app/.env
```

Открыть `config.json`:

```bash
nano /opt/app/config.json
```

## Обновление кода

Подтянуть свежий код:

```bash
cd /opt/app
git pull
```

После обновления перезапустить бота:

```bash
systemctl restart bookingbot
systemctl status bookingbot
```

## Проверка API

Проверить health endpoint:

```bash
curl https://api.tgbooking.online/api/health
```

## Удобные команды прямо из локального PowerShell

Статус бота:

```powershell
ssh root@84.247.171.240 "systemctl status bookingbot"
```

Перезапуск бота:

```powershell
ssh root@84.247.171.240 "systemctl restart bookingbot"
```

Последние логи:

```powershell
ssh root@84.247.171.240 "journalctl -u bookingbot -n 50 --no-pager"
```

Проверка API:

```powershell
curl https://api.tgbooking.online/api/health
```

## Полезно помнить

- После правки `.env` нужен `systemctl restart bookingbot`
- После правки `nginx` нужен `nginx -t`, потом `systemctl reload nginx`
- Из экрана `systemctl status ...` выйти клавишей `q`
