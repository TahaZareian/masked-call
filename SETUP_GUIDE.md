# راهنمای راه‌اندازی پروژه Masked Call

## 🎯 گزینه‌های راه‌اندازی

چون نیاز به دسترسی به خطوط فیزیکی دارید، سه راه دارید:

---

## 🚀 روش ۱: راه‌اندازی ترکیبی (پیشنهادی)

**Asterisk روی سرور جداگانه** + **سرویس وب و دیتابیس در Docker**

این روش بهترین است چون:
- ✅ Asterisk روی سروری که به خطوط دسترسی دارد اجرا می‌شود
- ✅ نیازی به نصب Asterisk در Docker نیست
- ✅ سرویس وب به راحتی قابل توسعه است

### مراحل:

#### ۱. نصب Asterisk روی سرور با خطوط

```bash
# روی سرور لینوکس
sudo apt update
sudo apt install -y asterisk

# یا برای CentOS/RHEL
sudo yum install -y asterisk
```

#### ۲. کانفیگ Asterisk

فایل‌های زیر را در `/etc/asterisk/` ایجاد/ویرایش کنید:

**manager.conf** (برای AMI):
```ini
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[ami_user]
secret = ami_secret
deny = 0.0.0.0/0.0.0.0
permit = 192.168.0.0/255.255.0.0  ; IP range مجاز برای اتصال
read = system,call,log,verbose,command,agent,user
write = system,call,log,verbose,command,agent,user
```

**extensions.conf** (برای routing تماس‌ها):
```ini
[general]
static=yes
writeprotect=no

[globals]

[from-internal]
; روتینگ برای تماس‌های داخلی
exten => _X.,1,NoOp(Calling ${EXTEN} from ${CALLERID(num)})
exten => _X.,n,Dial(SIP/${EXTEN}@your-sip-provider,30)
exten => _X.,n,Hangup()
```

**sip.conf** (برای SIP Trunk):
```ini
[general]
context=from-internal
allowguest=no
srvlookup=yes
udpbindaddr=0.0.0.0
tcpenable=yes
tcpbindaddr=0.0.0.0

; SIP Trunk به ارائه‌دهنده
[your-sip-provider]
type=peer
host=sip.provider.com
username=your_username
secret=your_password
fromuser=your_username
fromdomain=sip.provider.com
canreinvite=no
insecure=port,invite
context=from-internal
```

#### ۳. راه‌اندازی سرویس وب و دیتابیس

```bash
# فقط سرویس‌های وب و دیتابیس را بالا بیاورید
docker-compose up -d db web_service
```

#### ۴. تنظیم متغیرهای محیطی

یک فایل `.env` ایجاد کنید:

```bash
# .env
DB_HOST=localhost
DB_NAME=masked_call_db
DB_USER=user
DB_PASSWORD=password
DB_PORT=5432

# آدرس Asterisk روی سرور جداگانه
AMI_HOST=192.168.1.100  ; IP سرور Asterisk
AMI_PORT=5038
AMI_USER=ami_user
AMI_SECRET=ami_secret
```

#### ۵. اجرای سرویس وب محلی (بدون Docker)

```bash
# نصب پکیج‌ها
pip install -r requirements.txt

# اجرا
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🐳 روش ۲: راه‌اندازی کامل با Docker

اگر می‌خواهید همه چیز در Docker باشد:

### مشکل:
- در Docker به خطوط فیزیکی دسترسی ندارید
- باید از **SIP Trunk** یا **VoIP Provider** استفاده کنید

### مراحل:

#### ۱. ساختار فایل‌های کانفیگ

```bash
mkdir -p conf/asterisk
```

#### ۲. فایل‌های کانفیگ Asterisk

**conf/asterisk/manager.conf**:
```ini
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[ami_user]
secret = ami_secret
deny = 0.0.0.0/0.0.0.0
permit = 172.0.0.0/255.0.0.0
read = system,call,log,verbose,command,agent,user
write = system,call,log,verbose,command,agent,user
```

**conf/asterisk/extensions.conf**:
```ini
[general]
static=yes
writeprotect=no

