-- 캡처 자동분류 매칭용 키워드 컬럼 추가
-- Supabase SQL Editor에서 한 번만 실행하세요.

alter table targets add column if not exists match_keywords text;
-- 쉼표로 구분된 별칭들. 예: "장미종합상가,장미상가"
-- 캡처에서 Vision이 읽은 단지/건물 이름(name_hint)이 이 중 하나와 겹치면 자동으로 이 target에 연결됩니다.
