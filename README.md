# راهنمای استفاده

این پروژه یک فایل Python ساده دارد که "سلام دنیا" را چاپ می‌کند.

## مشکل: uvicorn not found

اگر خطای `uvicorn: executable file not found` می‌بینید، یعنی از image قدیمی استفاده می‌شود.

### راه حل:

1. **Build مجدد image:**
```bash
docker build -t registry.hamdocker.ir/airoom/masked-call:main .
```

2. **Push به registry:**
```bash
docker push registry.hamdocker.ir/airoom/masked-call:main
```

3. **یا اگر از platform استفاده می‌کنید، image را refresh کنید**

## تست محلی:

```bash
docker build -t test-hello .
docker run test-hello
```

باید "سلام دنیا" را ببینید!

## فایل‌های موجود:

- `app.py` - فایل Python ساده
- `Dockerfile` - فایل Docker که app.py را اجرا می‌کند

