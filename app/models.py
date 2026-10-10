import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RawSource(Base):
    __tablename__ = "raw_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    cards: Mapped[list["KnowledgeCard"]] = relationship(back_populates="raw_source")


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    raw_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_sources.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supersedes: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_cards.id"), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    raw_source: Mapped["RawSource"] = relationship(back_populates="cards")
