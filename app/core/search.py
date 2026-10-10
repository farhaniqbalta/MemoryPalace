from sqlalchemy.orm import Session

from app.core.embeddings import embed_text
from app.models import KnowledgeCard


def search_cards(db: Session, query: str, top_k: int = 5) -> list[tuple[KnowledgeCard, float]]:
    """Semantic search over active cards, ranked by cosine similarity."""
    query_embedding = embed_text(query)
    distance = KnowledgeCard.embedding.cosine_distance(query_embedding)
    rows = (
        db.query(KnowledgeCard, distance.label("distance"))
        .filter(KnowledgeCard.active.is_(True))
        .order_by(distance)
        .limit(top_k)
        .all()
    )
    return [(card, 1 - dist) for card, dist in rows]
