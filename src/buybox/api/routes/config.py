from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from buybox.api.auth import require_tenant_api_key
from buybox.api.deps import get_db
from buybox.api.schemas import ScoringWeightsIn, TenantConfigIn, TenantConfigOut
from buybox.domain.models import ScoringWeights, TenantRuleConfig
from buybox.persistence.repositories import TenantConfigRepository, TenantRepository

router = APIRouter()


def _to_out(config: TenantRuleConfig) -> TenantConfigOut:
    return TenantConfigOut(
        tenant_id=config.tenant_id,
        version=config.version,
        weights=ScoringWeightsIn(**vars(config.weights)),
        min_seller_rating=config.min_seller_rating,
        min_stock_qty=config.min_stock_qty,
        max_price_tolerance_pct=config.max_price_tolerance_pct,
    )


@router.get(
    "/v1/tenants/{tenant_id}/config",
    response_model=TenantConfigOut,
    dependencies=[Depends(require_tenant_api_key)],
)
def get_active_config(tenant_id: str, db: Session = Depends(get_db)) -> TenantConfigOut:
    config = TenantConfigRepository().get_active(db, tenant_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rule config found for tenant '{tenant_id}'",
        )
    return _to_out(config)


@router.put(
    "/v1/tenants/{tenant_id}/config",
    response_model=TenantConfigOut,
    dependencies=[Depends(require_tenant_api_key)],
)
def update_config(
    tenant_id: str, request: TenantConfigIn, db: Session = Depends(get_db)
) -> TenantConfigOut:
    if TenantRepository().get(db, tenant_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown tenant '{tenant_id}'"
        )

    config_repo = TenantConfigRepository()
    current = config_repo.get_active(db, tenant_id)
    next_version = (current.version if current else 0) + 1

    new_config = TenantRuleConfig(
        tenant_id=tenant_id,
        version=next_version,
        weights=ScoringWeights(**request.weights.model_dump()),
        min_seller_rating=request.min_seller_rating,
        min_stock_qty=request.min_stock_qty,
        max_price_tolerance_pct=request.max_price_tolerance_pct,
    )
    config_repo.add_version(db, new_config)
    return _to_out(new_config)
