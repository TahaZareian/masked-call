import os
import requests
from typing import Optional, Dict, Any
import base64


class ARIManager:
    """کلاس برای مدیریت اتصال به Asterisk از طریق ARI (Asterisk REST Interface)"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        مقداردهی اولیه ARI Manager

        Args:
            host: آدرس سرور Asterisk
            port: پورت ARI (پیش‌فرض: 8088)
            username: نام کاربری ARI
            password: رمز عبور ARI
        """
        self.host = host or os.getenv('ASTERISK_ARI_HOST') or 'localhost'
        self.port = port or int(os.getenv('ASTERISK_ARI_PORT', '8088'))
        self.username = username or os.getenv('ASTERISK_ARI_USERNAME') or 'asterisk'
        self.password = password or os.getenv('ASTERISK_ARI_PASSWORD') or 'asterisk'
        
        self.base_url = f"http://{self.host}:{self.port}/ari"
        self.auth = (self.username, self.password)

    def create_bridge(
        self,
        bridge_type: str = "mixing",
        bridge_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[Dict]]:
        """
        ایجاد bridge جدید

        Args:
            bridge_type: نوع bridge (mixing, holding, dtmf_events, proxy_media)
            bridge_id: شناسه منحصر به فرد bridge (اختیاری)
            name: نام bridge (اختیاری)

        Returns:
            tuple (success, bridge_id, bridge_data)
        """
        try:
            url = f"{self.base_url}/bridges"
            params = {"type": bridge_type}
            
            if bridge_id:
                url = f"{self.base_url}/bridges/{bridge_id}"
                response = requests.post(url, params=params, auth=self.auth)
            else:
                if name:
                    params["name"] = name
                response = requests.post(url, params=params, auth=self.auth)

            if response.status_code in [200, 201]:
                bridge_data = response.json()
                bridge_id = bridge_data.get('id')
                return True, bridge_id, bridge_data
            else:
                error_msg = f"خطا در ایجاد bridge: {response.status_code} - {response.text}"
                return False, None, {"error": error_msg}
        except Exception as e:
            return False, None, {"error": str(e)}

    def add_channel_to_bridge(
        self,
        bridge_id: str,
        channel_id: str,
        role: Optional[str] = None,
        mute: bool = False
    ) -> tuple[bool, str]:
        """
        اضافه کردن channel به bridge

        Args:
            bridge_id: شناسه bridge
            channel_id: شناسه channel
            role: نقش channel در bridge (اختیاری)
            mute: آیا channel باید mute باشد

        Returns:
            tuple (success, message)
        """
        try:
            url = f"{self.base_url}/bridges/{bridge_id}/addChannel"
            params = {"channel": channel_id}
            
            if role:
                params["role"] = role
            if mute:
                params["mute"] = "true"

            response = requests.post(url, params=params, auth=self.auth)

            if response.status_code in [200, 204]:
                return True, "Channel با موفقیت به bridge اضافه شد"
            else:
                error_msg = f"خطا: {response.status_code} - {response.text}"
                return False, error_msg
        except Exception as e:
            return False, f"خطا: {str(e)}"

    def remove_channel_from_bridge(
        self,
        bridge_id: str,
        channel_id: str
    ) -> tuple[bool, str]:
        """
        حذف channel از bridge

        Args:
            bridge_id: شناسه bridge
            channel_id: شناسه channel

        Returns:
            tuple (success, message)
        """
        try:
            url = f"{self.base_url}/bridges/{bridge_id}/removeChannel"
            params = {"channel": channel_id}

            response = requests.post(url, params=params, auth=self.auth)

            if response.status_code in [200, 204]:
                return True, "Channel با موفقیت از bridge حذف شد"
            else:
                error_msg = f"خطا: {response.status_code} - {response.text}"
                return False, error_msg
        except Exception as e:
            return False, f"خطا: {str(e)}"

    def get_bridge(self, bridge_id: str) -> tuple[bool, Optional[Dict]]:
        """
        دریافت اطلاعات bridge

        Args:
            bridge_id: شناسه bridge

        Returns:
            tuple (success, bridge_data)
        """
        try:
            url = f"{self.base_url}/bridges/{bridge_id}"
            response = requests.get(url, auth=self.auth)

            if response.status_code == 200:
                return True, response.json()
            else:
                return False, None
        except Exception as e:
            return False, None

    def delete_bridge(self, bridge_id: str) -> tuple[bool, str]:
        """
        حذف bridge

        Args:
            bridge_id: شناسه bridge

        Returns:
            tuple (success, message)
        """
        try:
            url = f"{self.base_url}/bridges/{bridge_id}"
            response = requests.delete(url, auth=self.auth)

            if response.status_code in [200, 204]:
                return True, "Bridge با موفقیت حذف شد"
            else:
                error_msg = f"خطا: {response.status_code} - {response.text}"
                return False, error_msg
        except Exception as e:
            return False, f"خطا: {str(e)}"

    def list_bridges(self) -> tuple[bool, list]:
        """
        دریافت لیست bridges فعال

        Returns:
            tuple (success, bridges_list)
        """
        try:
            url = f"{self.base_url}/bridges"
            response = requests.get(url, auth=self.auth)

            if response.status_code == 200:
                return True, response.json()
            else:
                return False, []
        except Exception as e:
            return False, []

    def bridge_two_channels(
        self,
        channel1_id: str,
        channel2_id: str,
        bridge_type: str = "mixing"
    ) -> tuple[bool, Optional[str], str]:
        """
        Bridge کردن دو channel با استفاده از ARI

        Args:
            channel1_id: شناسه channel اول
            channel2_id: شناسه channel دوم
            bridge_type: نوع bridge

        Returns:
            tuple (success, bridge_id, message)
        """
        # ایجاد bridge
        success, bridge_id, bridge_data = self.create_bridge(bridge_type=bridge_type)
        if not success:
            return False, None, bridge_data.get('error', 'خطا در ایجاد bridge')

        # اضافه کردن channel اول به bridge
        success1, msg1 = self.add_channel_to_bridge(bridge_id, channel1_id)
        if not success1:
            self.delete_bridge(bridge_id)  # پاک کردن bridge در صورت خطا
            return False, None, f"خطا در اضافه کردن channel اول: {msg1}"

        # اضافه کردن channel دوم به bridge
        success2, msg2 = self.add_channel_to_bridge(bridge_id, channel2_id)
        if not success2:
            self.remove_channel_from_bridge(bridge_id, channel1_id)
            self.delete_bridge(bridge_id)
            return False, None, f"خطا در اضافه کردن channel دوم: {msg2}"

        return True, bridge_id, "Bridge با موفقیت ایجاد شد"

