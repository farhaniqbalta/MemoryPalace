# Architecture Cheat Sheet

```text
User -> LLM
      |-> RAG -> Knowledge Cards
      |-> MCP -> GitHub/Jira/Confluence
```

- Knowledge Cards: structured knowledge
- Embeddings: semantic vectors
- Vector Search: searches embeddings
- Knowledge Graph: entity relationships
- RAG: retrieve historical knowledge
- MCP: access live tools


# Expanded Arhitecture
                     User

                       │

                       ▼

                  AI Assistant

                       │

              ┌────────┴─────────┐

              ▼                  ▼

      Historical Memory      Live Systems

           (RAG)                (MCP)

              │                  │

              ▼                  ▼

      Knowledge Cards      GitHub / Jira

      Embeddings           Calendar

      Knowledge Graph      Email

              │

              ▼

      PostgreSQL