from decimal import Decimal

from buybox.domain.models import Offer, TenantRuleConfig
from buybox.domain.ranking import rank
from buybox.persistence.repositories import AuditLogRepository


def _offer(seller_id: str, price: str) -> Offer:
    return Offer(
        seller_id=seller_id,
        listing_id="listing-1",
        price=Decimal(price),
        shipping_cost=Decimal("0.00"),
        shipping_speed_days=2.0,
        stock_qty=10,
        fulfillment_type="seller_fulfilled",
        seller_rating=4.5,
        dispatch_time_hours=24.0,
        return_rate=0.02,
    )


def test_record_and_fetch_ranking_result(db_session, tenant_id):
    config = TenantRuleConfig(tenant_id=tenant_id, version=1)
    offers = [_offer("seller-a", "90.00"), _offer("seller-b", "100.00")]
    result = rank(offers, config)

    repo = AuditLogRepository()
    repo.record(db_session, result)

    log_rows = repo.get_for_listing(db_session, tenant_id, "listing-1")

    assert len(log_rows) == 1
    assert log_rows[0].winner_seller_id == "seller-a"
    assert log_rows[0].config_version == 1
    assert len(log_rows[0].scores) == 2


def test_get_for_listing_orders_most_recent_first(db_session, tenant_id):
    config = TenantRuleConfig(tenant_id=tenant_id, version=1)
    repo = AuditLogRepository()

    first_result = rank([_offer("seller-a", "90.00")], config)
    repo.record(db_session, first_result)

    second_result = rank([_offer("seller-b", "80.00")], config)
    repo.record(db_session, second_result)

    log_rows = repo.get_for_listing(db_session, tenant_id, "listing-1")

    assert [row.winner_seller_id for row in log_rows] == ["seller-b", "seller-a"]
