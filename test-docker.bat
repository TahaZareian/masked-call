@echo off
echo ========================================
echo ساخت ایمیج Docker...
echo ========================================
docker build -t masked-call .

if %errorlevel% neq 0 (
    echo خطا در ساخت ایمیج!
    pause
    exit /b 1
)

echo.
echo ========================================
echo اجرای کانتینر...
echo ========================================
echo.
echo اپلیکیشن در حال اجراست...
echo برای دیدن خروجی، مرورگر را باز کنید و به آدرس زیر بروید:
echo http://localhost:5000
echo.
echo یا در یک ترمینال جدید این دستور را اجرا کنید:
echo curl http://localhost:5000
echo.
echo برای توقف کانتینر، Ctrl+C را فشار دهید
echo.
docker run -p 5000:5000 masked-call

pause

