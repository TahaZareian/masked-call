import os
import socket
import psycopg2
from typing import Optional, Dict, List, Any


class AsteriskManager:
    """کلاس برای مدیریت اتصال به Asterisk از طریق AMI"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        secret: Optional[str] = None,
        config_name: str = 'default'
    ):
        """
        مقداردهی اولیه Asterisk Manager
        ابتدا از دیتابیس می‌خواند، سپس از environment variables

        Args:
            host: آدرس سرور Asterisk (مستقیم)
            port: پورت AMI (مستقیم)
            username: نام کاربری AMI (مستقیم)
            secret: رمز عبور AMI (مستقیم)
            config_name: نام پیکربندی در دیتابیس (پیش‌فرض: 'default')
        """
        # اگر به صورت مستقیم داده شده، استفاده کن
        if host and port and username and secret:
            self.host = host
            self.port = port
            self.username = username
            self.secret = secret
        else:
            # ابتدا از دیتابیس بخوان
            db_config = self._load_from_db(config_name)
            if db_config:
                self.host = db_config.get('host') or ''
                port_value = db_config.get('port', 5038)
                self.port = int(port_value) if port_value else 5038
                self.username = db_config.get('username') or ''
                # رمز عبور را بدون تغییر از دیتابیس بگیر
                secret_from_db = db_config.get('secret')
                self.secret = secret_from_db if secret_from_db else ''
                
                print("=" * 80)
                print("SECRET ASSIGNED FROM DATABASE:")
                print(f"Secret type: {type(self.secret)}")
                print(f"Secret value: {repr(self.secret)}")
                secret_len = len(self.secret) if self.secret else 0
                print(f"Secret length: {secret_len}")
                print("=" * 80)
            else:
                # اگر در دیتابیس نبود، از environment variables بخوان
                self.host = host or os.getenv('ASTERISK_HOST') or ''
                self.port = port or int(os.getenv('ASTERISK_PORT', '5038'))
                username_val = username or os.getenv('ASTERISK_USERNAME')
                self.username = username_val or ''
                self.secret = secret or os.getenv('ASTERISK_SECRET') or ''

        self.socket: Optional[socket.socket] = None
        self.connected = False

    def _get_db_connection(self):
        """ایجاد اتصال به دیتابیس"""
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')

        if not all([db_host, db_port, db_name, db_user, db_password]):
            return None

        try:
            conn = psycopg2.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password
            )
            return conn
        except Exception as e:
            print(f"خطا در اتصال به دیتابیس: {e}")
            return None

    def _load_from_db(
        self,
        config_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        بارگذاری تنظیمات از دیتابیس

        Args:
            config_name: نام پیکربندی

        Returns:
            دیکشنری تنظیمات یا None
        """
        conn = self._get_db_connection()
        if not conn:
            return None

        try:
            # ایجاد جدول در صورت عدم وجود
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS asterisk_config (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL DEFAULT 'default',
                    host VARCHAR(255),
                    port INTEGER DEFAULT 5038,
                    username VARCHAR(255),
                    secret VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            # خواندن تنظیمات
            cursor.execute("""
                SELECT host, port, username, secret
                FROM asterisk_config
                WHERE name = %s
            """, (config_name,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row and row[0]:  # اگر host موجود باشد
                # خواندن رمز عبور بدون تغییر
                secret_from_db = row[3]
                print("=" * 80)
                print("LOADING SECRET FROM DATABASE:")
                print(f"Secret type: {type(secret_from_db)}")
                print(f"Secret value: {repr(secret_from_db)}")
                print(f"Secret length: {len(secret_from_db) if secret_from_db else 0}")
                secret_bytes = (
                    secret_from_db.encode('utf-8')
                    if secret_from_db else b''
                )
                print(f"Secret bytes: {repr(secret_bytes)}")
                print("=" * 80)
                
                return {
                    'host': str(row[0]) if row[0] else '',
                    'port': int(row[1]) if row[1] else 5038,
                    'username': str(row[2]) if row[2] else '',
                    # بدون تبدیل، دقیقاً همان‌طور که از دیتابیس خوانده شد
                    'secret': secret_from_db
                }
            return None
        except Exception as e:
            print(f"خطا در خواندن تنظیمات Asterisk از دیتابیس: {e}")
            if conn:
                conn.close()
            return None

    def connect(self) -> tuple[bool, str]:
        """
        اتصال به سرور Asterisk

        Returns:
            tuple (success, error_message)
        """
        if not all([self.host, self.port, self.username, self.secret]):
            error = "تنظیمات Asterisk کامل نیست"
            print(f"خطا: {error}")
            return False, error

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))

            # دریافت پیام خوش‌آمدگویی
            welcome_response = self._receive_response()
            print("=" * 80)
            print("Asterisk Welcome Response (FULL):")
            print(welcome_response)
            print("=" * 80)

            # ارسال اطلاعات احراز هویت
            # فرمت AMI: Action: Login\r\nUsername: ...\r\nSecret: ...\r\n\r\n
            
            # بررسی encoding رمز عبور
            print("=" * 80)
            print("SECRET ANALYSIS:")
            print(f"Secret length: {len(self.secret)}")
            print(f"Secret repr: {repr(self.secret)}")
            secret_utf8 = self.secret.encode('utf-8')
            secret_latin1 = self.secret.encode('latin-1', errors='ignore')
            print(f"Secret bytes (UTF-8): {repr(secret_utf8)}")
            print(f"Secret bytes (Latin-1): {repr(secret_latin1)}")
            for i, char in enumerate(self.secret):
                print(f"  Char {i}: {repr(char)} (U+{ord(char):04X})")
            print("=" * 80)
            
            login_command = (
                f"Action: Login\r\n"
                f"Username: {self.username}\r\n"
                f"Secret: {self.secret}\r\n"
                f"\r\n"
            )
            print("=" * 80)
            print("Sending Login Command:")
            print(f"Username: {self.username}")
            secret_mask = '*' * len(self.secret) if self.secret else 'empty'
            print(f"Secret: {secret_mask}")
            print(f"Secret repr: {repr(self.secret)}")
            print("Command (raw bytes - UTF-8):")
            cmd_utf8 = login_command.encode('utf-8')
            print(repr(cmd_utf8))
            print("Command (raw bytes - Latin-1):")
            cmd_latin1 = login_command.encode('latin-1', errors='ignore')
            print(repr(cmd_latin1))
            print("Command (text):")
            print(login_command)
            print("=" * 80)
            
            # ارسال دستور login با UTF-8 (بدون تغییر رمز عبور)
            print("=" * 80)
            print("Sending Login Command (UTF-8, original secret):")
            print("Secret will be sent exactly as stored (no modifications)")
            print("=" * 80)
            self.socket.send(cmd_utf8)
            
            # دریافت پاسخ
            response = self._receive_response(timeout=5)
            print("=" * 80)
            print("Login Response (FULL):")
            print(response)
            print("=" * 80)
            
            # تجزیه خط به خط
            print("Response Analysis:")
            lines = response.split('\n')
            for i, line in enumerate(lines):
                print(f"Line {i}: {repr(line)}")
            print("=" * 80)

            # بررسی پاسخ
            response_lower = response.lower()
            print("Checking response indicators...")
            has_success = 'success' in response_lower
            has_auth_accepted = 'authentication accepted' in response_lower
            has_error = 'error' in response_lower
            has_auth_failed = 'authentication failed' in response_lower
            
            print(f"Response contains 'success': {has_success}")
            print(
                f"Response contains 'authentication accepted': "
                f"{has_auth_accepted}"
            )
            print(f"Response contains 'error': {has_error}")
            print(
                f"Response contains 'authentication failed': "
                f"{has_auth_failed}"
            )
            
            success_indicators = (
                "success" in response_lower or
                "authentication accepted" in response_lower or
                "message: authentication accepted" in response_lower
            )

            error_indicators = (
                "authentication failed" in response_lower or
                ("error" in response_lower and
                 "authentication" in response_lower)
            )

            print(f"Success indicators: {success_indicators}")
            print(f"Error indicators: {error_indicators}")

            if success_indicators:
                self.connected = True
                print("=" * 80)
                print("✓ اتصال به Asterisk برقرار شد")
                print("=" * 80)
                return True, ""
            elif error_indicators:
                # استخراج پیام خطای دقیق
                error_msg = "Authentication failed"
                error_details = {}
                
                lines = response.split('\r\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()
                        error_details[key] = value
                        if key == 'message':
                            error_msg = value
                
                print("=" * 80)
                print("✗ خطا در احراز هویت")
                print("Error Details:")
                for key, value in error_details.items():
                    print(f"  {key}: {value}")
                print("=" * 80)
                
                full_error = (
                    f"خطا در احراز هویت: {error_msg}. "
                    f"پاسخ کامل: {response}"
                )
                self.disconnect()
                return False, full_error
            else:
                error = (
                    f"پاسخ نامعتبر از سرور. "
                    f"پاسخ کامل: {response}"
                )
                print("=" * 80)
                print("✗ پاسخ نامعتبر")
                print(f"Response: {response}")
                print("=" * 80)
                self.disconnect()
                return False, error

        except socket.timeout:
            error = f"Timeout: نمی‌توان به {self.host}:{self.port} متصل شد"
            print(error)
            self.disconnect()
            return False, error
        except socket.gaierror as e:
            error = f"خطا در DNS: نمی‌توان host '{self.host}' را پیدا کرد"
            print(f"{error}: {e}")
            self.disconnect()
            return False, error
        except ConnectionRefusedError:
            error = (
                f"اتصال رد شد: "
                f"سرور {self.host}:{self.port} در دسترس نیست"
            )
            print(error)
            self.disconnect()
            return False, error
        except Exception as e:
            error = f"خطا در اتصال: {str(e)}"
            print(error)
            self.disconnect()
            return False, error

    def _receive_response(self, timeout: int = 5) -> str:
        """
        دریافت پاسخ از Asterisk

        Args:
            timeout: زمان انتظار برای دریافت پاسخ

        Returns:
            پاسخ دریافت شده
        """
        if not self.socket:
            return ""

        response = ""
        self.socket.settimeout(timeout)
        chunks = []
        try:
            while True:
                data = self.socket.recv(4096)
                if not data:
                    break
                chunks.append(data)
                decoded = data.decode('utf-8', errors='ignore')
                response += decoded
                print(f"Received chunk: {repr(data)}")
                print(f"Decoded chunk: {repr(decoded)}")
                if "\r\n\r\n" in response:
                    print("Found end marker (\\r\\n\\r\\n)")
                    break
        except socket.timeout:
            print(f"Socket timeout after {timeout} seconds")
            pass
        except Exception as e:
            print(f"خطا در دریافت پاسخ: {e}")
            print(f"Exception type: {type(e).__name__}")

        print(f"Total chunks received: {len(chunks)}")
        print(f"Total response length: {len(response)} bytes")
        return response

    def originate_call(
        self,
        channel: str,
        number: str,
        caller_id: Optional[str] = None,
        context: str = "from-trunk",
        timeout: int = 30
    ) -> tuple[bool, str, Optional[str]]:
        """
        برقراری تماس به یک شماره

        Args:
            channel: کانال تماس (مثال: SIP/trunk/09140916320)
            number: شماره مقصد (مثال: 09221609805)
            caller_id: شماره نمایش داده شده (اختیاری)
            context: کانتکست Asterisk (پیش‌فرض: from-trunk)
            timeout: زمان انتظار برای برقراری تماس (ثانیه)

        Returns:
            tuple (success, message, action_id)
        """
        if not self.connected:
            success, error = self.connect()
            if not success:
                return False, f"خطا در اتصال به Asterisk: {error}", None

        # ساخت دستور Originate
        # برای تماس مستقیم از trunk، از Application/Dial استفاده می‌کنیم
        # فرمت: Channel: SIP/trunk/number
        # Application: Dial
        # Data: SIP/trunk/number
        
        # استخراج trunk name از channel
        channel_parts = channel.split('/')
        trunk_name = (
            channel_parts[1]
            if len(channel_parts) > 1 else 'trunk_external'
        )
        
        # استفاده از Application/Dial برای تماس مستقیم
        params = {
            'Channel': channel,
            'Application': 'Dial',
            'Data': f"SIP/{trunk_name}/{number}",  # Dial to number
            'Timeout': str(timeout * 1000),  # میلی‌ثانیه
            'Async': 'true'
        }

        # اگر caller_id مشخص شده، اضافه می‌کنیم
        if caller_id:
            params['CallerID'] = caller_id

        print(f"Originate params: {params}")
        response = self._send_command('Originate', params)
        print(f"Originate response: {response}")

        # بررسی پاسخ
        if 'Response: Success' in response:
            # استخراج ActionID
            action_id = None
            for line in response.split('\r\n'):
                if line.startswith('ActionID:'):
                    action_id = line.split(':', 1)[1].strip()
                    break

            return True, "تماس با موفقیت آغاز شد", action_id
        elif 'Response: Error' in response:
            # استخراج پیام خطا
            error_msg = "خطا در برقراری تماس"
            for line in response.split('\r\n'):
                if line.startswith('Message:'):
                    error_msg = line.split(':', 1)[1].strip()
                    break
            return False, error_msg, None
        else:
            return False, f"پاسخ نامعتبر: {response}", None

    def _send_command(
        self,
        action: str,
        params: Optional[Dict[str, str]] = None
    ) -> str:
        """
        ارسال دستور به Asterisk

        Args:
            action: نام action
            params: پارامترهای اضافی

        Returns:
            پاسخ دریافت شده
        """
        if not self.connected or not self.socket:
            return "Not connected"

        command = f"Action: {action}\r\n"
        if params:
            for key, value in params.items():
                command += f"{key}: {value}\r\n"
        command += "\r\n"

        try:
            self.socket.send(command.encode())
            response = self._receive_response()
            return response
        except Exception as e:
            print(f"خطا در ارسال دستور: {e}")
            return f"Error: {e}"

    def disconnect(self):
        """قطع اتصال از Asterisk"""
        if self.socket:
            try:
                if self.connected:
                    self._send_command("Logoff")
                self.socket.close()
            except Exception:
                pass
            finally:
                self.socket = None
                self.connected = False

    def create_pjsip_trunk(
        self,
        trunk_name: str,
        host: str,
        username: str,
        secret: str,
        port: int = 5060,
        transport: str = "udp"
    ) -> bool:
        """
        ایجاد trunk PJSIP در Asterisk

        Args:
            trunk_name: نام trunk
            host: آدرس سرور trunk
            username: نام کاربری
            secret: رمز عبور
            port: پورت (پیش‌فرض: 5060)
            transport: نوع انتقال (udp/tcp/tls)

        Returns:
            True اگر موفق باشد
        """
        if not self.connected:
            success, _ = self.connect()
            if not success:
                return False

        # بررسی وجود endpoint
        response = self._send_command("PJSIPShowEndpoints")
        if trunk_name in response:
            print(f"Trunk {trunk_name} از قبل وجود دارد")
            return True

        # ایجاد trunk با استفاده از CLI (اگر AMI مستقیماً پشتیبانی نکند)
        # این کار معمولاً از طریق CLI یا فایل‌های پیکربندی انجام می‌شود
        print(
            f"برای ایجاد trunk {trunk_name}، "
            f"از CLI یا فایل‌های پیکربندی استفاده کنید"
        )
        return True

    def get_trunk_status(self, trunk_name: str) -> Dict:
        """
        دریافت وضعیت trunk

        Args:
            trunk_name: نام trunk

        Returns:
            اطلاعات وضعیت trunk
        """
        if not self.connected:
            if not self.connect():
                return {"status": "not_connected"}

        response = self._send_command("PJSIPShowEndpoints")
        if trunk_name in response:
            return {
                "status": "exists",
                "name": trunk_name
            }
        return {"status": "not_found"}

    def list_trunks(self) -> List[str]:
        """
        دریافت لیست trunk‌ها

        Returns:
            لیست نام trunk‌ها
        """
        if not self.connected:
            if not self.connect():
                return []

        response = self._send_command("PJSIPShowEndpoints")
        # تجزیه پاسخ و استخراج نام trunk‌ها
        trunks = []
        lines = response.split('\n')
        for line in lines:
            if 'Endpoint:' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    trunk_name = parts[1].strip()
                    if trunk_name:
                        trunks.append(trunk_name)

        return trunks

    def is_connected(self) -> bool:
        """بررسی اتصال به Asterisk"""
        return self.connected

    def __enter__(self):
        """Context manager entry"""
        self.connect()  # ignore result for context manager
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
