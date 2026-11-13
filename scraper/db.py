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


def insert_transaction(target_id: str, source: str, fields: dict) -> None:
    get_client().table("transactions").insert(
        {"target_id": target_id, "source": source, **fields}
    ).execute()


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
