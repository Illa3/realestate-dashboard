"""네이버 부동산 내부(비공개) API 클라이언트.

주의: 공식 API가 아니라 커뮤니티에서 확인된 엔드포인트를 그대로 재현한 것이라
네이버가 화면을 개편하면 예고 없이 깨질 수 있습니다. 403/빈 응답이 계속되면
브라우저 개발자도구(F12) > Network 탭에서 new.land.naver.com/api/... 요청을
직접 열어 헤더/파라미터/경로가 바뀌었는지 확인하고 아래 상수를 고치세요.

요청 간 최소 1~2초 간격을 두고, 하루 전체 호출 횟수를 낮게 유지해 개인
소규모 조회 수준을 넘지 않도록 하세요(이용약관/차단 리스크).
"""

import time

import requests

BASE = "https://new.land.naver.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://new.land.naver.com/complexes",
}

_MIN_INTERVAL_SEC = 1.5
_last_request_at = 0.0


def _throttled_get(url: str, params: dict | None = None) -> requests.Response:
    global _last_request_at
    elapsed = time.time() - _last_request_at
    if elapsed < _MIN_INTERVAL_SEC:
        time.sleep(_MIN_INTERVAL_SEC - elapsed)
    resp = requests.get(url, headers=_HEADERS, params=params, timeout=15)
    _last_request_at = time.time()
    return resp


def resolve_complex_no(name: str) -> str | None:
    """단지명으로 네이버 단지번호를 검색. 확인 못하면 None 반환 — 수동 확인 필요."""
    resp = _throttled_get(f"{BASE}/api/search", params={"keyword": name})
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    complexes = data.get("complexes") or data.get("result") or []
    if not complexes:
        return None
    return str(complexes[0].get("complexNo") or complexes[0].get("id"))


def fetch_complex_overview(complex_no: str) -> dict:
    resp = _throttled_get(f"{BASE}/api/complexes/overview/{complex_no}")
    resp.raise_for_status()
    return resp.json()


def fetch_articles(complex_no: str, trade_type: str = "A1") -> list[dict]:
    """매매(A1) 매물 목록. 전세(B2)/월세(B3) 등은 trade_type만 바꾸면 됨."""
    articles: list[dict] = []
    page = 1
    while True:
        resp = _throttled_get(
            f"{BASE}/api/articles/complex/{complex_no}",
            params={"realEstateType": "APT", "tradeType": trade_type, "page": page},
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        batch = data.get("articleList", [])
        if not batch:
            break
        articles.extend(batch)
        if data.get("isMoreData") is not True:
            break
        page += 1
    return articles
