from unittest.mock import patch

from app.core import cards as cards_core

FAKE_EMBEDDING = [0.0] * 1536


@patch("app.core.cards.embed_text", return_value=FAKE_EMBEDDING)
def test_create_card(mock_embed, db_session):
    raw = cards_core.create_raw_source(db_session, "test", "some raw text")
    card = cards_core.create_card(
        db_session, raw, type_="Fact", title="Test", content={"a": 1}, tags=["x"]
    )

    assert card.active is True
    assert card.supersedes is None

    fetched = cards_core.get_card(db_session, card.id)
    assert fetched.title == "Test"


@patch("app.core.cards.embed_text", return_value=FAKE_EMBEDDING)
def test_supersede_card_marks_old_inactive(mock_embed, db_session):
    raw = cards_core.create_raw_source(db_session, "test", "raw")
    old = cards_core.create_card(
        db_session, raw, type_="Fact", title="Old", content={"a": 1}, tags=[]
    )

    new = cards_core.supersede_card(
        db_session, old, type_="Fact", title="New", content={"a": 2}, tags=[]
    )

    db_session.refresh(old)
    assert old.active is False
    assert new.active is True
    assert new.supersedes == old.id

    active_ids = [c.id for c in cards_core.list_cards(db_session, active=True)]
    assert old.id not in active_ids
    assert new.id in active_ids

    # nothing is ever deleted -- the old card is still fetchable directly
    assert cards_core.get_card(db_session, old.id) is not None
