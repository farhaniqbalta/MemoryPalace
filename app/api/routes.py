from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.ingestion import ingest_text, normalize_source
from app.core.rag import answer_question
from app.core.search import EmbeddingModelMismatch, search_chunks
from app.db import get_db
from app.schemas import AskRequest, AskResponse, IngestRequest, IngestResponse, SearchRequest, SearchResult

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest, db: Session = Depends(get_db)):
    try:
        source = normalize_source(payload.source)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    rows = ingest_text(db, source, payload.content, payload.metadata)
    return IngestResponse(source=source, chunks_created=len(rows), chunk_ids=[row.id for row in rows])


@router.post("/search", response_model=list[SearchResult])
def search(payload: SearchRequest, db: Session = Depends(get_db)):
    try:
        results = search_chunks(db, payload.query, payload.top_k)
    except EmbeddingModelMismatch as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return [SearchResult(chunk=chunk, score=score) for chunk, score in results]


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    try:
        answer, cited, retrieved = answer_question(db, payload.question, payload.top_k)
    except EmbeddingModelMismatch as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return AskResponse(answer=answer, sources=list(dict.fromkeys(c.source for c in cited)),
                       cited_chunks=cited, retrieved_chunks=retrieved)
