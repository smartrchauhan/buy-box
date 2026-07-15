import pytest

from buybox.domain.models import ScoringWeights, TenantRuleConfig
from buybox.domain.ranking import rank


def _config(**weight_kwargs) -> TenantRuleConfig:
    return TenantRuleConfig(
        tenant_id="t1",
        version=1,
        weights=ScoringWeights(**weight_kwargs),
        max_price_tolerance_pct=200.0,
    )


def test_single_eligible_offer_wins_by_default(make_offer):
    offers = [make_offer("only-seller")]
    result = rank(offers, _config())

    assert result.winner is not None
    assert result.winner.seller_id == "only-seller"
    assert result.winner.eligible is True
    assert result.winner.reason.startswith("won:")


def test_no_eligible_offers_yields_no_winner(make_offer):
    offers = [make_offer("seller-a", stock_qty=0), make_offer("seller-b", stock_qty=0)]
    result = rank(offers, _config())

    assert result.winner is None
    assert len(result.scores) == 2
    assert all(not s.eligible for s in result.scores)


def test_rank_rejects_empty_offer_list():
    with pytest.raises(ValueError):
        rank([], _config())


def test_rank_rejects_offers_for_different_listings(make_offer):
    offers = [make_offer("a", listing_id="listing-1"), make_offer("b", listing_id="listing-2")]
    with pytest.raises(ValueError):
        rank(offers, _config())


def test_tie_breaks_by_price_then_seller_id(make_offer):
    # Identical on every signal -> weighted scores tie exactly; seller_id order decides.
    offers = [
        make_offer("seller-z", price="100.00"),
        make_offer("seller-a", price="100.00"),
    ]
    result = rank(offers, _config())

    assert result.winner.seller_id == "seller-a"


def test_tie_breaks_by_lower_price_before_seller_id(make_offer):
    offers = [
        make_offer("seller-a", price="120.00"),
        make_offer("seller-z", price="100.00"),
    ]
    # Equal on every non-price signal; price differs, and price weight is included by default
    # so this isn't a pure tie — but confirm the cheaper offer wins when all else is equal.
    result = rank(offers, _config())

    assert result.winner.seller_id == "seller-z"


@pytest.mark.parametrize(
    "weight_kwargs,expected_winner",
    [
        (
            {
                "price": 1,
                "shipping_speed": 0,
                "seller_rating": 0,
                "dispatch_time": 0,
                "return_rate": 0,
            },
            "cheaper-worse-service",
        ),
        (
            {
                "price": 0,
                "shipping_speed": 1,
                "seller_rating": 0,
                "dispatch_time": 0,
                "return_rate": 0,
            },
            "pricier-better-service",
        ),
        (
            {
                "price": 0,
                "shipping_speed": 0,
                "seller_rating": 1,
                "dispatch_time": 0,
                "return_rate": 0,
            },
            "pricier-better-service",
        ),
        (
            {
                "price": 0,
                "shipping_speed": 0,
                "seller_rating": 0,
                "dispatch_time": 1,
                "return_rate": 0,
            },
            "pricier-better-service",
        ),
        (
            {
                "price": 0,
                "shipping_speed": 0,
                "seller_rating": 0,
                "dispatch_time": 0,
                "return_rate": 1,
            },
            "pricier-better-service",
        ),
    ],
)
def test_each_weight_in_isolation_picks_the_expected_winner(
    make_offer, weight_kwargs, expected_winner
):
    offers = [
        make_offer(
            "cheaper-worse-service",
            price="100.00",
            shipping_speed_days=5,
            seller_rating=3.0,
            dispatch_time_hours=48,
            return_rate=0.10,
        ),
        make_offer(
            "pricier-better-service",
            price="150.00",
            shipping_speed_days=1,
            seller_rating=5.0,
            dispatch_time_hours=2,
            return_rate=0.01,
        ),
    ]
    result = rank(offers, _config(**weight_kwargs))

    assert result.winner.seller_id == expected_winner


def test_loser_explanation_references_winner_and_score_gap(make_offer):
    offers = [
        make_offer("winner", price="90.00"),
        make_offer("loser", price="110.00"),
    ]
    result = rank(offers, _config())

    loser_score = next(s for s in result.scores if s.seller_id == "loser")
    assert loser_score.eligible is True
    assert "lost:" in loser_score.reason
    assert "winner" in loser_score.reason
    assert loser_score.score is not None
    assert result.winner.score is not None
    assert loser_score.score <= result.winner.score


def test_config_version_is_carried_through_to_result(make_offer):
    offers = [make_offer("seller-a")]
    config = TenantRuleConfig(tenant_id="t1", version=7)

    result = rank(offers, config)

    assert result.config_version == 7
    assert result.tenant_id == "t1"
