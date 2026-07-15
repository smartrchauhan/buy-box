from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from buybox.api.auth import require_tenant_api_key
from buybox.api.deps import get_db
from buybox.api.schemas import OfferScoreOut, RankingResultOut, RankRequest
from buybox.domain.models import Offer
from buybox.domain.ranking import rank
from buybox.persistence.repositories import AuditLogRepository, TenantConfigRepository

router = APIRouter()


@router.post(
    "/v1/tenants/{tenant_id}/rank",
    response_model=RankingResultOut,
    dependencies=[Depends(require_tenant_api_key)],
)
def rank_offers(
    tenant_id: str, request: RankRequest, db: Session = Depends(get_db)
) -> RankingResultOut:
    config = TenantConfigRepository().get_active(db, tenant_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rule config found for tenant '{tenant_id}'",
        )

    offers = [
        Offer(
            seller_id=o.seller_id,
            listing_id=request.listing_id,
            price=o.price,
            shipping_cost=o.shipping_cost,
            shipping_speed_days=o.shipping_speed_days,
            stock_qty=o.stock_qty,
            fulfillment_type=o.fulfillment_type,
            seller_rating=o.seller_rating,
            dispatch_time_hours=o.dispatch_time_hours,
            return_rate=o.return_rate,
        )
        for o in request.offers
    ]

    result = rank(offers, config)
    AuditLogRepository().record(db, result)

    return RankingResultOut(
        tenant_id=result.tenant_id,
        listing_id=result.listing_id,
        config_version=result.config_version,
        winner=OfferScoreOut(**vars(result.winner)) if result.winner else None,
        scores=[OfferScoreOut(**vars(s)) for s in result.scores],
    )
