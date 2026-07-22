from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from geekbaku.config.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base para los modelos ORM de infraestructura.

    No confundir con las entidades de dominio en `geekbaku.domain.*`.
    """


settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug)

async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
