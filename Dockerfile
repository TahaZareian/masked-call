# استفاده از image پایه Python
FROM python:3.11-slim

# تنظیم working directory
WORKDIR /app

# کپی فایل پایتون
COPY app.py .

# اجرای فایل پایتون
CMD ["python", "app.py"]

