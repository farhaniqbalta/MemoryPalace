"""Resumable re-embedding with atomic vector/model updates."""
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.embeddings import embed_text, embedding_identity
from app.models import Chunk


@dataclass
class ReembeddingResult:
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    remaining: int = 0


def reembed_chunks(db: Session, *, force: bool = False, report=print) -> ReembeddingResult:
    target = embedding_identity()
    result = ReembeddingResult()
    # Snapshot IDs/content only; do not retain row locks during cloud calls.
    rows = db.execute(select(Chunk.id, Chunk.content, Chunk.embedding_model)
                      .order_by(Chunk.source, Chunk.chunk_index)).all()
    db.rollback()
    report(f"Target: {target}; chunks: {len(rows)}")
    for index, (chunk_id, content, previous) in enumerate(rows, 1):
        if previous == target and not force:
            result.skipped += 1
            report(f"[{index}/{len(rows)}] Already current: {chunk_id}")
            continue
        try:
            vector = embed_text(content, purpose="document")
            # Concurrent replacement/removal must never overwrite new content.
            changed = db.execute(update(Chunk).where(
                Chunk.id == chunk_id, Chunk.content == content, Chunk.embedding_model == previous
            ).values(embedding=vector, embedding_model=target)).rowcount
            db.commit()
            if changed:
                result.updated += 1
                report(f"[{index}/{len(rows)}] Updated: {chunk_id}")
            else:
                result.skipped += 1
                report(f"[{index}/{len(rows)}] Changed concurrently; skipped: {chunk_id}")
        except Exception as error:
            db.rollback()
            result.failed += 1
            report(f"[{index}/{len(rows)}] Failed: {chunk_id} ({type(error).__name__})")
    result.remaining = db.scalar(select(func.count()).select_from(Chunk)
                                 .where(Chunk.embedding_model != target))
    db.rollback()
    report(f"Updated: {result.updated}; skipped: {result.skipped}; failed: {result.failed}; remaining: {result.remaining}")
    return result
