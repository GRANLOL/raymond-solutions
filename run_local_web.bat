@echo off
setlocal

if exist ".\.venv\Scripts\python.exe" (
    ".\.venv\Scripts\python.exe" -m http.server 5500 --bind 127.0.0.1
) else (
    python -m http.server 5500 --bind 127.0.0.1
)

endlocal
