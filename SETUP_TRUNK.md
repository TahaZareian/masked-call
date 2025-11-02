# راهنمای راه‌اندازی SIP Trunk بین Docker Asterisk و سرور خارجی

## 📋 خلاصه معماری

```
سرور Docker (همروش)
├── Asterisk Container
│   ├── SIP Port: 5060 (UDP/TCP)
│   ├── AMI Port: 5038
│   └── RTP Ports: 10000-10099
│
└── Web Service Container
    ├── API Port: 8000
    └── اتصال به:
        ├── دیتابیس PostgreSQL (خارجی - همروش)
        └── Asterisk AMI (داخل Docker)

                ↓ SIP Trunk ↓

سرور Asterisk خارجی
├── خطوط فیزیکی (PRI/T1/E1/SIP Trunk به اپراتور)
└── SIP Trunk به Docker Asterisk
```

---

## 🚀 مراحل راه‌اندازی

### مرحله 1: آماده‌سازی Docker Compose

#### گزینه A: استفاده از فایل آماده

```bash
# استفاده از docker-compose.external-db.yml
cp docker-compose.external-db.yml docker-compose.yml
```

#### گزینه B: تنظیم دستی

در `docker-compose.yml`:
1. سرویس `db` را حذف کنید (اگر از دیتابیس خارجی استفاده می‌کنید)
2. در `web_service`، متغیرهای محیطی دیتابیس را به IP خارجی تنظیم کنید

---

### مرحله 2: ایجاد فایل `.env`

```bash
# .env
# ===== دیتابیس خارجی (همروش) =====
DB_HOST=123.45.67.89           # IP دیتابیس روی همروش
DB_NAME=masked_call_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_PORT=5432

# ===== Asterisk AMI =====
AMI_HOST=asterisk               # برای داخل Docker
AMI_PORT=5038
AMI_USER=ami_user
AMI_SECRET=ami_secret           # باید با manager.conf مطابقت داشته باشد

# ===== تنظیمات اضافی =====
# LOG_LEVEL=INFO
```

---

### مرحله 3: کانفیگ Asterisk در Docker

#### 3.1. ایجاد ساختار فولدر

```bash
mkdir -p conf/asterisk
mkdir -p logs/asterisk
```

#### 3.2. فایل `conf/asterisk/manager.conf`

```ini
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[ami_user]
secret = ami_secret
deny = 0.0.0.0/0.0.0.0
permit = 172.0.0.0/255.0.0.0    ; شبکه Docker
permit = 192.168.0.0/255.255.0.0  ; شبکه محلی (اگر نیاز دارید)
read = system,call,log,verbose,command,agent,user
write = system,call,log,verbose,command,agent,user
```

#### 3.3. فایل `conf/asterisk/sip.conf`

```ini
[general]
context=from-internal
allowguest=no
udpbindaddr=0.0.0.0
tcpenable=yes
tcpbindaddr=0.0.0.0
srvlookup=yes

; اگر پشت NAT هستید:
externip=IP_PUBLIC_DOCKER_SERVER
localnet=192.168.0.0/255.255.0.0

; ===== SIP Trunk به سرور خارجی =====
[external-server-trunk]
type=peer
host=IP_EXTERNAL_ASTERISK         ; IP سرور Asterisk خارجی
username=trunk_docker             ; نام کاربری در سرور خارجی
secret=trunk_password              ; رمز عبور
fromuser=trunk_docker
context=from-internal
canreinvite=no
dtmfmode=rfc2833
disallow=all
allow=ulaw
allow=alaw
qualify=yes

; ثبت‌نام خودکار (Register)
; در بخش [general] این خط را اضافه کنید:
; register => trunk_docker:trunk_password@IP_EXTERNAL_ASTERISK/external-server-trunk
```

**⚠️ مهم:** 
- `IP_EXTERNAL_ASTERISK`: IP یا hostname سرور Asterisk خارجی که خطوط دارد
- `username` و `secret`: باید در سرور خارجی هم تعریف شده باشد

#### 3.4. فایل `conf/asterisk/extensions.conf`

```ini
[general]
static=yes
writeprotect=no
autofallthrough=yes

[from-internal]
; روتینگ تماس به سرور خارجی از طریق trunk
exten => _X.,1,NoOp(Calling ${EXTEN} from ${CALLERID(num)})
; استفاده از masked caller number اگر تعریف شده باشد
exten => _X.,n,Set(CALLERID(num)=${MASKED_CALLER_ID:${CALLERID(num)}})
exten => _X.,n,Dial(SIP/${EXTEN}@external-server-trunk,30,tT)
exten => _X.,n,Hangup()
```

---

### مرحله 4: کانفیگ سرور Asterisk خارجی

روی سرور Asterisk خارجی که خطوط فیزیکی دارد، باید peer برای Docker تعریف کنید:

