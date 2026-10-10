from typing import Optional

import json
import uuid

from sqlalchemy.orm import Session

from app.core.embeddings import embed_text
from app.models import KnowledgeCard, RawSource


def _embedding_text(type_: str, title: str, content: dict) -> str:
    return f"{type_}: {title}\n{json.dumps(content, sort_keys=True)}"


def create_raw_source(db: Session, source_type: str, content: str) -> RawSource:
    raw_source = RawSource(source_type=source_type, content=content)
    db.add(raw_source)
    db.commit()
    db.refresh(raw_source)
    return raw_source


def create_card(
    db: Session,
    raw_source: RawSource,
    type_: str,
    title: str,
    content: dict,
    tags: list[str],
) -> KnowledgeCard:
    embedding = embed_text(_embedding_text(type_, title, content))
    card = KnowledgeCard(
        raw_source_id=raw_source.id,
        type=type_,
        title=title,
        content=content,
        tags=tags,
        embedding=embedding,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def get_card(db: Session, card_id: uuid.UUID) -> Optional[KnowledgeCard]:
    return db.get(KnowledgeCard, card_id)


def list_cards(
    db: Session,
    type_: Optional[str] = None,
    tag: Optional[str] = None,
    active: Optional[bool] = True,
) -> list[KnowledgeCard]:
    query = db.query(KnowledgeCard)
    if type_ is not None:
        query = query.filter(KnowledgeCard.type == type_)
    if tag is not None:
        query = query.filter(KnowledgeCard.tags.any(tag))
    if active is not None:
        query = query.filter(KnowledgeCard.active == active)
    return query.order_by(KnowledgeCard.created_at.desc()).all()


def supersede_card(
    db: Session,
    old_card: KnowledgeCard,
    type_: str,
    title: str,
    content: dict,
    tags: list[str],
) -> KnowledgeCard:
    """Create a replacement card and retire the old one, atomically.

    Cards are append-only: nothing is edited or deleted, so a wrong/outdated
    card is always recoverable via its `supersedes` chain.
    """
    embedding = embed_text(_embedding_text(type_, title, content))
    new_card = KnowledgeCard(
        raw_source_id=old_card.raw_source_id,
        type=type_,
        title=title,
        content=content,
        tags=tags,
        embedding=embedding,
        supersedes=old_card.id,
    )
    old_card.active = False
    db.add(new_card)
    db.commit()
    db.refresh(new_card)
    return new_card
