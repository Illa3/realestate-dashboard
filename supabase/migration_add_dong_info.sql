-- 실거래가에 동(아파트 단지 내 건물 번호) 정보 추가
-- Supabase SQL Editor에서 한 번만 실행하세요.

alter table transactions add column if not exists dong_info text;
-- 아파트(source='apt')만 국토부 API가 동 번호(aptDong)를 제공함. 연립다세대/단독다가구/상업용은 해당 없음.
