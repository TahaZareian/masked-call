"""
منطق پردازش رویدادهای AMI و بروزرسانی DB (ماشین حالت)
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import CallSessions, CallStatus

logger = logging.getLogger(__name__)


class AMIEventHandler:
    """
    مدیریت ماشین حالت تماس بر اساس رویدادهای AMI
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.event_handlers = {
            "OriginateResponse": self._handle_originate_response,
            "Newchannel": self._handle_new_channel,
            "Newstate": self._handle_new_state,
            "NewCallerid": self._handle_new_callerid,
            "Ringing": self._handle_ringing,
            "Answer": self._handle_answer,
            "Hangup": self._handle_hangup,
            "BridgeEnter": self._handle_bridge_enter,
            "BridgeLeave": self._handle_bridge_leave,
        }
    
    async def handle_event(self, event: Dict[str, Any]):
        """
        پردازش رویداد دریافت شده از AMI
        """
        event_type = event.get("Event")
        if not event_type:
            return
        
        handler = self.event_handlers.get(event_type)
        if handler:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"خطا در پردازش رویداد {event_type}: {e}", exc_info=True)
        else:
            logger.debug(f"رویداد بدون handler: {event_type}")
    
    async def _get_session_by_unique_id(self, unique_id: str) -> Optional[CallSessions]:
        """
        یافتن session بر اساس unique_id
        """
        try:
            result = await self.db_session.execute(
                select(CallSessions).where(CallSessions.unique_id == unique_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"خطا در یافتن session: {e}")
            return None
    
    async def _get_session_by_channel(self, channel: str) -> Optional[CallSessions]:
        """
        یافتن session بر اساس channel
        """
        try:
            result = await self.db_session.execute(
                select(CallSessions).where(CallSessions.channel_id == channel)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"خطا در یافتن session: {e}")
            return None
    
    async def _handle_originate_response(self, event: Dict[str, Any]):
        """
        پردازش پاسخ Originate
        """
        response = event.get("Response")

        if response == "Success":
            unique_id = event.get("Uniqueid")
            channel = event.get("Channel")

            # یافتن session بر اساس Channel
            logger.info(
                f"Originate موفق: UniqueID={unique_id}, "
                f"Channel={channel}"
            )
        else:
            logger.error(f"Originate ناموفق: {response}")
    
    async def _handle_new_channel(self, event: Dict[str, Any]):
        """
        پردازش رویداد NewChannel
        """
        unique_id = event.get("Uniqueid")
        channel = event.get("Channel")
        
        session = await self._get_session_by_unique_id(unique_id)
        if session:
            session.channel_id = channel
            session.unique_id = unique_id
            session.status = CallStatus.INITIATED
            session.started_at = datetime.utcnow()
            await self.db_session.commit()
            logger.info(f"کانال جدید ایجاد شد: {channel}")
    
    async def _handle_new_state(self, event: Dict[str, Any]):
        """
        پردازش تغییر وضعیت کانال
        """
        unique_id = event.get("Uniqueid")
        channel_state = event.get("ChannelState")
        
        session = await self._get_session_by_unique_id(unique_id)
        if not session:
            return
        
        # ChannelState: 0=Down, 1=Rsrvd, 2=OffHook, 3=Dialing,
        # 4=Ringing, 5=Up, 6=Busy
        if channel_state == "4":  # Ringing
            session.status = CallStatus.RINGING
            logger.info(f"تماس در حال زنگ خوردن: {unique_id}")
        elif channel_state == "5":  # Up (Answered)
            session.status = CallStatus.ANSWERED
            session.answered_at = datetime.utcnow()
            logger.info(f"تماس پاسخ داده شد: {unique_id}")
        
        await self.db_session.commit()
    
    async def _handle_ringing(self, event: Dict[str, Any]):
        """
        پردازش رویداد Ringing
        """
        unique_id = event.get("Uniqueid")
        session = await self._get_session_by_unique_id(unique_id)
        if session:
            session.status = CallStatus.RINGING
            await self.db_session.commit()
            logger.info(f"رویداد Ringing دریافت شد: {unique_id}")
    
    async def _handle_answer(self, event: Dict[str, Any]):
        """
        پردازش رویداد Answer
        """
        unique_id = event.get("Uniqueid")
        session = await self._get_session_by_unique_id(unique_id)
        if session:
            session.status = CallStatus.ANSWERED
            session.answered_at = datetime.utcnow()
            await self.db_session.commit()
            logger.info(f"تماس پاسخ داده شد: {unique_id}")
    
    async def _handle_hangup(self, event: Dict[str, Any]):
        """
        پردازش رویداد Hangup (پایان تماس)
        """
        unique_id = event.get("Uniqueid")
        cause = event.get("Cause", "0")
        cause_txt = event.get("Cause-txt", "Unknown")
        
        session = await self._get_session_by_unique_id(unique_id)
        if session:
            if cause == "0" or cause == "16":  # Normal clearing
                session.status = CallStatus.COMPLETED
            else:
                session.status = CallStatus.FAILED
                session.error_message = f"{cause}: {cause_txt}"
            
            session.completed_at = datetime.utcnow()
            await self.db_session.commit()
            logger.info(f"تماس تمام شد: {unique_id}, Cause={cause}")
    
    async def _handle_new_callerid(self, event: Dict[str, Any]):
        """
        پردازش تغییر CallerID (برای masking)
        """
        unique_id = event.get("Uniqueid")
        caller_id_num = event.get("CallerIDNum")

        session = await self._get_session_by_unique_id(unique_id)
        if session and caller_id_num:
            # اگر شماره مخفی تنظیم شده است
            if (session.masked_caller_number and
                    caller_id_num == session.masked_caller_number):
                session.status = CallStatus.MASKED
                session.masked_at = datetime.utcnow()
                await self.db_session.commit()
                logger.info(f"تماس مخفی شد: {unique_id}")
    
    async def _handle_bridge_enter(self, event: Dict[str, Any]):
        """
        پردازش ورود به Bridge (اتصال دو کانال)
        """
        unique_id = event.get("Uniqueid")
        bridge_unique_id = event.get("BridgeUniqueid")
        
        logger.debug(f"ورود به Bridge: {unique_id}, Bridge={bridge_unique_id}")
    
    async def _handle_bridge_leave(self, event: Dict[str, Any]):
        """
        پردازش خروج از Bridge
        """
        unique_id = event.get("Uniqueid")
        
        logger.debug(f"خروج از Bridge: {unique_id}")

