"""Text/Markdown chunk ingestion with atomic replacement per source."""
import re
from pathlib import PurePosixPath

import tiktoken
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.core.embeddings import embed_text, embedding_identity
from app.models import Chunk


def normalize_source(source: str) -> str:
    source = source.strip().replace("\\", "/")
    path = PurePosixPath(source)
    if not source or path.is_absolute() or ".." in path.parts or str(path) == ".":
        raise ValueError("Source must be a nonempty relative path without '..'")
    if path.suffix.lower() not in (".txt", ".md", ".markdown"):
        raise ValueError("Source must be a text or Markdown file")
    return str(path)


def chunk_text(content: str, size: int = 500, overlap: int = 75) -> list[str]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Chunk size must be positive and overlap smaller than size")
    if not content.strip():
        return []
    encoding = tiktoken.get_encoding("cl100k_base")
    # Work in characters so token windows never split UTF-8 sequences.
    chunks = []
    start = 0
    while start < len(content):
        low, high = start + 1, len(content)
        end = start
        while low <= high:
            middle = (low + high) // 2
            candidate = content[start:middle]
            # Conservative byte cap for Gemini's 2048-token input limit;
            # cl100k_base is our chunking measure, not Gemini's tokenizer.
            if len(encoding.encode(candidate, disallowed_special=())) <= size and len(candidate.encode("utf-8")) <= 2048:
                end = middle
                low = middle + 1
            else:
                high = middle - 1
        if end == start:
            raise ValueError("Chunk size is too small for the input")
        if end < len(content):
            boundaries = list(re.finditer(r"\n\s*\n", content[start:end]))
            if boundaries and boundaries[-1].end() > (end - start) // 2:
                end = start + boundaries[-1].end()
        value = content[start:end]
        if value.strip():
            chunks.append(value)
        if end == len(content):
            break
        next_start = end
        while next_start > start + 1 and len(encoding.encode(content[next_start - 1:end], disallowed_special=())) <= overlap:
            next_start -= 1
        start = max(start + 1, next_start)
    return chunks


def ingest_text(db: Session, source: str, content: str, metadata=None) -> list[Chunk]:
    source = normalize_source(source)
    parts = chunk_text(content)
    # Empty files are skipped; they do not silently erase previous knowledge.
    if not parts:
        return []
    identity = embedding_identity()
    vectors = [embed_text(part, purpose="document") for part in parts]
    rows = [Chunk(source=source, chunk_index=index, content=part,
                  source_metadata=dict(metadata or {}), embedding=vector,
                  embedding_model=identity)
            for index, (part, vector) in enumerate(zip(parts, vectors))]
    try:
        # Serialize replacement of the same source across API/CLI processes.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:source, 0))"), {"source": source})
        db.execute(delete(Chunk).where(Chunk.source == source))
        db.add_all(rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return rows
