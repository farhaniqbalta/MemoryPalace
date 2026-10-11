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

**The API now uses document chunks for ingestion, search, and answers.**
Knowledge Card models, extraction, and supersession routes have been removed.
Legacy database tables remain preserved by the migration history.

- `app/core/ingestion.py` — token chunking and atomic source replacement.
- `scripts/ingest.py` — text/Markdown file and folder ingestion.
- `app/core/embeddings.py` — Gemini/OpenAI embeddings with validation and retries.
- `app/core/search.py` — chunk cosine search with model-identity checks.
- `app/core/rag.py` — grounded answers with validated chunk citation IDs.
- `app/api/` — `/ingest`, `/search`, and `/ask`.
- `app/models.py` — `Chunk` model.
- `migrations/` — legacy schema plus additive chunk-storage migration.
- `tests/` — mocked-provider ingestion, retrieval, citations, and API tests.
- `scripts/verify_chunk_storage.py` — migration and ORM verification.
- `bot/telegram_bot.py` — owner-only private-chat answers and chunk search.

Full suite: 32 tests passed with AI calls mocked. Live provider behavior and answers
on real documents remain to be verified.

## Work needed for the revised MVP

- Validate live embedding providers and the complete ingestion/query flow.
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
| `GEMINI_API_KEY` | Credential for Gemini embeddings. |
| `OPENAI_API_KEY` | Credential for OpenAI embeddings. |
| `CLAUDE_MODEL` | `claude-haiku-5-5`. |
| `EMBEDDING_PROVIDER` | `gemini` (default) or `openai`; other values are rejected. |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001`. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small`. |
| `EMBEDDING_MODEL` | Optional explicit model override; leave unset for provider-based selection. |
| `EMBEDDING_DIMENSIONS` | Fixed at 1536; other values are rejected. |
| `TELEGRAM_BOT_TOKEN` | Bot credential; required to start the bot. |
| `TELEGRAM_OWNER_ID` | Positive numeric owner ID; required, checked before every request. |
| `API_BASE_URL` | `http://localhost:8000`. |

Keys may remain empty for configuration/database checks and API startup. AI operations
require the selected embedding key and the Anthropic key for nonempty answer context.
Provider adapters are implemented; switching stored knowledge safely still requires
the re-embedding script; retrieval already rejects mismatched models.
The existing virtualenv uses Python 3.9; annotation compatibility has been fixed,
but its Google dependencies warn about Python end of life and system LibreSSL.
Use a maintained Python with OpenSSL when rebuilding the environment.

## Running the existing code locally

These commands start the chunk-based API and owner-only Telegram bot.

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
   `EMBEDDING_PROVIDER` selects the implemented adapter. The API is still card-based;
   use the forthcoming chunk pipeline for provider switching with model-identity checks.

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

6. Configure `TELEGRAM_OWNER_ID` and `TELEGRAM_BOT_TOKEN`, then start the bot
   in a second activated terminal.

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

## Ingesting text and Markdown

Configure the selected embedding provider's key and apply migrations first.

```bash
python -m scripts.ingest docs
python -m scripts.ingest /path/to/notes --root /path/to
```

The root defines stable source names (for example, `docs/example.md`). Reuse the
same root when updating files. Each source is replaced atomically; folder ingestion
reports per-file failures and exits with a nonzero status if any fail. Empty files
are skipped. The first tokenizer use downloads its vocabulary cache.

The API accepts file content rather than reading arbitrary server paths:

```json
{"source": "notes/example.md", "content": "Your Markdown text", "metadata": {"format": "md"}}
```

POST this JSON to `/ingest`; the response reports `source`, `chunks_created`, and
`chunk_ids`. Ingestion calls the selected embedding provider. Query with `/search` (`query`, optional `top_k`) or `/ask` (`question`, optional
`top_k`). Answers include cited source files separately from all retrieved chunks.
Changing the embedding provider/model requires re-embedding; otherwise queries
return HTTP 409.

## Switching embedding providers

Change `EMBEDDING_PROVIDER` in `.env`, configure that provider's key, and leave
`EMBEDDING_MODEL` unset unless overriding its default. Restart the API/bot so they
use the same settings, then run:

```bash
python -m scripts.reembed
```

Each successful chunk saves its new vector and model identity in one transaction.
Failed chunks keep their old vectors. If interrupted, run the command again: chunks
already using the target model are skipped. The script reports progress and returns
a nonzero exit status if failures or mismatched chunks remain. Use `--force` to
regenerate even chunks already marked with the selected model.

Retrieval rejects mixed/mismatched model identities until re-embedding completes.
Keep ingestion paused and use one re-embedding process during a provider switch.
Concurrent content changes are skipped rather than overwritten; a subsequent run
can process any remaining chunks. A force run interrupted halfway can be restarted
with `--force` to regenerate all chunks again.

## Telegram usage

Set `TELEGRAM_OWNER_ID` to your numeric Telegram account ID (not your username).
The bot refuses to start without it and a bot token. Only that account's private
messages are processed; other users and group chats are ignored.

- Send plain text or `/ask <question>` to get an answer with cited source files.
- Use `/search <query>` to inspect retrieved chunks, source names, and scores.
- Ingest files through the script/API; Telegram messages ask questions.

Telegram behavior has been checked with 20 mocked HTTP tests. Live Gemini ingestion,
Anthropic answers, and Telegram responses were validated on October 11, 2026.
Live OpenAI provider switching is deferred; Gemini is the active provider.

## Deployment

Use [the Ubuntu deployment guide](deploy/README.md) and `scripts/deploy.sh` to run
PostgreSQL in Docker and the app/bot under systemd on a Droplet. Deployment is
prepared but not yet verified on a server.

Pushes to `main` trigger `.github/workflows/deploy.yml`: GitHub Actions connects
by SSH, fetches the pushed commit, and runs the deployment script on the Droplet.
Complete the one-time server and GitHub `production` secret setup in the deployment
guide to activate it. Server `.env` and stored chunks persist across redeploys.
