# SEREY Chatbot Backend (AI Builder API)

FastAPI backend for the SEREY AI assistant and landing-page builder.

This service provides:
- a SEREY knowledge chatbot,
- a one-shot landing page blueprint generator,
- a conversational landing page builder,
- scheduled knowledge synchronization into ChromaDB.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Local Setup](#local-setup)
- [Run with Docker](#run-with-docker)
- [Data and Indexing](#data-and-indexing)
- [API Endpoints](#api-endpoints)
- [Example Requests](#example-requests)

## Features

- `POST /api/chat` for SEREY platform Q&A with optional flow modes.
- `POST /api/generate-blueprint` for one-shot landing page JSON generation.
- `POST /api/builder/chat` for conversational page updates (blueprint or patches).
- ChromaDB-backed semantic search and memory.
- Startup + daily scheduled knowledge sync from live SEREY APIs.
- Health/readiness checks for deployment.

## Tech Stack

- Python 3.12
- FastAPI + Uvicorn
- Google Gemini (`gemini-2.5-flash`)
- ChromaDB (persistent local vector store)
- APScheduler (daily cron sync)

## Project Structure

```text
.
|-- main.py
|-- requirements.txt
|-- Dockerfile
|-- routes/
|   |-- chat.py
|   |-- builder.py
|   `-- builder_chat.py
|-- services/
|   |-- gemini.py
|   |-- search.py
|   |-- memory.py
|   `-- knowledge_sync.py
|-- schemas/
|   |-- chat.py
|   |-- requests.py
|   `-- blueprint.py
|-- scripts/
|   |-- index_components.py
|   |-- index_serey_knowledge.py
|   `-- test_gemini.py
`-- chroma_db/
```

## Prerequisites

- Python `3.12+`
- A valid Google Gemini API key (`GOOGLE_API_KEY`)

## Environment Variables

Create a `.env` file in the project root. You can start from `.env.example`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_API_KEY` | Yes | - | Gemini API key used by AI generation/chat |
| `MEM0_API_KEY` | No | - | Reserved for Mem0 integration (if used) |
| `CHAT_API_KEY` | No | empty | If set, `POST /api/chat` and `POST /api/builder/chat` require `X-Serey-Api-Key` |
| `ADMIN_API_KEY` | No | empty | If set, `POST /api/admin/sync-knowledge` requires `Authorization: Bearer <key>` |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Comma-separated allowed origins |
| `SYNC_CRON_HOUR` | No | `2` | Daily knowledge sync hour (server time) |
| `SYNC_CRON_MINUTE` | No | `0` | Daily knowledge sync minute |

Minimal `.env` example:

```env
GOOGLE_API_KEY=your_google_gemini_api_key_here
MEM0_API_KEY=optional_mem0_key
CHAT_API_KEY=optional_chat_key
ADMIN_API_KEY=optional_admin_key
CORS_ORIGINS=http://localhost:3000
SYNC_CRON_HOUR=2
SYNC_CRON_MINUTE=0
```

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start the API:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open:
- `http://localhost:8000/docs` (Swagger UI)
- `http://localhost:8000/health`

## Run with Docker

Build image:

```powershell
docker build -t serey-chatbot .
```

Run container:

```powershell
docker run --rm -p 8000:8000 --env-file .env serey-chatbot
```

## Data and Indexing

- ChromaDB data is stored in `./chroma_db`.
- Components collection must exist for readiness checks.

Index components:

```powershell
python scripts/index_components.py
```

Optional one-time static knowledge indexing:

```powershell
python scripts/index_serey_knowledge.py
```

Live knowledge sync behavior:
- runs once during app startup,
- then runs daily at `SYNC_CRON_HOUR:SYNC_CRON_MINUTE`,
- can be triggered manually via `POST /api/admin/sync-knowledge`.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Basic liveness check |
| `GET` | `/ready` | Readiness check (Gemini reachable + components indexed) |
| `POST` | `/api/chat` | SEREY chatbot with optional links and flow modes |
| `POST` | `/api/generate-blueprint` | Generate full landing page blueprint |
| `POST` | `/api/builder/chat` | Conversational page building (reply + blueprint/patches) |
| `POST` | `/api/admin/sync-knowledge` | Manual knowledge synchronization |
| `GET` | `/api/components` | List supported section types |

## Example Requests

### 1) Chat

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-Serey-Api-Key: your_chat_api_key_if_enabled" \
  -d '{
    "message": "How do I open a shop on Serey?",
    "user_id": "user_123",
    "session_id": "session_abc",
    "flow": "post_guide"
  }'
```

### 2) Generate Blueprint (one-shot)

```bash
curl -X POST http://localhost:8000/api/generate-blueprint \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Build a bold restaurant landing page",
    "user_id": "user_123",
    "session_id": "session_builder_1",
    "n_components": 4
  }'
```

### 3) Builder Chat (iterative)

```bash
curl -X POST http://localhost:8000/api/builder/chat \
  -H "Content-Type: application/json" \
  -H "X-Serey-Api-Key: your_chat_api_key_if_enabled" \
  -d '{
    "message": "Change hero style to 2 and make accent red",
    "user_id": "user_123",
    "session_id": "session_builder_1",
    "community_id": 57,
    "page_context": "{\"community_id\":57,\"content\":[{\"type\":\"HERO\"}]}"
  }'
```

Response contract highlights for `POST /api/builder/chat`:

- `sections_used`: visible section types (lowercase) in final layout order.
- `sections_hidden`: hidden section types (lowercase) in final layout order.
- `styles_selected`: final style state per section (`section`, `style`, `is_hidden`, optional `style_reason`).
- `color_tokens`: backend policy-selected palette (`site_type`, `palette_family`, `title`, `accent`, `body`, `bg`, `subtitle`, `accent_usage_max`).
- `uploads_needed`: server-derived upload prompts based on final visible layout + style.
  Hidden sections and non-image styles (for example ABOUT style 5/6/8) are excluded.

### 4) Manual Knowledge Sync (admin)

```bash
curl -X POST http://localhost:8000/api/admin/sync-knowledge \
  -H "Authorization: Bearer your_admin_api_key"
```

## Notes

- `GET /ready` returns `503` if:
  - components are not indexed (`python scripts/index_components.py`), or
  - Gemini is not reachable (`GOOGLE_API_KEY` missing/invalid).
- Chat/builder endpoints skip API key checks if `CHAT_API_KEY` is unset.
- Admin sync endpoint skips auth checks if `ADMIN_API_KEY` is unset.