#### در `/etc/asterisk/sip.conf` سرور خارجی:

```ini
; Peer برای Docker Asterisk
[docker-asterisk]
type=peer
host=IP_DOCKER_SERVER            ; IP سرور Docker
secret=trunk_password            ; باید با Docker مطابقت داشته باشد
username=trunk_docker
context=from-internal
canreinvite=no
insecure=port,invite            ; اگر authentication نمی‌خواهید
```

#### در `/etc/asterisk/extensions.conf` سرور خارجی:

```ini
[from-internal]
; روتینگ تماس‌های ورودی از Docker
exten => _X.,1,NoOp(Incoming from Docker: ${EXTEN})
exten => _X.,n,Dial(PRI/g1/${EXTEN})    ; یا SIP/trunk/${EXTEN}
exten => _X.,n,Hangup()
```

---

### مرحله 5: راه‌اندازی

```bash
# 1. ساخت و اجرای کانتینرها
docker-compose up -d

# 2. بررسی لاگ‌ها
docker-compose logs -f asterisk

# 3. بررسی وضعیت SIP در Asterisk
docker exec -it asterisk_server asterisk -rx "sip show peers"
docker exec -it asterisk_server asterisk -rx "sip show registry"

# 4. بررسی AMI
docker exec -it asterisk_server asterisk -rx "manager show connected"
```

---

## ✅ تست کردن

### تست 1: بررسی اتصال SIP Trunk

```bash
# در Docker Asterisk
docker exec -it asterisk_server asterisk -rx "sip show peers"
# باید external-server-trunk را ببینید با status OK

docker exec -it asterisk_server asterisk -rx "sip show registry"
# اگر register کرده باشید، باید Registered باشد
```

### تست 2: تست تماس از طریق API

```bash
curl -X POST "http://localhost:8000/api/v1/call/create" \
  -H "Content-Type: application/json" \
  -d '{
    "caller_number": "09123456789",
    "callee_number": "02112345678",
    "masked_caller_number": "02187654321"
  }'
```

### تست 3: بررسی لاگ‌ها

```bash
# لاگ‌های Asterisk
docker-compose logs -f asterisk

# لاگ‌های سرویس وب
docker-compose logs -f web_service
```

---

## 🔧 عیب‌یابی

### مشکل 1: SIP Trunk برقرار نمی‌شود

**بررسی‌ها:**
```bash
# 1. بررسی پورت‌های باز
docker exec -it asterisk_server netstat -tulpn | grep 5060

# 2. بررسی کانفیگ SIP
docker exec -it asterisk_server asterisk -rx "sip show peers"

# 3. بررسی لاگ‌ها
docker-compose logs asterisk | grep -i sip
```

**راه‌حل:**
- IP و port را چک کنید
- Firewall را بررسی کنید (5060 UDP/TCP)
- در NAT، `externip` را تنظیم کنید

### مشکل 2: Register نمی‌شود

**بررسی:**
```bash
docker exec -it asterisk_server asterisk -rx "sip show registry"
```

**راه‌حل:**
- username و password را بررسی کنید
- در سرور خارجی، peer برای Docker تعریف شده باشد
- اگر NAT دارید، `externip` را تنظیم کنید

### مشکل 3: تماس برقرار نمی‌شود

**بررسی:**
- لاگ‌های Asterisk در Docker
- لاگ‌های Asterisk در سرور خارجی
- بررسی extensions.conf

**راه‌حل:**
- Context را بررسی کنید
- Dial string را چک کنید
- CallerID را تنظیم کنید

---

## 📝 نکات مهم

1. **امنیت:**
   - از رمزهای قوی استفاده کنید
   - IP های مجاز را محدود کنید
   - از TLS برای SIP استفاده کنید (اختیاری)

2. **NAT:**
   - اگر Docker پشت NAT است، `externip` را در sip.conf تنظیم کنید
   - Port forwarding را در router انجام دهید

3. **RTP:**
   - پورت‌های 10000-10099 برای RTP باید باز باشند
   - در docker-compose.yml پورت‌ها را map کنید

4. **دیتابیس:**
   - مطمئن شوید firewall دیتابیس خارجی به Docker اجازه اتصال می‌دهد
   - از SSL برای اتصال دیتابیس استفاده کنید (توصیه می‌شود)

---

## 🎯 خلاصه

1. ✅ دیتابیس: روی همروش (خارجی)
2. ✅ Asterisk: در Docker
3. ✅ سرویس وب: در Docker
4. ✅ SIP Trunk: Docker ↔ سرور خارجی

**ترانک از Docker به سرور خارجی یا برعکس؟**
- اگر سرور خارجی به Docker trunk می‌زند: peer در Docker
- اگر Docker به سرور خارجی متصل می‌شود: register در Docker

**پیشنهاد:** از register استفاده کنید (ساده‌تر و مناسب‌تر برای NAT)

