"""30분마다 GitHub Actions가 실행하는 전체 파이프라인.

1. targets 테이블에서 활성 단지/구역을 읽는다.
2. apartment/commercial: 네이버 매물 수집 + 국토부 실거래가(최근 6개월)로 중위값 비교.
3. redevelopment: 국토부 연립다세대 실거래가로 총투자금 기준 비교 (네이버 매물 수집은 TODO).
4. 급매 조건에 맞으면 alerts 기록 + 텔레그램 알림.
"""

from datetime import date

from . import alert_rules, db, molit_client, naver_client, telegram_notify

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


def _price_per_m2_list(trades: list[dict]) -> list[float]:
    out = []
    for t in trades:
        try:
            price_man_won = float(t.get("거래금액", "0").replace(",", ""))
            area = float(t.get("전용면적", "0"))
            if area > 0:
                out.append(price_man_won * 10000 / area)
        except (ValueError, TypeError):
            continue
    return out


def _total_investments(trades: list[dict]) -> list[int]:
    out = []
    for t in trades:
        try:
            price_man_won = float(t.get("거래금액", "0").replace(",", ""))
            out.append(int(price_man_won * 10000))
        except (ValueError, TypeError):
            continue
    return out


def process_apartment_or_commercial(target: dict) -> None:
    deal_ymds = _recent_deal_ymds()
    trades: list[dict] = []
    for ymd in deal_ymds:
        try:
            if target["type"] == "commercial":
                batch = molit_client.fetch_commercial_trades(target["lawd_cd"], ymd)
                source = "commercial"
            else:
                batch = molit_client.fetch_apt_trades(target["lawd_cd"], ymd)
                source = "apt"
        except Exception as e:  # noqa: BLE001
            print(f"[molit] {target['name']} {ymd} 조회 실패: {e}")
            continue
        trades.extend(batch)
        for t in batch:
            try:
                db.insert_transaction(
                    target["id"],
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

    price_per_m2 = _price_per_m2_list(trades)

    complex_no = target.get("naver_complex_no")
    if not complex_no:
        complex_no = naver_client.resolve_complex_no(target["name"])
        if complex_no:
            db.update_target(target["id"], {"naver_complex_no": complex_no})
        else:
            print(f"[naver] {target['name']} 단지번호를 찾지 못했습니다. 수동 등록 필요.")
            return

    try:
        articles = naver_client.fetch_articles(complex_no)
    except Exception as e:  # noqa: BLE001
        print(f"[naver] {target['name']} 매물 조회 실패: {e}")
        return

    seen_article_nos = set()
    for article in articles:
        article_no = str(article.get("articleNo"))
        seen_article_nos.add(article_no)
        price = _parse_naver_price(article.get("dealOrWarrantPrc", "0"))
        area = float(article.get("area1") or 0)
        tags = article.get("tagList", [])
        description = article.get("articleFeatureDesc", "")

        listing = db.upsert_listing(
            target["id"],
            article_no,
            {
                "price": price,
                "area_m2": area,
                "floor_info": article.get("floorInfo"),
                "tags": tags,
                "description": description,
                "raw_json": article,
            },
        )
        db.record_price_history(listing["id"], price)

        threshold = target["discount_threshold_pct"]
        market_alert = alert_rules.evaluate_against_market(price, area, price_per_m2, threshold)
        keyword_alert = alert_rules.evaluate_keyword(description, tags)

        for alert in filter(None, [market_alert, keyword_alert]):
            row = db.insert_alert(target["id"], listing["id"], alert["reason"], alert["detail"])
            telegram_notify.send(telegram_notify.format_alert(target["name"], alert["reason"], alert["detail"]))
            db.mark_alert_notified(row["id"])

    db.mark_missing_listings_inactive(target["id"], seen_article_nos)


def process_redevelopment(target: dict) -> None:
    deal_ymds = _recent_deal_ymds()
    trades: list[dict] = []
    for ymd in deal_ymds:
        try:
            batch = molit_client.fetch_villa_trades(target["lawd_cd"], ymd)
        except Exception as e:  # noqa: BLE001
            print(f"[molit] {target['name']} {ymd} 조회 실패: {e}")
            continue
        trades.extend(batch)
        for t in batch:
            try:
                db.insert_transaction(
                    target["id"],
                    "villa",
                    {
                        "deal_date": f"{t.get('년','2000')}-{int(t.get('월','1')):02d}-{int(t.get('일','1')):02d}",
                        "price": int(float(t.get("거래금액", "0").replace(",", "")) * 10000),
                        "area_m2": float(t.get("전용면적", 0) or 0),
                        "raw_json": t,
                    },
                )
            except Exception as e:  # noqa: BLE001
                print(f"[molit] 거래 저장 실패: {e}")

    # TODO: 북아현3구역처럼 단일 '단지'가 아닌 구역은 네이버 매물 수집 로직을 별도로 붙여야 함.
    # 지금은 실거래가만으로 시세 추이를 기록한다.
    print(f"[redevelopment] {target['name']}: 실거래 {len(trades)}건 수집, 매물 비교는 TODO")


def run() -> None:
    for target in db.get_active_targets():
        print(f"=== {target['name']} ({target['type']}) ===")
        if target["type"] in ("apartment", "commercial"):
            process_apartment_or_commercial(target)
        elif target["type"] == "redevelopment":
            process_redevelopment(target)


def _parse_naver_price(raw: str) -> int:
    """'15억 3,000' 형태를 원 단위 정수로 변환."""
    raw = raw.replace(",", "").strip()
    won = 0
    if "억" in raw:
        eok, _, rest = raw.partition("억")
        won += int(eok.strip()) * 100_000_000
        raw = rest.strip()
    if raw:
        won += int(raw) * 10_000
    return won


if __name__ == "__main__":
    run()
