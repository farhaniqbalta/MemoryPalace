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

- [ ] Add the `chunks` model: id, source, chunk_index, content, metadata, embedding, embedding_model, created_at.
- [ ] Use a `vector(1536)` column and record an unambiguous provider/model identity.
- [ ] Create an Alembic migration, following the agreed handling of existing data.
- [ ] Verify migration on a fresh database and on the existing schema.
- [ ] Remove obsolete card models, extraction, supersession, and routes once their replacements work.

### 4. Embedding providers

- [ ] Implement one embedding interface used by ingestion, query, and re-embedding.
- [ ] Implement Gemini and OpenAI adapters with 1536-dimensional output.
- [ ] Use the same embedding model for stored chunks and questions, with provider-specific document/query settings where required.
- [ ] Validate returned vector dimensions and handle API failures with bounded retries.
- [ ] Test provider selection and error handling with mocked API calls.

### 5. File ingestion and chunking

- [ ] Read UTF-8 text and Markdown files and retain their source names.
- [ ] Implement chunking with the agreed size and overlap; skip empty content.
- [ ] Embed chunks and persist content, source, chunk index, metadata, and model identity.
- [ ] Implement the agreed duplicate/updated-file behavior.
- [ ] Avoid partially replacing a source when embedding or storage fails.
- [ ] Add a command-line script for a file or folder, with a useful ingestion summary.
- [ ] Adapt the FastAPI ingest endpoint and validate its inputs.
- [ ] Test chunk boundaries, empty files, ingestion failures, and re-ingestion behavior.

### 6. Retrieval and answers

- [ ] Embed the question and retrieve top-k chunks by cosine distance.
- [ ] Prevent comparing a query with vectors from a different model, including during re-embedding.
- [ ] Pass chunk content and source identifiers to Anthropic as context.
- [ ] Ask the model to answer from the supplied material and say when it cannot answer.
- [ ] Return the answer with source files actually cited; distinguish these from all retrieved candidates.
- [ ] Adapt the query endpoint and validate question and top-k inputs.
- [ ] Test retrieval ranking, model mismatch, empty results, and source reporting.

### 7. Re-embedding

- [ ] Add a script that regenerates embeddings from stored chunk content using the configured provider/model.
- [ ] Update each vector and its model identity together.
- [ ] Define safe behavior for interrupted runs so retrieval cannot mix embedding models.
- [ ] Show progress, failures, and completion; make retrying an interrupted run safe.
- [ ] Verify switching provider requires only configuration plus the script, with no code changes.

### 8. Telegram

- [ ] Check the sender's Telegram user ID before processing any command or message.
- [ ] Send questions to the query endpoint and display answers with source names.
- [ ] Decide how plain messages and the existing `/ask` and `/search` commands should behave under the revised design.
- [ ] Handle API failures and replies exceeding Telegram's message limit.
- [ ] Test owner access and rejection of other accounts without invoking AI APIs.

### 9. Validate the local MVP

- [ ] Update the existing tests for the chunk pipeline and run the suite.
- [ ] Ingest a small folder of real notes and inspect stored chunks and metadata.
- [ ] Ask questions with known answers and check both answers and cited sources.
- [ ] Ask a question the notes cannot answer and inspect the response.
- [ ] Switch embedding providers, re-embed, and repeat the known-answer checks.
- [ ] Run the full flow through Telegram.
- [ ] Update README commands and remove obsolete card-based instructions.

### 10. Deploy to a DigitalOcean Droplet

- [ ] Choose the Droplet and deploy PostgreSQL + pgvector in Docker.
- [ ] Install the app in a virtualenv and configure server-side environment variables.
- [ ] Apply migrations and ingest the initial notes.
- [ ] Run the API and bot as services that restart after failures and server reboots.
- [ ] Keep database and API access restricted to what the deployment requires.
- [ ] Verify logs and a basic database backup/restore procedure.
- [ ] Confirm answers and sources work through Telegram after a server restart.

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
