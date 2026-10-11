from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.embeddings import embedding_identity
from app.core.reembedding import reembed_chunks
from app.core.search import EmbeddingModelMismatch, search_chunks
from app.models import Chunk

VECTOR = [1.] + [0.] * 1535
NEW_VECTOR = [0., 1.] + [0.] * 1534


def seed(db, count=2):
    for index in range(count):
        db.add(Chunk(source='notes.md', chunk_index=index, content=f'note {index}',
                     source_metadata={}, embedding=VECTOR, embedding_model='old:model'))
    db.commit()


def test_partial_failure_and_resume(db_session):
    seed(db_session)
    with patch('app.core.reembedding.embed_text', side_effect=[NEW_VECTOR, RuntimeError('failure')]):
        first = reembed_chunks(db_session, report=lambda _: None)
    assert (first.updated, first.failed, first.remaining) == (1, 1, 1)
    db_session.expire_all()
    rows = db_session.scalars(select(Chunk).order_by(Chunk.chunk_index)).all()
    assert rows[0].embedding_model == embedding_identity()
    assert rows[0].embedding[1] == 1
    assert rows[1].embedding_model == 'old:model' and rows[1].embedding[0] == 1
    with pytest.raises(EmbeddingModelMismatch):
        search_chunks(db_session, 'query')
    with patch('app.core.reembedding.embed_text', return_value=NEW_VECTOR) as embed:
        second = reembed_chunks(db_session, report=lambda _: None)
    assert (second.updated, second.skipped, second.remaining) == (1, 1, 0)
    embed.assert_called_once_with('note 1', purpose='document')
    with patch('app.core.search.embed_text', return_value=NEW_VECTOR):
        assert len(search_chunks(db_session, 'query')) == 2


def test_commit_failure_keeps_vector_and_identity(db_session):
    seed(db_session, 1)
    with patch('app.core.reembedding.embed_text', return_value=NEW_VECTOR), patch.object(db_session, 'commit', side_effect=RuntimeError('failure')):
        result = reembed_chunks(db_session, report=lambda _: None)
    assert result.failed == 1 and result.remaining == 1
    db_session.expire_all()
    row = db_session.scalars(select(Chunk)).one()
    assert row.embedding_model == 'old:model' and row.embedding[0] == 1


def test_interrupt_resumes(db_session):
    seed(db_session)
    with patch('app.core.reembedding.embed_text', side_effect=[NEW_VECTOR, KeyboardInterrupt]):
        with pytest.raises(KeyboardInterrupt):
            reembed_chunks(db_session, report=lambda _: None)
    with patch('app.core.reembedding.embed_text', return_value=NEW_VECTOR):
        result = reembed_chunks(db_session, report=lambda _: None)
    assert result.updated == 1 and result.skipped == 1 and result.remaining == 0


def test_force_and_empty_database(db_session):
    assert reembed_chunks(db_session, report=lambda _: None).updated == 0
    seed(db_session, 1)
    with patch('app.core.reembedding.embed_text', return_value=NEW_VECTOR):
        reembed_chunks(db_session, report=lambda _: None)
        result = reembed_chunks(db_session, force=True, report=lambda _: None)
    assert result.updated == 1 and result.remaining == 0


def test_provider_switch_with_settings_only(db_session, monkeypatch):
    from app.config import settings
    seed(db_session, 1)
    with patch('app.core.reembedding.embed_text', return_value=NEW_VECTOR):
        for provider, model in [('openai', 'text-embedding-3-small'), ('gemini', 'gemini-embedding-001')]:
            monkeypatch.setattr(settings, 'embedding_provider', provider)
            monkeypatch.setattr(settings, 'embedding_model', model)
            result = reembed_chunks(db_session, report=lambda _: None)
            assert result.updated == 1 and result.remaining == 0
            db_session.expire_all()
            assert db_session.scalars(select(Chunk)).one().embedding_model == f'{provider}:{model}'
