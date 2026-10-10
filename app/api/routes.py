from typing import Optional

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import cards as cards_core
from app.core.extraction import extract_card
from app.core.rag import answer_question
from app.core.search import search_cards
from app.db import get_db
from app.schemas import (
    AskRequest,
    AskResponse,
    CardResponse,
    IngestRequest,
    SearchRequest,
    SearchResult,
    SupersedeRequest,
)

router = APIRouter()


@router.post("/ingest", response_model=CardResponse)
def ingest(payload: IngestRequest, db: Session = Depends(get_db)) -> CardResponse:
    raw_source = cards_core.create_raw_source(db, payload.source_type, payload.content)
    extracted = extract_card(payload.content)
    card = cards_core.create_card(
        db,
        raw_source,
        type_=extracted["type"],
        title=extracted["title"],
        content=extracted["content"],
        tags=extracted.get("tags", []),
    )
    return card


@router.get("/cards/{card_id}", response_model=CardResponse)
def get_card(card_id: uuid.UUID, db: Session = Depends(get_db)) -> CardResponse:
    card = cards_core.get_card(db, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("/cards", response_model=list[CardResponse])
def list_cards(
    type: Optional[str] = None,
    tag: Optional[str] = None,
    active: Optional[bool] = True,
    db: Session = Depends(get_db),
) -> list[CardResponse]:
    return cards_core.list_cards(db, type_=type, tag=tag, active=active)


@router.post("/cards/{card_id}/supersede", response_model=CardResponse)
def supersede_card(
    card_id: uuid.UUID, payload: SupersedeRequest, db: Session = Depends(get_db)
) -> CardResponse:
    old_card = cards_core.get_card(db, card_id)
    if old_card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return cards_core.supersede_card(
        db,
        old_card,
        type_=payload.type,
        title=payload.title,
        content=payload.content,
        tags=payload.tags,
    )


@router.post("/search", response_model=list[SearchResult])
def search(payload: SearchRequest, db: Session = Depends(get_db)) -> list[SearchResult]:
    results = search_cards(db, payload.query, top_k=payload.top_k)
    return [SearchResult(card=card, score=score) for card, score in results]


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    answer, cards = answer_question(db, payload.question, top_k=payload.top_k)
    return AskResponse(answer=answer, cited_cards=cards)
