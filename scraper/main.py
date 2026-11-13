"""30분마다 GitHub Actions가 실행하는 전체 파이프라인.

1. targets 테이블에서 활성 단지/구역을 읽어 국토부 실거래가(최근 6개월)를 수집·저장한다.
   (네이버 매물 자동 수집은 봇 차단으로 포기 — README 참고)
2. 대기 중인 매물/경매 캡처 이미지를 Claude Vision으로 파싱해 정리한다.
   매물 캡처는 이 실거래가 데이터와 비교해 급매 여부를 판정하고 텔레그램으로 알린다.
3. 입찰일이 임박한 관심 경매물건을 텔레그램으로 알린다.
"""

from datetime import date

from . import auction_reminders, db, molit_client, process_captures

RECENT_MONTHS = 6


def _recent_deal_ymds(n: int = RECENT_MONTHS) -> list[str]:
    months = []
    y, m = date.today().year, date.today().month
    for _ in range(n):
        months.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return months


def _insert_trades(target_id: str, source: str, trades: list[dict]) -> None:
    for t in trades:
        try:
            db.insert_transaction(
                target_id,
                source,
                {
                    "deal_date": f"{t.get('년', t.get('dealYear',''))}-{int(t.get('월', t.get('dealMonth','1'))):02d}-{int(t.get('일', t.get('dealDay','1'))):02d}",
                    "price": int(float(t.get("거래금액", "0").replace(",", "")) * 10000),
                    "area_m2": float(t.get("전용면적", 0) or 0),
                    "floor_info": t.get("층"),
                    "raw_json": t,
                },
            )
        except Exception as e:  # noqa: BLE001
            print(f"[molit] 거래 저장 실패: {e}")


def process_apartment_or_commercial(target: dict) -> None:
    fetch_fn = molit_client.fetch_commercial_trades if target["type"] == "commercial" else molit_client.fetch_apt_trades
    source = "commercial" if target["type"] == "commercial" else "apt"

    trade_count = 0
    for ymd in _recent_deal_ymds():
        try:
            batch = fetch_fn(target["lawd_cd"], ymd)
        except Exception as e:  # noqa: BLE001
            print(f"[molit] {target['name']} {ymd} 조회 실패: {e}")
            continue
        trade_count += len(batch)
        _insert_trades(target["id"], source, batch)

    print(f"[molit] {target['name']}: 실거래 {trade_count}건 수집")


def process_redevelopment(target: dict) -> None:
    # 재개발구역은 빌라(연립다세대)와 단독/다가구(상가주택 포함)가 섞여 있어 둘 다 수집
    sources = [("villa", molit_client.fetch_villa_trades), ("house", molit_client.fetch_house_trades)]
    trade_count = 0
    for source, fetch_fn in sources:
        for ymd in _recent_deal_ymds():
            try:
                batch = fetch_fn(target["lawd_cd"], ymd)
            except Exception as e:  # noqa: BLE001
                print(f"[molit:{source}] {target['name']} {ymd} 조회 실패: {e}")
                continue
            trade_count += len(batch)
            _insert_trades(target["id"], source, batch)

    print(f"[redevelopment] {target['name']}: 실거래 {trade_count}건 수집")


def run() -> None:
    for target in db.get_active_targets():
        print(f"=== {target['name']} ({target['type']}) ===")
        if target["type"] in ("apartment", "commercial"):
            process_apartment_or_commercial(target)
        elif target["type"] == "redevelopment":
            process_redevelopment(target)

    print("=== 캡처(매물/경매) 처리 ===")
    process_captures.run()

    print("=== 경매 입찰일 알림 ===")
    auction_reminders.run()


if __name__ == "__main__":
    run()
