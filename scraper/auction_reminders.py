"""입찰일이 3일 이내로 다가온 관심 경매물건을 텔레그램으로 알림."""

from . import db, telegram_notify


def run(within_days: int = 3) -> None:
    items = db.get_upcoming_auction_items(within_days)
    print(f"입찰일 임박 경매물건 {len(items)}건")
    for item in items:
        lines = [
            f"⚖️ <b>경매 입찰일 임박</b> — {item.get('title') or item.get('case_number')}",
            f"- 사건번호: {item.get('case_number')}",
            f"- 입찰기일: {item.get('bid_date')}",
        ]
        if item.get("min_bid_price"):
            lines.append(f"- 최저입찰가: {item['min_bid_price']:,}원")
        if item.get("notes"):
            lines.append(f"- 비고: {item['notes']}")
        telegram_notify.send("\n".join(lines))
        db.mark_auction_reminded(item["id"])


if __name__ == "__main__":
    run()
