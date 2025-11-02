"""
مدیریت API ورودی (درخواست جدید تماس)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
import uuid

from database.db import get_db
from database.models import CallSessions, CallStatus
from ami_client.client import AMIClient

router = APIRouter()


class CreateCallRequest(BaseModel):
    """درخواست ایجاد تماس جدید"""
    caller_number: str
    callee_number: str
    masked_caller_number: Optional[str] = None
    metadata: Optional[dict] = None


class CreateCallResponse(BaseModel):
    """پاسخ ایجاد تماس"""
    session_id: str
    status: str
    message: str


@router.post(
    "/call/create", response_model=CreateCallResponse
)
async def create_call(
    request: CreateCallRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    ایجاد تماس جدید
    """
    try:
        # ایجاد session جدید
        session_id = str(uuid.uuid4())
        new_session = CallSessions(
            session_id=session_id,
            caller_number=request.caller_number,
            callee_number=request.callee_number,
            masked_caller_number=request.masked_caller_number,
            status=CallStatus.INITIATED,
            metadata=str(request.metadata) if request.metadata else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        
        # ارسال فرمان Originate به AMI
        ami_client = AMIClient()
        await ami_client.connect()
        
        if not ami_client.is_connected():
            raise HTTPException(
                status_code=503,
                detail="امکان اتصال به AMI وجود ندارد"
            )
        
        # ارسال فرمان Originate
        originate_response = await ami_client.originate_call(
            caller_number=request.masked_caller_number or request.caller_number,
            callee_number=request.callee_number,
            channel_id=new_session.channel_id
        )
        
        if not originate_response:
            new_session.status = CallStatus.FAILED
            new_session.error_message = "خطا در ارسال فرمان Originate"
            await db.commit()
            raise HTTPException(
                status_code=500,
                detail="خطا در ایجاد تماس"
            )
        
        await ami_client.disconnect()
        
        return CreateCallResponse(
            session_id=session_id,
            status=new_session.status.value,
            message="تماس با موفقیت ایجاد شد"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"خطای داخلی: {str(e)}"
        )


@router.get("/call/{session_id}")
async def get_call_status(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت وضعیت تماس
    """
    from sqlalchemy import select
    
    result = await db.execute(
        select(CallSessions).where(CallSessions.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session یافت نشد"
        )

    created_at = (
        session.created_at.isoformat()
        if session.created_at else None
    )
    started_at = (
        session.started_at.isoformat()
        if session.started_at else None
    )
    answered_at = (
        session.answered_at.isoformat()
        if session.answered_at else None
    )
    masked_at = (
        session.masked_at.isoformat()
        if session.masked_at else None
    )
    completed_at = (
        session.completed_at.isoformat()
        if session.completed_at else None
    )

    return {
        "session_id": session.session_id,
        "caller_number": session.caller_number,
        "callee_number": session.callee_number,
        "masked_caller_number": session.masked_caller_number,
        "status": session.status.value,
        "created_at": created_at,
        "started_at": started_at,
        "answered_at": answered_at,
        "masked_at": masked_at,
        "completed_at": completed_at,
        "error_message": session.error_message,
    }

