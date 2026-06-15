from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str
    title: str
    category: str
    brand: str
    price: float
    rating: float
    tags: list[str]
    features: list[str]
    stock: int
    description: str

    def searchable_text(self) -> str:
        return " ".join(
            [
                self.title,
                self.category,
                self.brand,
                " ".join(self.tags),
                " ".join(self.features),
                self.description,
            ]
        )


class ProductMatch(BaseModel):
    product: Product
    score: float = Field(ge=0)
    reasons: list[str]
    source: Literal["keyword", "vector", "hybrid"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    category: str | None = None
    max_price: float | None = Field(default=None, gt=0)


class SearchResponse(BaseModel):
    query: str
    matches: list[ProductMatch]


class RecommendRequest(SearchRequest):
    session_id: str | None = None


class Recommendation(BaseModel):
    product_id: str
    title: str
    price: float
    score: float
    reasons: list[str]
    caveats: list[str] = []


class RecommendResponse(BaseModel):
    query: str
    intent: dict[str, Any]
    needs_clarification: bool
    clarification_question: str | None
    recommendations: list[Recommendation]
    trace: list[dict[str, Any]]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(default="default", min_length=1)
    top_k: int = Field(default=4, ge=1, le=10)


class ChatResponse(BaseModel):
    session_id: str
    version: int
    answer: str
    recommendations: list[Recommendation]
    trace: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
