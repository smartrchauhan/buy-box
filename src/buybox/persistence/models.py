"""SQLAlchemy ORM models. These are an implementation detail behind the repository layer —
the Phase 1 domain package must never import from here.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TenantRow(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TenantRuleConfigRow(Base):
    """Versioned per-tenant rule config. Rows are never updated, only inserted — a new
    version row is added and the highest version number for a tenant is the active one.
    """

    __tablename__ = "tenant_rule_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "version", name="uq_tenant_config_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"))
    version: Mapped[int]
    weights: Mapped[dict[str, float]] = mapped_column(JSON)
    min_seller_rating: Mapped[float]
    min_stock_qty: Mapped[int]
    max_price_tolerance_pct: Mapped[float]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OfferRow(Base):
    """Current known state of one seller's offer for one listing. Upserted on every
    offer-update event (Phase 6) — this table always reflects latest-known state, not history.
    """

    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "listing_id", "seller_id", name="uq_tenant_listing_seller"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"))
    listing_id: Mapped[str]
    seller_id: Mapped[str]
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_speed_days: Mapped[float]
    stock_qty: Mapped[int]
    fulfillment_type: Mapped[str]
    seller_rating: Mapped[float]
    dispatch_time_hours: Mapped[float]
    return_rate: Mapped[float]
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RankingAuditLogRow(Base):
    """One row per ranking decision — inputs are not stored (they live in `offers`), but the
    resulting scores/explanation and which config version was active are, for debugging and
    for the future seller-facing analytics (Phase 9).
    """

    __tablename__ = "ranking_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"))
    listing_id: Mapped[str]
    config_version: Mapped[int]
    winner_seller_id: Mapped[str | None]
    scores: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
