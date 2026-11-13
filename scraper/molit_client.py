"""공공데이터포털 국토교통부 실거래가 API 클라이언트.

엔드포인트는 data.go.kr에서 활용신청 후 '상세설명' 탭의 Request URL과 반드시
대조해서 쓰세요. 특히 COMMERCIAL_ENDPOINT는 검색만으로 확정하지 못했으니
실제 신청 화면에서 Operation 이름을 확인하고 이 값을 고쳐야 합니다.
"""

import xml.etree.ElementTree as ET

import requests

from . import config

BASE_URL = "http://apis.data.go.kr/1613000"

# 아래 4개는 모두 data.go.kr의 오픈API 상세 페이지(Explore 탭)에서 Base URL을 직접 확인한 값.
APT_ENDPOINT = f"{BASE_URL}/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
VILLA_ENDPOINT = f"{BASE_URL}/RTMSDataSvcRHTrade2/getRTMSDataSvcRHTrade2"
HOUSE_ENDPOINT = f"{BASE_URL}/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade"
COMMERCIAL_ENDPOINT = f"{BASE_URL}/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade"


def _fetch(endpoint: str, lawd_cd: str, deal_ymd: str) -> list[dict]:
    resp = requests.get(
        endpoint,
        params={
            "serviceKey": config.MOLIT_SERVICE_KEY,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": 1000,
            "pageNo": 1,
        },
        timeout=20,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    result_code = root.findtext("./header/resultCode")
    if result_code not in ("00", "000"):
        msg = root.findtext("./header/resultMsg")
        raise RuntimeError(f"MOLIT API error {result_code}: {msg}")

    items = []
    for item in root.findall("./body/items/item"):
        items.append({child.tag: (child.text or "").strip() for child in item})
    return items


def fetch_apt_trades(lawd_cd: str, deal_ymd: str) -> list[dict]:
    """아파트 매매 실거래가."""
    return _fetch(APT_ENDPOINT, lawd_cd, deal_ymd)


def fetch_villa_trades(lawd_cd: str, deal_ymd: str) -> list[dict]:
    """연립다세대 매매 실거래가 (재개발 구역 내 빌라류)."""
    return _fetch(VILLA_ENDPOINT, lawd_cd, deal_ymd)


def fetch_house_trades(lawd_cd: str, deal_ymd: str) -> list[dict]:
    """단독/다가구 매매 실거래가 (재개발 구역 내 단독·다가구·상가주택 등)."""
    return _fetch(HOUSE_ENDPOINT, lawd_cd, deal_ymd)


def fetch_commercial_trades(lawd_cd: str, deal_ymd: str) -> list[dict]:
    """상업업무용 부동산 매매 실거래가 (상가)."""
    return _fetch(COMMERCIAL_ENDPOINT, lawd_cd, deal_ymd)
