@echo off
REM اسکریپت برای راه‌اندازی پروژه روی Windows (بدون Docker)

echo ========================================
echo راه‌اندازی پروژه Masked Call
echo ========================================

REM بررسی وجود Python
python --version >nul 2>&1
if errorlevel 1 (
    echo خطا: Python نصب نشده است!
    pause
    exit /b 1
)

REM بررسی وجود محیط مجازی
if not exist "venv" (
    echo ایجاد محیط مجازی...
    python -m venv venv
)

REM فعال کردن محیط مجازی
echo فعال کردن محیط مجازی...
call venv\Scripts\activate.bat

REM نصب پکیج‌ها
echo نصب پکیج‌ها...
pip install -r requirements.txt

REM بررسی فایل .env
if not exist ".env" (
    echo هشدار: فایل .env پیدا نشد!
    echo لطفا فایل .env.example را کپی کنید و به .env تغییر نام دهید
    echo سپس مقادیر را با اطلاعات واقعی پر کنید
    pause
)

REM بارگذاری متغیرهای محیطی (اگر python-dotenv نصب باشد)
echo بارگذاری متغیرهای محیطی...

REM اجرای اپلیکیشن
echo ========================================
echo در حال راه‌اندازی اپلیکیشن...
echo API در آدرس http://localhost:8000 در دسترس است
echo برای خروج، Ctrl+C را فشار دهید
echo ========================================
echo.

uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

pause

