from __future__ import annotations

import os

import httpx


def generate_openai_compatible_reply(prompt: str) -> str | None:
    api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
    base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_COMPATIBLE_MODEL", "gpt-4o-mini")
    if not api_key or api_key == "sk-***":
        return None

    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是电商导购 Agent，请基于给定商品信息生成简洁、可信的中文推荐理由。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=8,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
