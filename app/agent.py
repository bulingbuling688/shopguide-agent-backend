from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .llm import generate_openai_compatible_reply
from .models import Recommendation
from .retrievers import HybridRetriever


class ShopGuideState(TypedDict, total=False):
    query: str
    top_k: int
    category: str | None
    max_price: float | None
    intent: dict[str, Any]
    matches: list[Any]
    recommendations: list[Recommendation]
    needs_clarification: bool
    clarification_question: str | None
    answer: str
    trace: list[dict[str, Any]]


def append_trace(state: ShopGuideState, node: str, detail: dict[str, Any]) -> None:
    state.setdefault("trace", []).append({"node": node, **detail})


def parse_intent(state: ShopGuideState) -> ShopGuideState:
    query = state["query"]
    category = state.get("category")
    category_map = ["手机", "笔记本", "耳机", "相机", "家电", "手表"]
    inferred_category = category or next((item for item in category_map if item in query), None)
    max_price = state.get("max_price")
    price_match = re.search(r"(\d{3,5})\s*(?:元|以内|以下|预算)?", query)
    if max_price is None and price_match:
        max_price = float(price_match.group(1))
    negations = [word for word in ["不要", "不想", "不需要", "别推荐", "不要游戏"] if word in query]
    needs_clarification = inferred_category is None and len(query) < 8
    state["category"] = inferred_category
    state["max_price"] = max_price
    state["intent"] = {
        "category": inferred_category,
        "max_price": max_price,
        "negations": negations,
        "preference_keywords": [word for word in ["轻薄", "游戏", "拍照", "办公", "降噪", "续航", "宠物", "剪辑"] if word in query],
    }
    state["needs_clarification"] = needs_clarification
    state["clarification_question"] = "你更关注品类、预算还是使用场景？例如：3000 元以内拍照好的手机。" if needs_clarification else None
    append_trace(state, "parse_intent", {"intent": state["intent"], "needs_clarification": needs_clarification})
    return state


def retrieve_products(state: ShopGuideState) -> ShopGuideState:
    if state.get("needs_clarification"):
        state["matches"] = []
        append_trace(state, "retrieve_products", {"skipped": True, "reason": "needs_clarification"})
        return state
    retriever = HybridRetriever()
    state["matches"] = retriever.search(
        state["query"],
        top_k=state.get("top_k", 5),
        category=state.get("category"),
        max_price=state.get("max_price"),
    )
    append_trace(state, "retrieve_products", {"match_count": len(state["matches"])})
    return state


def rank_and_explain(state: ShopGuideState) -> ShopGuideState:
    recommendations: list[Recommendation] = []
    query = state["query"]
    for match in state.get("matches", []):
        product = match.product
        caveats = []
        if "不要游戏" in state.get("intent", {}).get("negations", []) and "游戏" in product.tags:
            caveats.append("用户表达不需要游戏属性，已降低推荐优先级")
        if product.stock < 30:
            caveats.append("库存偏少，建议尽快确认")
        reasons = match.reasons[:]
        if product.price <= (state.get("max_price") or product.price):
            reasons.append("价格满足预算约束")
        if any(tag in query for tag in product.tags):
            reasons.append("商品标签命中用户偏好")
        recommendations.append(
            Recommendation(
                product_id=product.id,
                title=product.title,
                price=product.price,
                score=match.score,
                reasons=list(dict.fromkeys(reasons))[:5],
                caveats=caveats,
            )
        )
    state["recommendations"] = recommendations
    append_trace(state, "rank_and_explain", {"recommendation_count": len(recommendations)})
    return state


def generate_response(state: ShopGuideState) -> ShopGuideState:
    if state.get("needs_clarification"):
        state["answer"] = state["clarification_question"] or "请补充预算、品类或使用场景。"
        append_trace(state, "generate_response", {"mode": "clarification"})
        return state
    recommendations = state.get("recommendations", [])
    if not recommendations:
        state["answer"] = "暂时没有找到完全匹配的商品，建议放宽预算或补充使用场景。"
    else:
        top = recommendations[0]
        prompt = (
            f"用户需求：{state['query']}\n"
            f"推荐商品：{top.title}\n"
            f"价格：{top.price:.0f} 元\n"
            f"推荐理由：{'；'.join(top.reasons[:4])}\n"
            f"注意事项：{'；'.join(top.caveats) if top.caveats else '无'}"
        )
        state["answer"] = generate_openai_compatible_reply(prompt) or (
            f"优先推荐 {top.title}，价格约 {top.price:.0f} 元。"
            f"推荐理由：{'；'.join(top.reasons[:3])}。"
        )
    append_trace(state, "generate_response", {"mode": "recommendation", "answer_length": len(state["answer"])})
    return state


def route_after_intent(state: ShopGuideState) -> str:
    return "generate_response" if state.get("needs_clarification") else "retrieve_products"


def build_shopguide_graph():
    graph = StateGraph(ShopGuideState)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("retrieve_products", retrieve_products)
    graph.add_node("rank_and_explain", rank_and_explain)
    graph.add_node("generate_response", generate_response)
    graph.set_entry_point("parse_intent")
    graph.add_conditional_edges("parse_intent", route_after_intent)
    graph.add_edge("retrieve_products", "rank_and_explain")
    graph.add_edge("rank_and_explain", "generate_response")
    graph.add_edge("generate_response", END)
    return graph.compile()


SHOPGUIDE_GRAPH = build_shopguide_graph()


def run_recommendation(query: str, top_k: int = 5, category: str | None = None, max_price: float | None = None) -> ShopGuideState:
    return SHOPGUIDE_GRAPH.invoke(
        {
            "query": query,
            "top_k": top_k,
            "category": category,
            "max_price": max_price,
            "trace": [],
        }
    )
