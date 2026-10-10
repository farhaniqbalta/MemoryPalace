from sqlalchemy.orm import Session

from app.config import settings
from app.core.extraction import client
from app.core.search import search_cards
from app.models import KnowledgeCard

_SYSTEM_PROMPT = (
    "Answer the user's question using only the knowledge cards given as context. "
    "Cite which card(s) you used by title. If the cards don't contain the answer, "
    "say so plainly instead of guessing."
)


def answer_question(
    db: Session, question: str, top_k: int = 5
) -> tuple[str, list[KnowledgeCard]]:
    results = search_cards(db, question, top_k=top_k)
    cards = [card for card, _ in results]
    context = "\n\n".join(f"[{c.id}] {c.title} ({c.type})\n{c.content}" for c in cards)

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ],
    )
    answer_text = next(b.text for b in response.content if b.type == "text")
    return answer_text, cards
