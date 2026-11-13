"""Supabase/환경변수 설정이 끝난 뒤 한 번 돌려서 연결을 확인하는 스크립트.

사용법: python -m scraper.healthcheck
"""

from . import config, db


def run() -> None:
    print("1. 환경변수 로드 확인...")
    print(f"   SUPABASE_URL = {config.SUPABASE_URL}")
    print(f"   MOLIT_SERVICE_KEY 길이 = {len(config.MOLIT_SERVICE_KEY)}자")

    print("2. Supabase 연결 + targets 테이블 조회...")
    targets = db.get_active_targets()
    print(f"   활성 단지/구역 {len(targets)}개:")
    for t in targets:
        print(f"   - {t['name']} ({t['type']}, lawd_cd={t['lawd_cd']})")

    if not targets:
        print("   ⚠️ 0개입니다. schema.sql / seed_targets.sql을 실행했는지 확인하세요.")
    else:
        print("✅ Supabase 연결 정상")


if __name__ == "__main__":
    run()
