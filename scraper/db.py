from supabase import Client, create_client

from . import config

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def get_active_targets() -> list[dict]:
    res = get_client().table("targets").select("*").eq("active", True).execute()
    return res.data


def update_target(target_id: str, fields: dict) -> None:
    get_client().table("targets").update(fields).eq("id", target_id).execute()


def upsert_listing(target_id: str, article_no: str, fields: dict) -> dict:
    client = get_client()
    existing = (
        client.table("listings")
        .select("*")
        .eq("target_id", target_id)
        .eq("article_no", article_no)
        .limit(1)
        .execute()
    )
    if existing.data:
        row = existing.data[0]
        client.table("listings").update(
            {**fields, "last_seen_at": "now()", "is_active": True}
        ).eq("id", row["id"]).execute()
        return {**row, **fields}
    else:
        inserted = (
            client.table("listings")
            .insert({"target_id": target_id, "article_no": article_no, **fields})
            .execute()
        )
        return inserted.data[0]


def record_price_history(listing_id: str, price: int) -> None:
    get_client().table("listing_price_history").insert(
        {"listing_id": listing_id, "price": price}
    ).execute()


def mark_missing_listings_inactive(target_id: str, seen_article_nos: set[str]) -> None:
    client = get_client()
    active = (
        client.table("listings")
        .select("id, article_no")
        .eq("target_id", target_id)
        .eq("is_active", True)
        .execute()
    )
    for row in active.data:
        if row["article_no"] not in seen_article_nos:
            client.table("listings").update({"is_active": False}).eq("id", row["id"]).execute()


def get_target(target_id: str) -> dict:
    res = get_client().table("targets").select("*").eq("id", target_id).single().execute()
    return res.data


def get_recent_transactions(target_id: str, months: int = 6) -> list[dict]:
    from datetime import date, timedelta

    cutoff = (date.today() - timedelta(days=30 * months)).isoformat()
    res = (
        get_client()
        .table("transactions")
        .select("*")
        .eq("target_id", target_id)
        .gte("deal_date", cutoff)
        .execute()
    )
    return res.data


def insert_transaction(target_id: str, source: str, fields: dict) -> None:
    get_client().table("transactions").insert(
        {"target_id": target_id, "source": source, **fields}
    ).execute()


def delete_recent_transactions(target_id: str, source: str, months: int = 6) -> None:
    """같은 창(최근 n개월)을 다시 수집하기 전에 지워서 30분마다 중복이 쌓이지 않게 한다."""
    from datetime import date, timedelta

    cutoff = (date.today() - timedelta(days=30 * months)).isoformat()
    get_client().table("transactions").delete().eq("target_id", target_id).eq(
        "source", source
    ).gte("deal_date", cutoff).execute()


def insert_transactions_batch(rows: list[dict]) -> None:
    """건별 insert는 네트워크 왕복이 쌓여 수십 배 느려지므로 한 번에 bulk insert."""
    if not rows:
        return
    CHUNK = 500
    client = get_client()
    for i in range(0, len(rows), CHUNK):
        client.table("transactions").insert(rows[i : i + CHUNK]).execute()


def insert_alert(target_id: str, listing_id: str | None, reason: str, detail: dict) -> dict:
    inserted = (
        get_client()
        .table("alerts")
        .insert(
            {
                "target_id": target_id,
                "listing_id": listing_id,
                "reason": reason,
                "detail": detail,
            }
        )
        .execute()
    )
    return inserted.data[0]


def mark_alert_notified(alert_id: str) -> None:
    get_client().table("alerts").update({"notified": True}).eq("id", alert_id).execute()


def get_pending_captures() -> list[dict]:
    res = get_client().table("captures").select("*").eq("status", "pending").execute()
    return res.data


def download_capture_image(image_path: str) -> bytes:
    return get_client().storage.from_("captures").download(image_path)


def mark_capture_processed(capture_id: str, parsed: dict, target_id: str | None = None) -> None:
    fields = {"status": "processed", "parsed": parsed, "processed_at": "now()"}
    if target_id:
        fields["target_id"] = target_id
    get_client().table("captures").update(fields).eq("id", capture_id).execute()


def mark_capture_error(capture_id: str, message: str) -> None:
    get_client().table("captures").update(
        {"status": "error", "error_message": message, "processed_at": "now()"}
    ).eq("id", capture_id).execute()


def insert_manual_listing(target_id: str, capture_id: str, fields: dict) -> dict:
    article_no = f"manual-{capture_id}"
    inserted = (
        get_client()
        .table("listings")
        .insert({"target_id": target_id, "article_no": article_no, **fields})
        .execute()
    )
    return inserted.data[0]


def insert_auction_item(fields: dict) -> dict:
    inserted = get_client().table("auction_items").insert(fields).execute()
    return inserted.data[0]


def get_upcoming_auction_items(within_days: int = 3) -> list[dict]:
    res = (
        get_client()
        .table("auction_items")
        .select("*")
        .eq("status", "upcoming")
        .is_("reminded_at", "null")
        .execute()
    )
    from datetime import date, timedelta

    cutoff = date.today() + timedelta(days=within_days)
    return [
        row
        for row in res.data
        if row.get("bid_date") and date.today() <= date.fromisoformat(row["bid_date"]) <= cutoff
    ]


def mark_auction_reminded(auction_id: str) -> None:
    get_client().table("auction_items").update({"reminded_at": "now()"}).eq("id", auction_id).execute()
