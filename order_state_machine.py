from enum import Enum
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List


class OrderState(Enum):
    """حالت‌های سفارش تماس (مشابه تراکنش در درگاه پرداخت)"""
    CREATED = "created"           # سفارش ایجاد شده
    PENDING = "pending"           # در انتظار پردازش
    PROCESSING = "processing"      # در حال پردازش
    INITIATED = "initiated"       # تماس آغاز شده
    VERIFIED = "verified"         # تماس تایید شده
    COMPLETED = "completed"       # تماس کامل شده
    FAILED = "failed"             # ناموفق
    CANCELLED = "cancelled"       # لغو شده
    REFUNDED = "refunded"         # بازگشت (در صورت نیاز)


class OrderStateMachine:
    """ماشین حالت برای مدیریت سفارش تماس (مشابه Order در درگاه پرداخت)"""

    VALID_TRANSITIONS = {
        OrderState.CREATED: [
            OrderState.PENDING,
            OrderState.FAILED,
            OrderState.CANCELLED
        ],
        OrderState.PENDING: [
            OrderState.PROCESSING,
            OrderState.FAILED,
            OrderState.CANCELLED
        ],
        OrderState.PROCESSING: [
            OrderState.INITIATED,
            OrderState.FAILED,
            OrderState.CANCELLED
        ],
        OrderState.INITIATED: [
            OrderState.VERIFIED,
            OrderState.COMPLETED,
            OrderState.FAILED,
            OrderState.CANCELLED
        ],
        OrderState.VERIFIED: [
            OrderState.COMPLETED,
            OrderState.FAILED,
            OrderState.CANCELLED
        ],
        OrderState.COMPLETED: [],
        OrderState.FAILED: [],
        OrderState.CANCELLED: [],
        OrderState.REFUNDED: [],
    }

    FINAL_STATES = {
        OrderState.COMPLETED,
        OrderState.FAILED,
        OrderState.CANCELLED,
        OrderState.REFUNDED,
    }

    def __init__(
        self,
        initial_state: OrderState = OrderState.CREATED,
        order_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        مقداردهی اولیه ماشین حالت سفارش

        Args:
            initial_state: حالت اولیه (پیش‌فرض: CREATED)
            order_id: شناسه سفارش (اگر None باشد، جدید ایجاد می‌شود)
            metadata: اطلاعات اضافی (شماره‌ها، user_token، etc.)
        """
        self.current_state = initial_state
        self.state_history = [initial_state]
        self.order_id = order_id or str(uuid.uuid4())
        self.metadata = metadata or {}
        self.state_timestamps: List[Dict[str, Any]] = []
        self.error_log: List[Dict[str, Any]] = []
        self.call_id: Optional[str] = None  # شناسه تماس مرتبط
        
        # ثبت زمان ایجاد
        self.state_timestamps.append({
            'state': initial_state.value,
            'timestamp': datetime.now().isoformat(),
            'metadata': {}
        })

    def transition_to(
        self,
        new_state: OrderState,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        انتقال به حالت جدید با ثبت timestamp و metadata

        Args:
            new_state: حالت جدید برای انتقال
            metadata: اطلاعات اضافی
            error: پیام خطا (در صورت وجود)

        Returns:
            True اگر انتقال موفق باشد
        """
        if self.is_final_state():
            return False

        if new_state not in self.VALID_TRANSITIONS[self.current_state]:
            return False

        old_state = self.current_state
        self.current_state = new_state
        self.state_history.append(new_state)
        
        # ثبت timestamp و metadata
        state_entry = {
            'state': new_state.value,
            'previous_state': old_state.value,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        if error:
            state_entry['error'] = error
            self.error_log.append({
                'state': new_state.value,
                'timestamp': datetime.now().isoformat(),
                'error': error,
                'metadata': metadata or {}
            })
        
        self.state_timestamps.append(state_entry)
        
        # به‌روزرسانی metadata کلی
        if metadata:
            self.metadata.update(metadata)
        
        return True

    def can_transition_to(self, new_state: OrderState) -> bool:
        """بررسی امکان انتقال به حالت جدید"""
        if self.is_final_state():
            return False
        return new_state in self.VALID_TRANSITIONS[self.current_state]

    def is_final_state(self) -> bool:
        """بررسی اینکه آیا در حالت نهایی هستیم"""
        return self.current_state in self.FINAL_STATES

    def get_current_state(self) -> OrderState:
        """دریافت حالت فعلی"""
        return self.current_state

    def get_state_history(self) -> List[OrderState]:
        """دریافت تاریخچه حالت‌ها"""
        return self.state_history.copy()

    def get_order_id(self) -> str:
        """دریافت شناسه سفارش"""
        return self.order_id

    def get_state_timestamps(self) -> List[Dict[str, Any]]:
        """دریافت تاریخچه timestamp های state"""
        return self.state_timestamps.copy()

    def get_error_log(self) -> List[Dict[str, Any]]:
        """دریافت لاگ خطاها"""
        return self.error_log.copy()

    def get_metadata(self) -> Dict[str, Any]:
        """دریافت metadata کامل"""
        return self.metadata.copy()

    def update_metadata(self, **kwargs):
        """به‌روزرسانی metadata"""
        self.metadata.update(kwargs)

    def set_call_id(self, call_id: str):
        """تنظیم شناسه تماس مرتبط"""
        self.call_id = call_id
        self.metadata['call_id'] = call_id

    def get_call_id(self) -> Optional[str]:
        """دریافت شناسه تماس مرتبط"""
        return self.call_id

    def to_dict(self) -> Dict[str, Any]:
        """تبدیل به دیکشنری برای ذخیره در دیتابیس"""
        return {
            'order_id': self.order_id,
            'current_state': self.current_state.value,
            'state_history': [state.value for state in self.state_history],
            'state_timestamps': self.state_timestamps,
            'error_log': self.error_log,
            'metadata': self.metadata,
            'call_id': self.call_id,
            'is_final': self.is_final_state(),
            'created_at': self.state_timestamps[0]['timestamp'] if self.state_timestamps else None,
            'updated_at': self.state_timestamps[-1]['timestamp'] if self.state_timestamps else None
        }

