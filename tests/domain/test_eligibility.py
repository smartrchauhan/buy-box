from buybox.domain.eligibility import filter_eligible
from buybox.domain.models import TenantRuleConfig


def test_out_of_stock_offer_is_ineligible(make_offer):
    offers = [make_offer("seller-a", stock_qty=0)]
    config = TenantRuleConfig(tenant_id="t1", version=1, min_stock_qty=1)

    eligible, ineligible = filter_eligible(offers, config)

    assert eligible == []
    assert len(ineligible) == 1
    assert "out of stock" in ineligible[0].reason


def test_low_rating_offer_is_ineligible(make_offer):
    offers = [make_offer("seller-a", seller_rating=2.0)]
    config = TenantRuleConfig(tenant_id="t1", version=1, min_seller_rating=4.0)

    eligible, ineligible = filter_eligible(offers, config)

    assert eligible == []
    assert "seller rating" in ineligible[0].reason


def test_price_tolerance_excludes_far_pricier_offers(make_offer):
    offers = [
        make_offer("cheap", price="100.00"),
        make_offer("expensive", price="200.00"),
    ]
    config = TenantRuleConfig(tenant_id="t1", version=1, max_price_tolerance_pct=20.0)

    eligible, ineligible = filter_eligible(offers, config)

    assert [o.seller_id for o in eligible] == ["cheap"]
    assert len(ineligible) == 1
    assert ineligible[0].seller_id == "expensive"
    assert "above the lowest eligible price" in ineligible[0].reason


def test_price_tolerance_is_relative_to_cheapest_eligible_not_cheapest_overall(make_offer):
    # The cheapest offer overall is out of stock, so the tolerance must be computed
    # against the cheapest *eligible* offer, not this one.
    offers = [
        make_offer("out_of_stock_cheap", price="10.00", stock_qty=0),
        make_offer("eligible_baseline", price="100.00"),
        make_offer("just_within_tolerance", price="115.00"),
    ]
    config = TenantRuleConfig(tenant_id="t1", version=1, max_price_tolerance_pct=20.0)

    eligible, ineligible = filter_eligible(offers, config)

    eligible_ids = {o.seller_id for o in eligible}
    assert eligible_ids == {"eligible_baseline", "just_within_tolerance"}
    ineligible_ids = {o.seller_id for o in ineligible}
    assert ineligible_ids == {"out_of_stock_cheap"}


def test_no_offers_survive_filtering_returns_empty_eligible_list(make_offer):
    offers = [make_offer("seller-a", stock_qty=0), make_offer("seller-b", stock_qty=0)]
    config = TenantRuleConfig(tenant_id="t1", version=1)

    eligible, ineligible = filter_eligible(offers, config)

    assert eligible == []
    assert len(ineligible) == 2
