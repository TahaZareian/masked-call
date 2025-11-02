# Masked Call

سیستم مدیریت تماس‌های مخفی با استفاده از Asterisk و Python (FastAPI)

## ویژگی‌ها

- ✅ پردازش ناهمگام رویدادهای AMI
- ✅ مدیریت ماشین حالت تماس‌ها
- ✅ API RESTful برای ایجاد و مدیریت تماس‌ها
- ✅ اتصال به PostgreSQL برای ذخیره‌سازی
- ✅ Docker Compose برای اجرای کامل سیستم

## ساختار پروژه

```
masked-call/
├── src/
│   ├── api/              # API endpoints
│   ├── ami_client/       # منطق اتصال به AMI
│   ├── database/         # مدل‌ها و اتصال به DB
│   └── main.py          # نقطه شروع اپلیکیشن
├── conf/                 # فایل‌های کانفیگ Asterisk
├── logs/                 # لاگ‌های Asterisk
├── Dockerfile.web
├── Dockerfile.asterisk
├── docker-compose.yml
└── requirements.txt
```

## راه‌اندازی

### پیش‌نیازها

- Docker و Docker Compose نصب شده باشد

### مراحل

1. کپی کردن فایل‌های کانفیگ Asterisk به `conf/asterisk/`:
   - `manager.conf` - کانفیگ AMI
   - `extensions.conf` - کانفیگ تماس‌ها
   - سایر فایل‌های مورد نیاز

2. اجرای سرویس‌ها:

```bash
docker-compose up -d
```

3. بررسی وضعیت سرویس‌ها:

```bash
docker-compose ps
```

4. مشاهده لاگ‌ها:

```bash
docker-compose logs -f web_service
```

## استفاده از API

### ایجاد تماس جدید

```bash
curl -X POST "http://localhost:8000/api/v1/call/create" \
  -H "Content-Type: application/json" \
  -d '{
    "caller_number": "09123456789",
    "callee_number": "09187654321",
    "masked_caller_number": "02112345678"
  }'
```

### دریافت وضعیت تماس

```bash
curl "http://localhost:8000/api/v1/call/{session_id}"
```

## متغیرهای محیطی

در `docker-compose.yml` می‌توانید تنظیمات زیر را تغییر دهید:

- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: تنظیمات دیتابیس
- `AMI_HOST`, `AMI_PORT`, `AMI_USER`, `AMI_SECRET`: تنظیمات AMI

## توسعه

برای توسعه محلی:

```bash
# نصب پکیج‌ها
pip install -r requirements.txt

# اجرای اپلیکیشن
uvicorn src.main:app --reload
```

## لایسنس

MIT

