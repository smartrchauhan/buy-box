"""Repository layer: the only path between the app and the database.

The Phase 1 domain package (`buybox.domain`) stays framework- and DB-agnostic; these
repositories translate between domain objects and SQLAlchemy rows so nothing else in the
codebase needs to know SQLAlchemy exists.
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from buybox.domain.models import Offer, RankingResult, ScoringWeights, TenantRuleConfig
from buybox.persistence.models import (
    OfferRow,
    RankingAuditLogRow,
    TenantRow,
    TenantRuleConfigRow,
)


class TenantRepository:
    def create(self, session: Session, tenant_id: str, name: str) -> TenantRow:
        row = TenantRow(tenant_id=tenant_id, name=name)
        session.add(row)
        session.flush()
        return row

    def get(self, session: Session, tenant_id: str) -> TenantRow | None:
        return session.get(TenantRow, tenant_id)


class TenantConfigRepository:
    def add_version(self, session: Session, config: TenantRuleConfig) -> TenantRuleConfigRow:
        row = TenantRuleConfigRow(
            tenant_id=config.tenant_id,
            version=config.version,
            weights=asdict(config.weights),
            min_seller_rating=config.min_seller_rating,
            min_stock_qty=config.min_stock_qty,
            max_price_tolerance_pct=config.max_price_tolerance_pct,
        )
        session.add(row)
        session.flush()
        return row

    def get_active(self, session: Session, tenant_id: str) -> TenantRuleConfig | None:
        stmt = (
            select(TenantRuleConfigRow)
            .where(TenantRuleConfigRow.tenant_id == tenant_id)
            .order_by(TenantRuleConfigRow.version.desc())
            .limit(1)
        )
        row = session.scalars(stmt).first()
        return self._to_domain(row) if row else None

    def get_version(
        self, session: Session, tenant_id: str, version: int
    ) -> TenantRuleConfig | None:
        stmt = select(TenantRuleConfigRow).where(
            TenantRuleConfigRow.tenant_id == tenant_id,
            TenantRuleConfigRow.version == version,
        )
        row = session.scalars(stmt).first()
        return self._to_domain(row) if row else None

    @staticmethod
    def _to_domain(row: TenantRuleConfigRow) -> TenantRuleConfig:
        return TenantRuleConfig(
            tenant_id=row.tenant_id,
            version=row.version,
            weights=ScoringWeights(**row.weights),
            min_seller_rating=row.min_seller_rating,
            min_stock_qty=row.min_stock_qty,
            max_price_tolerance_pct=row.max_price_tolerance_pct,
        )


class OfferRepository:
    def upsert(self, session: Session, tenant_id: str, offer: Offer) -> OfferRow:
        stmt = select(OfferRow).where(
            OfferRow.tenant_id == tenant_id,
            OfferRow.listing_id == offer.listing_id,
            OfferRow.seller_id == offer.seller_id,
        )
        row = session.scalars(stmt).first()
        if row is None:
            row = OfferRow(
                tenant_id=tenant_id, listing_id=offer.listing_id, seller_id=offer.seller_id
            )
            session.add(row)

        row.price = offer.price
        row.shipping_cost = offer.shipping_cost
        row.shipping_speed_days = offer.shipping_speed_days
        row.stock_qty = offer.stock_qty
        row.fulfillment_type = offer.fulfillment_type
        row.seller_rating = offer.seller_rating
        row.dispatch_time_hours = offer.dispatch_time_hours
        row.return_rate = offer.return_rate
        session.flush()
        return row

    def get_for_listing(self, session: Session, tenant_id: str, listing_id: str) -> list[Offer]:
        stmt = select(OfferRow).where(
            OfferRow.tenant_id == tenant_id, OfferRow.listing_id == listing_id
        )
        rows = session.scalars(stmt).all()
        return [self._to_domain(row) for row in rows]

    def delete(self, session: Session, tenant_id: str, listing_id: str, seller_id: str) -> None:
        stmt = select(OfferRow).where(
            OfferRow.tenant_id == tenant_id,
            OfferRow.listing_id == listing_id,
            OfferRow.seller_id == seller_id,
        )
        row = session.scalars(stmt).first()
        if row is not None:
            session.delete(row)
            session.flush()

    @staticmethod
    def _to_domain(row: OfferRow) -> Offer:
        return Offer(
            seller_id=row.seller_id,
            listing_id=row.listing_id,
            price=row.price,
            shipping_cost=row.shipping_cost,
            shipping_speed_days=row.shipping_speed_days,
            stock_qty=row.stock_qty,
            fulfillment_type=row.fulfillment_type,
            seller_rating=row.seller_rating,
            dispatch_time_hours=row.dispatch_time_hours,
            return_rate=row.return_rate,
        )


class AuditLogRepository:
    def record(self, session: Session, result: RankingResult) -> RankingAuditLogRow:
        row = RankingAuditLogRow(
            tenant_id=result.tenant_id,
            listing_id=result.listing_id,
            config_version=result.config_version,
            winner_seller_id=result.winner.seller_id if result.winner else None,
            scores=[asdict(score) for score in result.scores],
        )
        session.add(row)
        session.flush()
        return row

    def get_for_listing(
        self, session: Session, tenant_id: str, listing_id: str, limit: int = 50, offset: int = 0
    ) -> list[RankingAuditLogRow]:
        stmt = (
            select(RankingAuditLogRow)
            .where(
                RankingAuditLogRow.tenant_id == tenant_id,
                RankingAuditLogRow.listing_id == listing_id,
            )
            .order_by(RankingAuditLogRow.created_at.desc(), RankingAuditLogRow.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(session.scalars(stmt).all())
