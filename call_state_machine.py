from enum import Enum
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
import json


class CallState(Enum):
    """حالت‌های ماشین حالت تماس"""
    PENDING = "pending"
    CALLING_A = "calling_a"
    RINGING_A = "ringing_a"
    CONNECTED_A = "connected_a"
    CALLING_B = "calling_b"
    RINGING_B = "ringing_b"
    CONNECTED_B = "connected_b"
    BRIDGED = "bridged"
    COMPLETED = "completed"
    FAILED_A = "failed_a"
    FAILED_B = "failed_b"
    FAILED_SYSTEM = "failed_system"
    CANCELLED = "cancelled"


class CallSessionStateMachine:
    """ماشین حالت برای مدیریت جلسه تماس مسدود"""

    # تعریف انتقال‌های مجاز
    VALID_TRANSITIONS = {
        CallState.PENDING: [
            CallState.CALLING_A,
            CallState.FAILED_SYSTEM,
            CallState.CANCELLED
        ],
        CallState.CALLING_A: [
            CallState.RINGING_A,
            CallState.CONNECTED_A,
            CallState.FAILED_A,
            CallState.FAILED_SYSTEM,
            CallState.CANCELLED
        ],
        CallState.RINGING_A: [
            CallState.CONNECTED_A,
            CallState.FAILED_A,
            CallState.FAILED_SYSTEM,
            CallState.CANCELLED
        ],
        CallState.CONNECTED_A: [
            CallState.CALLING_B,
            CallState.FAILED_SYSTEM,
            CallState.CANCELLED
        ],
        CallState.CALLING_B: [
            CallState.RINGING_B,
            CallState.CONNECTED_B,
            CallState.BRIDGED,
            CallState.FAILED_B,
            CallState.FAILED_SYSTEM,
            CallState.CANCELLED
        ],
        CallState.RINGING_B: [
            CallState.CONNECTED_B,
            CallState.BRIDGED,
            CallState.FAILED_B,
            CallState.FAILED_SYSTEM,
            CallState.CANCELLED
        ],
        CallState.CONNECTED_B: [
            CallState.BRIDGED,
            CallState.FAILED_SYSTEM,
            CallState.CANCELLED
        ],
        CallState.BRIDGED: [
            CallState.COMPLETED,
            CallState.FAILED_SYSTEM,
            CallState.CANCELLED
        ],
        # حالت‌های نهایی نمی‌توانند تغییر کنند
        CallState.COMPLETED: [],
        CallState.FAILED_A: [],
        CallState.FAILED_B: [],
        CallState.FAILED_SYSTEM: [],
        CallState.CANCELLED: [],
    }

    # حالت‌های نهایی
    FINAL_STATES = {
        CallState.COMPLETED,
        CallState.FAILED_A,
        CallState.FAILED_B,
        CallState.FAILED_SYSTEM,
        CallState.CANCELLED,
    }

    def __init__(
        self,
        initial_state: CallState = CallState.PENDING,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        مقداردهی اولیه ماشین حالت

        Args:
            initial_state: حالت اولیه (پیش‌فرض: PENDING)
            session_id: شناسه session (اگر None باشد، جدید ایجاد می‌شود)
            metadata: اطلاعات اضافی (شماره‌ها، channel IDs، etc.)
        """
        self.current_state = initial_state
        self.state_history = [initial_state]
        self.session_id = session_id or str(uuid.uuid4())
        self.metadata = metadata or {}
        self.state_timestamps: List[Dict[str, Any]] = []
        self.error_log: List[Dict[str, Any]] = []
        
        # ثبت زمان ایجاد
        self.state_timestamps.append({
            'state': initial_state.value,
            'timestamp': datetime.now().isoformat(),
            'metadata': {}
        })

    def transition_to(
        self,
        new_state: CallState,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        انتقال به حالت جدید با ثبت timestamp و metadata

        Args:
            new_state: حالت جدید برای انتقال
            metadata: اطلاعات اضافی (channel IDs، error messages، etc.)
            error: پیام خطا (در صورت وجود)

        Returns:
            True اگر انتقال موفق باشد، False در غیر این صورت
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

    def can_transition_to(self, new_state: CallState) -> bool:
        """
        بررسی امکان انتقال به حالت جدید

        Args:
            new_state: حالت مورد نظر

        Returns:
            True اگر انتقال امکان‌پذیر باشد
        """
        if self.is_final_state():
            return False
        return new_state in self.VALID_TRANSITIONS[self.current_state]

    def is_final_state(self) -> bool:
        """
        بررسی اینکه آیا در حالت نهایی هستیم

        Returns:
            True اگر در حالت نهایی باشیم
        """
        return self.current_state in self.FINAL_STATES

    def get_current_state(self) -> CallState:
        """
        دریافت حالت فعلی

        Returns:
            حالت فعلی
        """
        return self.current_state

    def get_state_history(self) -> list[CallState]:
        """
        دریافت تاریخچه حالت‌ها

        Returns:
            لیست تمام حالت‌هایی که از ابتدا تا کنون داشتیم
        """
        return self.state_history.copy()

    def get_session_id(self) -> str:
        """
        دریافت شناسه جلسه

        Returns:
            شناسه منحصر به فرد جلسه
        """
        return self.session_id

    def get_state_timestamps(self) -> List[Dict[str, Any]]:
        """
        دریافت تاریخچه timestamp های state

        Returns:
            لیست تمام state entries با timestamp
        """
        return self.state_timestamps.copy()

    def get_error_log(self) -> List[Dict[str, Any]]:
        """
        دریافت لاگ خطاها

        Returns:
            لیست تمام خطاها
        """
        return self.error_log.copy()

    def get_metadata(self) -> Dict[str, Any]:
        """
        دریافت metadata کامل

        Returns:
            دیکشنری metadata
        """
        return self.metadata.copy()

    def update_metadata(self, **kwargs):
        """
        به‌روزرسانی metadata

        Args:
            **kwargs: فیلدهای metadata برای به‌روزرسانی
        """
        self.metadata.update(kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """
        تبدیل به دیکشنری برای ذخیره در دیتابیس

        Returns:
            دیکشنری کامل state machine
        """
        return {
            'session_id': self.session_id,
            'current_state': self.current_state.value,
            'state_history': [state.value for state in self.state_history],
            'state_timestamps': self.state_timestamps,
            'error_log': self.error_log,
            'metadata': self.metadata,
            'is_final': self.is_final_state(),
            'created_at': self.state_timestamps[0]['timestamp'] if self.state_timestamps else None,
            'updated_at': self.state_timestamps[-1]['timestamp'] if self.state_timestamps else None
        }

    def reset(self, initial_state: CallState = CallState.PENDING):
        """
        بازنشانی ماشین حالت به حالت اولیه

        Args:
            initial_state: حالت اولیه جدید (پیش‌فرض: PENDING)
        """
        self.current_state = initial_state
        self.state_history = [initial_state]
        self.state_timestamps = [{
            'state': initial_state.value,
            'timestamp': datetime.now().isoformat(),
            'metadata': {}
        }]
        self.error_log = []
        self.metadata = {}

    def __str__(self) -> str:
        """نمایش رشته‌ای ماشین حالت"""
        return (
            f"CallSessionStateMachine("
            f"current_state={self.current_state.value}, "
            f"is_final={self.is_final_state()})"
        )

    def __repr__(self) -> str:
        """نمایش رسمی ماشین حالت"""
        return (
            f"CallSessionStateMachine("
            f"current_state={self.current_state}, "
            f"state_history={self.state_history})"
        )
