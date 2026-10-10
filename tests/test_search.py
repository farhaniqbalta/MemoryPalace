from unittest.mock import patch

from app.core import cards as cards_core
from app.core.search import search_cards


def fake_embed(text: str) -> list[float]:
    vec = [0.0] * 1536
    if "postgres" in text.lower():
        vec[0] = 1.0
    else:
        vec[1] = 1.0
    return vec


@patch("app.core.search.embed_text", side_effect=fake_embed)
@patch("app.core.cards.embed_text", side_effect=fake_embed)
def test_search_ranks_by_similarity(mock_cards_embed, mock_search_embed, db_session):
    raw = cards_core.create_raw_source(db_session, "test", "raw")
    postgres_card = cards_core.create_card(
        db_session,
        raw,
        type_="Decision",
        title="Why Postgres",
        content={"reason": "pgvector"},
        tags=["postgres"],
    )
    cards_core.create_card(
        db_session,
        raw,
        type_="Decision",
        title="Why Telegram",
        content={"reason": "bot ui"},
        tags=["telegram"],
    )

    results = search_cards(db_session, "why did we choose postgres?", top_k=2)

    assert results[0][0].id == postgres_card.id
    assert results[0][1] > results[1][1]


@patch("app.core.search.embed_text", side_effect=fake_embed)
@patch("app.core.cards.embed_text", side_effect=fake_embed)
def test_search_excludes_inactive_cards(mock_cards_embed, mock_search_embed, db_session):
    raw = cards_core.create_raw_source(db_session, "test", "raw")
    old = cards_core.create_card(
        db_session,
        raw,
        type_="Decision",
        title="Why Postgres",
        content={"reason": "old"},
        tags=[],
    )
    cards_core.supersede_card(
        db_session, old, type_="Decision", title="Why Postgres v2", content={"reason": "new"}, tags=[]
    )

    results = search_cards(db_session, "why postgres", top_k=5)

    assert old.id not in [card.id for card, _ in results]
