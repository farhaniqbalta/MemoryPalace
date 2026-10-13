# MemoryPalace: Product Requirements Document

**Author:** Farhan · **Status:** Draft v0.2 · **Date:** October 13, 2026

## 1. Overview

MemoryPalace is a personal AI knowledge platform. You feed it your own documents and notes, then ask questions through a Telegram bot or the planned web interface and get answers grounded in that material. It is built first as a learning project: the point is to understand RAG, embeddings, MCP, and agentic AI by building them, not to ship a polished product.

## 2. Goals and non-goals

### Goals

- A working end-to-end RAG pipeline: ingest, chunk, embed, store, retrieve, answer.
- Hands-on understanding of embeddings and vector search with pgvector.
- Later phases introduce MCP and agentic behavior on top of a working base.
- Keep everything as simple as possible. Add complexity only when a real problem demands it.

### Non-goals (for now)

- Knowledge Cards and append-only versioning. Dropped from the MVP as unnecessary. Revisit later if needed; adding them would require schema, extraction, and retrieval changes.
- Local models (e.g. Ollama). Inference and embeddings use cloud APIs.
- Multi-user support and production-grade hardening. The web interface remains a single-user tool with basic access protection.
- Knowledge Graphs. Revisit only after the base system works.

## 3. User and use cases

The only user is Farhan, who has limited backend experience and prefers to discuss decisions before implementing them.

- Add a document or note to the knowledge base.
- Ask a question in Telegram and get an answer based on stored material, with the sources shown.
- Check which sources and chunks were used, to judge whether retrieval is working.
- Upload and browse sources and experiment with questions in a cozy illustrated web interface.

## 4. Scope by phase

### Phase 1: Core RAG (MVP)

- Postgres with pgvector running in Docker.
- Ingestion script for plain text and Markdown files.
- Chunking, embedding, and storage in a single table.
- FastAPI endpoints for ingest and query.
- Telegram bot that sends questions to the query endpoint and replies with the answer and sources.
- Deployed to a DigitalOcean Droplet.

### Phase 1 extension: Web interface (planned)

- Static HTML/CSS/JavaScript served by FastAPI; no React or separate frontend runtime.
- Cozy illustrated style, using generated image assets or simple flat SVGs for v1.
- Sidebar navigation: Sources, Playground, Processes, Settings.
- Build order: shell and Playground → Sources → Processes animation → Settings.
- Private access or HTTPS with authentication before exposing the interface publicly.

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
8. Updated sources: identify files by a stable relative source path; replace their chunks atomically after all replacement embeddings succeed. Empty files are skipped rather than deleting stored content.

### Web interface requirements (v1, planned)

1. Playground: a question text box displays the answer, cited source names, and supporting chunk text. Distinguish cited chunks from all retrieved candidates.
2. Sources: list stored source names and chunk counts; accept text/Markdown uploads with explicit size and type limits. Additional formats remain Phase 2 work.
3. Processes: loop a decorative four-stage illustration labeled extract, chunk, embed, store. It has no backend tie-in and must not imply real ingestion progress. Here, extract means reading source text, not Knowledge Card extraction.
4. Settings: show read-only provider/model information; do not expose API keys or allow provider switching through the v1 page.
5. Backend: mount static assets in FastAPI; add `GET /api/sources` and an upload endpoint. Reuse the query pipeline and return source names and chunk text. Decide route names and limits before implementation.
6. Optional source deletion: discuss scope and confirmation behavior before adding an endpoint that removes a source's chunks.
7. Access: choose Caddy with HTTPS and basic auth (requires a domain), or private access through Tailscale/Cloudflare Tunnel with appropriate access controls.
8. For public Caddy hosting, permit inbound 22/80/443 through the cloud firewall and ufw, keep PostgreSQL and the API bound to loopback, and add upload limits and basic rate limiting. Review Docker port publishing separately from ufw.
9. Right-hand System Status / Cozy Activity panel: decide whether it is decorative or shows real data such as chunk count and active embedding model. Decorative content must not present invented operational numbers as live measurements.

## 6. Technical decisions

| Area | Decision |
| --- | --- |
| LLM and embeddings | Cloud APIs. Gemini embeddings by default, switchable to OpenAI. |
| Embedding size | 1536 dimensions for both providers, so one vector(1536) column works for either. |
| Database | PostgreSQL with pgvector, chosen for pgvector's maturity. |
| Docker | Database only. App components run natively in a virtualenv for faster iteration. |
| App stack | FastAPI, uvicorn, SQLAlchemy, psycopg 3 (`psycopg[binary]`), alembic, python-telegram-bot, tenacity, pytest, httpx. |
| SDKs | Anthropic (`claude-haiku-5-5`) for answers; Gemini and OpenAI SDKs for embeddings. |
| Hosting | DigitalOcean Droplet upgraded to 1 GB RAM on October 13, 2026; keep the app lightweight. Swap was added to address deployment OOM. |
| Deployment | GitHub Actions on pushes to `main`, SSH to Droplet, fetch the pushed commit, run deployment script, restart systemd services. |
| Web stack | Planned static HTML/CSS/JavaScript served by FastAPI. |
| Web access | Caddy HTTPS/basic auth with a domain, or private-access alternative; final choice pending. |

