from decimal import Decimal

import pytest

from buybox.domain.models import Offer


@pytest.fixture
def make_offer():
    def _make(
        seller_id: str,
        listing_id: str = "listing-1",
        price: str = "100.00",
        shipping_cost: str = "0.00",
        shipping_speed_days: float = 2.0,
        stock_qty: int = 10,
        fulfillment_type: str = "seller_fulfilled",
        seller_rating: float = 4.5,
        dispatch_time_hours: float = 24.0,
        return_rate: float = 0.02,
    ) -> Offer:
        return Offer(
            seller_id=seller_id,
            listing_id=listing_id,
            price=Decimal(price),
            shipping_cost=Decimal(shipping_cost),
            shipping_speed_days=shipping_speed_days,
            stock_qty=stock_qty,
            fulfillment_type=fulfillment_type,
            seller_rating=seller_rating,
            dispatch_time_hours=dispatch_time_hours,
            return_rate=return_rate,
        )

    return _make
