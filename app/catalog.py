from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import Product


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_PATH = ROOT / "data" / "products.json"


@lru_cache(maxsize=1)
def load_products() -> list[Product]:
    raw = json.loads(PRODUCT_PATH.read_text(encoding="utf-8"))
    return [Product.model_validate(item) for item in raw]


def get_product(product_id: str) -> Product | None:
    return next((product for product in load_products() if product.id == product_id), None)
