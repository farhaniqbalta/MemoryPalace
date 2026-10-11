from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.embeddings import embed_text, embedding_identity
from app.models import Chunk


class EmbeddingModelMismatch(ValueError):
    pass


def search_chunks(db: Session, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
    if not query.strip() or not 1 <= top_k <= 20:
        raise ValueError("Query must be nonempty and top_k between 1 and 20")
    identity = embedding_identity()
    identities = set(db.scalars(select(Chunk.embedding_model).distinct()).all())
    if identities - {identity}:
        raise EmbeddingModelMismatch("Stored embeddings differ from the configured model; finish re-embedding before searching")
    if not identities:
        return []
    vector = embed_text(query, purpose="query")
    distance = Chunk.embedding.cosine_distance(vector)
    # Identity filter also prevents comparison if another transaction changes rows.
    rows = db.execute(select(Chunk, distance.label("distance"))
                      .where(Chunk.embedding_model == identity)
                      .order_by(distance, Chunk.source, Chunk.chunk_index).limit(top_k)).all()
    return [(chunk, 1 - dist) for chunk, dist in rows]