[from-internal]
exten => _X.,1,NoOp(Calling ${EXTEN})
exten => _X.,n,Dial(SIP/${EXTEN}@voip-provider,30)
exten => _X.,n,Hangup()
```

**conf/asterisk/sip.conf**:
```ini
[general]
context=from-internal
allowguest=no
udpbindaddr=0.0.0.0
tcpenable=yes
tcpbindaddr=0.0.0.0

; مثال: SIP Trunk
[voip-provider]
type=peer
host=sip.provider.com
username=your_username
secret=your_password
context=from-internal
```

#### ۳. اجرا

```bash
docker-compose up -d
```

---

## 🔧 روش ۳: راه‌اندازی محلی کامل (بدون Docker)

### پیش‌نیازها:
- Python 3.11+
- PostgreSQL
- Asterisk

### مراحل:

#### ۱. نصب PostgreSQL

```bash
# Ubuntu/Debian
sudo apt install -y postgresql postgresql-contrib

# راه‌اندازی
sudo systemctl start postgresql
sudo systemctl enable postgresql

# ایجاد دیتابیس
sudo -u postgres psql
CREATE DATABASE masked_call_db;
CREATE USER user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE masked_call_db TO user;
\q
```

#### ۲. نصب Asterisk

```bash
sudo apt install -y asterisk
sudo systemctl start asterisk
sudo systemctl enable asterisk
```

#### ۳. کانفیگ Asterisk (مثل روش ۱)

#### ۴. راه‌اندازی Python

```bash
# ایجاد محیط مجازی
python -m venv venv
source venv/bin/activate  # Linux/Mac
# یا
venv\Scripts\activate  # Windows

# نصب پکیج‌ها
pip install -r requirements.txt

# تنظیم متغیرهای محیطی
export DB_HOST=localhost
export DB_NAME=masked_call_db
export DB_USER=user
export DB_PASSWORD=password
export AMI_HOST=localhost
export AMI_PORT=5038
export AMI_USER=ami_user
export AMI_SECRET=ami_secret

# اجرا
uvicorn src.main:app --reload
```

---

## ✅ تست کردن

### ۱. بررسی سلامت API

```bash
curl http://localhost:8000/health
```

### ۲. تست ایجاد تماس

```bash
curl -X POST "http://localhost:8000/api/v1/call/create" \
  -H "Content-Type: application/json" \
  -d '{
    "caller_number": "09123456789",
    "callee_number": "09187654321",
    "masked_caller_number": "02112345678"
  }'
```

### ۳. بررسی وضعیت تماس

```bash
curl "http://localhost:8000/api/v1/call/{session_id}"
```

---

## 🔍 عیب‌یابی

### مشکل: اتصال به AMI برقرار نمی‌شود

- بررسی کنید Asterisk در حال اجرا باشد: `sudo systemctl status asterisk`
- بررسی کنید پورت 5038 باز باشد: `sudo netstat -tulpn | grep 5038`
- لاگ‌های Asterisk را بررسی کنید: `sudo tail -f /var/log/asterisk/messages`

### مشکل: تماس برقرار نمی‌شود

- بررسی کانفیگ SIP Trunk
- بررسی extensions.conf
- لاگ‌های Asterisk را بررسی کنید

### مشکل: دیتابیس متصل نمی‌شود

- بررسی کنید PostgreSQL در حال اجرا باشد
- بررسی credentials در متغیرهای محیطی
- بررسی کنید پورت 5432 باز باشد

---

## 📝 نکات مهم

1. **امنیت**: در production، رمزهای عبور قوی استفاده کنید
2. **Firewall**: پورت‌های لازم را باز کنید (8000, 5038, 5060)
3. **SIP Provider**: برای استفاده از خطوط واقعی، به SIP Trunk نیاز دارید
4. **لاگ‌ها**: همیشه لاگ‌ها را بررسی کنید

---

## 🎯 توصیه

برای شروع، **روش ۱ (ترکیبی)** را پیشنهاد می‌کنم:
- Asterisk روی سرور جداگانه با دسترسی به خطوط
- سرویس وب و دیتابیس در Docker یا محلی

این روش انعطاف‌پذیری بیشتری دارد و برای production مناسب‌تر است.

