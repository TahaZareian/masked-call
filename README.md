# برنامه Flask ساده با Docker

این یک برنامه Flask ساده است که با Docker containerize شده است.

## اجرای مستقیم

```bash
pip install -r requirements.txt
python app.py
```

## ساخت و اجرای با Docker

### ساخت ایمیج Docker
```bash
docker build -t masked-call .
```

### اجرای کانتینر
```bash
docker run -p 5000:5000 masked-call
```

### اجرا در بکگراند
```bash
docker run -d -p 5000:5000 --name my-app masked-call
```

## دسترسی به اپلیکیشن

بعد از اجرا، می‌توانید از طریق آدرس زیر به اپلیکیشن دسترسی پیدا کنید:
- http://localhost:5000
- http://localhost:5000/health

## دستورات مفید Docker

### مشاهده لاگ‌ها
```bash
docker logs my-app
```

### توقف کانتینر
```bash
docker stop my-app
```

### حذف کانتینر
```bash
docker rm my-app
```

### حذف ایمیج
```bash
docker rmi masked-call
```

