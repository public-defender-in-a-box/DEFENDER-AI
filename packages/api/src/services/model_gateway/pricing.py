"""Model pricing, loaded from ``pricing.json`` rather than hard-coded (§6).

Prices change; a constant in code silently falsifies every cost figure. The data
file carries the source URL and the date the prices were checked.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

PRICING_PATH = Path(__file__).with_name("pricing.json")


class PriceTier(BaseModel):
    # Upper bound (inclusive) on prompt tokens for this tier; None = no bound.
    max_prompt_tokens: int | None
    input: float
    output: float
    cache_write: float
    cache_read: float


class ModelPricing(BaseModel):
    tiers: list[PriceTier]


class PricingTable(BaseModel):
    source_url: str
    effective_as_of: str
    checked_by: str
    currency: str
    unit: str
    notes: str
    models: dict[str, ModelPricing]


@lru_cache(maxsize=1)
def pricing_table() -> PricingTable:
    return PricingTable.model_validate(json.loads(PRICING_PATH.read_text(encoding="utf-8")))


class UnpricedModelError(KeyError):
    """A model has no pricing entry. Allowlisted models are checked at startup."""


def cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> float:
    entry = pricing_table().models.get(model)
    if entry is None:
        raise UnpricedModelError(f"No pricing for {model!r} in {PRICING_PATH.name}")
    prompt_tokens = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
    tier = next(
        t
        for t in entry.tiers
        if t.max_prompt_tokens is None or prompt_tokens <= t.max_prompt_tokens
    )
    per_token = 1 / 1_000_000
    return (
        input_tokens * tier.input
        + output_tokens * tier.output
        + cache_read_input_tokens * tier.cache_read
        + cache_creation_input_tokens * tier.cache_write
    ) * per_token
