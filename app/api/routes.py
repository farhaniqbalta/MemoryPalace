from fastapi import APIRouter, Depends, HTTPException, Request
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


@router.get('/api/sources')
def list_sources(db: Session = Depends(get_db)):
    from sqlalchemy import func, select
    from app.models import Chunk
    rows = db.execute(select(Chunk.source, func.count(Chunk.id).label('chunk_count'),
                             func.max(Chunk.created_at).label('updated_at'))
                      .group_by(Chunk.source).order_by(Chunk.source)).all()
    return [{'source': row.source, 'chunk_count': row.chunk_count, 'updated_at': row.updated_at}
            for row in rows]


@router.post('/api/sources/upload', response_model=IngestResponse)
async def upload_source(request: Request, filename: str, db: Session = Depends(get_db)):
    from starlette.concurrency import run_in_threadpool
    limit = 64 * 1024
    if '/' in filename or '\\' in filename:
        raise HTTPException(status_code=422, detail='Upload filename must not contain a path')
    try:
        source = normalize_source('uploads/' + filename)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    content = bytearray()
    async for block in request.stream():
        if len(content) + len(block) > limit:
            raise HTTPException(status_code=413, detail='Upload limit is 64 KiB')
        content.extend(block)
    try:
        value = content.decode('utf-8')
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail='File must be UTF-8 text') from error
    if not value.strip():
        raise HTTPException(status_code=422, detail='File must not be empty')
    rows = await run_in_threadpool(ingest_text, db, source, value, {'format': source.rsplit('.', 1)[-1]})
    return IngestResponse(source=source, chunks_created=len(rows), chunk_ids=[row.id for row in rows])


@router.get('/api/settings')
def public_settings():
    from app.config import settings
    return {
        'embedding_provider': settings.embedding_provider,
        'embedding_model': settings.embedding_model,
        'embedding_dimensions': settings.embedding_dimensions,
        'answer_provider': 'anthropic',
        'answer_model': settings.claude_model,
        'storage': 'PostgreSQL + pgvector',
        'chunk_size': 500,
        'chunk_overlap': 75,
        'upload_limit_bytes': 64 * 1024,
    }


@router.delete('/api/sources')
def delete_source(source: str, db: Session = Depends(get_db)):
    from sqlalchemy import delete, text
    from app.models import Chunk
    try:
        source = normalize_source(source)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:source, 0))'), {'source': source})
        count = db.execute(delete(Chunk).where(Chunk.source == source)).rowcount
        db.commit()
    except Exception:
        db.rollback()
        raise
    if not count:
        raise HTTPException(status_code=404, detail='Source not found')
    return {'source': source, 'chunks_deleted': count}


@router.post('/api/sources/text', response_model=IngestResponse)
async def save_text(request: Request, title: str, db: Session = Depends(get_db)):
    from starlette.concurrency import run_in_threadpool
    title = title.strip()
    if not title or len(title) > 120 or '/' in title or '\\' in title:
        raise HTTPException(status_code=422, detail='Use a note title of 1–120 characters without path separators')
    try:
        source = normalize_source('notes/' + title + '.txt')
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    content = bytearray()
    async for block in request.stream():
        if len(content) + len(block) > 64 * 1024:
            raise HTTPException(status_code=413, detail='Text limit is 64 KiB')
        content.extend(block)
    try:
        value = content.decode('utf-8')
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail='Text must be UTF-8') from error
    if not value.strip():
        raise HTTPException(status_code=422, detail='Note must not be empty')
    rows = await run_in_threadpool(ingest_text, db, source, value, {'format': 'text'})
    return IngestResponse(source=source, chunks_created=len(rows), chunk_ids=[row.id for row in rows])
