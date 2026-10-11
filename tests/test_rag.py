import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import settings
from app.core.rag import answer_question
from app.db import get_db
from app.core.search import EmbeddingModelMismatch


def chunk(source):
    return SimpleNamespace(id=uuid.uuid4(), source=source, chunk_index=0, content='notes')


def test_cites_only_used_chunks(monkeypatch):
    monkeypatch.setattr(settings, 'anthropic_api_key', 'test')
    a, b = chunk('a.md'), chunk('b.md')
    constructor = MagicMock()
    client = constructor.return_value.__enter__.return_value
    client.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(
        type='tool_use', name='submit_answer', input={'answer': 'From A', 'cited_chunk_ids': [str(a.id), str(a.id)]})])
    with patch('app.core.rag.search_chunks', return_value=[(a, 1), (b, .8)]), patch('app.core.rag.anthropic.Anthropic', constructor):
        answer, cited, retrieved = answer_question(None, 'question')
    assert answer == 'From A' and cited == [a] and retrieved == [a, b]


@pytest.mark.parametrize('ids', [[], ['invented-id']])
def test_no_citations_or_invalid_citations(monkeypatch, ids):
    monkeypatch.setattr(settings, 'anthropic_api_key', 'test')
    a = chunk('a.md')
    with patch('app.core.rag.search_chunks', return_value=[(a, 1)]), patch('app.core.rag.anthropic.Anthropic') as constructor:
        constructor.return_value.__enter__.return_value.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(
            type='tool_use', name='submit_answer', input={'answer': 'Unverified claim', 'cited_chunk_ids': ids})])
        if ids:
            with pytest.raises(ValueError, match='unknown chunk'):
                answer_question(None, 'question')
        else:
            answer, cited, retrieved = answer_question(None, 'question')
            assert 'not enough' in answer or "doesn't contain enough" in answer
            assert cited == [] and retrieved == [a]


def test_no_results_skips_answer_provider():
    with patch('app.core.rag.search_chunks', return_value=[]), patch('app.core.rag.anthropic.Anthropic') as client:
        assert answer_question(None, 'question')[1:] == ([], [])
    client.assert_not_called()


def test_api_validation_and_mismatch():
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app) as client:
            assert client.post('/search', json={'query': ' ', 'top_k': 5}).status_code == 422
            assert client.post('/ask', json={'question': 'q', 'top_k': 0}).status_code == 422
            assert client.get('/cards').status_code == 404
            with patch('app.api.routes.search_chunks', side_effect=EmbeddingModelMismatch('re-embed')):
                assert client.post('/search', json={'query': 'q'}).status_code == 409
    finally:
        app.dependency_overrides.clear()