## 7. Data model

One active knowledge table:

- `chunks`: `id`, `source`, `chunk_index`, `content`, `metadata` (JSON), `embedding` (`vector(1536)`), `embedding_model`, `created_at`.

The `embedding_model` column records the qualified provider/model identity that produced each vector. Vectors from different models are not comparable, so a provider switch requires re-embedding every row.

## 8. Success criteria

- Ingest a folder of real notes and ask questions whose answers are clearly in them. Most answers should be correct and cite the right source.
- Switch the embedding provider with one setting plus a re-embed run, with no code changes.
- The whole system runs on the Droplet and is reachable through Telegram after service/server restarts.
- For the web extension, Farhan can upload a source, ask a question, and inspect cited chunks behind the chosen access controls.
- Pushes to `main` trigger automated deployment; service status and logs make failures inspectable.
- You can explain to someone else how each part works: chunking, embeddings, similarity search, and how the answer is assembled.

## 9. Risks

- Memory: the original 512 MB Droplet encountered OOM during dependency installation. Keep the web layer lightweight, monitor RAM/swap, and resize if needed.
- Web exposure: uploads and private knowledge require authentication, request limits, and loopback database/API binding.
- Scope creep: Phase 3 is the main risk. Do not start it before Phase 1 and 2 work.
- Privacy: Gemini's free tier may use submitted content to improve Google's products. Keep private material out until you accept that tradeoff, or switch to OpenAI.
- Poor retrieval: weak answers usually come from chunking choices, not the embedding model. Plan time to tune.
- Provider changes: model names, limits, and free-tier terms change. Verify them in the vendors' docs before relying on them.

## 10. Starting decisions and remaining questions

Starting decisions agreed October 11, 2026:

- Answers: `claude-haiku-5-5`, evaluated on the initial notes.
- First ingestion: this repo's `docs/` folder, initially 5 Markdown files (approximately 16 KiB).
- Chunking: target 500 tokens with 75-token overlap, preserving paragraph boundaries where possible. Use tiktoken `cl100k_base` with a conservative byte cap; this is not Gemini's native tokenizer.
- Updated files: use a stable relative source path and replace that source's chunks in one transaction after all new embeddings succeed.
- Embeddings: Gemini `gemini-embedding-001` by default; OpenAI `text-embedding-3-small` as the alternative, both configured for 1536 dimensions.
- Migration: add chunk storage while preserving existing tables; inspect existing data before considering their removal.
- Database driver: retain the existing psycopg 3 driver.

### Current implementation and deployment status

- Phase 1 core RAG implemented and deployed; Farhan confirmed Telegram responses and automatic SSH deployment. Deployment OOM was confirmed and addressed with swap.
- Ingestion, search, and answers use chunks; active Knowledge Card extraction, models, and routes are removed. Legacy database tables remain under the additive migration history.
- `app/core/embeddings.py` exposes `embed_text(..., purpose="document" | "query")` and `embedding_identity()`. The transfer note's `embed_documents` / `embed_query` names are not the current API.
- Re-embedding is already implemented: `python -m scripts.reembed`, with per-row atomic updates, resume behavior, and mixed-model retrieval blocking.
- Gemini is active. Live OpenAI provider switching is deferred by Farhan; mocked switch tests passed.
- Live validation ingested 5 repository docs into 18 chunks, answered a known question with sources, and declined an unsupported question. Automated suite had 57 passing tests at that validation point.
- The local HTML/CSS/JS interface includes Playground, a decorative sunset Processes animation, Sources listing/upload (UTF-8 text/Markdown, 64 KiB limit), and read-only Settings from actual configuration. Web authentication, rate limiting, and browser end-to-end validation remain pending. Reboot persistence and backup/restore verification remain outstanding unless separately confirmed.

### Remaining design questions

- Should the right-hand status panel be decorative, show real counts/provider information, or combine both with clear labels?
- Keep the current Anthropic answer provider, or evaluate Gemini answers? Anthropic `claude-haiku-5-5` remains the accepted default until a new decision is made.
- What domain and access approach should the web page use?
- What upload size limit and rate limits fit the 1 GB server?
- Should source deletion be included in web v1?
- Start Phase 2 with an evaluation set or the MCP search server?
- Is plain top-k retrieval sufficient, or do evaluation results justify reranking?

Re-ingestion is already decided: replace a source's chunks atomically; skipping
duplicates is not the current policy. Discuss design changes before implementing
new behavior. Keep Phase 3 optional until the base and Phase 2 work.
