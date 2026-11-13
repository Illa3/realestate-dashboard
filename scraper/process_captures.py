"""대기 중인 캡처 이미지(매물/경매)를 Claude Vision으로 파싱해서
listings 또는 auction_items 테이블로 정리한다. GitHub Actions 크론에서 호출.
"""

import re

from . import alert_rules, db, redevelopment, telegram_notify, vision_client


def _normalize(s: str | None) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def _candidate_names(target: dict) -> list[str]:
    names = [target.get("apt_name"), target.get("name"), target.get("dong_name")]
    names.extend((target.get("match_keywords") or "").split(","))
    return [n for n in names if n and n.strip()]


def match_targets(name_hint: str | None, targets: list[dict]) -> list[dict]:
    """Vision이 읽은 단지/건물 이름(name_hint)을 target의 apt_name/name/dong_name/
    match_keywords와 비교해 후보를 찾는다. 공백만 무시하는 단순 부분일치라 과매칭을
    피하려고 2글자 미만 후보는 무시한다."""
    norm_hint = _normalize(name_hint)
    if not norm_hint:
        return []
    matches = []
    for target in targets:
        for cand in _candidate_names(target):
            norm_cand = _normalize(cand)
            if len(norm_cand) >= 2 and (norm_cand in norm_hint or norm_hint in norm_cand):
                matches.append(target)
                break
    return matches


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
    elif target["type"] != "commercial" or target.get("jibun"):
        # 상가는 국토부 API가 기본적으로 구 전체 상업용 거래가 다 섞여서 비교 기준이
        # 신뢰할 수 없음. target에 dong_name/jibun(동·지번)이 지정돼 그 건물로 좁혀진
        # 경우에만 가격비교 알림을 켠다. 안 좁혀진 상가는 키워드 알림만 유지.
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

    target_id = capture.get("target_id")
    auto_matched = False
    if not target_id:
        matches = match_targets(parsed.get("name_hint"), db.get_active_targets())
        if len(matches) == 1:
            target_id = matches[0]["id"]
            auto_matched = True
            print(f"[capture:{capture['id']}] 자동분류: {matches[0]['name']}")
        elif len(matches) > 1:
            names = ", ".join(m["name"] for m in matches)
            print(f"[capture:{capture['id']}] 자동분류 모호함({names}) — 수동 확인 필요")
        else:
            print(f"[capture:{capture['id']}] 자동분류 실패 — 수동 확인 필요")

    db.mark_capture_processed(capture["id"], parsed, target_id if auto_matched else None)

    if not target_id:
        telegram_notify.send(
            f"🔍 캡처 자동분류 실패\n\"{parsed.get('name_hint') or '이름 미상'}\"\n"
            "업로드 탭 '최근 업로드'에서 관심구역을 직접 연결해주세요."
        )
        print(f"[capture:{capture['id']}] target 미지정 — listings엔 반영 안 됨, parsed만 저장")
        return

    listing = db.insert_manual_listing(
        target_id,
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
    print(f"[capture:{capture['id']}] 매물로 정리 완료: {parsed.get('name_hint')}")

    target = db.get_target(target_id)
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
