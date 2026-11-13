import requests

from . import config


def send(text: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[telegram] 토큰/chat_id 미설정, 알림 생략:", text)
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )
    resp.raise_for_status()


def format_alert(target_name: str, reason: str, detail: dict, listing_url: str | None = None) -> str:
    reason_label = {
        "below_median": "실거래가 대비 저가",
        "price_drop": "호가 인하",
        "keyword": "급매 키워드",
        "premium_low": "감정가 대비 저가",
    }.get(reason, reason)

    lines = [f"🏠 <b>{target_name}</b> — {reason_label}"]
    for key, value in detail.items():
        lines.append(f"- {key}: {value}")
    if listing_url:
        lines.append(listing_url)
    return "\n".join(lines)
