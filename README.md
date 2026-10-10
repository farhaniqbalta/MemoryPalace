# MemoryPalace

A personal AI knowledge platform and learning project. Feed it your own documents
and notes, then ask questions through Telegram and get answers grounded in that
material, with sources shown. The goal is to understand RAG, embeddings, vector
search, MCP, and agentic AI by building a simple working system.

See the [Product Requirements Document](docs/00_AI_Knowledge_Platform_Project_PRD.md)
for requirements, technical decisions, and open questions.

Track the work in the [implementation checklist](docs/04_Implementation_Checklist.md).

## Planned Phase 1 architecture

```text
Text / Markdown files → chunk → embed → PostgreSQL + pgvector
Telegram question → FastAPI → embed question → retrieve chunks → Claude → answer + sources
```

- Store document chunks in one `chunks` table, with source names, chunk indexes,
  metadata, embeddings, and the embedding model used.
- Use cloud embeddings: Gemini by default, with OpenAI selectable through
  `EMBEDDING_PROVIDER`. The target vector size is 1536 dimensions for both.
- Re-embed all stored chunks when the embedding model or provider changes;
  vectors from different models cannot be compared.
- Use Anthropic for answers, starting with `claude-haiku-5-5`.
- Run PostgreSQL with pgvector in Docker and the Python app in a virtualenv.
- Restrict the Telegram bot to Farhan's account and deploy to a DigitalOcean Droplet.

Knowledge Cards and append-only versioning have been dropped from the MVP.
Local models, knowledge graphs, multi-user support, and a web UI are outside the
current scope.

## Current implementation

**The code still implements the earlier Knowledge Card design.** The revised PRD
defines the intended direction; the application has not yet been migrated to it.

- `app/core/extraction.py` — Claude extracts one structured Knowledge Card from text.
- `app/core/cards.py` — creates, lists, retrieves, and supersedes cards.
- `app/core/embeddings.py` — OpenAI embeddings, currently `text-embedding-3-small`.
- `app/core/search.py` — cosine similarity search over active cards using pgvector.
- `app/core/rag.py` — retrieves cards and asks Claude to answer from their content.
- `app/api/` — `/ingest`, `/cards`, `/cards/{card_id}`,
  `/cards/{card_id}/supersede`, `/search`, and `/ask`.
- `bot/telegram_bot.py` — plain messages ingest text; `/ask` and `/search` call the API.
- `migrations/` and `tests/` — schema migration and tests for the existing card pipeline.

Runtime readiness and end-to-end behavior still need verification.

## Work needed for the revised MVP

- Replace the card schema and extraction flow with chunk storage and chunking.
- Add plain text / Markdown file and folder ingestion.
- Add Gemini embeddings, provider configuration, and a re-embedding script.
- Adapt retrieval, answers, and source reporting to chunks and source files.
- Restrict Telegram access to the configured owner account.
- Update migrations and tests, then validate with real notes and deploy.

Agreed starting choices: 500-token chunks with 75-token overlap; re-ingesting a
source replaces its old chunks after new embeddings succeed. The first smoke-test
source is this repo’s `docs/` folder.

## Configuration

Settings load from `.env`; existing process environment variables take precedence.

| Setting | Purpose / default |
| --- | --- |
| `DATABASE_URL` | Required PostgreSQL connection URL, using psycopg 3. |
| `ANTHROPIC_API_KEY` | Credential for answers (and legacy extraction). |
| `GEMINI_API_KEY` | Credential for the planned Gemini embedding adapter. |
| `OPENAI_API_KEY` | Credential for OpenAI embeddings. |
| `CLAUDE_MODEL` | `claude-haiku-5-5`. |
| `EMBEDDING_PROVIDER` | `gemini` (default) or `openai`; other values are rejected. |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001`. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small`. |
| `EMBEDDING_MODEL` | Optional explicit model override; leave unset for provider-based selection. |
| `EMBEDDING_DIMENSIONS` | Fixed at 1536; other values are rejected. |
| `TELEGRAM_BOT_TOKEN` | Bot credential. |
| `TELEGRAM_OWNER_ID` | Positive numeric owner ID; access enforcement is pending. |
| `API_BASE_URL` | `http://localhost:8000`. |

Keys may remain empty for configuration/database checks. AI operations need the
relevant credentials; the legacy API still initializes clients on import.
Provider switching will work once adapters and re-embedding are implemented.
The existing virtualenv uses Python 3.9; annotation compatibility has been fixed,
but its Google dependencies warn about Python end of life and system LibreSSL.
Use a maintained Python with OpenSSL when rebuilding the environment.

## Running the existing code locally

These commands run the current card-based implementation.

1. Start the database. If you use Colima on macOS, run `colima start` first.

   ```bash
   docker compose up -d
   ```

2. Create a virtualenv if needed, activate it, and install dependencies.

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` if `.env` does not already exist. Configure
   `DATABASE_URL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `TELEGRAM_BOT_TOKEN`.
   Set `CLAUDE_MODEL` to the answer/extraction model you intend to use.
   `EMBEDDING_PROVIDER` is validated by configuration; provider adapters are still
   pending, so the existing card-based pipeline is not ready to use Gemini.

4. Apply the current migration and run tests.

   ```bash
   alembic upgrade head
   pytest
   ```

   Tests create a separate `memorypalace_test` database and require a running
   PostgreSQL instance with database-creation permissions. AI calls are mocked.

5. Start the API.

   ```bash
   uvicorn app.api.main:app --reload
   ```

6. In a second terminal with the virtualenv activated, start the bot.

   ```bash
   python -m bot.telegram_bot
   ```

## Roadmap

- **Phase 1 — Core RAG:** file ingestion, chunking, embeddings, retrieval,
  answers with sources, Telegram, and Droplet deployment.
- **Phase 2 — Quality and MCP:** retrieval tuning, metadata filters, evaluation
  questions, an MCP search server, and additional source types such as PDFs and web pages.
- **Phase 3 — Agentic (optional):** a small agent that decides when and how to
  search, considered only after Phases 1 and 2 work.
