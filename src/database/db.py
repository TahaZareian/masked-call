"""
کانفیگ و اتصال به دیتابیس PostgreSQL
"""
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
import os
from typing import AsyncGenerator

# دریافت تنظیمات از متغیرهای محیطی
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "masked_call_db")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_PORT = os.getenv("DB_PORT", "5432")

# ساخت URL اتصال async برای PostgreSQL
DATABASE_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@"
    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ایجاد موتور دیتابیس async
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # برای debug - در production روی False بگذارید
    future=True,
    pool_pre_ping=True,  # بررسی اتصال قبل از استفاده
)

# ایجاد session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency برای FastAPI برای دریافت session دیتابیس
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    ایجاد جداول در دیتابیس (اگر وجود نداشته باشند)
    """
    from database.models import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

