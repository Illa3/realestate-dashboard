"""급매 판정 규칙. target.type에 따라 아파트/상가는 실거래가 중위값 기준,
재개발구역은 redevelopment.py의 총투자금 기준을 쓴다.
"""

from . import redevelopment

URGENT_KEYWORDS = ["급매", "급처", "협의가능", "급급매"]


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[len(s) // 2]


def evaluate_against_market(
    listing_price: int,
    area_m2: float | None,
    recent_transaction_prices_per_m2: list[float],
    threshold_pct: float,
) -> dict | None:
    """최근 실거래가 평당가 중위값보다 threshold_pct% 이상 싼 매물인지 판정."""
    if not area_m2 or area_m2 <= 0:
        return None
    median_price_per_m2 = _median(recent_transaction_prices_per_m2)
    if median_price_per_m2 is None:
        return None
    listing_price_per_m2 = listing_price / area_m2
    discount_pct = (listing_price_per_m2 - median_price_per_m2) / median_price_per_m2 * 100
    if discount_pct <= -threshold_pct:
        return {
            "reason": "below_median",
            "detail": {
                "listing_price_per_m2": round(listing_price_per_m2),
                "median_price_per_m2": round(median_price_per_m2),
                "discount_pct": round(discount_pct, 2),
            },
        }
    return None


def evaluate_price_drop(price_history: list[int], threshold_pct: float) -> dict | None:
    """같은 매물의 호가가 등록 시점 대비 threshold_pct% 이상 내려갔는지 판정."""
    if len(price_history) < 2:
        return None
    first, latest = price_history[0], price_history[-1]
    if first <= 0:
        return None
    drop_pct = (latest - first) / first * 100
    if drop_pct <= -threshold_pct:
        return {
            "reason": "price_drop",
            "detail": {"first_price": first, "latest_price": latest, "drop_pct": round(drop_pct, 2)},
        }
    return None


def evaluate_keyword(description: str | None, tags: list[str] | None) -> dict | None:
    text = " ".join(filter(None, [description, " ".join(tags or [])]))
    hits = [kw for kw in URGENT_KEYWORDS if kw in text]
    if hits:
        return {"reason": "keyword", "detail": {"matched_keywords": hits}}
    return None


def evaluate_redevelopment(
    price: int,
    deposit: int,
    appraisal_value: int | None,
    recent_investments: list[int],
    threshold_pct: float,
) -> dict | None:
    return redevelopment.evaluate_redevelopment_listing(
        price, deposit, appraisal_value, recent_investments, threshold_pct
    )
