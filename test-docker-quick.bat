@echo off
echo ساخت ایمیج و اجرای کانتینر...
docker build -t masked-call . && docker run -p 5000:5000 masked-call

