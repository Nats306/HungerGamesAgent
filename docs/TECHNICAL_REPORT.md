# Technical Report — Hunger Games Agent

> Fields marked **TODO** must be completed after deploying and running the evaluation.

**Team:** TODO · **Course:** Implementación e Integración de Software · **Date:** TODO

## 1. Overview

Hunger Games Agent is a web application where authenticated users ask questions about *The
Hunger Games* saga and get answers grounded in a private knowledge base. It is built on a RAG
(Retrieval-Augmented Generation) architecture orchestrated with LangGraph, uses a local LLM served
by Ollama, and stores embeddings in PostgreSQL with pgvector. Users can upload new documents to
expand the knowledge base.

**Why this topic:** the saga has five novels, dozens of characters, thirteen districts and
several Games, which allows varied questions (facts, relationships, events, definitions), and
there is a large amount of openly licensed material (The Hunger Games Wiki and Wikipedia, CC BY-SA).

## 2. Architecture

```
 Browser (React SPA on Vercel)
   │  1. login / register (OIDC Authorization Code + PKCE)
   ├───────────────────────────────► Keycloak (realm hunger-games)
   │  2. REST calls with Bearer JWT
   ▼
 FastAPI backend (EC2, Docker) ── validates JWT (JWKS, iss, aud, exp)
   ├── routers/      controllers
   ├── services/     chat, documents, ingestion, embeddings
   ├── agent/        LangGraph graph ──► Ollama (qwen2.5:3b)
   └── repositories/ SQLAlchemy ──────► PostgreSQL 16 + pgvector
```

| Component | Technology | Deployed on |
|---|---|---|
| Frontend | React 18, Vite, TypeScript, keycloak-js | Vercel |
| Backend | FastAPI, SQLAlchemy 2 | AWS EC2 (Docker Compose) |
| Authentication | Keycloak 26 | AWS EC2 (same host) |
| Agent | LangGraph + LangChain | inside the backend |
| LLM | qwen2.5:3b on Ollama | AWS EC2 (same host) |
| Embeddings | intfloat/multilingual-e5-small | inside the backend (CPU) |
| Vector DB | PostgreSQL + pgvector (HNSW, cosine) | AWS EC2 (same host) |
| HTTPS | Caddy + Let's Encrypt | AWS EC2 |

### 2.1 Data model

- `documents` — id, filename, title, source_url, status (`processing`/`ready`/`failed`), chunk_count, uploaded_by.
- `chunks` — id, document_id (FK, cascade), chunk_index, content, meta (page/section), embedding `vector(384)`.
- `conversations` — id, user_id (Keycloak `sub`), title, timestamps.
- `messages` — id, conversation_id, role, content, status, sources (JSONB).

Every chunk is linked to its original document, and the search query joins both tables so each
fragment returned to the agent carries its title, URL and page.

## 3. Authentication and authorization

- Keycloak realm `hunger-games` with self-registration enabled, roles `user` (default) and `admin`.
- Public client `hga-frontend` using Authorization Code + PKCE (S256). The frontend only renders
  the app when `keycloak.init` reports an authenticated session; tokens are refreshed
  automatically before each API call; logout ends the Keycloak session.
- An audience mapper adds `hga-api` to the access token. The backend validates signature (RS256,
  keys from the realm JWKS), `iss`, `aud` and `exp` on every request. No endpoint except
  `/health` is public (covered by `tests/test_auth.py`).
- Authorization rules: users only see their own conversations; a document can be deleted by
  its uploader or by an `admin`.

## 4. Document ingestion

1. Frontend sends the file (`multipart/form-data`) to `POST /api/documents`.
2. The backend validates type and size, creates the document with status `processing` and returns 202.
3. Background task: text extraction (PyMuPDF for PDF — one section per page —, python-docx, CSV
   rows as `column: value`, Markdown split by headings).
4. Split with `RecursiveCharacterTextSplitter` (900 characters, 150 overlap).
5. Embeddings with multilingual-e5-small (`passage:` prefix, normalized vectors).
6. Insert chunks into pgvector; status becomes `ready` (or `failed` with the error).
7. The frontend polls the document and shows a confirmation with the number of fragments.

Base knowledge: `scripts/scrape_wiki.py` downloads ~100 pages (characters, districts, Games,
books) from The Hunger Games Wiki and Wikipedia through the MediaWiki API and stores them as
Markdown with their source URL; `scripts/seed.py` loads them. **TODO:** final number of documents and chunks.

