from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from buybox.api.auth import require_tenant_api_key
from buybox.api.deps import get_db
from buybox.api.schemas import AuditLogEntryOut, AuditLogPageOut
from buybox.persistence.repositories import AuditLogRepository

router = APIRouter()


@router.get(
    "/v1/tenants/{tenant_id}/audit-log",
    response_model=AuditLogPageOut,
    dependencies=[Depends(require_tenant_api_key)],
)
def get_audit_log(
    tenant_id: str,
    listing_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AuditLogPageOut:
    rows = AuditLogRepository().get_for_listing(db, tenant_id, listing_id, limit, offset)
    entries = [
        AuditLogEntryOut(
            listing_id=row.listing_id,
            config_version=row.config_version,
            winner_seller_id=row.winner_seller_id,
            scores=row.scores,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
    return AuditLogPageOut(entries=entries, limit=limit, offset=offset)
