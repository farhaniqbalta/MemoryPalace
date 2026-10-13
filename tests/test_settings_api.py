from fastapi.testclient import TestClient
from app.api.main import app
from app.config import settings


def test_settings_are_read_only_and_exclude_secrets(monkeypatch):
    monkeypatch.setattr(settings, 'gemini_api_key', 'secret-sentinel')
    monkeypatch.setattr(settings, 'anthropic_api_key', 'secret-sentinel')
    monkeypatch.setattr(settings, 'telegram_bot_token', 'secret-sentinel')
    with TestClient(app) as client:
        response = client.get('/api/settings')
        assert response.status_code == 200
        data = response.json()
        assert data['embedding_model'] == settings.embedding_model
        assert data['answer_model'] == settings.claude_model
        assert 'secret-sentinel' not in response.text
        assert set(data) == {'embedding_provider', 'embedding_model', 'embedding_dimensions',
                             'answer_provider', 'answer_model', 'storage', 'chunk_size',
                             'chunk_overlap', 'upload_limit_bytes'}
        assert client.post('/api/settings', json={'embedding_provider': 'openai'}).status_code == 405
