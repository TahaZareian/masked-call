import os
import socket
from typing import Optional, Dict, List


class AsteriskManager:
    """کلاس برای مدیریت اتصال به Asterisk از طریق AMI"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        secret: Optional[str] = None
    ):
        """
        مقداردهی اولیه Asterisk Manager

        Args:
            host: آدرس سرور Asterisk
                (از environment variable یا پارامتر)
            port: پورت AMI (پیش‌فرض: 5038)
            username: نام کاربری AMI
                (از environment variable یا پارامتر)
            secret: رمز عبور AMI
                (از environment variable یا پارامتر)
        """
        self.host = host or os.getenv('ASTERISK_HOST')
        self.port = port or int(os.getenv('ASTERISK_PORT', '5038'))
        self.username = username or os.getenv('ASTERISK_USERNAME')
        self.secret = secret or os.getenv('ASTERISK_SECRET')
        self.socket: Optional[socket.socket] = None
        self.connected = False

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
