import os
from typing import Dict, Optional


class TrunkConfig:
    """کلاس برای مدیریت پیکربندی trunk Asterisk"""

    @staticmethod
    def from_environment(trunk_name: str = "default") -> Dict[str, str]:
        """
        خواندن پیکربندی trunk از environment variables

        Args:
            trunk_name: نام trunk (برای prefix کردن متغیرها)

        Returns:
            دیکشنری پیکربندی trunk
        """
        if trunk_name != "default":
            prefix = f"TRUNK_{trunk_name.upper()}_"
        else:
            prefix = "TRUNK_"

        config = {}
        # خواندن تمام پارامترهای trunk از environment
        env_vars = {
            'type': os.getenv(f'{prefix}TYPE', 'friend'),
            'send_rpid': os.getenv(f'{prefix}SEND_RPID', 'yes'),
            'send_early_media': os.getenv(f'{prefix}SEND_EARLY_MEDIA', 'yes'),
            'qualify': os.getenv(f'{prefix}QUALIFY', 'yes'),
            'port': os.getenv(f'{prefix}PORT', '5060'),
            'nat': os.getenv(
                f'{prefix}NAT',
                'force_rport,comedia'
            ),
            'insecure': os.getenv(f'{prefix}INSECURE', 'port,invite'),
            'host': os.getenv(f'{prefix}HOST', ''),
            'fromuser': os.getenv(f'{prefix}FROMUSER', ''),
            'disallow': os.getenv(f'{prefix}DISALLOW', 'all'),
            'context': os.getenv(f'{prefix}CONTEXT', 'from-trunk'),
            'allow': os.getenv(f'{prefix}ALLOW', 'ulaw,alaw'),
            'username': os.getenv(f'{prefix}USERNAME', ''),
            'secret': os.getenv(f'{prefix}SECRET', ''),
        }

        # فقط متغیرهای تنظیم شده را اضافه می‌کنیم
        for key, value in env_vars.items():
            if value:
                config[key] = value

        return config

    @staticmethod
    def from_dict(data: Dict[str, str]) -> Dict[str, str]:
        """
        ساخت پیکربندی trunk از دیکشنری

        Args:
            data: دیکشنری پیکربندی

        Returns:
            دیکشنری پیکربندی trunk
        """
        return data.copy()

    @staticmethod
    def to_asterisk_config(trunk_name: str, config: Dict[str, str]) -> str:
        """
        تبدیل پیکربندی به فرمت فایل پیکربندی Asterisk

        Args:
            trunk_name: نام trunk
            config: دیکشنری پیکربندی

        Returns:
            رشته پیکربندی به فرمت Asterisk
        """
        lines = [f"[{trunk_name}]"]
        lines.append(f"type={config.get('type', 'friend')}")
        lines.append(f"send_rpid={config.get('send_rpid', 'yes')}")
        lines.append(
            f"send_early_media={config.get('send_early_media', 'yes')}"
        )
        lines.append(f"qualify={config.get('qualify', 'yes')}")
        lines.append(f"port={config.get('port', '5060')}")
        lines.append(f"nat={config.get('nat', 'force_rport,comedia')}")
        lines.append(
            f"insecure={config.get('insecure', 'port,invite')}"
        )

        if config.get('host'):
            lines.append(f"host={config['host']}")
        if config.get('fromuser'):
            lines.append(f"fromuser={config['fromuser']}")
        if config.get('username'):
            lines.append(f"username={config['username']}")
        if config.get('secret'):
            lines.append(f"secret={config['secret']}")

        lines.append(f"disallow={config.get('disallow', 'all')}")
        lines.append(f"context={config.get('context', 'from-trunk')}")
        lines.append(f"allow={config.get('allow', 'ulaw,alaw')}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def validate(config: Dict[str, str]) -> tuple[bool, Optional[str]]:
        """
        اعتبارسنجی پیکربندی trunk

        Args:
            config: دیکشنری پیکربندی

        Returns:
            tuple (is_valid, error_message)
        """
        required_fields = ['host']
        for field in required_fields:
            if not config.get(field):
                return False, f"فیلد {field} الزامی است"

        return True, None
