-- 초기 관심 단지/구역 등록 (schema.sql 실행 후, Supabase SQL Editor에서 실행)
-- 주의: lawd_cd(법정동코드 5자리)는 https://www.code.go.kr/stdcode/regCodeL.do 에서 다시 한 번 확인하세요.

insert into targets (name, type, lawd_cd, discount_threshold_pct, memo) values
  ('잠실 엘스', 'apartment', '11710', 10, '송파구 잠실동'),
  ('옥수 리버젠', 'apartment', '11200', 10, '성동구 옥수동'),
  ('마포 프레스티지 자이', 'apartment', '11440', 10, '마포구'),
  ('철산역 롯데캐슬 SK뷰 클래스티지', 'apartment', '41210', 10, '광명시 철산동');

insert into targets (name, type, lawd_cd, discount_threshold_pct, memo) values
  ('신천동 장미아파트 상가', 'commercial', '11710', 15, '송파구 신천동 — 상가는 공실률/임대수익률도 함께 확인 필요');

insert into targets (name, type, lawd_cd, discount_threshold_pct, appraisal_value, memo) values
  ('북아현3구역', 'redevelopment', '11410', 15, null, '서대문구 북아현동 — 총투자금(매매가-보증금) 기준 판정, appraisal_value는 감정가 확정되면 입력');

-- naver_complex_no는 아파트 4곳에 대해 scraper가 최초 실행 시 이름으로 검색해 자동으로 채웁니다.
-- (scraper/naver_client.py의 resolve_complex_no 참고)
