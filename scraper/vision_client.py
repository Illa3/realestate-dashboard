"""매물/경매 캡처 이미지를 Claude Vision으로 읽어 구조화된 데이터로 변환.

prescription-scanner 프로젝트의 extractor.py와 같은 패턴을 씁니다.
"""

import json
import re

import anthropic

from . import config

MODEL = "claude-sonnet-5-5"

LISTING_PROMPT = """이 이미지는 부동산 매물 정보 캡처(네이버 부동산, 매물 중개 사이트 등)입니다.
다음 정보를 추출해서 JSON으로만 응답하세요 (설명 없이 JSON만):

{
  "name_hint": "단지명 또는 주소 (보이는 대로)",
  "price": 매매가(원 단위 정수, 예: 15억 3000만원 -> 1530000000),
  "deposit": 보증금(원 단위 정수, 없으면 null),
  "area_m2": 전용면적(제곱미터, 숫자),
  "floor_info": "층 정보 (예: 14/20)",
  "description": "매물 설명/특이사항 요약",
  "tags": ["급매", "협의가능" 등 보이는 키워드 배열],
  "is_urgent_sale": true 또는 false ("급매", "급처" 같은 표현이 있으면 true)
}

값을 읽을 수 없으면 null로 표기하세요. JSON 외 다른 텍스트는 출력하지 마세요."""

AUCTION_PROMPT = """이 이미지는 법원 경매 물건 정보 캡처입니다.
다음 정보를 추출해서 JSON으로만 응답하세요 (설명 없이 JSON만):

{
  "case_number": "사건번호 (예: 2025타경13341)",
  "title": "물건 소재지/설명",
  "court": "관할법원 (보이면)",
  "bid_date": "입찰기일 (YYYY-MM-DD 형식, 보이면)",
  "appraisal_value": 감정가(원 단위 정수, 없으면 null),
  "min_bid_price": 최저입찰가(원 단위 정수, 없으면 null),
  "notes": "유찰횟수, 인수권리 등 특이사항 요약"
}

값을 읽을 수 없으면 null로 표기하세요. JSON 외 다른 텍스트는 출력하지 마세요."""


def _media_type(image_bytes: bytes) -> str:
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF":
        return "image/webp"
    return "image/jpeg"


def extract(image_bytes: bytes, kind: str) -> dict:
    """kind: 'listing' 또는 'auction'."""
    import base64

    prompt = LISTING_PROMPT if kind == "listing" else AUCTION_PROMPT
    media_type = _media_type(image_bytes)
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 파싱 실패:\n{cleaned}\n오류: {e}") from e