## 5. Agent (LangGraph)

| Node | Responsibility |
|---|---|
| `validate_intent` | Detects greetings / unclear input (regex + LLM in JSON mode) and rewrites the question as a standalone English search query using the conversation history. |
| `retrieve` | Embeds the query (`query:` prefix), searches top-k=6 by cosine similarity with both the rewritten and the original question, and **drops chunks below the similarity threshold**. |
| `grade_context` | **Dedicated validation node**: the LLM decides whether the fragments contain the answer (JSON `{"sufficient": bool}`). |
| `generate` | Answers with a **strict prompt** (only the numbered fragments, cite `[n]`, reply `NO_ANSWER` if the answer is not there), temperature 0. |
| `reject` | Returns the **explicit rejection**: "I don't have enough information in my knowledge base to answer that question." + suggestion to upload documents. |
| `greet` / `ask_clarification` | Fixed replies, no retrieval. |
| `save_history` | Stores the question and the answer (with status and sources) in the conversation. |

Conditional edges send the flow to `reject` whenever a check fails, so the model is never asked
to answer without supporting context.

### 5.1 Hallucination control

| Strategy (from the assignment) | Implementation |
|---|---|
| Minimum similarity threshold | `SIMILARITY_THRESHOLD` in `retrieve` |
| Context verification before answering | `grade_context` node |
| Prompt that forces answering only with retrieved info | `ANSWER_SYSTEM` in `agent/prompts.py` |
| LangGraph node that validates the context | `grade_context` + conditional edges |
| Explicit rejection answers | `reject` node + `NO_ANSWER` sentinel |
| Showing sources / fragments | `sources` in every answer, rendered in the chat |

## 6. Local model

**Chosen model:** `qwen2.5:3b` (Q4_K_M quantization in Ollama, ~1.9 GB on disk).

**Why:**
- Runs on CPU with ~3 GB of RAM, so it fits on an 8 GB VM together with Keycloak and Postgres.
- Among 3B-class models it follows instructions and JSON output reliably, which the router and the grader need.
- Good multilingual support: users can ask in Spanish even though the knowledge base is in English.

**How it runs:** Ollama container (`ollama/ollama`) exposes `:11434` only inside the Docker
network; the `ollama-pull` container downloads the model on first start; the backend calls it
through `langchain-ollama` (`ChatOllama`, temperature 0, `num_ctx` 4096, `format="json"` for the
classifier and the grader).

**Embeddings:** `intfloat/multilingual-e5-small` (384 dimensions, ~120 MB) through Sentence
Transformers, downloaded at image build time. Multilingual, so a Spanish question matches English passages.

**Alternatives considered:** llama3.2:3b (similar quality, weaker JSON), phi3.5 (3.8B, slower on
CPU), mistral 7B / llama3.1 8B (better answers but need ~6–8 GB RAM and 2–3× the latency).

**Limitations found:** **TODO** (fill with real observations). Expected ones: CPU latency of
5–15 s per answer (three LLM calls per question); the 3B model sometimes paraphrases instead of
citing; the grader occasionally rejects answerable questions (false rejections); context limited
to 4096 tokens.

## 7. Evaluation

`scripts/evaluate.py` runs 30 questions (20 answerable, 10 that must be rejected: off-topic or
details that are not in the base) against the deployed stack.

**TODO:** paste `backend/eval/results.md` here and comment on the threshold chosen (compare, for
example, 0.78 / 0.80 / 0.82 / 0.85).

## 8. Deployment

| Item | Value |
|---|---|
| Frontend URL | **TODO** `https://<app>.vercel.app` |
| Backend URL | **TODO** `https://api.<ip>.sslip.io` (docs at `/docs`) |
| Keycloak URL | **TODO** `https://auth.<ip>.sslip.io` |
| Server | AWS EC2 t3.large, Ubuntu 24.04, Elastic IP |

Process, environment variables and troubleshooting: see `deploy/DEPLOY.md`.

### 8.1 Problems found during deployment

**TODO:** list the real problems and how they were solved. Common ones with this stack:
- Token issuer mismatch between the internal (`keycloak:8080`) and public Keycloak URLs → fixed with `KC_HOSTNAME` + separate `KEYCLOAK_JWKS_URL`.
- Mixed content (HTTPS frontend → HTTP API) → Caddy with automatic certificates.
- Keycloak redirect URI for the Vercel domain.
- Memory limits: the LLM does not fit on free PaaS tiers → EC2 t3.large.

## 9. How to run

See `README.md`.
