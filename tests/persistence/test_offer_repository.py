from decimal import Decimal

from buybox.domain.models import Offer
from buybox.persistence.repositories import OfferRepository


def _offer(seller_id: str, price: str = "100.00") -> Offer:
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


def test_upsert_inserts_then_updates_same_offer(db_session, tenant_id):
    repo = OfferRepository()

    repo.upsert(db_session, tenant_id, _offer("seller-a", price="100.00"))
    offers = repo.get_for_listing(db_session, tenant_id, "listing-1")
    assert len(offers) == 1
    assert offers[0].price == Decimal("100.00")

    repo.upsert(db_session, tenant_id, _offer("seller-a", price="90.00"))
    offers = repo.get_for_listing(db_session, tenant_id, "listing-1")
    assert len(offers) == 1
    assert offers[0].price == Decimal("90.00")


def test_get_for_listing_returns_all_sellers_offers(db_session, tenant_id):
    repo = OfferRepository()
    repo.upsert(db_session, tenant_id, _offer("seller-a"))
    repo.upsert(db_session, tenant_id, _offer("seller-b"))

    offers = repo.get_for_listing(db_session, tenant_id, "listing-1")

    assert {o.seller_id for o in offers} == {"seller-a", "seller-b"}


def test_delete_offer_removes_it(db_session, tenant_id):
    repo = OfferRepository()
    repo.upsert(db_session, tenant_id, _offer("seller-a"))

    repo.delete(db_session, tenant_id, "listing-1", "seller-a")

    assert repo.get_for_listing(db_session, tenant_id, "listing-1") == []
