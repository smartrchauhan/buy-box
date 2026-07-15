"""Eligibility filtering: which offers are even allowed to compete for the buy box.

Two passes are required because the price-tolerance check is relative to the cheapest
*eligible* offer, not the cheapest offer overall — an out-of-stock $1 offer shouldn't set
the bar for every other seller.
"""

from __future__ import annotations

from decimal import Decimal

from buybox.domain.models import Offer, OfferScore, TenantRuleConfig


def filter_eligible(
    offers: list[Offer], config: TenantRuleConfig
) -> tuple[list[Offer], list[OfferScore]]:
    """Return (eligible offers, OfferScore entries for every ineligible offer with a reason)."""
    ineligible: list[OfferScore] = []
    stage1: list[Offer] = []

    for offer in offers:
        if offer.stock_qty < config.min_stock_qty:
            ineligible.append(
                OfferScore(
                    seller_id=offer.seller_id,
                    eligible=False,
                    reason=(
                        f"out of stock: qty {offer.stock_qty} below required minimum "
                        f"{config.min_stock_qty}"
                    ),
                )
            )
            continue
        if offer.seller_rating < config.min_seller_rating:
            ineligible.append(
                OfferScore(
                    seller_id=offer.seller_id,
                    eligible=False,
                    reason=(
                        f"seller rating {offer.seller_rating:.2f} below required minimum "
                        f"{config.min_seller_rating:.2f}"
                    ),
                )
            )
            continue
        stage1.append(offer)

    if not stage1:
        return [], ineligible

    lowest_price: Decimal = min(o.total_price for o in stage1)
    tolerance_multiplier = Decimal(1) + (
        Decimal(str(config.max_price_tolerance_pct)) / Decimal(100)
    )
    price_ceiling = lowest_price * tolerance_multiplier

    eligible: list[Offer] = []
    for offer in stage1:
        if offer.total_price > price_ceiling:
            pct_above = ((offer.total_price - lowest_price) / lowest_price) * 100
            ineligible.append(
                OfferScore(
                    seller_id=offer.seller_id,
                    eligible=False,
                    reason=(
                        f"price {offer.total_price} is {pct_above:.1f}% above the lowest "
                        f"eligible price {lowest_price} (tolerance "
                        f"{config.max_price_tolerance_pct:.1f}%)"
                    ),
                )
            )
            continue
        eligible.append(offer)

    return eligible, ineligible
