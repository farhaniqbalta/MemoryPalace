# MemoryPalace: Product Requirements Document

**Author:** Farhan · **Status:** Draft v0.1 · **Date:** October 11, 2026

## 1. Overview

MemoryPalace is a personal AI knowledge platform. You feed it your own documents and notes, then ask questions through a Telegram bot and get answers grounded in that material. It is built first as a learning project: the point is to understand RAG, embeddings, MCP, and agentic AI by building them, not to ship a polished product.

## 2. Goals and non-goals

### Goals

- A working end-to-end RAG pipeline: ingest, chunk, embed, store, retrieve, answer.
- Hands-on understanding of embeddings and vector search with pgvector.
- Later phases introduce MCP and agentic behavior on top of a working base.
- Keep everything as simple as possible. Add complexity only when a real problem demands it.

### Non-goals (for now)

- Knowledge Cards and append-only versioning. Dropped from the MVP as unnecessary. Revisit later if needed; adding them would require schema, extraction, and retrieval changes.
- Local models (e.g. Ollama). Inference and embeddings use cloud APIs.
- Multi-user support, a web UI, or production-grade hardening.
- Knowledge Graphs. Revisit only after the base system works.

## 3. User and use cases

The only user is Farhan, who has limited backend experience and prefers to discuss decisions before implementing them.

- Add a document or note to the knowledge base.
- Ask a question in Telegram and get an answer based on stored material, with the sources shown.
- Check which sources were used, to judge whether retrieval is working.

## 4. Scope by phase

### Phase 1: Core RAG (MVP)

- Postgres with pgvector running in Docker.
- Ingestion script for plain text and Markdown files.
- Chunking, embedding, and storage in a single table.
- FastAPI endpoints for ingest and query.
- Telegram bot that sends questions to the query endpoint and replies with the answer and sources.
- Deployed to a DigitalOcean Droplet.

### Phase 2: Quality and MCP

- Improve retrieval: chunk size tuning, metadata filters, simple evaluation questions.
- Expose search as an MCP server so other AI clients can query the knowledge base.
- More source types (e.g. PDFs, web pages).

### Phase 3: Agentic (stretch, scope to be confirmed)

- An agent that decides when to search, which source to use, and whether to search again.
- Flagged earlier as overly ambitious. Keep it small, or cut it, after Phase 2.

## 5. Functional requirements (Phase 1)

1. Ingest: accept a text or Markdown file, split it into chunks, embed each chunk, and store it with its source name.
2. Query: embed the question, retrieve the top-k most similar chunks by cosine distance, and pass them to the LLM to write an answer.
3. Sources: every answer lists the source files of the chunks it used.
4. Provider switch: the embedding provider is chosen by one setting, `EMBEDDING_PROVIDER` (`gemini` or `openai`). Gemini is the default.
5. Re-embed: a script re-embeds all stored chunks after the provider changes.
6. Access control: the Telegram bot only responds to Farhan's own account.
7. Config: API keys and settings come from environment variables, never from code.

## 6. Technical decisions

| Area | Decision |
| --- | --- |
| LLM and embeddings | Cloud APIs. Gemini embeddings by default, switchable to OpenAI. |
| Embedding size | 1536 dimensions for both providers, so one vector(1536) column works for either. |
| Database | PostgreSQL with pgvector, chosen for pgvector's maturity. |
| Docker | Database only. App components run natively in a virtualenv for faster iteration. |
| App stack | FastAPI, uvicorn, SQLAlchemy, psycopg2, alembic, python-telegram-bot, tenacity, pytest, httpx. |
| SDKs | Anthropic for answers; Gemini and OpenAI SDKs for embeddings. |
| Hosting | DigitalOcean Droplet. |

## 7. Data model (draft)

One table to start:

- `chunks`: `id`, `source`, `chunk_index`, `content`, `metadata` (JSON), `embedding` (`vector(1536)`), `embedding_model`, `created_at`.

The `embedding_model` column records which model produced each vector. Vectors from different models are not comparable, so a provider switch requires re-embedding every row.

## 8. Success criteria

- Ingest a folder of real notes and ask questions whose answers are clearly in them. Most answers should be correct and cite the right source.
- Switch the embedding provider with one setting plus a re-embed run, with no code changes.
- The whole system runs on the Droplet and is reachable through Telegram.
- You can explain to someone else how each part works: chunking, embeddings, similarity search, and how the answer is assembled.

## 9. Risks

- Scope creep: Phase 3 is the main risk. Do not start it before Phase 1 and 2 work.
- Privacy: Gemini's free tier may use submitted content to improve Google's products. Keep private material out until you accept that tradeoff, or switch to OpenAI.
- Poor retrieval: weak answers usually come from chunking choices, not the embedding model. Plan time to tune.
- Provider changes: model names, limits, and free-tier terms change. Verify them in the vendors' docs before relying on them.

## 10. Open questions

- Which LLM model will write the answers?
- What source types matter most in the first ingest, and roughly how much content?
- Chunk size and overlap to start with?
- How should re-ingesting an updated file work: replace its old chunks, or skip duplicates?
- Is a plain top-k search enough, or is a reranking step worth adding in Phase 2?
