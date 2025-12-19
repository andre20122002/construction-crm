@echo off
chcp 65001 >nul
color 0A
cls

echo ========================================================
echo        ZAPUSK SYSTEMY "BUD-SKLAD" (Django)
echo ========================================================
echo.

:: 1. ПЕРЕХІД У ПАПКУ СКРИПТА
:: Це гарантує, що ми в правильній папці, навіть якщо запуск від імені Адміна
cd /d "%~dp0"

:: 2. ПЕРЕВІРКА VENV
if not exist "venv" (
    color 0C
    echo [ERROR] Papka 'venv' ne znaydena!
    echo.
    echo Vasha diya:
    echo 1. Vidkryyte terminal.
    echo 2. Vvedit: python -m venv venv
    echo 3. Vvedit: pip install django psycopg2-binary openpyxl xhtml2pdf reportlab
    echo.
    pause
    exit
)

:: 3. АКТИВАЦІЯ СЕРЕДОВИЩА
call venv\Scripts\activate
if errorlevel 1 (
    color 0C
    echo [ERROR] Ne vdalosya aktyvuvaty venv!
    pause
    exit
)
echo [OK] Virtualne seredovyshche aktyvovano.

:: 4. ЗАПУСК БРАУЗЕРА (чекаємо 2 секунди, щоб сервер встиг прокинутись)
echo [INFO] Vidkryvayemo browser...
timeout /t 2 >nul
start http://127.0.0.1:8000/

:: 5. ЗАПУСК СЕРВЕРА
echo.
echo [INFO] Zapusk servera... (Schob zupynyty - natysnit Ctrl+C)
echo ========================================================
echo.

python manage.py runserver

:: Якщо сервер впав з помилкою, не закриваємо вікно одразу
if errorlevel 1 (
    color 0C
    echo.
    echo [ERROR] Server zupynyvsya z pomylkoyu!
    pause
)