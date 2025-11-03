# استفاده از ایمیج پایتون رسمی
FROM python:3.11-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# کپی فایل requirements و نصب وابستگی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی بقیه فایل‌های اپلیکیشن
COPY app.py .

# پورت اکسپوز کن
EXPOSE 5000

# اجرای اپلیکیشن
CMD ["python", "app.py"]

