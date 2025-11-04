from enum import Enum


class CallState(Enum):
    """حالت‌های ماشین حالت تماس"""
    PENDING = "pending"
    CALLING_A = "calling_a"
    CONNECTED_A = "connected_a"
    CALLING_B = "calling_b"
    BRIDGED = "bridged"
    COMPLETED = "completed"
    FAILED_A = "failed_a"
    FAILED_B = "failed_b"
    FAILED_SYSTEM = "failed_system"


class CallSessionStateMachine:
    """ماشین حالت برای مدیریت جلسه تماس مسدود"""

    # تعریف انتقال‌های مجاز
    VALID_TRANSITIONS = {
        CallState.PENDING: [
            CallState.CALLING_A,
            CallState.FAILED_SYSTEM
        ],
        CallState.CALLING_A: [
            CallState.CONNECTED_A,
            CallState.FAILED_A,
            CallState.FAILED_SYSTEM
        ],
        CallState.CONNECTED_A: [
            CallState.CALLING_B,
            CallState.FAILED_SYSTEM
        ],
        CallState.CALLING_B: [
            CallState.BRIDGED,
            CallState.FAILED_B,
            CallState.FAILED_SYSTEM
        ],
        CallState.BRIDGED: [
            CallState.COMPLETED,
            CallState.FAILED_SYSTEM
        ],
        # حالت‌های نهایی نمی‌توانند تغییر کنند
        CallState.COMPLETED: [],
        CallState.FAILED_A: [],
        CallState.FAILED_B: [],
        CallState.FAILED_SYSTEM: [],
    }

    # حالت‌های نهایی
    FINAL_STATES = {
        CallState.COMPLETED,
        CallState.FAILED_A,
        CallState.FAILED_B,
        CallState.FAILED_SYSTEM,
    }

    def __init__(self, initial_state: CallState = CallState.PENDING):
        """
        مقداردهی اولیه ماشین حالت

        Args:
            initial_state: حالت اولیه (پیش‌فرض: PENDING)
        """
        self.current_state = initial_state
        self.state_history = [initial_state]

    def transition_to(self, new_state: CallState) -> bool:
        """
        انتقال به حالت جدید

        Args:
            new_state: حالت جدید برای انتقال

        Returns:
            True اگر انتقال موفق باشد، False در غیر این صورت
        """
        if self.is_final_state():
            return False

        if new_state not in self.VALID_TRANSITIONS[self.current_state]:
            return False

        self.current_state = new_state
        self.state_history.append(new_state)
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

    def reset(self, initial_state: CallState = CallState.PENDING):
        """
        بازنشانی ماشین حالت به حالت اولیه

        Args:
            initial_state: حالت اولیه جدید (پیش‌فرض: PENDING)
        """
        self.current_state = initial_state
        self.state_history = [initial_state]

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
