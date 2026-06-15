# ShopGuide Agent Backend

## Online URL

Production target:

```text
https://shopguide-agent-backend.chatapi.fun
```

Status: deployed.

## Overview

ShopGuide Agent Backend is a FastAPI service for multi-turn e-commerce shopping guidance and product retrieval.

It is built for shopping assistant scenarios where users describe vague needs such as budget, usage context, product category, preferences, or exclusions. The backend parses intent, retrieves products, ranks candidates, explains recommendations, keeps conversation state, and streams generated responses to the frontend through SSE.

The current version is designed as an interview-ready backend project: it exposes real API endpoints, uses a LangGraph workflow, supports hybrid retrieval with ChromaDB indexing plus keyword matching, and keeps session state in SQLite.

## Features

- `/recommend` endpoint for structured shopping recommendations.
- `/rag/search` endpoint for hybrid product retrieval.
- `/chat` endpoint for multi-turn shopping conversation.
- `/chat/stream` endpoint for Server-Sent Events token streaming.
- LangGraph workflow for intent parsing, product retrieval, ranking, explanation, and response generation.
- KeywordRetriever, VectorRetriever, and HybridRetriever components.
- ChromaDB product index with lightweight local embeddings.
- SQLiteConversationStore with per-session lock and version counter.
- OpenAI-compatible API integration with deterministic fallback when no key is configured.
- Tests covering health checks, retrieval, recommendation, clarification, chat persistence, and SSE streaming.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI |
| Agent Orchestration | LangGraph |
| Retrieval | ChromaDB, keyword retrieval, lightweight vector retrieval |
| Data Model | Pydantic |
| Session Store | SQLite |
| Streaming | SSE |
| Testing | pytest, FastAPI TestClient |
| LLM Provider | OpenAI-compatible API, optional |
| Deployment Style | FastAPI systemd service reverse-proxied by Nginx |

## Local Development

Recommended Python version: 3.11 or 3.12. Python 3.14 may fail on native dependencies such as `pydantic-core` and `tokenizers`.

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Local URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```bash
pytest -q
```

## Environment Variables

| Name | Purpose | Required | Example |
|---|---|---|---|
| APP_HOST | Backend bind host | No | 127.0.0.1 |
| APP_PORT | Backend internal port | No | 18083 |
| DATABASE_URL | SQLite conversation database | No | sqlite:///./shopguide.db |
| CHROMA_DIR | ChromaDB persistence directory placeholder | No | ./.chroma |
| OPENAI_COMPATIBLE_API_KEY | Optional LLM API key | No | sk-*** |
| OPENAI_COMPATIBLE_BASE_URL | Optional OpenAI-compatible API base URL | No | https://api.openai.com/v1 |
| OPENAI_COMPATIBLE_MODEL | Optional model name | No | gpt-4o-mini |

Do not commit real credentials. Runtime secrets belong only in the VPS environment file.

## Deployment

Project slug:

```text
shopguide-agent-backend
```

GitHub repo:

```text
https://github.com/bulingbuling688/shopguide-agent-backend
```

VPS:

```text
34.81.224.158
```

VPS path:

```text
/opt/apps/shopguide-agent-backend
```

Runtime:

```text
FastAPI systemd service behind Nginx
```

Build command:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Start command:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 18083
```

Internal port:

```text
18083
```

Public domain:

```text
https://shopguide-agent-backend.chatapi.fun
```

Nginx config:

```text
/etc/nginx/sites-available/shopguide-agent-backend.conf
```

Cloudflare DNS:

```text
A shopguide-agent-backend -> 34.81.224.158, proxied
```

Environment file:

```text
/opt/apps/shopguide-agent-backend/.env.production
```

## Directory Structure

```text
shopguide-agent-backend/
  app/
    agent.py
    catalog.py
    conversation.py
    llm.py
    main.py
    models.py
    retrievers.py
  data/
    products.json
  tests/
    test_api.py
  .env.example
  .gitignore
  pytest.ini
  requirements.txt
  README.md
```

## Common Commands

Run tests:

```bash
pytest -q
```

Check service status:

```bash
sudo systemctl status shopguide-agent-backend
```

Restart service:

```bash
sudo systemctl restart shopguide-agent-backend
```

View logs:

```bash
sudo journalctl -u shopguide-agent-backend -f
```

Reload Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Smoke test:

```bash
curl https://shopguide-agent-backend.chatapi.fun/health
curl -X POST https://shopguide-agent-backend.chatapi.fun/recommend \
  -H "Content-Type: application/json" \
  -d '{"query":"我想买轻薄办公笔记本，预算 6000","top_k":3}'
```

## Maintenance Notes

- Keep recommendation filters deterministic; use the LLM only for final natural-language response generation.
- Store real LLM keys only in `/opt/apps/shopguide-agent-backend/.env.production`.
- Do not commit `.env`, SQLite databases, ChromaDB directories, logs, or virtual environments.
- If ChromaDB fails at runtime, the retriever falls back to local lightweight vector scoring.
