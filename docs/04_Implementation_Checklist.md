# MemoryPalace implementation checklist

Based on the [revised PRD](00_AI_Knowledge_Platform_Project_PRD.md).
The current code uses Knowledge Cards; this checklist tracks the move to
document chunks. Unchecked items include existing components that need adaptation
or verification. Discuss the open decisions before implementing them.

## Phase 1 — Core RAG

### 1. Agree on the starting decisions

- [x] Choose the Anthropic answer model.
- [x] Choose the first notes folder and estimate its size; start with text and Markdown.
- [x] Choose initial chunk size, overlap, and how to measure them.
- [x] Decide whether re-ingesting a source replaces its chunks or skips duplicates.
- [x] Check whether the existing database contains data to preserve; agree on migration handling.
- [x] Verify embedding model names, 1536-dimension support, input limits, and applicable provider terms in official docs.
- [x] Resolve the stack difference: the PRD lists psycopg2, while current code uses psycopg 3.

#### Starting decision review — October 11, 2026

Farhan accepted these starting choices on October 11, 2026. Database inspection completed: the running `memorypalace` database has no public tables.

| Item | Accepted starting choice / findings | Status |
| --- | --- | --- |
| Answer model | `claude-haiku-5-5`, as a low-cost baseline for answering from retrieved context; evaluate on actual notes. | Accepted |
| First source | This repo's `docs/` folder: 5 Markdown files, approximately 16 KiB at review time. Older architecture notes may describe the superseded design; use the current PRD for current requirements. | Accepted |
| Chunking | Target 500 tokens with 75-token overlap, preserving paragraph boundaries where possible. Token counting must be defined in implementation and provider input limits checked separately. This replaces the earlier word-based suggestion. | Accepted |
| Re-ingestion | Identify a source by its stable relative path; replace that source's chunks in one transaction after all new embeddings succeed. | Accepted |
| Existing data | PostgreSQL is running. Read-only inspection found zero public tables in `memorypalace`; there are no existing card tables or rows to preserve there. Retain the agreed additive migration approach. | Verified |
| Embeddings | Gemini `gemini-embedding-001` with 1536 output dimensions; OpenAI `text-embedding-3-small` with 1536 dimensions. | Documentation checked; no live API validation |
| Database driver | Keep existing psycopg 3 (`psycopg[binary]`) rather than changing drivers; PRD aligned. | Accepted |

Provider documentation checked:

