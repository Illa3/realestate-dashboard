"""대기 중인 캡처 이미지(매물/경매)를 Claude Vision으로 파싱해서
listings 또는 auction_items 테이블로 정리한다. GitHub Actions 크론에서 호출.
"""

from . import alert_rules, db, redevelopment, telegram_notify, vision_client


def _evaluate_and_notify(target: dict, listing: dict, parsed: dict) -> None:
    transactions = db.get_recent_transactions(target["id"])
    threshold = target["discount_threshold_pct"]
    alerts = []

    if target["type"] == "redevelopment":
        investments = [
            t["price"] for t in transactions if t.get("price") and t.get("area_m2")
        ]
        result = redevelopment.evaluate_redevelopment_listing(
            parsed.get("price") or 0,
            parsed.get("deposit") or 0,
            target.get("appraisal_value"),
            investments,
            threshold,
        )
        if result:
            alerts.append(result)
    elif target["type"] != "commercial":
        # 상가는 국토부 API가 법정동/건물 단위로 안 좁혀져서(구 전체 상업용 거래가 다 섞임)
        # 실거래가 비교 기준 자체가 신뢰할 수 없어 가격비교 알림은 끔. 키워드 알림은 유지.
        price_per_m2 = [
            t["price"] / t["area_m2"] for t in transactions if t.get("price") and t.get("area_m2")
        ]
        market_alert = alert_rules.evaluate_against_market(
            parsed.get("price") or 0, parsed.get("area_m2"), price_per_m2, threshold
        )
        if market_alert:
            alerts.append(market_alert)

    keyword_alert = alert_rules.evaluate_keyword(parsed.get("description"), parsed.get("tags"))
    if keyword_alert:
        alerts.append(keyword_alert)

    for alert in alerts:
        row = db.insert_alert(target["id"], listing["id"], alert["reason"], alert["detail"])
        telegram_notify.send(telegram_notify.format_alert(target["name"], alert["reason"], alert["detail"]))
        db.mark_alert_notified(row["id"])


def process_listing_capture(capture: dict) -> None:
    image_bytes = db.download_capture_image(capture["image_path"])
    parsed = vision_client.extract(image_bytes, "listing")

    if not capture.get("target_id"):
        db.mark_capture_processed(capture["id"], parsed)
        print(f"[capture:{capture['id']}] target 미지정 — listings엔 반영 안 됨, parsed만 저장")
        return

    listing = db.insert_manual_listing(
        capture["target_id"],
        capture["id"],
        {
            "price": parsed.get("price"),
            "deposit": parsed.get("deposit"),
            "area_m2": parsed.get("area_m2"),
            "floor_info": parsed.get("floor_info"),
            "description": parsed.get("description"),
            "tags": parsed.get("tags") or [],
            "raw_json": parsed,
        },
    )
    db.mark_capture_processed(capture["id"], parsed)
    print(f"[capture:{capture['id']}] 매물로 정리 완료: {parsed.get('name_hint')}")

    target = db.get_target(capture["target_id"])
    _evaluate_and_notify(target, listing, parsed)


def process_auction_capture(capture: dict) -> None:
    image_bytes = db.download_capture_image(capture["image_path"])
    parsed = vision_client.extract(image_bytes, "auction")

    db.insert_auction_item(
        {
            "target_id": capture.get("target_id"),
            "capture_id": capture["id"],
            "case_number": parsed.get("case_number"),
            "title": parsed.get("title"),
            "court": parsed.get("court"),
            "bid_date": parsed.get("bid_date"),
            "appraisal_value": parsed.get("appraisal_value"),
            "min_bid_price": parsed.get("min_bid_price"),
            "notes": parsed.get("notes"),
        }
    )
    db.mark_capture_processed(capture["id"], parsed)
    print(f"[capture:{capture['id']}] 경매물건으로 정리 완료: {parsed.get('case_number')}")


def run() -> None:
    pending = db.get_pending_captures()
    print(f"대기 중인 캡처 {len(pending)}건")
    for capture in pending:
        try:
            if capture["kind"] == "listing":
                process_listing_capture(capture)
            else:
                process_auction_capture(capture)
        except Exception as e:  # noqa: BLE001
            print(f"[capture:{capture['id']}] 처리 실패: {e}")
            db.mark_capture_error(capture["id"], str(e))


if __name__ == "__main__":
    run()
