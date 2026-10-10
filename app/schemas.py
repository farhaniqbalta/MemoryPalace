from typing import Optional

import uuid
from datetime import datetime

from pydantic import BaseModel


class IngestRequest(BaseModel):
    source_type: str
    content: str


class SupersedeRequest(BaseModel):
    type: str
    title: str
    content: dict
    tags: list[str] = []


class CardResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    content: dict
    tags: list[str]
    active: bool
    supersedes: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResult(BaseModel):
    card: CardResponse
    score: float


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class AskResponse(BaseModel):
    answer: str
    cited_cards: list[CardResponse]
