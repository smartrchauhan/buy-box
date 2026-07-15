"""The core buy-box ranking algorithm: eligibility filtering, weighted scoring, and a
deterministic tie-break, over a framework-agnostic in-memory list of offers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from buybox.domain.eligibility import filter_eligible
from buybox.domain.explain import explain_loser, explain_winner
from buybox.domain.models import Offer, OfferScore, RankingResult, TenantRuleConfig


@dataclass(frozen=True)
class _Signal:
    name: str
    value_fn: Callable[[Offer], float]
    higher_is_better: bool


_SIGNALS: list[_Signal] = [
    _Signal("price", lambda o: float(o.total_price), higher_is_better=False),
    _Signal("shipping_speed", lambda o: o.shipping_speed_days, higher_is_better=False),
    _Signal("seller_rating", lambda o: o.seller_rating, higher_is_better=True),
    _Signal("dispatch_time", lambda o: o.dispatch_time_hours, higher_is_better=False),
    _Signal("return_rate", lambda o: o.return_rate, higher_is_better=False),
]


def _normalize(offers: list[Offer], signal: _Signal) -> dict[str, float]:
    values = {o.seller_id: signal.value_fn(o) for o in offers}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return dict.fromkeys(values, 1.0)
    span = hi - lo
    if signal.higher_is_better:
        return {seller_id: (v - lo) / span for seller_id, v in values.items()}
    return {seller_id: (hi - v) / span for seller_id, v in values.items()}


def rank(offers: list[Offer], config: TenantRuleConfig) -> RankingResult:
    if not offers:
        raise ValueError("Cannot rank an empty offer list")
    listing_id = offers[0].listing_id
    if any(o.listing_id != listing_id for o in offers):
        raise ValueError("All offers passed to rank() must be for the same listing_id")

    eligible, ineligible_scores = filter_eligible(offers, config)

    if not eligible:
        return RankingResult(
            tenant_id=config.tenant_id,
            listing_id=listing_id,
            config_version=config.version,
            winner=None,
            scores=ineligible_scores,
        )

    weights = config.weights.normalized()
    per_signal_norm = {signal.name: _normalize(eligible, signal) for signal in _SIGNALS}

    weighted_scores: dict[str, float] = {}
    component_scores: dict[str, dict[str, float]] = {}
    for offer in eligible:
        components = {
            signal.name: per_signal_norm[signal.name][offer.seller_id] for signal in _SIGNALS
        }
        component_scores[offer.seller_id] = components
        weighted_scores[offer.seller_id] = sum(
            components[name] * weight for name, weight in weights.items()
        )

    # Deterministic ordering: highest score wins; ties broken by lower total price, then
    # lexicographically by seller_id so results are reproducible across runs.
    offers_by_id = {o.seller_id: o for o in eligible}
    ranked_seller_ids = sorted(
        weighted_scores,
        key=lambda sid: (
            -weighted_scores[sid],
            offers_by_id[sid].total_price,
            sid,
        ),
    )

    winner_id = ranked_seller_ids[0]
    winner_score = weighted_scores[winner_id]

    eligible_scores: list[OfferScore] = []
    for seller_id in ranked_seller_ids:
        score = weighted_scores[seller_id]
        if seller_id == winner_id:
            reason = explain_winner(seller_id, score)
        else:
            reason = explain_loser(seller_id, score, winner_id, winner_score)
        eligible_scores.append(
            OfferScore(
                seller_id=seller_id,
                eligible=True,
                reason=reason,
                score=score,
                component_scores=component_scores[seller_id],
            )
        )

    winner = eligible_scores[0]
    return RankingResult(
        tenant_id=config.tenant_id,
        listing_id=listing_id,
        config_version=config.version,
        winner=winner,
        scores=eligible_scores + ineligible_scores,
    )
