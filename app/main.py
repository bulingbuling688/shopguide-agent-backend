from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agent import run_recommendation
from .conversation import SQLiteConversationStore
from .models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    RecommendRequest,
    RecommendResponse,
    Recommendation,
    SearchRequest,
    SearchResponse,
)
from .retrievers import HybridRetriever


APP_VERSION = "0.1.0"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shopguide.db")
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="ShopGuide Agent Backend",
    description="Multi-turn shopping guide and product retrieval Agent backend.",
    version=APP_VERSION,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = HybridRetriever()
store = SQLiteConversationStore(DATABASE_URL)


@app.get("/health", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="shopguide-agent-backend", version=APP_VERSION)


@app.post("/rag/search", response_model=SearchResponse)
@app.post("/api/rag/search", response_model=SearchResponse)
def rag_search(payload: SearchRequest) -> SearchResponse:
    matches = retriever.search(
        payload.query,
        top_k=payload.top_k,
        category=payload.category,
        max_price=payload.max_price,
    )
    return SearchResponse(query=payload.query, matches=matches)


@app.post("/recommend", response_model=RecommendResponse)
@app.post("/api/recommend", response_model=RecommendResponse)
def recommend(payload: RecommendRequest) -> RecommendResponse:
    state = run_recommendation(
        query=payload.query,
        top_k=payload.top_k,
        category=payload.category,
        max_price=payload.max_price,
    )
    return RecommendResponse(
        query=payload.query,
        intent=state.get("intent", {}),
        needs_clarification=bool(state.get("needs_clarification")),
        clarification_question=state.get("clarification_question"),
        recommendations=state.get("recommendations", []),
        trace=state.get("trace", []),
    )


@app.post("/chat", response_model=ChatResponse)
@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    version, _ = store.append(payload.session_id, "user", payload.message)
    state = run_recommendation(query=payload.message, top_k=payload.top_k)
    answer = state.get("answer", "")
    version, _ = store.append(payload.session_id, "assistant", answer)
    return ChatResponse(
        session_id=payload.session_id,
        version=version,
        answer=answer,
        recommendations=state.get("recommendations", []),
        trace=state.get("trace", []),
    )


async def stream_events(response: ChatResponse):
    chunks = [
        {"event": "session", "data": {"session_id": response.session_id, "version": response.version}},
        {"event": "trace", "data": response.trace},
        {"event": "recommendations", "data": [item.model_dump() for item in response.recommendations]},
    ]
    for chunk in chunks:
        yield f"event: {chunk['event']}\ndata: {json.dumps(chunk['data'], ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.04)
    for index, char in enumerate(response.answer):
        yield f"event: token\ndata: {json.dumps({'index': index, 'text': char}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.006)
    yield "event: done\ndata: {}\n\n"


@app.post("/chat/stream")
@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    response = chat(payload)
    return StreamingResponse(stream_events(response), media_type="text/event-stream")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
