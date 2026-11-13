"""30분마다 GitHub Actions가 실행하는 전체 파이프라인.

1. targets 테이블에서 활성 단지/구역을 읽어 국토부 실거래가(최근 6개월)를 수집·저장한다.
   (네이버 매물 자동 수집은 봇 차단으로 포기 — README 참고)
2. 대기 중인 매물/경매 캡처 이미지를 Claude Vision으로 파싱해 정리한다.
   매물 캡처는 이 실거래가 데이터와 비교해 급매 여부를 판정하고 텔레그램으로 알린다.
3. 입찰일이 임박한 관심 경매물건을 텔레그램으로 알린다.
"""

import time
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


def _first(t: dict, *keys: str, default=None):
    for k in keys:
        v = t.get(k)
        if v not in (None, ""):
            return v
    return default


def _matches_location(t: dict, target: dict) -> bool:
    """target에 dong_name/jibun이 지정돼 있으면 그 동·지번 거래만 통과시킨다.
    (예: 신천동 장미아파트 상가처럼 구 전체 조회로는 범위가 너무 넓은 경우)"""
    dong = target.get("dong_name")
    if dong and _first(t, "법정동", "umdNm") != dong:
        return False
    jibun = target.get("jibun")
    if jibun and str(_first(t, "지번", "jibun", default="")) != str(jibun):
        return False
    return True


def _to_rows(target_id: str, source: str, trades: list[dict]) -> list[dict]:
    rows = []
    for t in trades:
        try:
            year = _first(t, "년", "dealYear", default="2000")
            month = _first(t, "월", "dealMonth", default="1")
            day = _first(t, "일", "dealDay", default="1")
            # MOLIT API 응답은 API마다 영문 필드(dealAmount, excluUseAr, floor 등)를
            # 쓰기도 하고 한글 필드를 쓰기도 해서 둘 다 시도한다.
            price_raw = _first(t, "거래금액", "dealAmount", "물건금액", default="0")
            # 아파트/연립다세대=excluUseAr(전용면적), 단독다가구=totalFloorAr(연면적), 상업용=buildingAr(건물면적)
            area_raw = _first(
                t, "전용면적", "excluUseAr", "totalFloorAr", "buildingAr", "plottageAr", "대지권면적", default=0
            )
            floor_info = _first(t, "층", "floor")

            rows.append(
                {
                    "target_id": target_id,
                    "source": source,
                    "deal_date": f"{year}-{int(month):02d}-{int(day):02d}",
                    "price": int(float(str(price_raw).replace(",", "")) * 10000),
                    "area_m2": float(str(area_raw).replace(",", "") or 0),
                    "floor_info": floor_info,
                    "raw_json": t,
                }
            )
        except Exception as e:  # noqa: BLE001
            print(f"[molit] 거래 변환 실패: {e}")
    return rows


def process_apartment_or_commercial(target: dict) -> None:
    fetch_fn = molit_client.fetch_commercial_trades if target["type"] == "commercial" else molit_client.fetch_apt_trades
    source = "commercial" if target["type"] == "commercial" else "apt"

    db.delete_recent_transactions(target["id"], source)
    rows: list[dict] = []
    for ymd in _recent_deal_ymds():
        t0 = time.monotonic()
        try:
            batch = fetch_fn(target["lawd_cd"], ymd)
        except Exception as e:  # noqa: BLE001
            print(f"[molit] {target['name']} {ymd} 조회 실패 ({time.monotonic()-t0:.1f}s): {e}")
            continue
        batch = [t for t in batch if _matches_location(t, target)]
        print(f"[molit] {target['name']} {ymd}: {len(batch)}건 ({time.monotonic()-t0:.1f}s)")
        rows.extend(_to_rows(target["id"], source, batch))

    t0 = time.monotonic()
    db.insert_transactions_batch(rows)
    print(f"[molit] {target['name']}: 실거래 {len(rows)}건 저장 ({time.monotonic()-t0:.1f}s)")


def process_redevelopment(target: dict) -> None:
    # 재개발구역은 빌라(연립다세대)와 단독/다가구(상가주택 포함)가 섞여 있어 둘 다 수집
    sources = [("villa", molit_client.fetch_villa_trades), ("house", molit_client.fetch_house_trades)]
    rows: list[dict] = []
    for source, fetch_fn in sources:
        db.delete_recent_transactions(target["id"], source)
        for ymd in _recent_deal_ymds():
            t0 = time.monotonic()
            try:
                batch = fetch_fn(target["lawd_cd"], ymd)
            except Exception as e:  # noqa: BLE001
                print(f"[molit:{source}] {target['name']} {ymd} 조회 실패 ({time.monotonic()-t0:.1f}s): {e}")
                continue
            print(f"[molit:{source}] {target['name']} {ymd}: {len(batch)}건 ({time.monotonic()-t0:.1f}s)")
            rows.extend(_to_rows(target["id"], source, batch))

    t0 = time.monotonic()
    db.insert_transactions_batch(rows)
    print(f"[redevelopment] {target['name']}: 실거래 {len(rows)}건 저장 ({time.monotonic()-t0:.1f}s)")


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
