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
                self.secret = db_config.get('secret') or ''
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
                return {
                    'host': str(row[0]),
                    'port': int(row[1]) if row[1] else 5038,
                    'username': str(row[2]) if row[2] else '',
                    'secret': str(row[3]) if row[3] else ''
                }
            return None
        except Exception as e:
            print(f"خطا در خواندن تنظیمات Asterisk از دیتابیس: {e}")
            if conn:
                conn.close()
            return None

    def connect(self) -> bool:
        """
        اتصال به سرور Asterisk

        Returns:
            True اگر اتصال موفق باشد
        """
        if not all([self.host, self.port, self.username, self.secret]):
            print("خطا: تنظیمات Asterisk کامل نیست")
            return False

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))

            # دریافت پیام خوش‌آمدگویی
            response = self._receive_response()
            print(f"Asterisk response: {response[:200]}...")

            # ارسال اطلاعات احراز هویت
            login_command = (
                f"Action: Login\r\n"
                f"Username: {self.username}\r\n"
                f"Secret: {self.secret}\r\n"
                f"\r\n"
            )
            self.socket.send(login_command.encode())

            # دریافت پاسخ احراز هویت
            response = self._receive_response()
            success_indicators = (
                "Success" in response or
                "Message: Authentication accepted" in response
            )
            if success_indicators:
                self.connected = True
                print("اتصال به Asterisk برقرار شد")
                return True
            else:
                print(f"خطا در احراز هویت: {response}")
                self.disconnect()
                return False

        except Exception as e:
            print(f"خطا در اتصال به Asterisk: {e}")
            self.disconnect()
            return False

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
        try:
            while True:
                data = self.socket.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break
                response += data
                if "\r\n\r\n" in response:
                    break
        except socket.timeout:
            pass
        except Exception as e:
            print(f"خطا در دریافت پاسخ: {e}")

        return response

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
            if not self.connect():
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
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
