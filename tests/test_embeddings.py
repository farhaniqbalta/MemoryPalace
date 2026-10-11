from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors
from tenacity import wait_none

from app.core import embeddings


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(embeddings.settings, "gemini_api_key", "test")
    monkeypatch.setattr(embeddings.settings, "openai_api_key", "test")
    monkeypatch.setattr(embeddings._request.retry, "wait", wait_none())
    def configure(name):
        monkeypatch.setattr(embeddings.settings, "embedding_provider", name)
        monkeypatch.setattr(embeddings.settings, "embedding_model",
                            "gemini-embedding-001" if name == "gemini" else "text-embedding-3-small")
        constructor = MagicMock()
        client = constructor.return_value.__enter__.return_value
        monkeypatch.setattr(embeddings.genai if name == "gemini" else embeddings,
                            "Client" if name == "gemini" else "OpenAI", constructor)
        method = client.models.embed_content if name == "gemini" else client.embeddings.create
        vector = [2.0] + [0.0] * 1535
        method.return_value = (SimpleNamespace(embeddings=[SimpleNamespace(values=vector)])
                               if name == "gemini" else SimpleNamespace(data=[SimpleNamespace(embedding=vector)]))
        return method
    return configure


@pytest.mark.parametrize("name", ["gemini", "openai"])
@pytest.mark.parametrize("purpose", ["document", "query"])
def test_provider_request_and_normalization(provider, name, purpose):
    method = provider(name)
    vector = embeddings.embed_text("PostgreSQL notes", purpose=purpose)
    assert vector == [1.0] + [0.0] * 1535
    kwargs = method.call_args.kwargs
    assert kwargs["model"] == embeddings.settings.embedding_model
    assert embeddings.embedding_identity() == f"{name}:{kwargs['model']}"
    if name == "gemini":
        assert kwargs["config"].output_dimensionality == 1536
        assert kwargs["config"].auto_truncate is False
        assert kwargs["config"].task_type == ("RETRIEVAL_DOCUMENT" if purpose == "document" else "RETRIEVAL_QUERY")
    else:
        assert kwargs["dimensions"] == 1536


@pytest.mark.parametrize("values", [[1.0], [0.0] * 1536, [float("nan")] * 1536, [float("inf")] * 1536])
def test_reject_bad_vectors(provider, values):
    method = provider("gemini")
    method.return_value.embeddings[0].values = values
    with pytest.raises(ValueError):
        embeddings.embed_text("notes")
    assert method.call_count == 1


@pytest.mark.parametrize("name", ["gemini", "openai"])
def test_retry_transport_error_then_success(provider, name):
    method = provider(name)
    response = method.return_value
    method.side_effect = [httpx.ConnectError("temporary"), response]
    embeddings.embed_text("notes")
    assert method.call_count == 2


def test_retry_limit(provider):
    method = provider("gemini")
    method.side_effect = errors.ClientError(429, {"error": {"message": "quota"}})
    with pytest.raises(errors.ClientError):
        embeddings.embed_text("notes")
    assert method.call_count == 3


def test_no_retry_auth_error(provider):
    method = provider("gemini")
    method.side_effect = errors.ClientError(401, {"error": {"message": "unauthorized"}})
    with pytest.raises(errors.ClientError):
        embeddings.embed_text("notes")
    assert method.call_count == 1


@pytest.mark.parametrize("name", ["gemini", "openai"])
def test_missing_key_and_blank_input(provider, monkeypatch, name):
    method = provider(name)
    monkeypatch.setattr(embeddings.settings, name + "_api_key", "")
    with pytest.raises(ValueError, match="API_KEY"):
        embeddings.embed_text("notes")
    with pytest.raises(ValueError, match="nonempty"):
        embeddings.embed_text("  ")
    method.assert_not_called()
