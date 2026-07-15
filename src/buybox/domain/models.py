"""Framework-agnostic domain models for the Buy Box ranking engine.

No dependency on AWS, a database, or a web framework — this package must remain
importable and fully testable with plain Python only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class Offer:
    """A single seller's offer for a listing, as ingested from a tenant's marketplace."""

    seller_id: str
    listing_id: str
    price: Decimal
    shipping_cost: Decimal
    shipping_speed_days: float
    stock_qty: int
    fulfillment_type: str
    seller_rating: float  # 0.0 - 5.0
    dispatch_time_hours: float
    return_rate: float  # 0.0 - 1.0

    @property
    def total_price(self) -> Decimal:
        return self.price + self.shipping_cost


@dataclass(frozen=True)
class ScoringWeights:
    """Relative importance of each ranking signal. Need not sum to 1 — normalized at use time."""

    price: float = 1.0
    shipping_speed: float = 1.0
    seller_rating: float = 1.0
    dispatch_time: float = 1.0
    return_rate: float = 1.0

    def normalized(self) -> dict[str, float]:
        total = (
            self.price
            + self.shipping_speed
            + self.seller_rating
            + self.dispatch_time
            + self.return_rate
        )
        if total <= 0:
            raise ValueError("At least one scoring weight must be positive")
        return {
            "price": self.price / total,
            "shipping_speed": self.shipping_speed / total,
            "seller_rating": self.seller_rating / total,
            "dispatch_time": self.dispatch_time / total,
            "return_rate": self.return_rate / total,
        }


@dataclass(frozen=True)
class TenantRuleConfig:
    """A tenant's configurable eligibility thresholds and ranking weights.

    `version` lets Phase 2's persistence layer keep a history of configs rather than
    overwriting them, and lets the audit log record which version was active for a decision.
    """

    tenant_id: str
    version: int
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    min_seller_rating: float = 0.0
    min_stock_qty: int = 1
    max_price_tolerance_pct: float = 100.0  # % above the cheapest eligible total price allowed


@dataclass(frozen=True)
class OfferScore:
    """The outcome of evaluating a single offer: eligibility, score, and a human-readable reason."""

    seller_id: str
    eligible: bool
    reason: str
    score: float | None = None
    component_scores: dict[str, float] | None = None


@dataclass(frozen=True)
class RankingResult:
    """The outcome of ranking all offers for a single listing."""

    tenant_id: str
    listing_id: str
    config_version: int
    winner: OfferScore | None
    scores: list[OfferScore]
