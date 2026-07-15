"""Pydantic request/response schemas for the API layer. These mirror the Phase 1 domain
models but stay separate from them — the domain package must not depend on Pydantic.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class OfferIn(BaseModel):
    seller_id: str
    price: Decimal
    shipping_cost: Decimal = Decimal("0.00")
    shipping_speed_days: float
    stock_qty: int
    fulfillment_type: str
    seller_rating: float = Field(ge=0, le=5)
    dispatch_time_hours: float
    return_rate: float = Field(ge=0, le=1)


class RankRequest(BaseModel):
    listing_id: str
    offers: list[OfferIn]


class OfferScoreOut(BaseModel):
    seller_id: str
    eligible: bool
    reason: str
    score: float | None = None
    component_scores: dict[str, float] | None = None


class RankingResultOut(BaseModel):
    tenant_id: str
    listing_id: str
    config_version: int
    winner: OfferScoreOut | None
    scores: list[OfferScoreOut]


class ScoringWeightsIn(BaseModel):
    price: float = 1.0
    shipping_speed: float = 1.0
    seller_rating: float = 1.0
    dispatch_time: float = 1.0
    return_rate: float = 1.0


class TenantConfigIn(BaseModel):
    weights: ScoringWeightsIn = ScoringWeightsIn()
    min_seller_rating: float = 0.0
    min_stock_qty: int = 1
    max_price_tolerance_pct: float = 100.0


class TenantConfigOut(BaseModel):
    tenant_id: str
    version: int
    weights: ScoringWeightsIn
    min_seller_rating: float
    min_stock_qty: int
    max_price_tolerance_pct: float


class AuditLogEntryOut(BaseModel):
    listing_id: str
    config_version: int
    winner_seller_id: str | None
    scores: list[dict[str, object]]
    created_at: str


class AuditLogPageOut(BaseModel):
    entries: list[AuditLogEntryOut]
    limit: int
    offset: int
