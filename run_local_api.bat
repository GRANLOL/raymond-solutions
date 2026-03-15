@echo off
setlocal

if exist ".\.venv\Scripts\python.exe" (
    ".\.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8001
) else (
    python -m uvicorn main:app --host 127.0.0.1 --port 8001
)

endlocal
