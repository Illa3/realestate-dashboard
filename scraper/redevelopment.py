"""재개발 구역(빌라/무허가 건물 등) 급매 판정.

아파트처럼 평당가로 비교하면 매물마다 조건이 달라 왜곡되므로,
총투자금(매매가 - 보증금) 또는 감정가 대비 프리미엄을 기준으로 판정한다.
"""


def calc_total_investment(price: int, deposit: int = 0) -> int:
    return price - deposit


def calc_premium_pct(total_investment: int, appraisal_value: int) -> float:
    if appraisal_value <= 0:
        raise ValueError("appraisal_value must be positive")
    return (total_investment - appraisal_value) / appraisal_value * 100


def evaluate_redevelopment_listing(
    price: int,
    deposit: int,
    appraisal_value: int | None,
    recent_investments: list[int],
    threshold_pct: float,
) -> dict | None:
    """감정가가 있으면 프리미엄 기준, 없으면 최근 매물 총투자금 중위값 대비 할인율로 판정."""
    total_investment = calc_total_investment(price, deposit)

    if appraisal_value:
        premium_pct = calc_premium_pct(total_investment, appraisal_value)
        if premium_pct <= -threshold_pct:
            return {
                "reason": "premium_low",
                "detail": {
                    "total_investment": total_investment,
                    "appraisal_value": appraisal_value,
                    "premium_pct": round(premium_pct, 2),
                },
            }
        return None

    if not recent_investments:
        return None

    sorted_vals = sorted(recent_investments)
    median = sorted_vals[len(sorted_vals) // 2]
    if median <= 0:
        return None
    discount_pct = (total_investment - median) / median * 100
    if discount_pct <= -threshold_pct:
        return {
            "reason": "below_median",
            "detail": {
                "total_investment": total_investment,
                "median_investment": median,
                "discount_pct": round(discount_pct, 2),
            },
        }
    return None
