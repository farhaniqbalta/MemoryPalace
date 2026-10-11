import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class IngestRequest(BaseModel):
    source: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    source: str
    chunks_created: int
    chunk_ids: list[uuid.UUID]


class ChunkResponse(BaseModel):
    id: uuid.UUID
    source: str
    chunk_index: int
    content: str
    metadata: dict = Field(validation_alias="source_metadata")
    embedding_model: str
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Query must be nonempty")
        return value


class SearchResult(BaseModel):
    chunk: ChunkResponse
    score: float


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Question must be nonempty")
        return value


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    cited_chunks: list[ChunkResponse]
    retrieved_chunks: list[ChunkResponse]
