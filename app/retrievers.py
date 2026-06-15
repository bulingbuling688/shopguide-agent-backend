from __future__ import annotations

import math
import os
import re
from collections import Counter
from hashlib import sha256

try:
    import chromadb
    from chromadb.config import Settings
except Exception:  # pragma: no cover - optional runtime fallback
    chromadb = None
    Settings = None

from .catalog import load_products
from .models import Product, ProductMatch


os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]")
EMBEDDING_DIM = 64


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def cosine(left: Counter[str], right: Counter[str]) -> float:
    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def simple_embedding(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    for token in tokenize(text):
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIM
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


class KeywordRetriever:
    def __init__(self, products: list[Product] | None = None):
        self.products = products or load_products()

    def search(self, query: str, top_k: int = 5, category: str | None = None, max_price: float | None = None) -> list[ProductMatch]:
        query_tokens = tokenize(query)
        query_set = set(query_tokens)
        matches: list[ProductMatch] = []
        for product in self.products:
            if category and category not in product.category:
                continue
            if max_price and product.price > max_price:
                continue
            tokens = tokenize(product.searchable_text())
            overlap = query_set & set(tokens)
            category_bonus = 0.2 if product.category in query else 0.0
            tag_bonus = sum(0.08 for tag in product.tags if tag in query)
            score = len(overlap) * 0.18 + category_bonus + tag_bonus + product.rating * 0.02
            if score <= 0:
                continue
            reasons = [f"匹配关键词：{token}" for token in list(overlap)[:4]]
            if category_bonus:
                reasons.append(f"命中品类：{product.category}")
            matches.append(ProductMatch(product=product, score=round(score, 4), reasons=reasons, source="keyword"))
        return sorted(matches, key=lambda item: item.score, reverse=True)[:top_k]


class VectorRetriever:
    def __init__(self, products: list[Product] | None = None):
        self.products = products or load_products()
        self.product_vectors = {
            product.id: Counter(tokenize(product.searchable_text())) for product in self.products
        }
        self._collection = None
        if chromadb is not None and Settings is not None:
            try:
                client = chromadb.Client(Settings(anonymized_telemetry=False, is_persistent=False))
                self._collection = client.get_or_create_collection("shopguide_products")
                existing = set(self._collection.get(include=[])["ids"])
                for product in self.products:
                    if product.id not in existing:
                        self._collection.add(
                            ids=[product.id],
                            documents=[product.searchable_text()],
                            embeddings=[simple_embedding(product.searchable_text())],
                            metadatas=[{"category": product.category, "price": product.price}],
                        )
            except Exception:
                self._collection = None

    def search(self, query: str, top_k: int = 5, category: str | None = None, max_price: float | None = None) -> list[ProductMatch]:
        if self._collection is not None:
            try:
                where = {}
                if category:
                    where["category"] = category
                if max_price:
                    where["price"] = {"$lte": max_price}
                result = self._collection.query(
                    query_embeddings=[simple_embedding(query)],
                    n_results=min(top_k, len(self.products)),
                    where=where or None,
                    include=["distances"],
                )
                product_by_id = {product.id: product for product in self.products}
                matches = []
                for product_id, distance in zip(result["ids"][0], result["distances"][0]):
                    product = product_by_id[product_id]
                    score = max(0.0, 1.0 - float(distance))
                    matches.append(
                        ProductMatch(
                            product=product,
                            score=round(score, 4),
                            reasons=["ChromaDB 向量索引召回", f"商品标签：{', '.join(product.tags[:3])}"],
                            source="vector",
                        )
                    )
                return matches
            except Exception:
                pass

        query_vector = Counter(tokenize(query))
        matches: list[ProductMatch] = []
        for product in self.products:
            if category and category not in product.category:
                continue
            if max_price and product.price > max_price:
                continue
            score = cosine(query_vector, self.product_vectors[product.id])
            if score <= 0:
                continue
            matches.append(
                ProductMatch(
                    product=product,
                    score=round(score, 4),
                    reasons=["语义相似度较高", f"商品标签：{', '.join(product.tags[:3])}"],
                    source="vector",
                )
            )
        return sorted(matches, key=lambda item: item.score, reverse=True)[:top_k]


class HybridRetriever:
    def __init__(self):
        self.keyword = KeywordRetriever()
        self.vector = VectorRetriever()

    def search(self, query: str, top_k: int = 5, category: str | None = None, max_price: float | None = None) -> list[ProductMatch]:
        merged: dict[str, ProductMatch] = {}
        for item in self.keyword.search(query, top_k=top_k * 2, category=category, max_price=max_price):
            merged[item.product.id] = item
        for item in self.vector.search(query, top_k=top_k * 2, category=category, max_price=max_price):
            if item.product.id in merged:
                current = merged[item.product.id]
                current.score = round(current.score * 0.58 + item.score * 0.42 + 0.12, 4)
                current.source = "hybrid"
                current.reasons = list(dict.fromkeys([*current.reasons, *item.reasons]))
            else:
                merged[item.product.id] = item
        return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:top_k]
