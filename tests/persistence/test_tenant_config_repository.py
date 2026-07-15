from buybox.domain.models import ScoringWeights, TenantRuleConfig
from buybox.persistence.repositories import TenantConfigRepository


def _config(tenant_id: str, version: int, price_weight: float = 1.0) -> TenantRuleConfig:
    return TenantRuleConfig(
        tenant_id=tenant_id,
        version=version,
        weights=ScoringWeights(price=price_weight),
        min_seller_rating=3.0,
        min_stock_qty=1,
        max_price_tolerance_pct=20.0,
    )


def test_get_active_returns_highest_version(db_session, tenant_id):
    repo = TenantConfigRepository()
    repo.add_version(db_session, _config(tenant_id, version=1, price_weight=1.0))
    repo.add_version(db_session, _config(tenant_id, version=2, price_weight=2.0))

    active = repo.get_active(db_session, tenant_id)

    assert active is not None
    assert active.version == 2
    assert active.weights.price == 2.0


def test_get_version_returns_specific_historical_version(db_session, tenant_id):
    repo = TenantConfigRepository()
    repo.add_version(db_session, _config(tenant_id, version=1, price_weight=1.0))
    repo.add_version(db_session, _config(tenant_id, version=2, price_weight=2.0))

    v1 = repo.get_version(db_session, tenant_id, 1)

    assert v1 is not None
    assert v1.version == 1
    assert v1.weights.price == 1.0


def test_get_active_with_no_versions_returns_none(db_session, tenant_id):
    repo = TenantConfigRepository()

    assert repo.get_active(db_session, tenant_id) is None
