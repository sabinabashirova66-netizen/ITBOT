from datetime import datetime

from sqlalchemy import BigInteger, String, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    study_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recommended_course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manager_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
