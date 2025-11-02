"""
مدل‌های دیتابیس برای مدیریت Session های تماس
بر اساس بخش ۱: CallSessions Table
"""
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class CallStatus(enum.Enum):
    """وضعیت‌های مختلف تماس"""
    INITIATED = "initiated"  # تماس ایجاد شده
    RINGING = "ringing"  # در حال زنگ خوردن
    ANSWERED = "answered"  # تماس پاسخ داده شده
    MASKED = "masked"  # تماس مخفی شده
    COMPLETED = "completed"  # تماس تمام شده
    FAILED = "failed"  # تماس ناموفق


class CallSessions(Base):
    """
    جدول اصلی برای نگهداری اطلاعات Session های تماس
    """
    __tablename__ = "call_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # اطلاعات تماس اصلی
    caller_number = Column(String(20), nullable=False)
    callee_number = Column(String(20), nullable=False)
    
    # اطلاعات تماس مخفی
    masked_caller_number = Column(String(20), nullable=True)
    
    # وضعیت تماس
    status = Column(Enum(CallStatus), default=CallStatus.INITIATED, nullable=False)
    
    # شناسه‌های استریسک
    channel_id = Column(String(100), nullable=True)
    unique_id = Column(String(50), nullable=True, index=True)
    
    # زمان‌بندی
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    started_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    masked_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # اطلاعات اضافی
    error_message = Column(Text, nullable=True)
    metadata = Column(Text, nullable=True)  # JSON string برای داده‌های اضافی

