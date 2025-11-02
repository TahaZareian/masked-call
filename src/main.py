"""
نقطه شروع اپلیکیشن FastAPI
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging

from database.db import init_db, AsyncSessionLocal
from api.routes import router
from ami_client.client import AMIClient
from ami_client.event_handler import AMIEventHandler

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def start_ami_listener():
    """
    شروع گوش دادن به رویدادهای AMI
    """
    ami_client = AMIClient()

    while True:
        try:
            connected = await ami_client.connect()
            if not connected:
                logger.warning(
                    "اتصال به AMI برقرار نشد. تلاش مجدد در 5 ثانیه..."
                )
                await asyncio.sleep(5)
                continue

            logger.info("شروع گوش دادن به رویدادهای AMI...")

            # دریافت رویدادها
            while ami_client.is_connected():
                event = await ami_client.get_event()
                if event:
                    # دریافت session دیتابیس برای هر رویداد
                    async with AsyncSessionLocal() as db_session:
                        event_handler = AMIEventHandler(db_session)
                        await event_handler.handle_event(event)

        except Exception as e:
            logger.error(
                f"خطا در گوش دادن به AMI: {e}", exc_info=True
            )
            await ami_client.disconnect()
            await asyncio.sleep(5)  # انتظار قبل از تلاش مجدد


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    مدیریت چرخه حیات اپلیکیشن
    """
    # راه‌اندازی
    logger.info("شروع راه‌اندازی اپلیکیشن...")
    
    # ایجاد جداول دیتابیس
    await init_db()
    logger.info("جداول دیتابیس آماده شد")
    
    # شروع task گوش دادن به AMI
    ami_task = asyncio.create_task(start_ami_listener())
    logger.info("گوش دادن به رویدادهای AMI شروع شد")
    
    yield
    
    # خاموش کردن
    logger.info("در حال خاموش کردن اپلیکیشن...")
    ami_task.cancel()
    try:
        await ami_task
    except asyncio.CancelledError:
        pass
    logger.info("اپلیکیشن خاموش شد")


# ایجاد اپلیکیشن FastAPI
app = FastAPI(
    title="Masked Call API",
    description="API برای مدیریت تماس‌های مخفی با Asterisk",
    version="1.0.0",
    lifespan=lifespan
)

# افزودن router
app.include_router(router, prefix="/api/v1", tags=["calls"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Masked Call API is running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

