from unittest.mock import patch

import pytest

from app.core.embeddings import embedding_identity
from app.core.search import EmbeddingModelMismatch, search_chunks
from app.models import Chunk


def add(db, source, vector, identity=None):
    row = Chunk(source=source, chunk_index=0, content=source, source_metadata={},
                embedding=vector, embedding_model=identity or embedding_identity())
    db.add(row)
    db.commit()
    return row


def test_ranking_and_query_purpose(db_session):
    a = add(db_session, 'postgres.md', [1.] + [0.] * 1535)
    add(db_session, 'other.md', [0., 1.] + [0.] * 1534)
    with patch('app.core.search.embed_text', return_value=[1.] + [0.] * 1535) as embed:
        rows = search_chunks(db_session, 'postgres', 2)
    assert rows[0][0].id == a.id
    assert rows[0][1] > rows[1][1]
    embed.assert_called_once_with('postgres', purpose='query')


def test_model_mismatch_before_api_call(db_session):
    add(db_session, 'old.md', [1.] + [0.] * 1535, 'different:model')
    with patch('app.core.search.embed_text') as embed:
        with pytest.raises(EmbeddingModelMismatch):
            search_chunks(db_session, 'query')
    embed.assert_not_called()


def test_empty_database_skips_embedding(db_session):
    with patch('app.core.search.embed_text') as embed:
        assert search_chunks(db_session, 'query') == []
    embed.assert_not_called()
