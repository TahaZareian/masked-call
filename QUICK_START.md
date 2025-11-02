# راه‌اندازی سریع - با ترانک SIP

## 📌 وضعیت شما:
- ✅ دیتابیس PostgreSQL روی همروش دارید
- ✅ سرور Asterisk خارجی با خطوط فیزیکی دارید
- ✅ می‌خواهید Asterisk را در Docker اجرا کنید
- ✅ می‌خواهید ترانک SIP بین Docker و سرور خارجی برقرار کنید

---

## 🚀 مراحل سریع

### 1️⃣ ایجاد فایل `.env`

```bash
# .env
DB_HOST=123.45.67.89           # IP دیتابیس روی همروش
DB_NAME=masked_call_db
DB_USER=your_user
DB_PASSWORD=your_password
DB_PORT=5432

AMI_HOST=asterisk
AMI_PORT=5038
AMI_USER=ami_user
AMI_SECRET=ami_secret
```

### 2️⃣ آماده‌سازی فایل‌های کانفیگ Asterisk

```bash
mkdir -p conf/asterisk logs/asterisk
```

### 3️⃣ کانفیگ Asterisk

#### `conf/asterisk/manager.conf`:
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

#### `conf/asterisk/sip.conf`:
```ini
[general]
context=from-internal
allowguest=no
udpbindaddr=0.0.0.0
tcpenable=yes
tcpbindaddr=0.0.0.0

; اگر پشت NAT هستید:
externip=IP_PUBLIC_DOCKER_SERVER
localnet=192.168.0.0/255.255.0.0

; ترانک به سرور خارجی
[external-server-trunk]
type=peer
host=IP_EXTERNAL_ASTERISK        ; IP سرور Asterisk خارجی
username=trunk_docker
secret=trunk_password
context=from-internal
canreinvite=no
dtmfmode=rfc2833
disallow=all
allow=ulaw
allow=alaw

; ثبت‌نام خودکار (اختیاری - اگر می‌خواهید Docker به سرور خارجی متصل شود)
; register => trunk_docker:trunk_password@IP_EXTERNAL_ASTERISK/external-server-trunk
```

#### `conf/asterisk/extensions.conf`:
```ini
[general]
static=yes
writeprotect=no

[from-internal]
exten => _X.,1,NoOp(Calling ${EXTEN} from ${CALLERID(num)})
exten => _X.,n,Dial(SIP/${EXTEN}@external-server-trunk,30,tT)
exten => _X.,n,Hangup()
```

### 4️⃣ کانفیگ سرور Asterisk خارجی

در سرور Asterisk خارجی که خطوط دارد، در `/etc/asterisk/sip.conf`:

```ini
[docker-asterisk]
type=peer
host=IP_DOCKER_SERVER           ; IP سرور Docker
secret=trunk_password            ; باید با Docker مطابقت داشته باشد
username=trunk_docker
context=from-internal
```

### 5️⃣ راه‌اندازی

```bash
# استفاده از فایل آماده
cp docker-compose.external-db.yml docker-compose.yml

# یا از docker-compose.yml اصلی استفاده کنید (دیتابیس محلی را حذف کنید)

# راه‌اندازی
docker-compose up -d

# بررسی لاگ‌ها
docker-compose logs -f asterisk
```

### 6️⃣ تست

```bash
# بررسی SIP Trunk
docker exec -it asterisk_server asterisk -rx "sip show peers"

# تست API
curl -X POST "http://localhost:8000/api/v1/call/create" \
  -H "Content-Type: application/json" \
  -d '{
    "caller_number": "09123456789",
    "callee_number": "02112345678",
    "masked_caller_number": "02187654321"
  }'
```

---

## 📚 راهنمای کامل

برای جزئیات بیشتر، فایل `SETUP_TRUNK.md` را بخوانید.

---

## ⚠️ نکات مهم

1. **IP ها را تغییر دهید:**
   - `IP_DOCKER_SERVER`: IP سرور Docker شما
   - `IP_EXTERNAL_ASTERISK`: IP سرور Asterisk خارجی
   - `IP_PUBLIC_DOCKER_SERVER`: IP عمومی سرور Docker (اگر NAT دارید)

2. **Firewall:**
   - پورت‌های 5060 (SIP) و 10000-10099 (RTP) را باز کنید
   - اگر از بیرون به دیتابیس وصل می‌شوید، 5432 را باز کنید

3. **امنیت:**
   - رمزهای قوی استفاده کنید
   - IP های مجاز را محدود کنید

---

## 🔧 عیب‌یابی سریع

### SIP Trunk برقرار نمی‌شود؟
```bash
# بررسی peers
docker exec -it asterisk_server asterisk -rx "sip show peers"

# بررسی لاگ‌ها
docker-compose logs asterisk | grep -i sip
```

### دیتابیس وصل نمی‌شود؟
- IP و port را بررسی کنید
- Firewall دیتابیس را بررسی کنید
- Credentials را چک کنید

### API کار نمی‌کند؟
```bash
# بررسی سرویس وب
docker-compose logs web_service

# بررسی اتصال AMI
docker exec -it asterisk_server asterisk -rx "manager show connected"
```