- [Gemini embedding model](https://ai.google.dev/gemini-api/docs/models/gemini-embedding-001): supports 1536 dimensions; the model-specific page lists a 2048-token input limit. Use this conservative limit for this model; do not assume another Gemini embedding model has the same limits.
- [OpenAI embedding guide](https://developers.openai.com/api/docs/guides/embeddings): `text-embedding-3-small` defaults to 1536 dimensions and lists an 8192-token input limit.
- [Anthropic Haiku page](https://www.anthropic.com/claude/haiku): documents the `claude-haiku-5-5` API identifier and its availability.
- [Gemini terms](https://ai.google.dev/gemini-api/terms): unpaid-service content can be used for product improvement and reviewed by humans; paid-service terms differ. Confirm the project's billing status before choosing material.
- [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data): API content is not used for training by default, but standard abuse-monitoring retention still applies.

Checklist 1 is complete. Read-only inspection on October 11, 2026 found zero
public tables in the running `memorypalace` database. No migrations were applied
and no application data was changed.

### 2. Configuration and local environment

- [x] Verify Docker PostgreSQL + pgvector and the Python virtualenv work locally.
- [x] Add Gemini SDK and retry dependencies; retain OpenAI and Anthropic SDKs.
- [x] Add `EMBEDDING_PROVIDER` with `gemini` as the default and reject unsupported values.
- [x] Configure provider keys, embedding model, answer model, and Telegram owner ID through environment variables.
- [x] Update `.env.example` with placeholders and document settings in README.

Configuration and environment implementation verified October 11, 2026:

- Python connects to `memorypalace`; pgvector is available. No migrations applied.
- Gemini SDK and tenacity installed; dependency consistency check passed.
- Provider/model defaults, invalid provider rejection, dimensions, and owner ID validation checked.
- Legacy model/schema annotations now load on Python 3.9.
- Local `.env` non-secret settings aligned with agreed defaults; credentials preserved.
- Credentials and the actual Telegram owner ID still need to be supplied before live use.
- Provider adapters and bot access enforcement belong to later checklist sections.
- Python 3.9/LibreSSL dependency warnings remain; use maintained Python/OpenSSL for the eventual runtime.

### 3. Chunk storage and migration

- [x] Add the `chunks` model: id, source, chunk_index, content, metadata, embedding, embedding_model, created_at.
- [x] Use a `vector(1536)` column and record an unambiguous provider/model identity.
- [x] Create an Alembic migration, following the agreed handling of existing data.
- [x] Verify migration on a fresh database and on the existing schema.
- [x] Remove obsolete card models, extraction, supersession, and routes once their replacements work.

Chunk storage verified October 11, 2026:

- Migration `0002` applied locally through the existing `0001` migration chain.
- `chunks` has unique `(source, chunk_index)` and nonnegative chunk-index constraints.
- JSON column `metadata` maps to `source_metadata` in Python because SQLAlchemy reserves `metadata`.
- Embedding identity uses `provider:model`, such as `gemini:gemini-embedding-001`.
- `scripts/verify_chunk_storage.py` verified a fresh database, the `0001` → `0002` upgrade, legacy-table preservation, vector size, and an ORM round-trip.
- Verification uses `memorypalace_migration_check`, retained for inspection; the inserted verification row was rolled back.
- Legacy app code and card routes were removed when chunk retrieval and answers became functional in checklist 6; old database tables remain preserved.

### 4. Embedding providers

- [x] Implement one embedding interface used by ingestion, query, and re-embedding.
- [x] Implement Gemini and OpenAI adapters with 1536-dimensional output.
- [x] Use the same embedding model for stored chunks and questions, with provider-specific document/query settings where required.
- [x] Validate returned vector dimensions and handle API failures with bounded retries.
- [x] Test provider selection and error handling with mocked API calls.

Embedding adapters implemented October 11, 2026:

- `embed_text(text, purpose="document" | "query")` is the shared entry point for subsequent chunk ingestion and re-embedding work.
- `embedding_identity()` returns the configured `provider:model` for storage and retrieval checks.
- Gemini uses retrieval document/query task types; ingestion limits input size conservatively; OpenAI uses the same model for both purposes.
- Both request 1536 dimensions and validate/normalize finite nonzero vectors.
- Clients are created lazily with 30-second timeouts. Transient transport, rate-limit, and server failures get at most three attempts; authentication and validation failures are not retried.
- 14 mocked embedding tests passed with no AI API calls. Database setup now applies only to tests that require it.
- Model-mismatch protection in chunk retrieval and input token bounds remain in the ingestion/retrieval sections. Legacy cards do not record model identity; use the forthcoming chunk pipeline for safe provider switching.

### 5. File ingestion and chunking

- [x] Read UTF-8 text and Markdown files and retain their source names.
- [x] Implement chunking with the agreed size and overlap; skip empty content.
- [x] Embed chunks and persist content, source, chunk index, metadata, and model identity.
- [x] Implement the agreed duplicate/updated-file behavior.
- [x] Avoid partially replacing a source when embedding or storage fails.
- [x] Add a command-line script for a file or folder, with a useful ingestion summary.
- [x] Adapt the FastAPI ingest endpoint and validate its inputs.
- [x] Test chunk boundaries, empty files, ingestion failures, and re-ingestion behavior.

Ingestion implemented October 11, 2026:

- `python -m scripts.ingest docs` reads text/Markdown recursively; `--root` controls stable relative source paths.
- Chunk size uses tiktoken `cl100k_base`, targeting 500 tokens and 75-token overlap, with paragraph boundaries where practical and a conservative 2048-byte cap. This is not Gemini's native token count.
- Empty files are skipped without deleting existing chunks. Updated files replace their source's chunks after embeddings succeed, inside a transaction serialized by a per-source PostgreSQL advisory lock.
- `/ingest` accepts `source`, `content`, and optional `metadata`; returns source, chunk count, and chunk IDs. It does not accept server filesystem paths.
- Tests cover Unicode, chunk limits, overlap, empty files, invalid sources, re-ingestion, embedding failure, database rollback, and folder handling, using mocked embeddings.
- No real docs ingestion or paid embedding requests were performed. Search/answer endpoints and Telegram still need adaptation in subsequent sections.

### 6. Retrieval and answers

- [x] Embed the question and retrieve top-k chunks by cosine distance.
- [x] Prevent comparing a query with vectors from a different model, including during re-embedding.
- [x] Pass chunk content and source identifiers to Anthropic as context.
- [x] Ask the model to answer from the supplied material and say when it cannot answer.
- [x] Return the answer with source files actually cited; distinguish these from all retrieved candidates.
- [x] Adapt the query endpoint and validate question and top-k inputs.
- [x] Test retrieval ranking, model mismatch, empty results, and source reporting.

Retrieval and answers implemented October 11, 2026:

- `/search` ranks chunks by cosine similarity. `/ask` returns `answer`, unique cited `sources`, `cited_chunks`, and all `retrieved_chunks`.
- Mixed or mismatched model identities return HTTP 409 before query embedding. Retrieval also filters by configured identity to prevent cross-model comparisons during concurrent changes.
- Empty databases skip AI calls. Anthropic uses forced structured answer output; citations must identify retrieved chunks. No citations produce an insufficient-information response; unknown citations are rejected.
- Nonempty questions and top-k bounds (1–20) are validated. A valid citation identifies a retrieved source; it does not prove factual entailment, which still needs evaluation on real notes.
- Removed active card models, extraction, supersession code, and routes. Legacy database tables and migration history remain preserved.
- Full suite: 32 tests passed, all AI calls mocked. Telegram's old payloads still need adaptation in checklist 8.

### 7. Re-embedding

- [x] Add a script that regenerates embeddings from stored chunk content using the configured provider/model.
- [x] Update each vector and its model identity together.
- [x] Define safe behavior for interrupted runs so retrieval cannot mix embedding models.
- [x] Show progress, failures, and completion; make retrying an interrupted run safe.
- [x] Verify switching provider requires only configuration plus the script, with no code changes.

Re-embedding implementation:

- Run `python -m scripts.reembed` after changing provider/model settings; `--force` regenerates already-current vectors too.
- Commits each vector and its qualified model identity atomically. Failures retain old values; restarting skips completed rows.
- Conditional updates avoid overwriting content/model changes made concurrently. Pause ingestion and use one re-embedding process during a provider switch.
- Progress, failed chunk IDs, and mismatched-row counts are reported without submitted text or provider exception bodies. Failed/incomplete runs exit nonzero.
- Retrieval blocks mismatched/mixed identities. Provider switching, interruption/resume, and rollback tested with mocked embeddings; live provider validation remains checklist 9.

### 8. Telegram

- [x] Check the sender's Telegram user ID before processing any command or message.
- [x] Send questions to the query endpoint and display answers with source names.
- [x] Decide how plain messages and the existing `/ask` and `/search` commands should behave under the revised design.
- [x] Handle API failures and replies exceeding Telegram's message limit.
- [x] Test owner access and rejection of other accounts without invoking AI APIs.

Telegram implemented October 11, 2026:

- Plain text and `/ask` ask questions; `/search` shows source names, chunk indexes, scores, and excerpts. File ingestion remains in the CLI/API.
- Every handler checks the configured owner ID before network calls or replies. Bot startup requires the owner ID and token. Responses are restricted to private chats to avoid exposing notes in groups.
- Answers show cited source files. Long replies split safely within Telegram's UTF-16 length limit.
- Timeouts, invalid responses, validation errors, and model mismatches return concise messages without raw API exception bodies.
- 20 mocked Telegram/HTTP tests passed, including unauthorized users, groups, missing owner, owner requests, failures, and Unicode reply splitting.
- Live Telegram polling has not been started. Fill `TELEGRAM_OWNER_ID` and `TELEGRAM_BOT_TOKEN` before checklist 9's live validation.

### 9. Validate the local MVP

- [x] Update the existing tests for the chunk pipeline and run the suite.
- [x] Ingest a small folder of real notes and inspect stored chunks and metadata.
- [x] Ask questions with known answers and check both answers and cited sources.
- [x] Ask a question the notes cannot answer and inspect the response.
- [ ] Switch embedding providers, re-embed, and repeat the known-answer checks. **Deferred by Farhan: Gemini only for now; mocked provider-switch tests passed.**
- [x] Run the full flow through Telegram.
- [x] Update README commands and remove obsolete card-based instructions.

Live validation — October 11, 2026:

- Full automated suite: 57 passed.
- Live Gemini ingestion initially failed because `auto_truncate` is unsupported by the Gemini API. Removed that argument; 14 adapter tests passed afterward.
- Successfully ingested all 5 `docs/` files as 18 chunks using `gemini:gemini-embedding-001`.
- Live `/ask` through FastAPI's test client used Gemini query embeddings and Anthropic answers: the chunk-size question returned 500 tokens / 75 overlap with PRD and checklist sources.
- An unrelated refrigerator-serial-number question returned insufficient information and no sources.
- Telegram owner ID configured locally. Farhan confirmed the bot is responding on October 11, 2026; live Telegram flow passed.
- Live OpenAI provider switching is deferred by Farhan; Gemini remains the active provider. The OpenAI adapter remains available but has only mocked validation.

### 10. Deploy to a DigitalOcean Droplet

- [ ] Choose the Droplet and deploy PostgreSQL + pgvector in Docker.
- [ ] Install the app in a virtualenv and configure server-side environment variables.
- [ ] Apply migrations and ingest the initial notes.
- [ ] Run the API and bot as services that restart after failures and server reboots.
- [ ] Keep database and API access restricted to what the deployment requires.
- [ ] Verify logs and a basic database backup/restore procedure.
- [ ] Confirm answers and sources work through Telegram after a server restart.

Deployment preparation: `scripts/deploy.sh`, `deploy/compose.yml`, and
`deploy/README.md` are ready for server review. Local Bash syntax/help checks passed.
Server installation, service startup, reboot, and backup/restore remain unchecked
until verified on the Droplet.

### Phase 1 completion

- [ ] Real notes can be ingested and queried with useful, source-grounded answers.
- [ ] Provider switching and re-embedding work without code changes.
- [ ] The deployed bot responds only to Farhan.
- [ ] Explain chunking, embeddings, cosine retrieval, and answer assembly in your own words.

## Phase 2 — Quality and MCP

- [ ] Build a small evaluation set of questions, expected answers, and expected sources.
- [ ] Measure retrieval quality and tune chunk size, overlap, and top-k.
- [ ] Add useful metadata filters.
- [ ] Decide whether measured retrieval problems justify reranking.
- [ ] Expose search as an MCP server and test it from an AI client.
- [ ] Add PDFs or web pages based on actual source needs.

## Phase 3 — Optional agentic behavior

- [ ] Confirm Phases 1 and 2 work before defining this phase.
- [ ] Decide whether an agent adds value; cut this phase if it does not.
- [ ] If retained, define one small search task with limits on repeat searches.
- [ ] Compare the agent's results and cost with the existing RAG flow.
