"""Human-readable explanations for why an offer won or lost the buy box.

Kept separate from the scoring math so the wording can evolve independently of the
ranking algorithm itself.
"""

from __future__ import annotations


def explain_winner(seller_id: str, score: float) -> str:
    return f"won: best weighted score {score:.4f} among eligible offers"


def explain_loser(seller_id: str, score: float, winner_seller_id: str, winner_score: float) -> str:
    gap = winner_score - score
    return (
        f"lost: weighted score {score:.4f}, {gap:.4f} behind winning seller "
        f"{winner_seller_id} (score {winner_score:.4f})"
    )
