"""Cloud embeddings shared by document ingestion, retrieval, and re-embedding."""

import math
from typing import Literal

import httpx
from google import genai
from google.genai import errors, types
from openai import APIConnectionError, APIStatusError, OpenAI
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from app.config import settings


def embedding_identity() -> str:
    return f"{settings.embedding_provider}:{settings.embedding_model}"


def _transient(error: BaseException) -> bool:
    if isinstance(error, (APIConnectionError, httpx.TransportError)):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code == 429 or 500 <= error.status_code < 600
    if isinstance(error, errors.APIError):
        return error.code == 429 or 500 <= error.code < 600
    return False


def _validate(values) -> list[float]:
    if values is None or len(values) != settings.embedding_dimensions:
        raise ValueError("Embedding response must contain 1536 dimensions")
    vector = [float(value) for value in values]
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("Embedding response contains non-finite values")
    norm = math.hypot(*vector)
    if not norm or not math.isfinite(norm):
        raise ValueError("Embedding response must be a finite nonzero vector")
    return [value / norm for value in vector]


@retry(retry=retry_if_exception(_transient), stop=stop_after_attempt(3),
       wait=wait_random_exponential(multiplier=1, max=8), reraise=True)
def _request(text: str, purpose: str) -> list[float]:
    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key.strip():
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings")
        # Disable SDK retries so the outer three-attempt limit is authoritative.
        with genai.Client(api_key=settings.gemini_api_key, http_options=types.HttpOptions(
            timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)
        )) as client:
            response = client.models.embed_content(
                model=settings.embedding_model, contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.embedding_dimensions,
                    task_type="RETRIEVAL_DOCUMENT" if purpose == "document" else "RETRIEVAL_QUERY",
                ),
            )
        if not response.embeddings or len(response.embeddings) != 1:
            raise ValueError("Expected one Gemini embedding")
        return _validate(response.embeddings[0].values)
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key.strip():
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
        with OpenAI(api_key=settings.openai_api_key, max_retries=0, timeout=30) as client:
            response = client.embeddings.create(
                model=settings.embedding_model, input=text,
                dimensions=settings.embedding_dimensions,
            )
        if len(response.data) != 1:
            raise ValueError("Expected one OpenAI embedding")
        return _validate(response.data[0].embedding)
    raise ValueError("Unsupported embedding provider")


def embed_text(text: str, *, purpose: Literal["document", "query"] = "document") -> list[float]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding input must be nonempty text")
    if purpose not in ("document", "query"):
        raise ValueError("Embedding purpose must be document or query")
    return _request(text, purpose)
