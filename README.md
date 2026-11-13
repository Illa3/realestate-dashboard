# 관심구역 부동산 대시보드

네이버 부동산 매물 + 국토부 실거래가를 30분마다 모아서 급매를 감지하고,
폰 브라우저로 볼 수 있는 대시보드 + 텔레그램 알림.

```
GitHub Actions (30분 cron) → 스크래핑 → Supabase → 정적 프론트엔드(Vercel) + 텔레그램 알림
```

## 설정 순서

### 1. 공공데이터포털 서비스키 발급
1. https://www.data.go.kr 가입 후 아래 4개를 각각 검색해서 활용신청 (보통 즉시~1일 승인, 키는 4개 다 동일한 서비스키 하나 공유):
   - **국토교통부_아파트 매매 실거래가 상세 자료** (https://www.data.go.kr/data/15126468/openapi.do)
   - **국토교통부_연립다세대 매매 실거래가 자료**
   - **국토교통부_단독/다가구 매매 실거래가 자료** (북아현3구역 등 재개발구역의 단독·다가구·상가주택용)
   - **국토교통부_상업업무용 부동산 매매 신고 자료** (신천동 장미아파트 상가용)
2. 단독/다가구, 상업업무용 두 API는 **정확한 Operation 주소를 신청 화면에서 확인해서** [scraper/molit_client.py](scraper/molit_client.py)의 `HOUSE_ENDPOINT`, `COMMERCIAL_ENDPOINT` 값을 맞게 고쳐주세요 (검색만으로는 100% 확정하지 못했습니다).
3. 마이페이지 > 오픈API 활용현황에서 서비스키(인증키) 복사

### 2. Supabase 프로젝트 생성
1. https://supabase.com 가입 (GitHub 계정으로 바로 가능, 카드 등록 불필요)
2. New Project 생성
3. SQL Editor에서 [supabase/schema.sql](supabase/schema.sql) 전체 실행
4. 이어서 [config/seed_targets.sql](config/seed_targets.sql) 실행 (초기 6개 단지/구역 등록 — lawd_cd는 code.go.kr에서 확인 완료된 값)
5. Authentication > Users에서 본인 계정 1개 생성 (관리 탭 로그인용)
6. Settings > API에서 `Project URL`, `anon public key`, `service_role key` 복사
7. 로컬에 `.env` 만들고 (`.env.example` 복사) 값 채운 뒤 `pip install -r requirements.txt && python -m scraper.healthcheck` 실행해서 연결 확인

### 3. 텔레그램 봇 만들기
1. 텔레그램에서 `@BotFather` 검색 → `/newbot` → 토큰 받기
2. `@userinfobot`에게 말 걸어서 본인 chat_id 확인
3. 만든 봇에게 먼저 아무 메시지나 한 번 보내두기 (안 하면 알림이 안 옴)

### 4. GitHub 저장소 설정
1. 이 폴더를 public 저장소로 push
2. Settings > Secrets and variables > Actions에서 등록:
   - `MOLIT_SERVICE_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY` (service_role — 절대 코드에 커밋하지 말 것)
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Actions 탭에서 `scrape` 워크플로를 한 번 수동 실행(`workflow_dispatch`)해서 에러 없는지 확인

### 5. 프론트엔드 배포 (Vercel)
1. [frontend/config.js](frontend/config.js)에 Supabase `Project URL`과 `anon public key` 입력 (anon key는 공개되어도 안전함)
2. Vercel에 GitHub 저장소 연결, **Root Directory를 `frontend`로 설정**, Build Command 없음(정적 파일)
3. 배포 후 나온 URL을 폰 브라우저 홈 화면에 추가하면 앱처럼 쓸 수 있음

## 알아둘 점 / 한계

- **네이버 내부 API는 비공식**이라 화면 개편 시 깨질 수 있어요. 403이나 빈 응답이 계속되면 브라우저 개발자도구로 실제 요청을 다시 확인해서 [scraper/naver_client.py](scraper/naver_client.py)를 고쳐야 해요.
- **북아현3구역(재개발)의 네이버 매물 수집은 아직 TODO**예요. 단일 단지가 아니라 구역 전체라 매물 검색 방식이 달라서, 지금은 연립다세대 실거래가만 수집하고 있어요. 매물까지 보고 싶으면 추가 작업이 필요해요.
- **단독/다가구, 상업업무용 실거래가 엔드포인트는 미확정**이에요. data.go.kr에서 신청할 때 정확한 주소를 확인해 고쳐주세요.
- 요청 사이 최소 1.5초 간격을 두고 있지만, 그래도 네이버 약관상 "과도한 자동 수집"에는 해당하지 않게 개인 소규모 조회 수준을 유지하세요.
- 단지 추가/삭제는 대시보드의 "관리" 탭에서 로그인 후 바로 할 수 있어요 (코드 수정 불필요).
