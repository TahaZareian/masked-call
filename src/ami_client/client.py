"""
منطق اتصال به AMI و ارسال فرمان Originate
"""
import asyncio
import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)


class AMIClient:
    """
    کلاینت برای مدیریت اتصال و فرمان‌های AMI
    """

    def __init__(self):
        self.host = os.getenv("AMI_HOST", "asterisk")
        self.port = int(os.getenv("AMI_PORT", "5038"))
        self.username = os.getenv("AMI_USER", "ami_user")
        self.secret = os.getenv("AMI_SECRET", "ami_secret")
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self) -> bool:
        """
        اتصال به AMI
        """
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            # خواندن پاسخ اولیه
            await self._read_response()

            # ارسال درخواست Login
            login_command = (
                f"Action: Login\r\n"
                f"Username: {self.username}\r\n"
                f"Secret: {self.secret}\r\n\r\n"
            )
            self.writer.write(login_command.encode())
            await self.writer.drain()

            # بررسی پاسخ Login
            response = await self._read_response()
            if "Success" in response:
                self._connected = True
                logger.info(
                    f"متصل شد به AMI در {self.host}:{self.port}"
                )
                # شروع گوش دادن به رویدادها
                asyncio.create_task(self._listen_events())
                return True
            else:
                logger.error(f"خطا در Login: {response}")
                self._connected = False
                await self.disconnect()
                return False
        except Exception as e:
            logger.error(f"خطا در اتصال به AMI: {e}")
            self._connected = False
            return False

    async def _read_response(self) -> str:
        """
        خواندن پاسخ از AMI
        """
        if not self.reader:
            return ""
        response_lines = []
        while True:
            line = await self.reader.readline()
            if not line:
                break
            line_str = line.decode().strip()
            response_lines.append(line_str)
            if line_str == "":
                break
        return "\n".join(response_lines)

    async def _listen_events(self):
        """
        گوش دادن به رویدادهای AMI
        """
        while self._connected and self.reader:
            try:
                event_dict = await self._read_event()
                if event_dict:
                    await self._event_queue.put(event_dict)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"خطا در خواندن رویداد: {e}")
                break

    async def _read_event(self) -> Optional[Dict[str, Any]]:
        """
        خواندن یک رویداد از AMI
        """
        if not self.reader:
            return None
        event_dict = {}
        while True:
            try:
                line = await asyncio.wait_for(
                    self.reader.readline(), timeout=1.0
                )
                if not line:
                    break
                line_str = line.decode().strip()
                if not line_str:
                    if event_dict:
                        return event_dict
                    continue

                # پارس کردن خط
                if ":" in line_str:
                    key, value = line_str.split(":", 1)
                    event_dict[key.strip()] = value.strip()
            except asyncio.TimeoutError:
                if event_dict:
                    return event_dict
                return None
            except Exception as e:
                logger.error(f"خطا در خواندن رویداد: {e}")
                return None

    async def get_event(self) -> Optional[Dict[str, Any]]:
        """
        دریافت رویداد از صف
        """
        try:
            return await asyncio.wait_for(
                self._event_queue.get(), timeout=1.0
            )
        except asyncio.TimeoutError:
            return None

    async def send_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        ارسال فرمان به AMI
        """
        if not self._connected or not self.writer:
            logger.error("کلاینت AMI متصل نیست")
            return {}

        # ساخت فرمان
        command_lines = []
        for key, value in action.items():
            command_lines.append(f"{key}: {value}")
        command_lines.append("")  # خط خالی برای پایان
        command = "\r\n".join(command_lines)

        try:
            self.writer.write(command.encode())
            await self.writer.drain()

            # خواندن پاسخ
            response = await self._read_response()
            response_dict = {}
            for line in response.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    response_dict[key.strip()] = value.strip()

            return response_dict
        except Exception as e:
            logger.error(f"خطا در ارسال فرمان: {e}")
            return {}

    async def disconnect(self):
        """
        قطع اتصال از AMI
        """
        if self._connected:
            try:
                # ارسال Logoff
                logoff_command = "Action: Logoff\r\n\r\n"
                if self.writer:
                    self.writer.write(logoff_command.encode())
                    await self.writer.drain()
            except Exception as e:
                logger.error(f"خطا در Logoff: {e}")

        self._connected = False
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        logger.info("اتصال AMI قطع شد")

    async def originate_call(
        self,
        caller_number: str,
        callee_number: str,
        context: str = "from-internal",
        timeout: int = 30,
        channel_id: Optional[str] = None,
        variables: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        ارسال فرمان Originate برای ایجاد تماس

        Args:
            caller_number: شماره تماس‌گیرنده
            callee_number: شماره تماس‌گیرنده
            context: Context استریسک
            timeout: زمان انتظار (ثانیه)
            channel_id: شناسه کانال (اختیاری)
            variables: متغیرهای اضافی برای تنظیم در کانال

        Returns:
            پاسخ از AMI یا None در صورت خطا
        """
        if not self._connected:
            logger.error("کلاینت AMI متصل نیست")
            return None

        try:
            # ساخت فرمان Originate
            channel = f"Local/{callee_number}@{context}"

            # ساخت متغیرها
            vars_dict = variables or {}
            vars_dict["CALLERID(num)"] = caller_number
            vars_dict["CALLERID(name)"] = caller_number

            # ساخت فرمان
            command = {
                "Action": "Originate",
                "Channel": channel,
                "Context": context,
                "Exten": callee_number,
                "Priority": "1",
                "Timeout": str(timeout * 1000),
                "CallerID": caller_number,
                "Async": "true",
            }

            # افزودن متغیرها
            if vars_dict:
                var_string = "|".join(
                    [f"{k}={v}" for k, v in vars_dict.items()]
                )
                command["Variable"] = var_string

            # ارسال فرمان
            response = await self.send_action(command)
            logger.info(f"فرمان Originate ارسال شد: {response}")
            return response

        except Exception as e:
            logger.error(f"خطا در ارسال فرمان Originate: {e}")
            return None

    def is_connected(self) -> bool:
        """
        بررسی وضعیت اتصال
        """
        return self._connected
