import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.models import Base, Lead

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def _get_database_url() -> str:
    user = os.getenv("POSTGRES_USER", "botuser")
    password = os.getenv("POSTGRES_PASSWORD", "botpassword")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "botdb")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


async def init_db() -> None:
    global _engine, _session_factory
    _engine = create_async_engine(_get_database_url(), echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("База данных инициализирована")


async def save_lead(
    telegram_id: int,
    name: str,
    phone: str | None = None,
    email: str | None = None,
    experience: str | None = None,
    study_time: str | None = None,
    goal: str | None = None,
    recommended_course: str | None = None,
    manager_note: str | None = None,
) -> Lead:
    async with _session_factory() as session:
        lead = Lead(
            telegram_id=telegram_id,
            name=name,
            phone=phone,
            email=email,
            experience=experience,
            study_time=study_time,
            goal=goal,
            recommended_course=recommended_course,
            manager_note=manager_note,
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
        logger.info("Лид сохранён: id=%d, name=%s", lead.id, name)
        return lead
