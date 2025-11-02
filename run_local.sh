#!/bin/bash

# اسکریپت برای راه‌اندازی پروژه روی Linux/Mac (بدون Docker)

echo "========================================"
echo "راه‌اندازی پروژه Masked Call"
echo "========================================"

# بررسی وجود Python
if ! command -v python3 &> /dev/null; then
    echo "خطا: Python نصب نشده است!"
    exit 1
fi

# بررسی وجود محیط مجازی
if [ ! -d "venv" ]; then
    echo "ایجاد محیط مجازی..."
    python3 -m venv venv
fi

# فعال کردن محیط مجازی
echo "فعال کردن محیط مجازی..."
source venv/bin/activate

# نصب پکیج‌ها
echo "نصب پکیج‌ها..."
pip install -r requirements.txt

# بررسی فایل .env
if [ ! -f ".env" ]; then
    echo "هشدار: فایل .env پیدا نشد!"
    echo "لطفا فایل .env.example را کپی کنید و به .env تغییر نام دهید"
    echo "سپس مقادیر را با اطلاعات واقعی پر کنید"
    read -p "آیا می‌خواهید ادامه دهید؟ (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# بارگذاری متغیرهای محیطی از .env (اگر وجود داشته باشد)
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# اجرای اپلیکیشن
echo "========================================"
echo "در حال راه‌اندازی اپلیکیشن..."
echo "API در آدرس http://localhost:8000 در دسترس است"
echo "برای خروج، Ctrl+C را فشار دهید"
echo "========================================"
echo

uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

