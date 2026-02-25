from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from ..config.settings import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    from ..models.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
